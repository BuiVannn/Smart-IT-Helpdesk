"""Unit test cho AssigneeScorer — gợi ý người xử lý (US-20).

Thuật toán này cố tình KHÔNG dùng LLM: nó là phép tính điểm trên dữ liệu có
cấu trúc, nên phải kiểm thử được đến từng ca biên. Toàn bộ file chạy không
cần database.
"""

from uuid import UUID, uuid4

import pytest

from app.modules.tickets.suggestions import (
    MAX_SKILL_LEVEL,
    OFF_DUTY_FACTOR,
    AgentSnapshot,
    AssigneeScorer,
)

W_SKILL, W_LOAD, W_DUTY = 0.5, 0.35, 0.15
MAX_LOAD = 20


@pytest.fixture
def scorer() -> AssigneeScorer:
    return AssigneeScorer(
        w_skill=W_SKILL, w_load=W_LOAD, w_duty=W_DUTY, max_load=MAX_LOAD
    )


def snapshot(
    *,
    name: str = "Nguyễn Văn A",
    skill: int = 0,
    open_tickets: int = 0,
    load: int = 0,
    agent_id: UUID | None = None,
) -> AgentSnapshot:
    return AgentSnapshot(
        agent_id=agent_id or uuid4(),
        full_name=name,
        email=f"{name}@company.com",
        skill_level=skill,
        open_tickets=open_tickets,
        weighted_load=load,
        last_login_at=None,
    )


class TestChamDiem:
    def test_agent_ly_tuong_dat_diem_toi_da(self, scorer):
        """Kỹ năng mức 3, không tải, đang trực ⇒ 1.0."""
        assert scorer.score(snapshot(skill=3), on_duty=True) == pytest.approx(1.0)

    def test_agent_te_nhat_chi_con_diem_ngoai_ca(self, scorer):
        """Không kỹ năng, quá tải, ngoài ca ⇒ chỉ còn W_DUTY × 0.3."""
        score = scorer.score(snapshot(skill=0, load=MAX_LOAD), on_duty=False)
        assert score == pytest.approx(W_DUTY * OFF_DUTY_FACTOR)

    def test_tai_vuot_tran_khong_lam_diem_am(self, scorer):
        """★ Agent gánh 100 điểm tải vẫn phải có điểm >= 0.

        Không kẹp trần, thành phần tải thành số âm lớn và Agent quá tải sẽ bị
        xếp sau cả Agent đã nghỉ việc — tệ hơn nữa, điểm âm làm thứ tự đảo
        lộn theo cách không ai đoán được.
        """
        score = scorer.score(snapshot(skill=3, load=100), on_duty=True)
        assert score >= 0
        assert score == pytest.approx(W_SKILL + W_DUTY)

    def test_ky_nang_vuot_muc_3_bi_kep_tran(self, scorer):
        """Dữ liệu bẩn (level = 9) không được cho điểm cao hơn mức 3 hợp lệ."""
        assert scorer.score(snapshot(skill=99), on_duty=True) == pytest.approx(
            scorer.score(snapshot(skill=MAX_SKILL_LEVEL), on_duty=True)
        )

    def test_ky_nang_quan_trong_hon_tai(self, scorer):
        """Trọng số mặc định: chuyên môn (0.5) nặng hơn tải (0.35)."""
        chuyen_gia_ban = scorer.score(snapshot(skill=3, load=MAX_LOAD), on_duty=True)
        nguoi_moi_ranh = scorer.score(snapshot(skill=0, load=0), on_duty=True)

        assert chuyen_gia_ban > nguoi_moi_ranh

    def test_ngoai_ca_bi_tru_diem_nhung_khong_bi_loai(self, scorer):
        trong_ca = scorer.score(snapshot(skill=2), on_duty=True)
        ngoai_ca = scorer.score(snapshot(skill=2), on_duty=False)

        assert ngoai_ca < trong_ca
        assert ngoai_ca > 0   # vẫn được gợi ý, chỉ xếp sau


class TestXepHang:
    def test_lay_dung_top_n(self, scorer):
        agents = [snapshot(name=f"Agent {i}", skill=i % 4) for i in range(10)]

        top = scorer.rank(agents, on_duty_of={}, category_name="Mạng", top_n=3)

        assert len(top) == 3

    def test_sap_xep_giam_dan_theo_diem(self, scorer):
        gioi = snapshot(name="Giỏi", skill=3)
        trung_binh = snapshot(name="Trung bình", skill=2)
        kem = snapshot(name="Kém", skill=0)

        top = scorer.rank(
            [kem, gioi, trung_binh],
            on_duty_of={a.agent_id: True for a in (kem, gioi, trung_binh)},
            category_name="Mạng",
        )

        assert [a.full_name for a in top] == ["Giỏi", "Trung bình", "Kém"]

    def test_thu_tu_on_dinh_khi_bang_diem(self, scorer):
        """Hai lần gọi liên tiếp phải ra cùng thứ tự.

        Thứ tự nhảy lung tung giữa hai lần tải trang là lỗi giao diện mà
        không ai truy được nguyên nhân.
        """
        agents = [snapshot(name=name, skill=1) for name in ("Cường", "An", "Bình")]
        on_duty = {a.agent_id: True for a in agents}

        lan_1 = scorer.rank(agents, on_duty_of=on_duty, category_name="Mạng", top_n=3)
        lan_2 = scorer.rank(
            list(reversed(agents)), on_duty_of=on_duty, category_name="Mạng", top_n=3
        )

        assert [a.full_name for a in lan_1] == [a.full_name for a in lan_2]

    def test_agent_it_tai_hon_thang_khi_bang_diem_ky_nang(self, scorer):
        ranh = snapshot(name="Rảnh", skill=2, open_tickets=1, load=2)
        ban = snapshot(name="Bận", skill=2, open_tickets=6, load=14)

        top = scorer.rank(
            [ban, ranh],
            on_duty_of={ranh.agent_id: True, ban.agent_id: True},
            category_name="Mạng",
        )

        assert top[0].full_name == "Rảnh"

    def test_danh_sach_rong(self, scorer):
        assert scorer.rank([], on_duty_of={}, category_name="Mạng") == []

    def test_thieu_thong_tin_ca_truc_thi_coi_nhu_ngoai_ca(self, scorer):
        """`on_duty_of` không có khoá của Agent ⇒ mặc định ngoài ca, không nổ."""
        agent = snapshot(skill=3)

        top = scorer.rank([agent], on_duty_of={}, category_name="Mạng")

        assert top[0].on_duty is False


class TestLyDoDocDuoc:
    """AC của US-20: "trả về top 3 kèm điểm VÀ lý do có thể đọc được"."""

    def test_neu_ro_chuyen_mon_tai_va_ca_truc(self, scorer):
        agent = snapshot(skill=3, open_tickets=2, load=5)

        top = scorer.rank(
            [agent], on_duty_of={agent.agent_id: True}, category_name="Mạng & Internet"
        )

        reason = top[0].reason
        assert "Mạng & Internet" in reason
        assert "mức 3" in reason
        assert "2 ticket" in reason
        assert "đang trong ca trực" in reason

    def test_agent_chua_co_chuyen_mon_van_noi_ro(self, scorer):
        agent = snapshot(skill=0)

        top = scorer.rank(
            [agent], on_duty_of={agent.agent_id: False}, category_name="Bảo mật"
        )

        assert "chưa ghi nhận chuyên môn" in top[0].reason.lower()
        assert "ngoài ca trực" in top[0].reason

    def test_agent_rong_viec(self, scorer):
        agent = snapshot(skill=1, open_tickets=0, load=0)

        top = scorer.rank([agent], on_duty_of={}, category_name="Mạng")

        assert "đang rảnh" in top[0].reason

    def test_ticket_chua_phan_loai_thi_khong_noi_ve_chuyen_mon(self, scorer):
        agent = snapshot(skill=0)

        top = scorer.rank([agent], on_duty_of={}, category_name=None)

        assert "chưa phân loại" in top[0].reason.lower()
