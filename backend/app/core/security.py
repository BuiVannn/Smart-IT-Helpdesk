"""Hash mật khẩu và tạo/giải mã JWT."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import UnauthenticatedError

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS)

# Hash giả dùng để so sánh khi email không tồn tại — giữ thời gian xử lý
# tương đương với trường hợp sai mật khẩu, chống timing attack.
_DUMMY_HASH = _pwd.hash("dummy-password-for-timing-attack-protection")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str | None) -> bool:
    if hashed is None:
        _pwd.verify(plain, _DUMMY_HASH)  # luôn tốn thời gian như thật
        return False
    return _pwd.verify(plain, hashed)


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
