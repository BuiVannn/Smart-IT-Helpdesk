"""Truy vấn phiên chat.

★ MỌI truy vấn đều lọc theo `user_id`. Phiên chat chứa câu hỏi riêng tư của
nhân viên ("tôi quên mật khẩu", "máy tôi nhiễm virus") — kể cả Admin cũng
KHÔNG đọc được phiên của người khác. Đây là ngoại lệ có chủ ý so với ticket:
ticket là việc chung của công ty, hội thoại với trợ lý thì không.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.pagination import PageParams
from app.modules.chatbot.models import ChatMessage, ChatSession


class ChatSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, chat_session: ChatSession) -> ChatSession:
        self.session.add(chat_session)
        self.session.flush()
        return chat_session

    def get_owned(self, session_id: UUID, user_id: UUID) -> ChatSession | None:
        """Lấy phiên CỦA CHÍNH người dùng. Trả None nếu của người khác."""
        return self.session.execute(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        ).scalar_one_or_none()

    def list_for_user(self, user_id: UUID, params: PageParams) -> tuple[list[ChatSession], int]:
        base = select(ChatSession).where(ChatSession.user_id == user_id)

        total = self.session.execute(select(func.count()).select_from(base.subquery())).scalar_one()

        rows = (
            self.session.execute(
                base.order_by(
                    # Phiên vừa nhắn xếp trước; phiên chưa nhắn lần nào dùng
                    # created_at để không bị rơi xuống cuối danh sách vì NULL.
                    func.coalesce(ChatSession.last_message_at, ChatSession.created_at).desc()
                )
                .offset(params.offset)
                .limit(params.limit)
            )
            .scalars()
            .all()
        )

        return list(rows), total

    def messages_of(self, session_id: UUID) -> list[ChatMessage]:
        return list(
            self.session.execute(
                select(ChatMessage)
                .options(selectinload(ChatMessage.citations))
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
            )
            .scalars()
            .all()
        )
