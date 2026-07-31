"""Gom toàn bộ router của các module.

CÁCH THÊM MODULE MỚI: import router của module rồi thêm một dòng
api_router.include_router(...) — không sửa gì khác.
"""

from fastapi import APIRouter

api_router = APIRouter()

# Các module sẽ được đăng ký ở đây khi hoàn thành router của mình:
# from app.modules.auth.router import router as auth_router
# api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
