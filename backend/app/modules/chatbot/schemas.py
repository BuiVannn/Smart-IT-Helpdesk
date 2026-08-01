"""Schema module chatbot (US-23, US-24, US-25).

Lưu ý: câu trả lời của trợ lý KHÔNG đi qua schema nào — nó được stream theo
từng token qua SSE. Schema ở đây chỉ dùng cho phần quản lý phiên và đọc lại
lịch sử hội thoại.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import ResponseModel, StrictModel
from app.modules.chatbot.constants import MessageRole


class CreateSessionRequest(StrictModel):
    # Câu hỏi đầu tiên (tuỳ chọn) — dùng để tự đặt tên phiên
    title: str | None = Field(default=None, max_length=200)


class AskRequest(StrictModel):
    question: str = Field(min_length=1, max_length=1000)


class CitationResponse(ResponseModel):
    article_id: UUID = Field(serialization_alias="articleId")
    title: str
    slug: str
    score: float
    rank: int


class MessageResponse(ResponseModel):
    id: UUID
    role: MessageRole
    content: str
    no_context_found: bool = Field(serialization_alias="noContextFound")
    citations: list[CitationResponse] = Field(default_factory=list)
    latency_ms: int | None = Field(default=None, serialization_alias="latencyMs")
    created_at: datetime = Field(serialization_alias="createdAt")


class SessionResponse(ResponseModel):
    id: UUID
    title: str | None
    message_count: int = Field(serialization_alias="messageCount")
    led_to_ticket: bool = Field(serialization_alias="ledToTicket")
    created_at: datetime = Field(serialization_alias="createdAt")
    last_message_at: datetime | None = Field(default=None, serialization_alias="lastMessageAt")


class SessionDetailResponse(SessionResponse):
    messages: list[MessageResponse] = Field(default_factory=list)
