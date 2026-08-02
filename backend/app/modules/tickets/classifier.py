"""F3 — Phân loại ticket tự động (US-19).

NGUYÊN TẮC CHI PHỐI (docs/design/07 §9): AI là tính năng bổ trợ, KHÔNG phải
đường sống của hệ thống. Mọi nhánh trong file này đều kết thúc bằng "ticket
vẫn dùng được bình thường, Agent phân loại tay" — không có nhánh nào ném lỗi
ra ngoài làm hỏng vòng đời ticket (BR-15).

NĂM TẦNG DỰ PHÒNG (docs/design/07 §2.5):

    1. LLM trả lời, confidence >= ngưỡng  → áp dụng vào ticket
    2. LLM trả lời, confidence <  ngưỡng  → ghi lại gợi ý, KHÔNG áp dụng (BR-14)
    3. LLM lỗi / timeout                  → thử lại 3 lần, backoff mũ có jitter
    4. Hết lượt thử                       → RuleBasedClassifier, confidence 0.4
                                            (dưới ngưỡng ⇒ cũng chỉ là gợi ý)
    5. Không luật nào khớp                → ai_status = FAILED

Tầng 4 còn một giá trị nữa: nó chạy được khi KHÔNG có API key, nên demo và
CI không phụ thuộc vào nhà cung cấp LLM.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm.base import LlmClient, LlmResponse
from app.ai.resilience import RetryConfig, with_retry
from app.core.config import settings
from app.core.logging import get_logger
from app.modules.tickets.constants import AiStatus, TicketPriority
from app.modules.tickets.models import AiClassification, Ticket, TicketCategory
from app.modules.tickets.prompts import (
    CLASSIFY_PROMPT_VERSION,
    build_classification_schema,
    build_classify_prompt,
)
from app.modules.tickets.service import TicketService

logger = get_logger(__name__)

MAX_REASONING_LENGTH = 300
RULE_CONFIDENCE = 0.4
RULES_VERSION = "rules-v1.0"
RULES_MODEL_NAME = "rule-based"


class ClassificationSource(StrEnum):
    LLM = "LLM"
    RULES = "RULES"


@dataclass(frozen=True)
class Suggestion:
    """Kết quả phân loại đã được kiểm chứng — slug chắc chắn tồn tại trong DB."""

    category_slug: str
    priority: TicketPriority
    confidence: float
    reasoning: str
    source: ClassificationSource


@dataclass
class ClassificationOutcome:
    """Kết quả một lượt phân loại, dùng cho log và cho giá trị trả về của task."""

    ticket_id: UUID
    ai_status: AiStatus
    suggestion: Suggestion | None = None
    error: str | None = None
    latency_ms: int = 0

    @property
    def was_applied(self) -> bool:
        return self.ai_status == AiStatus.APPLIED


# ─────────────────────────────────────────────────────────────────────
# Tầng 4 — phân loại bằng từ khoá. LỚP THUẦN, không I/O, không LLM.
# ─────────────────────────────────────────────────────────────────────


def normalize(text: str) -> str:
    """Bỏ dấu tiếng Việt và hạ chữ thường.

    Nhân viên gõ "mat khau", "khong vao duoc mang" nhiều không kém gõ có dấu.
    So khớp trên chuỗi đã bỏ dấu giúp một luật bắt được cả hai cách gõ, thay
    vì phải liệt kê hai lần mọi từ khoá.
    """
    lowered = text.lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class KeywordRule:
    slug: str
    priority: TicketPriority
    keywords: tuple[str, ...]
    dominant: bool = False
    """Khớp MỘT từ khoá là đủ để thắng mọi luật khác.

    Chỉ dùng cho bảo mật. "Laptop của tôi bị nhiễm virus" khớp `hardware` hai
    từ khoá ("laptop", "may tinh") và `security` một từ ("virus") — đếm từ
    khoá thì phần cứng thắng, và một sự cố bảo mật rơi vào hàng chờ sửa máy.
    Gán nhầm một ticket phần cứng rẻ hơn nhiều so với chậm một giờ với virus.
    """


# Thứ tự có ý nghĩa: khi hai luật khớp bằng số từ khoá thì luật đứng trước thắng.
KEYWORD_RULES: tuple[KeywordRule, ...] = (
    KeywordRule(
        "security",
        TicketPriority.URGENT,
        (
            "virus",
            "ma doc",
            "malware",
            "ransomware",
            "lua dao",
            "phishing",
            "bao mat",
            "lo du lieu",
            "tan cong",
            "hack",
            "gia mao",
        ),
        dominant=True,
    ),
    KeywordRule(
        "network",
        TicketPriority.HIGH,
        (
            "wifi",
            "mang",
            "internet",
            "vpn",
            "ket noi",
            "router",
            "switch",
            "rot mang",
            "mat mang",
            "duong truyen",
        ),
    ),
    KeywordRule(
        "account",
        TicketPriority.MEDIUM,
        (
            "mat khau",
            "password",
            "dang nhap",
            "tai khoan",
            "khoa tai khoan",
            "quen mat khau",
            "otp",
            "xac thuc",
            "doi mat khau",
        ),
    ),
    KeywordRule(
        "email",
        TicketPriority.MEDIUM,
        (
            "email",
            "outlook",
            "hom thu",
            "gui mail",
            "nhan mail",
            "hop thu",
            "lich hop",
            "calendar",
        ),
    ),
    KeywordRule(
        "access",
        TicketPriority.MEDIUM,
        (
            "cap quyen",
            "phan quyen",
            "quyen truy cap",
            "truy cap thu muc",
            "share folder",
            "thu muc chung",
        ),
    ),
    KeywordRule(
        "hardware",
        TicketPriority.MEDIUM,
        (
            "may in",
            "man hinh",
            "chuot",
            "ban phim",
            "laptop",
            "may tinh",
            "o cung",
            "khong len nguon",
            "docking",
            "tai nghe",
            "webcam",
        ),
    ),
    KeywordRule(
        "software",
        TicketPriority.MEDIUM,
        (
            "phan mem",
            "cai dat",
            "office",
            "excel",
            "word",
            "ung dung",
            "license",
            "ban quyen",
            "cap nhat",
            "phien ban",
        ),
    ),
)


class RuleBasedClassifier:
    """Đối chiếu từ khoá — đường dự phòng khi LLM không dùng được.

    Luôn trả confidence 0.4, tức là LUÔN nằm dưới ngưỡng áp dụng. Đây là chủ
    ý: đối chiếu từ khoá đủ tốt để gợi ý cho Agent, không đủ tốt để tự động
    đổi dữ liệu của người dùng.
    """

    def __init__(self, rules: tuple[KeywordRule, ...] = KEYWORD_RULES) -> None:
        # Biên dịch sẵn, và dùng ranh giới từ: nếu không, "mang" sẽ khớp cả
        # bên trong "mangan" và mọi luật đều dính nhau.
        self._compiled = [
            (rule, [(kw, re.compile(rf"\b{re.escape(normalize(kw))}\b")) for kw in rule.keywords])
            for rule in rules
        ]

    def classify(self, title: str, description: str) -> Suggestion | None:
        """Trả về gợi ý, hoặc None nếu không luật nào khớp."""
        text = normalize(f"{title}\n{description}")

        best: tuple[int, int, int, KeywordRule, list[str]] | None = None
        for order, (rule, keywords) in enumerate(self._compiled):
            matched = [kw for kw, pattern in keywords if pattern.search(text)]
            if not matched:
                continue
            # Thứ tự ưu tiên: luật áp đảo → nhiều từ khoá khớp hơn → đứng
            # trước trong bảng (-order để so sánh giảm dần vẫn chọn luật đầu).
            candidate = (int(rule.dominant), len(matched), -order, rule, matched)
            if best is None or candidate[:3] > best[:3]:
                best = candidate

        if best is None:
            return None

        *_, rule, matched = best
        return Suggestion(
            category_slug=rule.slug,
            priority=rule.priority,
            confidence=RULE_CONFIDENCE,
            reasoning=f"Đối chiếu từ khoá: {', '.join(matched[:3])}",
            source=ClassificationSource.RULES,
        )


# ─────────────────────────────────────────────────────────────────────
# Tầng 1–3 — gọi LLM, kiểm chứng, ghi kết quả
# ─────────────────────────────────────────────────────────────────────


class TicketClassifier:
    """Điều phối một lượt phân loại cho MỘT ticket.

    Được gọi từ Celery task (`tasks.classify_ticket`) và từ script đánh giá.
    Không bao giờ được gọi đồng bộ trong `POST /tickets`: một lời gọi LLM
    5–20 giây trong đường tạo ticket là vi phạm NFR p95 < 500 ms, và LLM hỏng
    sẽ thành "không tạo được ticket" (docs/design/07 §2.2).
    """

    def __init__(
        self,
        session: Session,
        llm: LlmClient,
        *,
        rules: RuleBasedClassifier | None = None,
        confidence_threshold: float | None = None,
        retry: RetryConfig | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.session = session
        self.llm = llm
        self.rules = rules or RuleBasedClassifier()
        self.threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.AI_CONFIDENCE_THRESHOLD
        )
        self.retry = retry or RetryConfig()
        self.timeout = timeout_seconds or settings.LLM_TIMEOUT_CLASSIFY
        self.tickets = TicketService(session)

    async def classify(self, ticket_id: UUID) -> ClassificationOutcome:
        ticket = self.session.get(Ticket, ticket_id)
        if ticket is None:
            logger.warning(
                "phân loại: không tìm thấy ticket",
                extra={"extra_fields": {"ticket_id": str(ticket_id)}},
            )
            return ClassificationOutcome(ticket_id, AiStatus.FAILED, error="Ticket không tồn tại")

        # Bảo đảm chạy lại nhiều lần vẫn an toàn: Celery giao lại task sau khi
        # worker chết, và job đối soát cũng có thể xếp hàng lần hai. Ticket đã
        # xử lý rồi thì bỏ qua, không gọi LLM lần nữa (mất tiền, không được gì).
        if ticket.ai_status != AiStatus.PENDING:
            return ClassificationOutcome(ticket_id, ticket.ai_status)

        categories = self._active_categories()
        if not categories:
            return self._finish(
                ticket_id,
                None,
                AiStatus.FAILED,
                error="Chưa cấu hình loại sự cố nào đang hoạt động",
            )

        title, description = ticket.title, ticket.description

        started = time.perf_counter()
        suggestion, response, error = await self._ask_llm(title, description, categories)
        latency_ms = int((time.perf_counter() - started) * 1000)

        if suggestion is None:
            # Tầng 4 — vẫn ghi lại `error` của LLM để US-22 đếm được tỉ lệ hỏng
            suggestion = self._fallback(title, description, categories)

        if suggestion is None:
            return self._finish(
                ticket_id,
                None,
                AiStatus.FAILED,
                error=error or "Không phân loại được",
                latency_ms=latency_ms,
                response=response,
            )

        if suggestion.confidence < self.threshold:
            # BR-14 — dưới ngưỡng thì ghi lại gợi ý nhưng KHÔNG tự áp dụng.
            # Ticket ở lại hàng chờ phân loại thủ công.
            return self._finish(
                ticket_id,
                suggestion,
                AiStatus.LOW_CONFIDENCE,
                error=error,
                latency_ms=latency_ms,
                response=response,
            )

        category = self._category_by_slug(categories, suggestion.category_slug)
        status = self.tickets.apply_ai_classification(
            ticket_id,
            category_id=category.id,
            priority=suggestion.priority,
            reasoning=suggestion.reasoning,
            confidence=suggestion.confidence,
        )
        return self._finish(
            ticket_id,
            suggestion,
            status,
            error=error,
            latency_ms=latency_ms,
            response=response,
            category_id=category.id,
        )

    async def suggest(self, title: str, description: str) -> tuple[Suggestion | None, str | None]:
        """Phân loại một đoạn văn bản, KHÔNG chạm tới ticket nào.

        Dùng cho `scripts/eval_classification.py`: chạy 50 ca mẫu mà tạo 50
        ticket rác trong database thì không ai chịu chạy tập đánh giá, và tập
        đánh giá không ai chạy thì mọi thay đổi prompt lại quay về cảm tính.
        """
        categories = self._active_categories()
        if not categories:
            return None, "Chưa cấu hình loại sự cố nào đang hoạt động"

        suggestion, _, error = await self._ask_llm(title, description, categories)
        if suggestion is None:
            suggestion = self._fallback(title, description, categories)
        return suggestion, error

    # ── Gọi LLM ───────────────────────────────────────────────────────

    async def _ask_llm(
        self, title: str, description: str, categories: list[TicketCategory]
    ) -> tuple[Suggestion | None, LlmResponse | None, str | None]:
        """Trả về (gợi ý, phản hồi thô, thông báo lỗi).

        KHÔNG ném lỗi ra ngoài — lỗi được biến thành `error` để tầng trên
        chuyển sang đường dự phòng.
        """
        system, user = build_classify_prompt(
            title=title,
            description=description,
            categories=[(c.slug, c.name) for c in categories],
        )
        schema = build_classification_schema([c.slug for c in categories])

        async def call() -> LlmResponse:
            # Timeout nằm TRONG hàm được retry: hết giờ lần này thì lần sau
            # vẫn được trọn thời gian, thay vì bị lần trước ăn mất.
            return await asyncio.wait_for(
                # ★ 900 chứ không phải 400. Model suy luận (nemotron, gpt-oss)
                # tiêu token vào phần suy nghĩ TRƯỚC khi viết câu trả lời; với
                # trần 400 thì `content` hay về rỗng trong khi HTTP vẫn 200, và
                # mọi ticket lặng lẽ rơi xuống tầng luật. Câu trả lời thật chỉ
                # tốn ~80 token nên phần dư này gần như miễn phí.
                self.llm.complete(system=system, user=user, schema=schema, max_tokens=900),
                timeout=self.timeout,
            )

        try:
            response = await with_retry(call, self.retry, operation="phân loại ticket")
        except Exception as exc:
            # Giữ lại NGUYÊN NHÂN GỐC. `with_retry` gói mọi thứ thành
            # ExternalServiceError("thất bại sau 3 lần thử") — thông báo đó
            # không phân biệt được hết hạn mức, sai API key hay Redis chết,
            # mà đó chính là ba câu trả lời khác nhau khi đi sửa.
            detail = f"{type(exc).__name__}: {exc}"
            if exc.__cause__ is not None:
                cause = exc.__cause__
                detail = f"{detail} — nguyên nhân: {type(cause).__name__}: {cause}"
            logger.warning(f"LLM phân loại thất bại: {detail}")
            return None, None, detail

        suggestion, error = self._validate(response, categories)
        return suggestion, response, error

    def _validate(
        self, response: LlmResponse, categories: list[TicketCategory]
    ) -> tuple[Suggestion | None, str | None]:
        """KHÔNG TIN đầu ra của LLM (docs/design/07 §2.3).

        Ràng buộc bằng JSON schema chỉ là lời đề nghị với nhà cung cấp; model
        vẫn có thể trả slug không tồn tại hoặc confidence ngoài [0, 1]. Dữ
        liệu chưa kiểm chứng mà ghi thẳng vào ticket là cách nhanh nhất để có
        một `category_id` trỏ vào hư không.
        """
        payload = response.parsed
        if payload is None:
            try:
                payload = json.loads(response.content)
            except (ValueError, TypeError):
                return None, "LLM trả về nội dung không phải JSON"
        if not isinstance(payload, dict):
            return None, "LLM trả về JSON không phải object"

        slug = payload.get("category_slug")
        if self._category_by_slug(categories, slug) is None:
            return None, f"LLM trả về loại sự cố không tồn tại: {slug!r}"

        try:
            priority = TicketPriority(payload.get("priority"))
        except ValueError:
            return None, f"LLM trả về mức ưu tiên không hợp lệ: {payload.get('priority')!r}"

        raw_confidence = payload.get("confidence")
        if not isinstance(raw_confidence, int | float) or isinstance(raw_confidence, bool):
            return None, f"LLM trả về confidence không phải số: {raw_confidence!r}"
        confidence = float(raw_confidence)
        if not 0.0 <= confidence <= 1.0:
            return None, f"LLM trả về confidence ngoài [0, 1]: {confidence}"

        return (
            Suggestion(
                category_slug=slug,
                priority=priority,
                confidence=confidence,
                reasoning=sanitize_reasoning(str(payload.get("reasoning") or "")),
                source=ClassificationSource.LLM,
            ),
            None,
        )

    def _fallback(
        self, title: str, description: str, categories: list[TicketCategory]
    ) -> Suggestion | None:
        suggestion = self.rules.classify(title, description)
        if suggestion is None:
            return None
        # Luật có thể trỏ tới một loại sự cố mà Admin đã vô hiệu hoá — khi đó
        # coi như không khớp, chứ không gán bừa vào một category đã tắt.
        if self._category_by_slug(categories, suggestion.category_slug) is None:
            return None
        logger.info(
            "dùng đường dự phòng đối chiếu từ khoá",
            extra={"extra_fields": {"category": suggestion.category_slug}},
        )
        return suggestion

    # ── Ghi kết quả ───────────────────────────────────────────────────

    def _finish(
        self,
        ticket_id: UUID,
        suggestion: Suggestion | None,
        status: AiStatus,
        *,
        error: str | None = None,
        latency_ms: int = 0,
        response: LlmResponse | None = None,
        category_id: UUID | None = None,
    ) -> ClassificationOutcome:
        """Ghi bản ghi `ai_classifications` và chốt `ai_status` của ticket.

        Ghi MỌI lượt, kể cả thất bại: đây là nguồn dữ liệu duy nhất cho báo
        cáo độ chính xác (US-22). Chỉ ghi lượt thành công thì mọi con số đều
        đẹp một cách vô nghĩa.
        """
        if suggestion is not None and category_id is None:
            category_id = self._slug_to_id(suggestion.category_slug)

        self.session.add(
            AiClassification(
                ticket_id=ticket_id,
                model_name=self._model_name(suggestion, response),
                prompt_version=(
                    RULES_VERSION
                    if suggestion is not None and suggestion.source == ClassificationSource.RULES
                    else CLASSIFY_PROMPT_VERSION
                ),
                suggested_category_id=category_id,
                suggested_priority=suggestion.priority if suggestion else None,
                confidence=suggestion.confidence if suggestion else None,
                reasoning=suggestion.reasoning if suggestion else None,
                was_applied=status == AiStatus.APPLIED,
                latency_ms=latency_ms or (response.latency_ms if response else None),
                prompt_tokens=response.prompt_tokens if response else None,
                completion_tokens=response.completion_tokens if response else None,
                error_message=error,
            )
        )

        # APPLIED/SKIPPED đã do TicketService đặt trong cùng transaction; ở đây
        # chỉ còn LOW_CONFIDENCE và FAILED cần chốt.
        if status in (AiStatus.LOW_CONFIDENCE, AiStatus.FAILED):
            self.tickets.mark_ai_status(ticket_id, status)

        self.session.commit()

        logger.info(
            "phân loại xong",
            extra={
                "extra_fields": {
                    "ticket_id": str(ticket_id),
                    "ai_status": status,
                    "category": suggestion.category_slug if suggestion else None,
                    "confidence": suggestion.confidence if suggestion else None,
                    "source": suggestion.source if suggestion else None,
                    "latency_ms": latency_ms,
                    "error": error,
                }
            },
        )
        return ClassificationOutcome(ticket_id, status, suggestion, error, latency_ms)

    @staticmethod
    def _model_name(suggestion: Suggestion | None, response: LlmResponse | None) -> str:
        if suggestion is not None and suggestion.source == ClassificationSource.RULES:
            return RULES_MODEL_NAME
        if response is not None:
            return response.model
        return settings.LLM_MODEL

    # ── Truy vấn phụ trợ ──────────────────────────────────────────────

    def _active_categories(self) -> list[TicketCategory]:
        return list(
            self.session.execute(
                select(TicketCategory)
                .where(TicketCategory.is_active.is_(True))
                .order_by(TicketCategory.sort_order, TicketCategory.slug)
            )
            .scalars()
            .all()
        )

    @staticmethod
    def _category_by_slug(categories: list[TicketCategory], slug: object) -> TicketCategory | None:
        return next((c for c in categories if c.slug == slug), None)

    def _slug_to_id(self, slug: str) -> UUID | None:
        return self.session.execute(
            select(TicketCategory.id).where(TicketCategory.slug == slug)
        ).scalar_one_or_none()


def sanitize_reasoning(text: str) -> str:
    """Cắt 300 ký tự và làm sạch trước khi lưu (docs/design/07 §2.3).

    `reasoning` là văn bản do LLM sinh ra từ dữ liệu người dùng nhập, nên nó
    là dữ liệu KHÔNG TIN CẬY và sẽ được hiển thị lại trên giao diện.
    """
    # THAY bằng khoảng trắng chứ không XOÁ: xoá thẳng ký tự xuống dòng sẽ dán
    # hai từ vào nhau ("có\nnhiều" → "cónhiều") và làm hỏng chính câu giải
    # thích mà Agent phải đọc.
    cleaned = "".join(c if c.isprintable() else " " for c in text)
    return " ".join(cleaned.split())[:MAX_REASONING_LENGTH]


def build_classifier(session: Session) -> TicketClassifier:
    """Dựng bộ phân loại theo cấu hình. Mặc định LLM_PROVIDER=fake ⇒ không cần API key."""
    from app.ai.llm.openai_client import build_llm_client

    return TicketClassifier(session, build_llm_client())
