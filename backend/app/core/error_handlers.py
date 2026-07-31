"""Dịch DomainError sang HTTP response.

MỌI lỗi đều có cùng một hình dạng — không có ngoại lệ:
    {"error": {"code", "message", "details?", "requestId"}}
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import DomainError
from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)


def _body(code: str, message: str, details=None) -> dict:
    error: dict = {"code": code, "message": message, "requestId": request_id_ctx.get()}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=_body(exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(x) for x in e["loc"][1:]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_body("VALIDATION_ERROR", "Dữ liệu không hợp lệ", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "BAD_REQUEST"}
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(codes.get(exc.status_code, "BAD_REQUEST"), str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Log đầy đủ cho developer, nhưng KHÔNG BAO GIỜ lộ chi tiết nội bộ ra client
        logger.exception("unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_body("INTERNAL_ERROR", "Đã có lỗi xảy ra. Vui lòng thử lại sau."),
        )
