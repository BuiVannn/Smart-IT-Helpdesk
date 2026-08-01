"""Hash mật khẩu và tạo/giải mã JWT."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import bcrypt
from jose import JWTError, jwt
from pydantic import AfterValidator, Field

from app.core.config import settings
from app.core.exceptions import UnauthenticatedError


def check_password_policy(v: str) -> str:
    if not any(c.isupper() for c in v):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ hoa")
    if not any(c.islower() for c in v):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ thường")
    if not any(c.isdigit() for c in v):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ số")
    return v


# ★ Chính sách mật khẩu khai báo ĐÚNG MỘT chỗ rồi dùng lại ở mọi nơi có nhận
# mật khẩu: đăng ký, đổi mật khẩu, và Admin tạo tài khoản hộ (US-07). Ba chỗ
# kiểm tra khác nhau là cách kinh điển để mật khẩu yếu lọt qua đường vòng.
#
# Nằm ở `core` chứ không nằm ở `modules/auth`: module `users` cũng cần nó, mà
# `auth/schemas.py` đã import `users/schemas.py` rồi — đặt ở auth thì thành
# vòng import, và vòng import chỉ nổ lúc khởi động thật.
Password = Annotated[
    str, Field(min_length=8, max_length=128), AfterValidator(check_password_policy)
]

# Dùng thư viện `bcrypt` TRỰC TIẾP thay vì passlib.
# Lý do: passlib ngừng bảo trì từ 2020 và không tương thích bcrypt >= 4.1
# (lỗi "password cannot be longer than 72 bytes" ngay khi khởi tạo).
# Gọi thẳng bcrypt vừa ít phụ thuộc hơn, vừa không còn lớp trung gian nào để hỏng.

# bcrypt chỉ dùng 72 byte đầu của mật khẩu. Mật khẩu dài hơn phải được cắt
# TƯỜNG MINH — nếu không, bcrypt 4.x sẽ ném lỗi thay vì âm thầm cắt.
BCRYPT_MAX_BYTES = 72


def _prepare(plain: str) -> bytes:
    return plain.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(_prepare(plain), salt).decode("ascii")


# Hash giả dùng khi email không tồn tại — giữ thời gian xử lý tương đương
# với trường hợp sai mật khẩu, chống timing attack (xem US-02).
_DUMMY_HASH = hash_password("dummy-password-for-timing-attack-protection")


def verify_password(plain: str, hashed: str | None) -> bool:
    if hashed is None:
        bcrypt.checkpw(_prepare(plain), _DUMMY_HASH.encode("ascii"))  # tốn thời gian như thật
        return False
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("ascii"))
    except ValueError:
        # Hash trong DB sai định dạng — coi như xác thực thất bại, không nổ 500
        return False


def create_access_token(subject: str, role: str, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": secrets.token_urlsafe(16),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise UnauthenticatedError("Phiên đăng nhập không hợp lệ hoặc đã hết hạn") from exc


def generate_refresh_token() -> tuple[str, str]:
    """Sinh refresh token. Trả về (bản rõ gửi cho client, hash lưu vào DB).

    KHÔNG BAO GIỜ lưu bản rõ vào database — DB bị lộ cũng không dùng được token.
    """
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
