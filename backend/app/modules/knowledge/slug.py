"""Sinh slug từ tiêu đề tiếng Việt — LỚP THUẦN, không I/O.

Trước đây hàm này nằm trong `scripts/seed_kb.py`. Chuyển vào app để API tạo
bài viết và script nạp dữ liệu dùng CHUNG một cách sinh slug: hai bản sao sẽ
trôi khác nhau, và khi đó cùng một tiêu đề cho ra hai slug khác nhau tuỳ theo
bài được tạo bằng đường nào.
"""

import re
import unicodedata
from collections.abc import Callable

MAX_SLUG_LENGTH = 200


def slugify(text: str) -> str:
    """Chuyển tiêu đề tiếng Việt thành slug không dấu.

    "Hướng dẫn đổi mật khẩu" → "huong-dan-doi-mat-khau"
    """
    normalized = unicodedata.normalize("NFD", text)
    # Bỏ dấu thanh và dấu phụ (category Mn = Mark, nonspacing)
    ascii_text = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    # đ/Đ không phải là "d + dấu" nên NFD không tách được, phải thay tay
    ascii_text = ascii_text.replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:MAX_SLUG_LENGTH]


def unique_slug(base: str, exists: Callable[[str], bool]) -> str:
    """Thêm hậu tố -2, -3… cho tới khi slug chưa tồn tại.

    Hai bài "Hướng dẫn cài VPN" viết cách nhau nửa năm là chuyện bình thường;
    để lỗi trùng khoá bắn lên mặt người soạn thảo thì không.
    """
    slug = slugify(base) or "bai-viet"
    if not exists(slug):
        return slug

    for suffix in range(2, 1000):
        candidate = f"{slug}-{suffix}"
        if not exists(candidate):
            return candidate
    raise ValueError(f"Không sinh được slug duy nhất từ {base!r}")
