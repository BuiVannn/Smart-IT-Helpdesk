"""Endpoint chatbot (US-23, US-24).

★★ VÌ SAO PHẢI TỰ MỞ SESSION TRONG LUỒNG STREAM ★★
`Depends(get_db)` đóng session NGAY KHI hàm xử lý trả về `StreamingResponse` —
tức là TRƯỚC khi generator được tiêu thụ. Dùng session đó bên trong generator
sẽ nhận `Session is closed` ngay token đầu tiên. Vì vậy generator mở session
riêng và tự đóng ở `finally`.

★★ VÌ SAO KIỂM TRA QUYỀN TRƯỚC KHI STREAM ★★
Khi đã bắt đầu stream thì HTTP status và header đã gửi đi rồi — không trả 404
được nữa. Nên quyền sở hữu phiên phải kiểm tra ở thân hàm, lúc còn trả được
mã lỗi tử tế.
"""

import json
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai.embedding.openai_embedding import build_embedding_client
from app.ai.llm.openai_client import build_llm_client
from app.ai.retriever import Retriever
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.pagination import Page, PageParams, page_params
from app.core.rate_limit import AttemptLimiter, build_attempt_store
from app.db.session import SessionLocal, get_db
from app.modules.chatbot.models import ChatSession
from app.modules.chatbot.repository import ChatSessionRepository
from app.modules.chatbot.schemas import (
    AskRequest,
    CitationResponse,
    CreateSessionRequest,
    MessageResponse,
    SessionDetailResponse,
    SessionResponse,
)
from app.modules.chatbot.service import ChatEvent, ChatService
from app.modules.users.models import User

logger = get_logger(__name__)

router = APIRouter()

# Mỗi lượt hỏi là một lần gọi LLM — tức là tiền thật. Giới hạn theo NGƯỜI
# DÙNG chứ không theo IP: cả công ty thường đi chung một địa chỉ NAT, giới hạn
# theo IP sẽ khoá nhầm toàn bộ văn phòng khi một người hỏi nhiều.
_ask_limiter = AttemptLimiter(
    build_attempt_store(),
    max_attempts=30,
    window_seconds=300,
    prefix="chat-ask",
)


def get_repository(db: Session = Depends(get_db)) -> ChatSessionRepository:
    return ChatSessionRepository(db)


@contextmanager
def _open_stream_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_stream_session():
    """Trả về context manager mở session cho luồng SSE.

    Tách thành dependency để test ghi đè được. Nếu gọi thẳng `SessionLocal()`
    trong generator thì luồng luôn nhìn vào một transaction KHÁC với test —
    dữ liệu test tạo ra (còn nằm trong transaction chưa commit) sẽ không thấy,
    và mọi test SSE đều nhận `error` thay vì câu trả lời.
    """
    return _open_stream_session()


def build_chat_service(db: Session) -> ChatService:
    return ChatService(db, Retriever(db, build_embedding_client()), build_llm_client())


def _sse(event: ChatEvent) -> str:
    """Định dạng một sự kiện SSE.

    `json.dumps` với ensure_ascii=False giữ nguyên tiếng Việt; quan trọng hơn
    là nó ESCAPE ký tự xuống dòng — nếu không, một token chứa "\\n" sẽ cắt đôi
    khung dữ liệu và trình duyệt hiểu sai toàn bộ luồng còn lại.
    """
    payload = json.dumps(event.data, ensure_ascii=False)
    return f"event: {event.type}\ndata: {payload}\n\n"


# ── Quản lý phiên ─────────────────────────────────────────────────────


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mở phiên trò chuyện mới (US-23)",
)
def create_session(
    data: CreateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSession:
    chat_session = ChatSessionRepository(db).add(
        ChatSession(user_id=current_user.id, title=data.title)
    )
    db.commit()
    db.refresh(chat_session)
    return chat_session


@router.get(
    "/sessions",
    response_model=Page[SessionResponse],
    summary="Danh sách phiên trò chuyện của tôi",
)
def list_sessions(
    params: PageParams = Depends(page_params),
    repo: ChatSessionRepository = Depends(get_repository),
    current_user: User = Depends(get_current_user),
) -> Page[SessionResponse]:
    rows, total = repo.list_for_user(current_user.id, params)
    return Page.create([SessionResponse.model_validate(r) for r in rows], total, params)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionDetailResponse,
    summary="Đọc lại một phiên trò chuyện",
)
def get_session(
    session_id: UUID,
    repo: ChatSessionRepository = Depends(get_repository),
    current_user: User = Depends(get_current_user),
) -> SessionDetailResponse:
    chat_session = repo.get_owned(session_id, current_user.id)
    # 404 kể cả với Admin: hội thoại với trợ lý là việc riêng của nhân viên
    if chat_session is None:
        raise NotFoundError("Không tìm thấy cuộc trò chuyện")

    # Dựng tường minh, KHÔNG dùng model_validate(chat_session): Pydantic sẽ
    # tự đọc quan hệ `messages` → `citations` từ ORM và vỡ, vì ChatCitation
    # không có sẵn `title`/`slug` (chúng nằm ở bảng kb_articles).
    messages = [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            no_context_found=m.no_context_found,
            latency_ms=m.latency_ms,
            created_at=m.created_at,
            citations=[
                CitationResponse(
                    article_id=c.article_id,
                    title=c.article.title,
                    slug=c.article.slug,
                    score=float(c.score),
                    rank=c.rank,
                )
                for c in sorted(m.citations, key=lambda c: c.rank)
                if c.article is not None
            ],
        )
        for m in repo.messages_of(session_id)
    ]
    return SessionDetailResponse(
        id=chat_session.id,
        title=chat_session.title,
        message_count=chat_session.message_count,
        led_to_ticket=chat_session.led_to_ticket,
        created_at=chat_session.created_at,
        last_message_at=chat_session.last_message_at,
        messages=messages,
    )


# ── Hỏi đáp theo luồng (SSE) ──────────────────────────────────────────


@router.post(
    "/sessions/{session_id}/messages",
    summary="Hỏi trợ lý ảo — trả lời theo luồng SSE (US-23, US-24)",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": (
                "Luồng SSE. Thứ tự sự kiện LUÔN là citations → token* → done, "
                "hoặc error rồi dừng."
            ),
            "content": {"text/event-stream": {}},
        }
    },
)
async def ask(
    session_id: UUID,
    data: AskRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    stream_session=Depends(get_stream_session),
) -> StreamingResponse:
    # Kiểm tra quyền TRƯỚC khi mở luồng — sau đó không trả mã lỗi được nữa
    if ChatSessionRepository(db).get_owned(session_id, current_user.id) is None:
        raise NotFoundError("Không tìm thấy cuộc trò chuyện")

    _ask_limiter.raise_if_blocked(str(current_user.id))
    _ask_limiter.record(str(current_user.id))

    user_id = current_user.id
    question = data.question

    async def stream() -> AsyncIterator[str]:
        # Session riêng cho luồng — xem chú thích đầu file
        try:
            with stream_session as stream_db:
                service = build_chat_service(stream_db)
                async for event in service.answer(
                    session_id=session_id, user_id=user_id, question=question
                ):
                    yield _sse(event)
                    # Người dùng đóng tab giữa chừng: dừng sinh token để khỏi
                    # đốt tiền LLM cho câu trả lời không ai đọc.
                    if await request.is_disconnected():
                        logger.info("client ngắt kết nối, dừng sinh câu trả lời")
                        break
        except Exception as exc:
            logger.exception("lỗi trong luồng trả lời", exc_info=exc)
            yield _sse(
                ChatEvent(
                    "error",
                    {
                        "code": "UPSTREAM_ERROR",
                        "message": (
                            "Trợ lý ảo tạm thời không phản hồi. "
                            "Bạn có thể tạo yêu cầu hỗ trợ để đội IT giúp trực tiếp."
                        ),
                        "canCreateTicket": True,
                    },
                )
            )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Nginx đệm response theo mặc định — không tắt thì người dùng chờ
            # im lặng vài giây rồi nhận cả câu trả lời một lúc, mất hết ý
            # nghĩa của streaming.
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/config", summary="Tham số hiển thị cho giao diện chat")
def chat_config(_: User = Depends(get_current_user)) -> dict:
    """Cho frontend biết giới hạn để hiển thị đúng, thay vì chép cứng số."""
    return {
        "maxQuestionLength": 1000,
        "rateLimitPerWindow": _ask_limiter.max_attempts,
        "rateLimitWindowSeconds": _ask_limiter.window_seconds,
        "model": settings.LLM_MODEL if settings.LLM_PROVIDER != "fake" else "fake",
    }
