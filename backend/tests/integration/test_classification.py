"""Integration test cho TicketClassifier — F3, US-19.

Đây là chỗ kiểm chứng lời hứa quan trọng nhất của F3: **AI hỏng thì ticket
vẫn dùng được bình thường** (BR-15). Mỗi nhánh lỗi đều có một test riêng, vì
đúng những nhánh đó mới là thứ chạy vào lúc demo gặp sự cố.

Toàn bộ file dùng LLM giả — không cần API key, không tốn tiền, chạy trong CI.
"""

import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.ai.llm.base import LlmResponse
from app.ai.resilience import RetryConfig
from app.modules.tickets.classifier import (
    ClassificationSource,
    RuleBasedClassifier,
    TicketClassifier,
)
from app.modules.tickets.constants import (
    ActorType,
    AiStatus,
    EventType,
    TicketPriority,
)
from app.modules.tickets.models import AiClassification, Ticket, TicketCategory, TicketEvent
from app.modules.tickets.schemas import CreateTicketRequest
from app.modules.tickets.service import TicketService
from app.modules.users.constants import UserRole

pytestmark = pytest.mark.asyncio

WIFI_TICKET = {
    "title": "Không kết nối được WiFi công ty tại tầng 5",
    "description": "Từ sáng nay máy tôi không thấy mạng CTY-WIFI, đã thử khởi động lại.",
}
# Cố tình không chứa từ khoá nào trong bảng luật — dùng để ép nhánh FAILED.
VAGUE_TICKET = {
    "title": "Nhờ hỗ trợ giúp tôi việc này",
    "description": "Có chút vướng mắc mong bộ phận liên quan xem giúp sớm ạ.",
}


class ScriptedLlm:
    """LLM giả trả về đúng payload đặt trước.

    `FakeLlmClient` đoán theo từ khoá nên không ép được confidence cụ thể;
    ở đây cần điều khiển chính xác từng nhánh quyết định.
    """

    def __init__(self, payload: dict | None = None, *, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.calls = 0

    @property
    def model_name(self) -> str:
        return "fake-model"

    async def complete(self, *, system, user, schema=None, max_tokens=1000, temperature=0.0):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return LlmResponse(
            content=json.dumps(self.payload, ensure_ascii=False),
            model="fake-model",
            prompt_tokens=120,
            completion_tokens=25,
            latency_ms=7,
            parsed=self.payload,
        )

    async def stream(self, *, system, user, max_tokens=800):  # pragma: no cover
        raise AssertionError("Phân loại không bao giờ được dùng stream")
        yield ""


NO_WAIT = RetryConfig(max_attempts=3, base_delay=0.0, multiplier=1.0, jitter=0.0)


@pytest.fixture
def categories(db) -> dict[str, TicketCategory]:
    """Bảo đảm có đủ loại sự cố. Dùng lại bản ghi seed vì `slug` là UNIQUE."""
    wanted = [
        ("network", "Mạng & Internet", TicketPriority.HIGH),
        ("hardware", "Phần cứng & Thiết bị", TicketPriority.MEDIUM),
        ("security", "Bảo mật", TicketPriority.URGENT),
        ("other", "Khác", TicketPriority.LOW),
    ]
    result = {}
    for slug, name, priority in wanted:
        category = db.execute(
            select(TicketCategory).where(TicketCategory.slug == slug)
        ).scalar_one_or_none()
        if category is None:
            category = TicketCategory(slug=slug, name=name, default_priority=priority)
            db.add(category)
            db.flush()
        result[slug] = category
    return result


@pytest.fixture
def requester(make_user):
    return make_user(role=UserRole.EMPLOYEE)


@pytest.fixture
def make_ticket(db, requester, sla_policies, categories):
    def _make(**overrides) -> Ticket:
        payload = {**WIFI_TICKET, **overrides}
        data = CreateTicketRequest.model_validate(payload)
        return TicketService(db).create(requester, data)

    return _make


def build(db, llm, **kwargs) -> TicketClassifier:
    return TicketClassifier(db, llm, retry=NO_WAIT, **kwargs)


def latest_record(db, ticket_id) -> AiClassification | None:
    return db.execute(
        select(AiClassification)
        .where(AiClassification.ticket_id == ticket_id)
        .order_by(AiClassification.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


class TestApDungKetQua:
    """Tầng 1 — LLM trả lời tự tin, ticket chưa có loại sự cố."""

    async def test_gan_category_va_priority(self, db, make_ticket, categories):
        ticket = make_ticket()
        assert ticket.category_id is None
        assert ticket.ai_status == AiStatus.PENDING

        llm = ScriptedLlm(
            {
                "category_slug": "network",
                "priority": "HIGH",
                "confidence": 0.93,
                "reasoning": "Mô tả nêu rõ không vào được WiFi",
            }
        )
        outcome = await build(db, llm).classify(ticket.id)

        assert outcome.ai_status == AiStatus.APPLIED
        db.refresh(ticket)
        assert ticket.category_id == categories["network"].id
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.ai_status == AiStatus.APPLIED

    async def test_ghi_ban_ghi_ai_classifications(self, db, make_ticket):
        ticket = make_ticket()
        llm = ScriptedLlm(
            {
                "category_slug": "network",
                "priority": "HIGH",
                "confidence": 0.93,
                "reasoning": "Rõ ràng là sự cố mạng",
            }
        )

        await build(db, llm).classify(ticket.id)

        record = latest_record(db, ticket.id)
        assert record is not None
        assert record.was_applied is True
        assert record.confidence == pytest.approx(0.93)
        assert record.prompt_tokens == 120
        assert record.completion_tokens == 25
        assert record.model_name == "fake-model"
        assert record.error_message is None

    async def test_ghi_su_kien_voi_actor_type_ai(self, db, make_ticket):
        """AC US-17: hành động của AI phải phân biệt được với hành động của người."""
        ticket = make_ticket()
        llm = ScriptedLlm(
            {
                "category_slug": "network",
                "priority": "HIGH",
                "confidence": 0.9,
                "reasoning": "Sự cố mạng",
            }
        )

        await build(db, llm).classify(ticket.id)

        events = (
            db.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket.id,
                    TicketEvent.event_type == EventType.AI_CLASSIFIED,
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
        assert events[0].actor_type == ActorType.AI
        assert events[0].actor_id is None
        assert events[0].event_metadata["confidence"] == pytest.approx(0.9)

    async def test_tinh_lai_han_sla_khi_doi_muc_uu_tien(self, db, make_ticket):
        """★ Đổi priority mà không tính lại SLA thì ticket URGENT giữ hạn của MEDIUM.

        Hậu quả im lặng: mọi cảnh báo SLA cho ticket được AI nâng mức đều
        muộn, và không có gì trên giao diện cho thấy điều đó.
        """
        ticket = make_ticket()
        han_cu = ticket.sla_resolution_due_at
        assert ticket.priority == TicketPriority.MEDIUM

        llm = ScriptedLlm(
            {
                "category_slug": "security",
                "priority": "URGENT",
                "confidence": 0.97,
                "reasoning": "Dấu hiệu sự cố bảo mật",
            }
        )
        await build(db, llm).classify(ticket.id)

        db.refresh(ticket)
        assert ticket.priority == TicketPriority.URGENT
        assert ticket.sla_resolution_due_at < han_cu

    async def test_tang_version_de_khoa_lac_quan_khong_bi_qua_mat(self, db, make_ticket):
        ticket = make_ticket()
        version_cu = ticket.version
        llm = ScriptedLlm(
            {
                "category_slug": "network",
                "priority": "HIGH",
                "confidence": 0.9,
                "reasoning": "Sự cố mạng",
            }
        )

        await build(db, llm).classify(ticket.id)

        db.refresh(ticket)
        assert ticket.version == version_cu + 1


class TestKhongGhiDePhanLoaiCuaNguoi:
    """BR-13 — AI không bao giờ ghi đè lựa chọn của con người."""

    async def test_giu_nguyen_category_nguoi_dung_chon(self, db, make_ticket, categories):
        ticket = make_ticket(categoryId=str(categories["hardware"].id))
        assert ticket.category_id == categories["hardware"].id

        llm = ScriptedLlm(
            {
                "category_slug": "network",
                "priority": "URGENT",
                "confidence": 0.99,
                "reasoning": "AI rất tự tin nhưng vẫn không được đè",
            }
        )
        outcome = await build(db, llm).classify(ticket.id)

        assert outcome.ai_status == AiStatus.SKIPPED
        db.refresh(ticket)
        assert ticket.category_id == categories["hardware"].id
        assert ticket.ai_status == AiStatus.SKIPPED

    async def test_van_ghi_lai_goi_y_de_so_sanh(self, db, make_ticket, categories):
        """AC US-19: "AI vẫn chạy để ghi nhận kết quả so sánh"."""
        ticket = make_ticket(categoryId=str(categories["hardware"].id))
        llm = ScriptedLlm(
            {
                "category_slug": "network",
                "priority": "HIGH",
                "confidence": 0.88,
                "reasoning": "Theo AI thì đây là sự cố mạng",
            }
        )

        await build(db, llm).classify(ticket.id)

        record = latest_record(db, ticket.id)
        assert record is not None
        assert record.was_applied is False
        assert record.suggested_category_id == categories["network"].id

    async def test_giu_nguyen_MUC_UU_TIEN_nguoi_dat_bang_tay(
        self, db, make_ticket, categories, make_user
    ):
        """★ "Phân loại" gồm CẢ mức ưu tiên, không riêng loại sự cố.

        Kịch bản thật đã tái hiện được: nhân viên tạo ticket không chọn loại;
        trong lúc LLM còn đang chạy, Agent xem qua và tự đặt URGENT vì sự cố
        gấp; AI trả về MEDIUM và GHI ĐÈ — hạ mức ưu tiên của con người xuống,
        đồng thời nới hạn SLA thêm hai ngày. Nhật ký ghi đúng hai dòng liên
        tiếp: `PRIORITY_CHANGED USER MEDIUM→URGENT` rồi `AI URGENT→MEDIUM`.

        Bản trước chỉ kiểm `category_id is not None` nên nhánh này lọt.
        """
        from app.modules.tickets.constants import TicketPriority
        from app.modules.tickets.schemas import UpdateTicketRequest
        from app.modules.tickets.service import TicketService
        from app.modules.users.constants import UserRole

        # Agent THẬT trong database: `ticket_events.actor_id` có khoá ngoại
        # sang `users`, nên fixture `agent` giả (không nằm trong DB) sẽ làm vỡ
        # ràng buộc — và đó là ràng buộc đúng, nhật ký phải truy được ra người.
        agent = make_user(role=UserRole.IT_AGENT)

        ticket = make_ticket()  # không chọn loại ⇒ AI được phép phân loại
        assert ticket.category_id is None

        # Agent tự nâng mức ưu tiên trong lúc AI còn đang chạy
        TicketService(db).update(
            agent,
            ticket.id,
            UpdateTicketRequest(priority=TicketPriority.URGENT, version=ticket.version),
        )
        db.refresh(ticket)
        assert ticket.priority == TicketPriority.URGENT
        han_do_nguoi_dat = ticket.sla_resolution_due_at

        llm = ScriptedLlm(
            {
                "category_slug": "network",
                "priority": "MEDIUM",
                "confidence": 0.95,
                "reasoning": "AI cho rằng đây chỉ là sự cố mạng thường",
            }
        )
        outcome = await build(db, llm).classify(ticket.id)

        assert outcome.ai_status == AiStatus.SKIPPED
        db.refresh(ticket)
        assert ticket.priority == TicketPriority.URGENT, "AI đã ghi đè quyết định của con người"
        assert ticket.sla_resolution_due_at == han_do_nguoi_dat, "hạn SLA bị nới ra"


class TestDoTinCayThap:
    """Tầng 2 — BR-14."""

    async def test_khong_ap_dung_khi_duoi_nguong(self, db, make_ticket):
        ticket = make_ticket()
        llm = ScriptedLlm(
            {
                "category_slug": "network",
                "priority": "HIGH",
                "confidence": 0.45,
                "reasoning": "Mô tả mơ hồ, có thể là mạng",
            }
        )

        outcome = await build(db, llm).classify(ticket.id)

        assert outcome.ai_status == AiStatus.LOW_CONFIDENCE
        db.refresh(ticket)
        assert ticket.category_id is None
        assert ticket.ai_status == AiStatus.LOW_CONFIDENCE

    async def test_van_luu_goi_y_cho_agent_tham_khao(self, db, make_ticket, categories):
        ticket = make_ticket()
        llm = ScriptedLlm(
            {
                "category_slug": "network",
                "priority": "HIGH",
                "confidence": 0.45,
                "reasoning": "Có thể là mạng",
            }
        )

        await build(db, llm).classify(ticket.id)

        record = latest_record(db, ticket.id)
        assert record is not None
        assert record.was_applied is False
        assert record.suggested_category_id == categories["network"].id
        assert record.confidence == pytest.approx(0.45)

    async def test_nguong_doc_tu_cau_hinh_khong_hardcode(self, db, make_ticket):
        """AC US-19: "Ngưỡng này để trong config, không hardcode"."""
        ticket = make_ticket()
        llm = ScriptedLlm(
            {
                "category_slug": "network",
                "priority": "HIGH",
                "confidence": 0.45,
                "reasoning": "Mơ hồ",
            }
        )

        outcome = await build(db, llm, confidence_threshold=0.3).classify(ticket.id)

        assert outcome.ai_status == AiStatus.APPLIED


class TestLlmHongKhongLamHongTicket:
    """Tầng 3, 4, 5 — BR-15, lời hứa quan trọng nhất của F3."""

    async def test_lui_ve_doi_chieu_tu_khoa_khi_llm_chet(self, db, make_ticket, categories):
        ticket = make_ticket()
        llm = ScriptedLlm(error=ConnectionError("provider sập"))

        outcome = await build(db, llm).classify(ticket.id)

        assert outcome.suggestion is not None
        assert outcome.suggestion.source == ClassificationSource.RULES
        assert outcome.suggestion.category_slug == "network"
        # Đường dự phòng chỉ GỢI Ý, không tự áp dụng
        assert outcome.ai_status == AiStatus.LOW_CONFIDENCE
        db.refresh(ticket)
        assert ticket.category_id is None

    async def test_da_thu_lai_du_so_lan_truoc_khi_bo_cuoc(self, db, make_ticket):
        ticket = make_ticket()
        llm = ScriptedLlm(error=TimeoutError("hết giờ"))

        await build(db, llm).classify(ticket.id)

        assert llm.calls == NO_WAIT.max_attempts

    async def test_ghi_lai_loi_de_us22_dem_duoc(self, db, make_ticket):
        ticket = make_ticket()
        llm = ScriptedLlm(error=ConnectionError("provider sập"))

        await build(db, llm).classify(ticket.id)

        record = latest_record(db, ticket.id)
        assert record is not None
        assert record.error_message is not None
        assert "provider sập" in record.error_message

    async def test_failed_khi_khong_luat_nao_khop(self, db, make_ticket):
        ticket = make_ticket(**VAGUE_TICKET)
        llm = ScriptedLlm(error=ConnectionError("provider sập"))

        outcome = await build(db, llm).classify(ticket.id)

        assert outcome.ai_status == AiStatus.FAILED
        db.refresh(ticket)
        assert ticket.ai_status == AiStatus.FAILED
        # ★ Ticket vẫn dùng được bình thường, chỉ là chưa được phân loại
        assert ticket.title == VAGUE_TICKET["title"]
        assert ticket.category_id is None

    async def test_khong_nem_loi_ra_ngoai(self, db, make_ticket):
        """Task Celery không được chết vì LLM chết — nếu không, Celery sẽ giao
        lại task và vòng lặp lỗi tiếp tục đốt tiền."""
        ticket = make_ticket(**VAGUE_TICKET)
        llm = ScriptedLlm(error=RuntimeError("lỗi lạ chưa từng gặp"))

        outcome = await build(db, llm).classify(ticket.id)

        assert outcome.ai_status == AiStatus.FAILED


class TestKhongTinDauRaCuaLlm:
    """docs/design/07 §2.3 — kiểm chứng lại mọi thứ LLM trả về."""

    async def test_slug_khong_ton_tai_bi_tu_choi(self, db, make_ticket):
        ticket = make_ticket()
        llm = ScriptedLlm(
            {
                "category_slug": "khong-he-ton-tai",
                "priority": "HIGH",
                "confidence": 0.99,
                "reasoning": "Bịa ra một loại sự cố",
            }
        )

        outcome = await build(db, llm).classify(ticket.id)

        db.refresh(ticket)
        # Rơi xuống đường dự phòng, KHÔNG tạo category_id trỏ vào hư không
        assert outcome.suggestion is not None
        assert outcome.suggestion.source == ClassificationSource.RULES
        assert ticket.category_id is None

    @pytest.mark.parametrize(
        "payload",
        [
            {
                "category_slug": "network",
                "priority": "SIÊU_GẤP",
                "confidence": 0.9,
                "reasoning": "mức ưu tiên bịa",
            },
            {
                "category_slug": "network",
                "priority": "HIGH",
                "confidence": 1.7,
                "reasoning": "confidence ngoài khoảng",
            },
            {
                "category_slug": "network",
                "priority": "HIGH",
                "confidence": "cao",
                "reasoning": "confidence không phải số",
            },
            {"category_slug": "network", "priority": "HIGH", "reasoning": "thiếu hẳn confidence"},
        ],
    )
    async def test_du_lieu_di_dang_bi_tu_choi(self, db, make_ticket, payload):
        ticket = make_ticket(**VAGUE_TICKET)
        llm = ScriptedLlm(payload)

        outcome = await build(db, llm).classify(ticket.id)

        assert outcome.ai_status == AiStatus.FAILED
        assert outcome.error is not None

    async def test_reasoning_dai_bi_cat_va_lam_sach(self, db, make_ticket):
        ticket = make_ticket()
        llm = ScriptedLlm(
            {
                "category_slug": "network",
                "priority": "HIGH",
                "confidence": 0.9,
                "reasoning": "x" * 900,
            }
        )

        await build(db, llm).classify(ticket.id)

        record = latest_record(db, ticket.id)
        assert record is not None and record.reasoning is not None
        assert len(record.reasoning) == 300


class TestChayLaiAnToan:
    async def test_bo_qua_ticket_da_phan_loai(self, db, make_ticket):
        """`task_acks_late=True` nghĩa là task ĐƯỢC PHÉP chạy hai lần.

        Không có chốt chặn này, worker chết giữa chừng sẽ khiến ticket bị phân
        loại lại — tốn thêm một lời gọi LLM và ghi đè cả phân loại mà Agent
        vừa sửa tay.
        """
        ticket = make_ticket()
        llm = ScriptedLlm(
            {
                "category_slug": "network",
                "priority": "HIGH",
                "confidence": 0.9,
                "reasoning": "Sự cố mạng",
            }
        )
        classifier = build(db, llm)

        await classifier.classify(ticket.id)
        assert llm.calls == 1

        outcome = await classifier.classify(ticket.id)

        assert llm.calls == 1, "lượt thứ hai không được gọi LLM nữa"
        assert outcome.ai_status == AiStatus.APPLIED
        records = (
            db.execute(select(AiClassification).where(AiClassification.ticket_id == ticket.id))
            .scalars()
            .all()
        )
        assert len(records) == 1

    async def test_ticket_khong_ton_tai_khong_lam_no_worker(self, db):
        llm = ScriptedLlm({})

        outcome = await build(db, llm).classify(uuid4())

        assert outcome.ai_status == AiStatus.FAILED
        assert llm.calls == 0


class TestKhongCoLoaiSuCoNaoDangHoatDong:
    async def test_tra_failed_thay_vi_no(self, db, make_ticket, categories):
        ticket = make_ticket()
        # Tắt TẤT CẢ loại sự cố trong DB, không chỉ bốn loại của fixture:
        # dữ liệu seed còn `email`, `software`, `account`, `access`.
        for category in db.execute(select(TicketCategory)).scalars().all():
            category.is_active = False
        db.flush()

        llm = ScriptedLlm({})
        outcome = await build(db, llm).classify(ticket.id)

        assert outcome.ai_status == AiStatus.FAILED
        assert llm.calls == 0

    async def test_luat_khong_gan_vao_category_da_tat(self, db, make_ticket, categories):
        """Admin tắt `network` thì đường dự phòng không được gán vào đó nữa."""
        ticket = make_ticket()
        categories["network"].is_active = False
        db.flush()

        llm = ScriptedLlm(error=ConnectionError("provider sập"))
        outcome = await build(db, llm, rules=RuleBasedClassifier()).classify(ticket.id)

        assert outcome.ai_status == AiStatus.FAILED
        db.refresh(ticket)
        assert ticket.category_id is None
