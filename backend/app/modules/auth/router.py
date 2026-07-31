"""★ FILE MẪU cho tầng router. Router CHỈ làm 4 việc:

  1. Nhận HTTP và kiểm tra kiểu dữ liệu (Pydantic lo)
  2. Kiểm tra quyền (Depends)
  3. Gọi service
  4. Đổi kết quả thành HTTP

KHÔNG có truy vấn database, KHÔNG có `if` nghiệp vụ trong file này. Logic nằm
ở service để còn dùng lại được trong Celery worker và script CLI.
"""

import ipaddress

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.exceptions import UnauthenticatedError
from app.core.rate_limit import AttemptLimiter, build_attempt_store
from app.db.session import get_db
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.modules.auth.service import AuthService, ClientInfo
from app.modules.users.models import User
from app.modules.users.schemas import UserResponse

router = APIRouter()

REFRESH_COOKIE = "refresh_token"

# Dựng MỘT lần cho cả tiến trình. Dựng lại theo từng request thì bộ đếm trong
# RAM sẽ reset mỗi lần gọi và giới hạn đăng nhập coi như không tồn tại.
_login_limiter = AttemptLimiter(
    build_attempt_store(),
    max_attempts=settings.LOGIN_MAX_ATTEMPTS,
    window_seconds=settings.LOGIN_LOCKOUT_MINUTES * 60,
    prefix="login-attempts",
)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db, login_limiter=_login_limiter)


def _client_info(request: Request) -> ClientInfo:
    """Lấy IP thật khi có reverse proxy đứng trước.

    Cột `ip_address` kiểu INET nên PHẢI kiểm tra tính hợp lệ: TestClient gửi
    host là chuỗi "testclient", ghi thẳng vào DB sẽ nổ lỗi kiểu dữ liệu.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    raw = forwarded.split(",")[0].strip() or (request.client.host if request.client else "")
    try:
        ip: str | None = str(ipaddress.ip_address(raw))
    except ValueError:
        ip = None
    return ClientInfo(user_agent=request.headers.get("user-agent"), ip_address=ip)


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        raw_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        httponly=True,   # JavaScript KHÔNG đọc được — XSS không lấy được phiên
        secure=settings.ENVIRONMENT != "local",
        samesite="strict",
        # Giới hạn đường dẫn: cookie chỉ được gửi tới các endpoint auth, không
        # đính kèm vào mọi request khác một cách vô ích.
        path=f"{settings.API_V1_PREFIX}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=f"{settings.API_V1_PREFIX}/auth")


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng ký tài khoản (US-01)",
)
def register(
    data: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> User:
    # Cố tình KHÔNG trả token: người dùng phải đăng nhập một lần nữa. Đăng ký
    # xong tự đăng nhập luôn nghĩa là mọi lỗ hổng ở /register đều thành lỗ hổng
    # chiếm phiên, và ta mất một điểm để chèn xác minh email về sau.
    return service.register(data)


@router.post("/login", response_model=TokenResponse, summary="Đăng nhập (US-02)")
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    result = service.login(data.email, data.password, _client_info(request))
    _set_refresh_cookie(response, result.refresh_token)
    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        user=UserResponse.model_validate(result.user),
    )


@router.post("/refresh", response_model=TokenResponse, summary="Xoay vòng token (US-03)")
def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    if not refresh_token:
        raise UnauthenticatedError("Không có phiên đăng nhập")

    result = service.refresh(refresh_token, _client_info(request))
    _set_refresh_cookie(response, result.refresh_token)
    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        user=UserResponse.model_validate(result.user),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đăng xuất thiết bị hiện tại (US-04)",
)
def logout(
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    service.logout(refresh_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response)
    return response


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đăng xuất mọi thiết bị (US-04)",
)
def logout_all(
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    service.logout_all(current_user.id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response)
    return response


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đổi mật khẩu, thu hồi mọi phiên (US-05)",
)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    service.change_password(current_user, data.current_password, data.new_password)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response)
    return response
