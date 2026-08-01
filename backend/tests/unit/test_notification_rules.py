"""Hai quy tắc quyết định thông báo có bị người dùng tắt đi hay không (F6).

BR-18 và chống lặp là thứ phân biệt một hệ thống thông báo dùng được với một
hệ thống mà ai cũng tắt sau ngày thứ hai. Chúng được test ở đây, tách khỏi
test API, vì chúng là quy tắc nghiệp vụ chứ không phải chi tiết HTTP.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.notifications.service import (
    NotificationService,
    assigned_message,
    sla_breached_message,
)


class GhiNho:
    """Repository giả — chỉ nhớ những gì được ghi và những gì bị hỏi."""

    def __init__(self, da_co_gan_day: bool = False) -> None:
        self.da_ghi: list = []
        self.da_co_gan_day = da_co_gan_day
        self.lan_hoi: list[tuple] = []

    def add(self, notification):
        self.da_ghi.append(notification)
        return notification

    def exists_recent(self, user_id, notification_type, entity_id, since):
        self.lan_hoi.append((user_id, notification_type, entity_id, since))
        return self.da_co_gan_day


def dung_service(da_co_gan_day: bool = False) -> tuple[NotificationService, GhiNho]:
    service = NotificationService.__new__(NotificationService)
    service.db = None
    service.notifications = GhiNho(da_co_gan_day)
    return service, service.notifications


class TestBR18KhongTuBaoChoChinhMinh:
    def test_KHONG_ghi_khi_nguoi_nhan_chinh_la_nguoi_vua_hanh_dong(self):
        service, repo = dung_service()
        toi = uuid4()

        ket_qua = service.notify(
            user_id=toi,
            notification_type="TICKET_ASSIGNED",
            title="Bạn được giao ticket HD-1",
            actor_id=toi,
        )

        assert ket_qua is None
        assert repo.da_ghi == []
        # Không được hỏi database làm gì cả — BR-18 phải chặn TRƯỚC mọi truy vấn
        assert repo.lan_hoi == []

    def test_van_ghi_khi_nguoi_khac_hanh_dong(self):
        service, repo = dung_service()

        ket_qua = service.notify(
            user_id=uuid4(),
            notification_type="TICKET_ASSIGNED",
            title="Bạn được giao ticket HD-1",
            actor_id=uuid4(),
        )

        assert ket_qua is not None
        assert len(repo.da_ghi) == 1

    def test_bo_qua_khi_khong_co_nguoi_nhan(self):
        """Ticket chưa giao cho ai thì `assignee_id` là None — gọi vẫn phải an
        toàn, để bên gọi không phải rải câu `if` ở mọi chỗ."""
        service, repo = dung_service()

        assert service.notify(user_id=None, notification_type="SLA_AT_RISK", title="x") is None
        assert repo.da_ghi == []


class TestChongLap:
    def test_KHONG_ghi_ban_sao_trong_cua_so_chong_lap(self):
        service, repo = dung_service(da_co_gan_day=True)

        ket_qua = service.notify(
            user_id=uuid4(),
            notification_type="TICKET_STATUS_CHANGED",
            title="Ticket HD-1 đổi trạng thái",
            entity_id=uuid4(),
        )

        assert ket_qua is None
        assert repo.da_ghi == []

    def test_hoi_dung_bo_ba_nguoi_nhan_loai_doi_tuong(self):
        """Chống lặp theo (người nhận, loại, đối tượng) chứ KHÔNG theo riêng
        ticket: "được giao việc" và "đã xử lý xong" là hai tin khác nhau, chặn
        mất tin thứ hai là giấu thông tin của người dùng."""
        service, repo = dung_service()
        nguoi_nhan, ticket = uuid4(), uuid4()

        service.notify(
            user_id=nguoi_nhan,
            notification_type="TICKET_RESOLVED",
            title="x",
            entity_id=ticket,
        )

        hoi_user, hoi_loai, hoi_entity, hoi_since = repo.lan_hoi[0]
        assert (hoi_user, hoi_loai, hoi_entity) == (nguoi_nhan, "TICKET_RESOLVED", ticket)
        assert hoi_since < datetime.now(UTC)

    def test_notify_many_khong_gui_hai_lan_cho_cung_mot_nguoi(self):
        """Một người vừa là assignee vừa là Admin chỉ được nhận một lần —
        đúng kịch bản của cảnh báo SLA_BREACHED."""
        service, repo = dung_service()
        trung = uuid4()

        da_gui = service.notify_many(
            [trung, uuid4(), trung],
            notification_type="SLA_BREACHED",
            title="Ticket HD-1 ĐÃ TRỄ HẠN",
            entity_id=uuid4(),
        )

        assert da_gui == 2
        assert len(repo.da_ghi) == 2

    def test_notify_many_bo_qua_nguoi_nhan_None(self):
        service, repo = dung_service()

        assert service.notify_many([None, None], notification_type="SLA_BREACHED", title="x") == 0
        assert repo.da_ghi == []


class TestLoaiThongBao:
    def test_loai_khong_hop_le_bi_tu_choi_ngay(self):
        """CHECK constraint dưới database cũng chặn, nhưng chặn ở đây thì lỗi
        chỉ ra đúng tên biến sai thay vì một IntegrityError khó đọc."""
        service, _ = dung_service()

        with pytest.raises(ValueError, match="Loại thông báo không hợp lệ"):
            service.notify(user_id=uuid4(), notification_type="TICKET_EXPLODED", title="x")


class TestNoiDungThongBao:
    def test_US34_kem_ma_tieu_de_uu_tien_va_han_sla(self):
        """AC của US-34 liệt kê đúng bốn thứ phải có trong nội dung."""
        han = datetime(2026, 8, 3, 12, 30, tzinfo=UTC)
        tieu_de, noi_dung = assigned_message("HD-202608-00042", "Máy in kẹt giấy", "URGENT", han)

        assert "HD-202608-00042" in tieu_de
        assert "Máy in kẹt giấy" in noi_dung
        assert "URGENT" in noi_dung
        assert "03/08" in noi_dung

    def test_khong_co_han_sla_thi_khong_hien_chu_han_rong(self):
        _, noi_dung = assigned_message("HD-1", "Sự cố", "LOW", None)

        assert "hạn xử lý" not in noi_dung
        assert noi_dung.endswith("LOW")

    def test_canh_bao_tre_han_noi_ro_la_da_tre(self):
        tieu_de, _ = sla_breached_message(
            "HD-9", "Mất mạng", datetime.now(UTC) - timedelta(hours=2)
        )

        assert "TRỄ HẠN" in tieu_de
