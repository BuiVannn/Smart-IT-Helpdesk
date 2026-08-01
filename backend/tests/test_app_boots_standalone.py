"""Kiểm tra ứng dụng khởi động ĐƯỢC KHI KHÔNG CÓ conftest của test.

★ VÌ SAO CẦN CHẠY TRONG TIẾN TRÌNH RIÊNG
`tests/conftest.py` nạp `app.db.all_models`, nên trong bộ test mọi model luôn
có mặt và mọi quan hệ khai báo bằng chuỗi đều phân giải được. Production thì
không có conftest. Nếu một entry point quên nạp all_models, ứng dụng vẫn khởi
động bình thường rồi vỡ ở REQUEST ĐẦU TIÊN — kiểu lỗi chỉ lộ ra khi demo.

Lỗi này đã xảy ra thật khi thêm quan hệ ChatCitation.article -> "KbArticle".
Test dưới đây tồn tại để nó không tái diễn.
"""

import subprocess
import sys
import textwrap

SCRIPT = textwrap.dedent("""
    import os
    os.environ.setdefault("JWT_SECRET", "test-secret-key-at-least-32-characters-long")
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://x:x@localhost:5432/x")
    os.environ.setdefault("LLM_PROVIDER", "fake")

    # CHỈ nạp entry point, không nạp gì thêm — giống hệt uvicorn/celery làm
    import app.main  # noqa: F401
    from sqlalchemy.orm import configure_mappers

    configure_mappers()
    print("OK")
""")


def test_khoi_dong_duoc_ma_khong_can_conftest():
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, (
        "Ứng dụng KHÔNG khởi động được ngoài môi trường test.\n" f"stderr:\n{result.stderr[-2000:]}"
    )
    assert "OK" in result.stdout
