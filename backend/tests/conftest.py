"""Fixture dùng chung cho toàn bộ test.

Nguyên tắc: MỖI TEST TỰ DỰNG DỮ LIỆU CỦA MÌNH, không phụ thuộc thứ tự chạy,
không phụ thuộc dữ liệu do test khác để lại. Test phụ thuộc thứ tự sẽ hỏng
ngẫu nhiên trong CI và làm cả nhóm mất niềm tin vào bộ test.
"""

import os

os.environ.setdefault("JWT_SECRET", "test-secret-key-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://helpdesk:helpdesk@localhost:5432/test")
os.environ.setdefault("LLM_PROVIDER", "fake")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.ai.embedding.fake_embedding import FakeEmbeddingClient  # noqa: E402
from app.ai.llm.fake_client import FakeLlmClient  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.users.constants import UserRole  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fake_llm() -> FakeLlmClient:
    """LLM giả — KHÔNG cần API key, KHÔNG tốn tiền."""
    return FakeLlmClient()


@pytest.fixture
def fake_embedding() -> FakeEmbeddingClient:
    return FakeEmbeddingClient()


# ─────────── User giả cho unit test (không chạm DB) ───────────

class FakeUser:
    """Đối tượng user tối thiểu cho unit test các lớp thuần."""

    def __init__(self, role: UserRole, user_id: str = "00000000-0000-0000-0000-000000000001"):
        self.id = user_id
        self.role = role
        self.is_active = True
        self.email = f"{role.lower()}@test.local"
        self.full_name = f"Test {role}"


@pytest.fixture
def employee() -> FakeUser:
    return FakeUser(UserRole.EMPLOYEE, "00000000-0000-0000-0000-000000000001")


@pytest.fixture
def agent() -> FakeUser:
    return FakeUser(UserRole.IT_AGENT, "00000000-0000-0000-0000-000000000002")


@pytest.fixture
def admin() -> FakeUser:
    return FakeUser(UserRole.ADMIN, "00000000-0000-0000-0000-000000000003")


# ─────────── Fixture cần DB (dùng cho integration test) ───────────
# TODO(T10): thêm fixture db_session dùng transaction + rollback sau mỗi test.
