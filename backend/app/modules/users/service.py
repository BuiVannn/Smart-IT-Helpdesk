"""UserService — hiện chỉ có hồ sơ cá nhân.

★ PHẦN CÒN LẠI ĐỂ NGƯỜI KHÁC LÀM (đừng viết hộ, sẽ đụng nhau):
- Admin CRUD người dùng, khoá/mở khoá tài khoản (US-07)
- `GET /users/agents` kèm tải hiện tại — cần cho gợi ý người xử lý (US-20)
"""

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UpdateProfileRequest

logger = get_logger(__name__)


class UserService:
    def __init__(self, session: Session) -> None:
        self.db = session
        self.users = UserRepository(session)

    def update_profile(self, user: User, data: UpdateProfileRequest) -> User:
        """Cập nhật hồ sơ của CHÍNH người đang đăng nhập.

        `exclude_unset` chứ không phải `exclude_none`: client gửi
        `{"phone": null}` là CỐ Ý xoá số điện thoại, còn không gửi field nào
        mới là "giữ nguyên". Dùng nhầm thì người dùng không bao giờ xoá được
        dữ liệu đã nhập.
        """
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(user, field, value)

        self.db.commit()
        self.db.refresh(user)

        logger.info("cập nhật hồ sơ", extra={"extra_fields": {
            "user_id": str(user.id), "fields": sorted(changes)
        }})
        return user
