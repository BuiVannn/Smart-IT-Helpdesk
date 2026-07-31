"""Fixture dùng chung cho toàn bộ test.

Nguyên tắc: MỖI TEST TỰ DỰNG DỮ LIỆU CỦA MÌNH, không phụ thuộc thứ tự chạy,
không phụ thuộc dữ liệu do test khác để lại. Test phụ thuộc thứ tự sẽ hỏng
ngẫu nhiên trong CI và làm cả nhóm mất niềm tin vào bộ test.

★ CÁCH DÙNG CHO CẢ NHÓM
    def test_gi_do(auth_client, db):          # đã đăng nhập sẵn vai EMPLOYEE
        r = auth_client.post("/api/v1/tickets", json={...})
        assert r.status_code == 201

    def test_quyen_admin(client, make_user, login):
        admin = make_user(role=UserRole.ADMIN)
        c = login(admin)
        assert c.get("/api/v1/users/me").json()["role"] == "ADMIN"

Mọi thay đổi trong một test đều bị ROLLBACK khi test kết thúc — kể cả khi
service đã gọi `commit()`. Xem chú thích ở fixture `db`.
"""

import os

os.environ.setdefault("JWT_SECRET", "test-secret-key-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://helpdesk:helpdesk@localhost:5432/test")
os.environ.setdefault("LLM_PROVIDER", "fake")

from collections.abc import Callable, Iterator  # noqa: E402
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.ai.embedding.fake_embedding import FakeEmbeddingClient  # noqa: E402
from app.ai.llm.fake_client import FakeLlmClient  # noqa: E402
from app.core.rate_limit import MemoryAttemptStore  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import all_models  # noqa: E402,F401  — nạp đủ mapper cho khoá ngoại
from app.db.session import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.users.constants import UserRole  # noqa: E402
from app.modules.users.models import User  # noqa: E402

DEFAULT_TEST_PASSWORD = "MatKhau123"


# ─────────── Fixture cần DB ───────────

@pytest.fixture(scope="session")
def db_connection():
    """Một kết nối dùng chung cho cả phiên test. Bỏ qua toàn bộ nếu không có DB."""
    try:
        connection = engine.connect()
        connection.execute(select(1))
        # Chính lệnh kiểm tra ở trên đã tự mở transaction (autobegin). Không
        # đóng lại thì fixture `db` gọi begin() sẽ nổ "already initialized".
        connection.rollback()
    except Exception as exc:
        pytest.skip(f"Không kết nối được database: {type(exc).__name__}")
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def db(db_connection) -> Iterator[Session]:
    """Session trong một transaction bị ROLLBACK sau mỗi test.

    ★ `join_transaction_mode="create_savepoint"` là mấu chốt: nếu không có nó,
    lời gọi `commit()` bên trong service sẽ ghi thật xuống database và test
    này để lại rác cho test sau. Với savepoint, `commit()` của service vẫn
    chạy đúng như thật (dữ liệu nhìn thấy được trong cùng transaction) nhưng
    transaction ngoài cùng bị rollback ở đây, nên database sạch trơn.
    """
    outer = db_connection.begin()
    factory = sessionmaker(
        bind=db_connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = factory()
    try:
        yield session
    finally:
        session.close()
        outer.rollback()


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    """Xoá bộ đếm đăng nhập giữa các test.

    Bộ đếm sống ở cấp tiến trình, nên test "sai mật khẩu 5 lần" sẽ làm test
    đăng nhập chạy sau nó nhận 429 — hỏng ngẫu nhiên theo thứ tự chạy.
    """
    from app.modules.auth import router as auth_router_module

    auth_router_module._login_limiter.store = MemoryAttemptStore()
    yield


@pytest.fixture
def client(db) -> Iterator[TestClient]:
    """TestClient dùng CHUNG session với fixture `db`.

    Dùng chung là bắt buộc: nếu endpoint mở session riêng, nó sẽ không thấy
    dữ liệu test vừa tạo (còn nằm trong transaction chưa commit).
    """
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def make_user(db) -> Callable[..., User]:
    """Tạo user thật trong DB. Email luôn duy nhất để test chạy song song được."""

    def _make(
        *,
        role: UserRole = UserRole.EMPLOYEE,
        password: str = DEFAULT_TEST_PASSWORD,
        email: str | None = None,
        is_active: bool = True,
        full_name: str = "Người Dùng Kiểm Thử",
    ) -> User:
        user = User(
            email=email or f"test-{uuid4().hex[:12]}@company.com",
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.flush()
        return user

    return _make


@pytest.fixture
def ticket_category(db):
    """Loại sự cố dùng chung. Tái sử dụng bản ghi seed nếu đã có — `slug` là
    UNIQUE nên chèn thêm sẽ vỡ ràng buộc."""
    from app.modules.tickets.constants import TicketPriority
    from app.modules.tickets.models import TicketCategory

    category = db.execute(
        select(TicketCategory).where(TicketCategory.slug == "network")
    ).scalar_one_or_none()
    if category is None:
        category = TicketCategory(
            slug="network", name="Mạng & Internet", default_priority=TicketPriority.HIGH
        )
        db.add(category)
        db.flush()
    return category


@pytest.fixture
def sla_policies(db):
    """Bảo đảm có chính sách SLA, nếu không ticket sẽ không có hạn xử lý."""
    from app.modules.tickets.constants import TicketPriority
    from app.modules.tickets.models import SlaPolicy

    defaults = {
        TicketPriority.URGENT: (15, 240),
        TicketPriority.HIGH: (60, 480),
        TicketPriority.MEDIUM: (240, 1440),
        TicketPriority.LOW: (480, 2400),
    }
    for priority, (first, resolution) in defaults.items():
        exists = db.execute(
            select(SlaPolicy).where(SlaPolicy.priority == priority)
        ).scalar_one_or_none()
        if exists is None:
            db.add(SlaPolicy(
                priority=priority,
                first_response_minutes=first,
                resolution_minutes=resolution,
            ))
    db.flush()


@pytest.fixture
def login(client) -> Callable[..., TestClient]:
    """Đăng nhập và gắn sẵn Authorization vào client. Trả về chính client đó."""

    def _login(user: User, password: str = DEFAULT_TEST_PASSWORD) -> TestClient:
        response = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": password}
        )
        assert response.status_code == 200, f"đăng nhập hỏng: {response.text}"
        token = response.json()["accessToken"]
        client.headers["Authorization"] = f"Bearer {token}"
        return client

    return _login


@pytest.fixture
def auth_client(client, make_user, login) -> TestClient:
    """Client đã đăng nhập sẵn vai EMPLOYEE — dùng cho phần lớn test."""
    return login(make_user())


# ─────────── Fixture không cần DB ───────────

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
