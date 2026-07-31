"""Gom toàn bộ router của các module.

CÁCH THÊM MODULE MỚI: import router của module rồi thêm một dòng
api_router.include_router(...) — không sửa gì khác.
"""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])

# Các module còn lại đăng ký ở đây khi router của mình xong.
# Mỗi người CHỈ thêm dòng của mình, không sửa dòng người khác — như vậy file
# này gần như không bao giờ bị xung đột khi merge.
#
# from app.modules.tickets.router import router as tickets_router
# api_router.include_router(tickets_router, prefix="/tickets", tags=["tickets"])
#
# from app.modules.knowledge.router import router as kb_router
# api_router.include_router(kb_router, prefix="/kb", tags=["knowledge"])
#
# from app.modules.chatbot.router import router as chat_router
# api_router.include_router(chat_router, prefix="/chat", tags=["chatbot"])
#
# from app.modules.notifications.router import router as notif_router
# api_router.include_router(notif_router, prefix="/notifications", tags=["notifications"])
#
# from app.modules.reports.router import router as reports_router
# api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
