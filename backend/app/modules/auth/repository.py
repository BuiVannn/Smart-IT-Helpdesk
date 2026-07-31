"""Truy vấn refresh token. Chỉ truy vấn — mọi quyết định nghiệp vụ ở service."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.modules.auth.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, token: RefreshToken) -> RefreshToken:
        self.session.add(token)
        self.session.flush()
        return token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Tra cứu bằng HASH, không bao giờ bằng bản rõ — DB không hề lưu bản rõ."""
        return self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).scalar_one_or_none()

    def revoke(self, token: RefreshToken, replaced_by: RefreshToken | None = None) -> None:
        token.revoked_at = datetime.now(UTC)
        if replaced_by is not None:
            token.replaced_by_id = replaced_by.id
        self.session.flush()

    def revoke_all_for_user(self, user_id: UUID) -> int:
        """Thu hồi mọi phiên còn hiệu lực. Trả về số phiên bị thu hồi."""
        result = self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        self.session.flush()
        return result.rowcount or 0

    def count_active(self, user_id: UUID) -> int:
        return self.session.execute(
            select(func.count())
            .select_from(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(UTC),
            )
        ).scalar_one()

    def delete_expired(self, before: datetime | None = None) -> int:
        """Dọn token đã hết hạn — gọi định kỳ bằng Celery beat."""
        cutoff = before or datetime.now(UTC)
        result = self.session.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < cutoff)
        )
        self.session.flush()
        return result.rowcount or 0
