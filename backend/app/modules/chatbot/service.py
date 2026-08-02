"""ChatService — điều phối toàn bộ pipeline RAG (US-23, US-24).

★★ HỢP ĐỒNG VỚI TẦNG API ★★
Chu Quang Vũ xây router `POST /chat/sessions/{id}/messages` và stream SSE.
Ranh giới đúng là:

    router.py  →  nhận HTTP, kiểm tra quyền, rate limit, đổi ChatEvent → SSE
    service.py →  toàn bộ logic RAG (file này)

Chữ ký hàm KHÔNG được đổi mà không báo trước, vì router phụ thuộc vào nó:

    async for event in chat_service.answer(session_id=..., user=..., question=...):
        yield sse(event.type, event.data)

Thứ tự sự kiện LUÔN là:  citations → token* → done
Hoặc khi lỗi:            error  (và dừng)

Trích dẫn được gửi TRƯỚC nội dung — người dùng thấy ngay câu trả lời dựa
trên tài liệu nào, trong khi câu trả lời còn đang sinh.
"""

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm.base import LlmClient
from app.ai.retriever import Retriever
from app.core.exceptions import ExternalServiceError, NotFoundError
from app.core.logging import get_logger
from app.modules.chatbot.constants import MessageRole
from app.modules.chatbot.models import ChatCitation, ChatMessage, ChatSession
from app.modules.chatbot.prompts import (
    NO_CONTEXT_ANSWER,
    RAG_PROMPT_VERSION,
    build_rag_prompt,
    build_rewrite_prompt,
    needs_rewrite,
)

logger = get_logger(__name__)

EventType = Literal["citations", "token", "done", "error"]

# Giới hạn lịch sử đưa vào prompt — kiểm soát chi phí token (docs/design/07 §6)
HISTORY_TURNS = 5
MAX_QUESTION_LENGTH = 1000


@dataclass
class ChatEvent:
    """Một sự kiện trong luồng trả lời. Router đổi thành SSE event."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)


class ChatService:
    def __init__(
        self,
        session: Session,
        retriever: Retriever,
        llm_client: LlmClient,
    ) -> None:
        self.db = session
        self.retriever = retriever
        self.llm = llm_client

    async def answer(
        self, *, session_id: UUID, user_id: UUID, question: str
    ) -> AsyncIterator[ChatEvent]:
        """Trả lời một câu hỏi, sinh sự kiện theo luồng.

        Raises:
            NotFoundError: phiên chat không tồn tại hoặc không thuộc người dùng.
        """
        question = question.strip()[:MAX_QUESTION_LENGTH]
        if not question:
            yield ChatEvent(
                "error", {"code": "VALIDATION_ERROR", "message": "Câu hỏi không được để trống"}
            )
            return

        chat_session = self._get_session(session_id, user_id)
        started = time.perf_counter()

        # Lưu câu hỏi trước — nếu tiến trình chết giữa chừng, câu hỏi vẫn còn.
        # PHẢI commit chứ không chỉ flush: flush mới đẩy xuống transaction,
        # session đóng là mất sạch. Câu hỏi được ghi bền vững ngay tại đây,
        # trước cả khi biết có trả lời được hay không.
        self._save_message(chat_session, MessageRole.USER, question)
        self.db.commit()

        history = self._recent_history(session_id)

        # ── Viết lại câu hỏi cho hội thoại nhiều lượt ──
        # "còn cách khác không?" không thể embed một mình. Không có bước này,
        # lượt hỏi thứ hai trở đi gần như luôn truy xuất sai.
        search_query = question
        if needs_rewrite(history):
            search_query = await self._rewrite(question, history)

        # ── Truy xuất tài liệu ──
        try:
            retrieval = await self.retriever.retrieve(search_query)
        except Exception as exc:
            logger.exception("lỗi truy xuất tài liệu", exc_info=exc)
            yield self._error_event()
            return

        # ── KHÔNG có tài liệu liên quan: TỪ CHỐI, không gọi LLM ──
        # Đây là lớp phòng vệ mạnh nhất chống bịa đặt. Model không được gọi
        # thì không thể bịa. Mục tiêu tỉ lệ từ chối đúng: 100%.
        if not retrieval.has_context:
            logger.info(
                "không tìm thấy tài liệu liên quan",
                extra={
                    "extra_fields": {
                        "question": question[:120],
                        "top_score": round(retrieval.top_score, 4),
                    }
                },
            )
            yield ChatEvent("citations", {"citations": []})
            yield ChatEvent("token", {"delta": NO_CONTEXT_ANSWER})
            message = self._save_message(
                chat_session,
                MessageRole.ASSISTANT,
                NO_CONTEXT_ANSWER,
                no_context_found=True,
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
            self.db.commit()
            yield ChatEvent(
                "done",
                {
                    "messageId": str(message.id),
                    "noContextFound": True,
                    "canCreateTicket": True,
                    "latencyMs": message.latency_ms,
                },
            )
            return

        # ── Gửi trích dẫn TRƯỚC khi sinh câu trả lời ──
        citations_payload = [
            {
                "articleId": c.article_id,
                "title": c.title,
                "slug": c.slug,
                "score": round(c.score, 4),
                "rank": c.rank,
            }
            for c in retrieval.chunks
        ]
        yield ChatEvent("citations", {"citations": citations_payload})

        # ── Sinh câu trả lời theo luồng ──
        system, user_prompt = build_rag_prompt(question=question, chunks=retrieval.chunks)
        parts: list[str] = []
        try:
            async for delta in self.llm.stream(system=system, user=user_prompt):
                parts.append(delta)
                yield ChatEvent("token", {"delta": delta})
        except Exception as exc:
            logger.exception("lỗi khi sinh câu trả lời", exc_info=exc)
            if parts:
                # Đã stream được một phần — lưu lại thay vì vứt bỏ
                self._save_message(chat_session, MessageRole.ASSISTANT, "".join(parts))
                self.db.commit()
            yield self._error_event()
            return

        answer = "".join(parts)
        latency = round((time.perf_counter() - started) * 1000)
        message = self._save_message(
            chat_session, MessageRole.ASSISTANT, answer, latency_ms=latency
        )
        self._save_citations(message, retrieval.chunks)
        self.db.commit()

        yield ChatEvent(
            "done",
            {
                "messageId": str(message.id),
                "noContextFound": False,
                "latencyMs": latency,
                "promptVersion": RAG_PROMPT_VERSION,
            },
        )

    # ── Nội bộ ────────────────────────────────────────────────────────

    def _get_session(self, session_id: UUID, user_id: UUID) -> ChatSession:
        chat_session = self.db.get(ChatSession, session_id)
        # Trả 404 thay vì 403 khi phiên của người khác — không tiết lộ sự tồn tại
        if chat_session is None or chat_session.user_id != user_id:
            raise NotFoundError("Không tìm thấy cuộc trò chuyện")
        return chat_session

    def _recent_history(self, session_id: UUID) -> list[tuple[str, str]]:
        """Lấy các lượt gần nhất, KHÔNG tính câu hỏi vừa lưu."""
        rows = (
            self.db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(HISTORY_TURNS * 2 + 1)
            )
            .scalars()
            .all()
        )
        # Bỏ câu hỏi vừa lưu (phần tử mới nhất), đảo lại thứ tự thời gian
        return [(m.role.value, m.content) for m in reversed(rows[1:])]

    async def _rewrite(self, question: str, history: list[tuple[str, str]]) -> str:
        """Viết lại câu hỏi thành câu độc lập. Lỗi thì dùng câu gốc."""
        try:
            system, user = build_rewrite_prompt(question=question, history=history)
            # 120 quá chật với model suy luận — xem chú thích ở classifier.py.
            response = await self.llm.complete(system=system, user=user, max_tokens=500)
            rewritten = response.content.strip().strip('"')
            if rewritten:
                logger.info(
                    "viết lại câu hỏi",
                    extra={"extra_fields": {"from": question[:80], "to": rewritten[:80]}},
                )
                return rewritten
        except Exception as exc:
            # Viết lại thất bại không được làm hỏng cả cuộc trò chuyện
            logger.warning(f"không viết lại được câu hỏi: {type(exc).__name__}: {exc}")
        return question

    def _save_message(
        self,
        chat_session: ChatSession,
        role: MessageRole,
        content: str,
        *,
        no_context_found: bool = False,
        latency_ms: int | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=chat_session.id,
            role=role,
            content=content,
            no_context_found=no_context_found,
            model_name=getattr(self.llm, "model_name", None),
            latency_ms=latency_ms,
        )
        self.db.add(message)
        chat_session.message_count += 1
        # Không có dòng này thì danh sách phiên luôn sắp xếp theo ngày TẠO,
        # nên phiên vừa nhắn vẫn nằm dưới phiên mở từ tuần trước.
        chat_session.last_message_at = datetime.now(UTC)
        self.db.flush()
        return message

    def _save_citations(self, message: ChatMessage, chunks) -> None:
        self.db.add_all(
            [
                ChatCitation(
                    message_id=message.id,
                    article_id=UUID(chunk.article_id),
                    score=round(chunk.score, 4),
                    rank=chunk.rank,
                )
                for chunk in chunks
            ]
        )
        self.db.flush()

    @staticmethod
    def _error_event() -> ChatEvent:
        """Thông điệp thân thiện, KHÔNG lộ chi tiết kỹ thuật ra người dùng."""
        return ChatEvent(
            "error",
            {
                "code": ExternalServiceError.code,
                "message": (
                    "Trợ lý ảo tạm thời không phản hồi. "
                    "Bạn có thể tạo yêu cầu hỗ trợ để đội IT giúp trực tiếp."
                ),
                "canCreateTicket": True,
            },
        )
