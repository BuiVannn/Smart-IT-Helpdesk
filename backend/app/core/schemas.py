"""Lớp nền cho MỌI schema Pydantic trong dự án.

★ Đặt ở core để 8 module không mỗi người định nghĩa một kiểu. Nếu mỗi module
tự viết base riêng thì chỉ cần một người quên `extra="forbid"` là chỗ đó âm
thầm nuốt field lạ, và lỗi chính tả của frontend không ai phát hiện ra.
"""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base cho mọi schema ĐẦU VÀO.

    `extra="forbid"`: field lạ bị TỪ CHỐI thay vì bỏ qua. Client gửi
    `fullname` thay vì `fullName` sẽ nhận 422 ngay, thay vì tạo ra một
    người dùng không có tên và không ai biết vì sao.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseModel(BaseModel):
    """Base cho mọi schema ĐẦU RA — đọc thẳng từ ORM, trả về camelCase."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
