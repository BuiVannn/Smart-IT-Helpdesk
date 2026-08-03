"""AuthService — đăng ký, đăng nhập, xoay vòng token, đổi mật khẩu (US-01→05).

★ FILE MẪU cho tầng service. Quy tắc áp dụng cho mọi module:
- Nhận Session + repository qua constructor, KHÔNG tự tạo session
- Ném DomainError, KHÔNG BAO GIỜ ném HTTPException (service còn chạy trong
  Celery worker và script, nơi không có HTTP)
- Không biết gì về Request/Response — router lo phần đó

★ HỢP ĐỒNG VỚI TẦNG API: mọi hàm trả về `AuthResult`. Router chỉ việc đặt
`refresh_token` vào cookie HttpOnly và trả phần còn lại ra body.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AccountDisabledError,
    ConflictError,
    ForbiddenError,
    InvalidCredentialsError,
    UnauthenticatedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.rate_limit import AttemptLimiter
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.modules.auth.models import RefreshToken
from app.modules.auth.repository import RefreshTokenRepository
from app.modules.auth.schemas import RegisterRequest
from app.modules.users.constants import UserRole
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

logger = get_logger(__name__)


@dataclass
class AuthResult:
    """Kết quả một lần xác thực thành công.

    `refresh_token` là BẢN RÕ và chỉ tồn tại trong bộ nhớ đúng một lần — đây là
    lần duy nhất nó ra khỏi hệ thống. DB chỉ giữ hash.
    """

    user: User
    access_token: str
    refresh_token: str
    expires_in: int


@dataclass
class ClientInfo:
    """Thông tin phiên, để người dùng nhận ra thiết bị lạ khi xem lịch sử đăng nhập."""

    user_agent: str | None = None
    ip_address: str | None = None


class AuthService:
    def __init__(
        self,
        session: Session,
        login_limiter: AttemptLimiter,
    ) -> None:
        self.db = session
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)
        self.login_limiter = login_limiter

    # ── US-01: Đăng ký ────────────────────────────────────────────────

    def register(self, data: RegisterRequest) -> User:
        # CITEXT đã so sánh không phân biệt hoa/thường, nhưng vẫn chuẩn hoá
        # trước khi lưu để dữ liệu hiển thị nhất quán.
        email = data.email.strip().lower()

        if self.users.email_exists(email):
            # 409 với thông điệp trung tính. Không nói "email này đã đăng ký
            # lúc nào / bởi ai" — đó là rò rỉ thông tin về nhân sự công ty.
            raise ConflictError("Email này đã được đăng ký", details=None)

        user = User(
            email=email,
            full_name=data.full_name.strip(),
            password_hash=hash_password(data.password),
            role=UserRole.EMPLOYEE,  # vai trò do Admin nâng, không tự chọn khi đăng ký
            is_active=True,
        )
        self.users.add(user)
        self.db.commit()
        self.db.refresh(user)

        logger.info("đăng ký tài khoản", extra={"extra_fields": {"user_id": str(user.id)}})
        return user

    # ── US-02: Đăng nhập ──────────────────────────────────────────────

    def login(self, email: str, password: str, client: ClientInfo) -> AuthResult:
        email = email.strip().lower()

        # Chặn TRƯỚC khi so mật khẩu — và chặn cả khi mật khẩu đúng.
        # Nếu mật khẩu đúng vẫn cho vào thì kẻ dò đã tìm ra mật khẩu rồi,
        # giới hạn số lần thử chẳng còn ngăn được gì.
        self.login_limiter.raise_if_blocked(email)

        user = self.users.get_by_email(email)

        # verify_password tự chạy một phép hash giả khi user là None, để thời
        # gian phản hồi của "sai email" và "sai mật khẩu" bằng nhau. Không có
        # bước này, kẻ tấn công đo thời gian là dò ra email nào tồn tại.
        password_ok = verify_password(password, user.password_hash if user else None)

        if user is None or not password_ok:
            attempts = self.login_limiter.record_failure(email)
            logger.warning(
                "đăng nhập thất bại",
                extra={"extra_fields": {"email": email, "attempts": attempts}},
            )
            raise InvalidCredentialsError()

        if not user.is_active:
            # Lỗi KHÁC với sai mật khẩu: người dùng cần biết để đi liên hệ Admin,
            # và kẻ tấn công đằng nào cũng đã có mật khẩu đúng rồi.
            logger.warning(
                "đăng nhập vào tài khoản bị khoá", extra={"extra_fields": {"user_id": str(user.id)}}
            )
            raise AccountDisabledError()

        self.login_limiter.reset(email)
        user.last_login_at = datetime.now(UTC)

        result = self._issue_tokens(user, client)
        self.db.commit()

        logger.info("đăng nhập thành công", extra={"extra_fields": {"user_id": str(user.id)}})
        return result

    # ── US-03: Xoay vòng refresh token ────────────────────────────────

    def refresh(self, raw_token: str, client: ClientInfo) -> AuthResult:
        """Đổi refresh token lấy cặp token mới, đồng thời THU HỒI token cũ.

        ★ Xoay vòng (rotation) + phát hiện tái sử dụng: mỗi refresh token chỉ
        dùng được ĐÚNG MỘT LẦN. Nếu một token đã bị thay thế lại xuất hiện lần
        nữa thì chỉ có hai khả năng — token bị đánh cắp, hoặc client lỗi. Cả hai
        đều xử lý giống nhau: thu hồi TOÀN BỘ phiên của người dùng đó.
        """
        stored = self.tokens.get_by_hash(hash_refresh_token(raw_token))
        if stored is None:
            raise UnauthenticatedError("Phiên đăng nhập không hợp lệ")

        if stored.revoked_at is not None:
            revoked = self.tokens.revoke_all_for_user(stored.user_id)
            self.db.commit()
            logger.error(
                "PHÁT HIỆN TÁI SỬ DỤNG REFRESH TOKEN — đã thu hồi toàn bộ phiên",
                extra={
                    "extra_fields": {"user_id": str(stored.user_id), "sessions_revoked": revoked}
                },
            )
            raise UnauthenticatedError(
                "Phiên đăng nhập đã bị thu hồi vì lý do an toàn. Vui lòng đăng nhập lại."
            )

        if stored.expires_at <= datetime.now(UTC):
            raise UnauthenticatedError("Phiên đăng nhập đã hết hạn")

        user = self.users.get_by_id(stored.user_id)
        if user is None or not user.is_active:
            raise UnauthenticatedError("Tài khoản không còn hiệu lực")

        result = self._issue_tokens(user, client)
        # Gắn token mới vào token cũ để lần sau còn truy được chuỗi
        new_token = self.tokens.get_by_hash(hash_refresh_token(result.refresh_token))
        self.tokens.revoke(stored, replaced_by=new_token)
        self.db.commit()
        return result

    # ── US-04: Đăng xuất ──────────────────────────────────────────────

    def logout(self, raw_token: str | None) -> None:
        """Thu hồi đúng phiên hiện tại. Token không hợp lệ cũng KHÔNG báo lỗi.

        Đăng xuất phải luôn thành công dưới góc nhìn người dùng: báo lỗi ở đây
        chỉ khiến họ mắc kẹt ở trạng thái nửa vời, mà chẳng bảo vệ được gì.
        """
        if not raw_token:
            return
        stored = self.tokens.get_by_hash(hash_refresh_token(raw_token))
        if stored is not None and stored.revoked_at is None:
            self.tokens.revoke(stored)
            self.db.commit()

    def logout_all(self, user_id: UUID) -> int:
        count = self.tokens.revoke_all_for_user(user_id)
        self.db.commit()
        logger.info(
            "đăng xuất toàn bộ thiết bị",
            extra={"extra_fields": {"user_id": str(user_id), "sessions_revoked": count}},
        )
        return count

    # ── US-05: Đổi mật khẩu ───────────────────────────────────────────

    def change_password(self, user: User, current_password: str, new_password: str) -> int:
        if not verify_password(current_password, user.password_hash):
            logger.warning(
                "đổi mật khẩu thất bại: sai mật khẩu hiện tại",
                extra={"extra_fields": {"user_id": str(user.id), "email": user.email}},
            )
            raise ForbiddenError("Mật khẩu hiện tại không đúng")

        if verify_password(new_password, user.password_hash):
            raise ValidationError("Mật khẩu mới phải khác mật khẩu hiện tại")

        user.password_hash = hash_password(new_password)

        # Thu hồi MỌI phiên, kể cả phiên đang thao tác. Người đổi mật khẩu
        # thường vì nghi bị lộ — để phiên cũ sống tiếp thì việc đổi vô nghĩa.
        count = self.tokens.revoke_all_for_user(user.id)
        self.db.commit()

        logger.info(
            "đổi mật khẩu",
            extra={"extra_fields": {"user_id": str(user.id), "sessions_revoked": count}},
        )
        return count

    # ── Nội bộ ────────────────────────────────────────────────────────

    def _issue_tokens(self, user: User, client: ClientInfo) -> AuthResult:
        access = create_access_token(subject=str(user.id), role=user.role.value)
        raw_refresh, token_hash = generate_refresh_token()

        self.tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                user_agent=(client.user_agent or "")[:300] or None,
                ip_address=client.ip_address,
            )
        )
        return AuthResult(
            user=user,
            access_token=access,
            refresh_token=raw_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
