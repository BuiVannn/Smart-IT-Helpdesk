"""Quản trị người dùng (US-07).

Story này là điều kiện để US-06 vận hành được: không có nó thì đăng ký tự
phục vụ luôn ra EMPLOYEE và không đường nào tạo được IT_AGENT hay ADMIN.
"""

from sqlalchemy import select

from app.modules.auth.models import RefreshToken
from app.modules.users.constants import UserRole
from app.modules.users.models import User

MAT_KHAU_HOP_LE = "MatKhauMoi123"


class TestPhanQuyen:
    def test_nhan_vien_thuong_KHONG_xem_duoc_danh_sach(self, auth_client):
        assert auth_client.get("/api/v1/users").status_code == 403

    def test_IT_AGENT_cung_KHONG_quan_tri_duoc(self, client, make_user, login):
        c = login(make_user(role=UserRole.IT_AGENT))

        assert c.get("/api/v1/users").status_code == 403
        assert c.post("/api/v1/users", json={}).status_code == 403
        assert c.get("/api/v1/users/departments").status_code == 403

    def test_admin_xem_duoc(self, client, make_user, login):
        c = login(make_user(role=UserRole.ADMIN))
        assert c.get("/api/v1/users").status_code == 200


class TestTaoTaiKhoan:
    def test_admin_tao_duoc_IT_AGENT(self, client, make_user, login):
        c = login(make_user(role=UserRole.ADMIN))

        r = c.post(
            "/api/v1/users",
            json={
                "email": "agent.moi@company.com",
                "password": MAT_KHAU_HOP_LE,
                "fullName": "Nguyễn Văn Mới",
                "role": "IT_AGENT",
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["role"] == "IT_AGENT"
        assert r.json()["isActive"] is True
        # Mật khẩu KHÔNG BAO GIỜ được xuất hiện trong response
        assert "password" not in r.text.lower()

    def test_tai_khoan_moi_dang_nhap_duoc_ngay(self, client, make_user, login):
        c = login(make_user(role=UserRole.ADMIN))
        c.post(
            "/api/v1/users",
            json={
                "email": "nguoi.moi@company.com",
                "password": MAT_KHAU_HOP_LE,
                "fullName": "Người Mới",
                "role": "IT_AGENT",
            },
        )

        del client.headers["Authorization"]
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "nguoi.moi@company.com", "password": MAT_KHAU_HOP_LE},
        )
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "IT_AGENT"

    def test_mat_khau_yeu_bi_tu_choi_giong_het_dang_ky_tu_phuc_vu(self, client, make_user, login):
        """Admin tạo hộ mà lách được chính sách mật khẩu thì chính sách đó vô
        nghĩa — đây là đường vòng kinh điển."""
        c = login(make_user(role=UserRole.ADMIN))

        r = c.post(
            "/api/v1/users",
            json={
                "email": "yeu@company.com",
                "password": "matkhauyeu",  # thiếu chữ hoa và chữ số
                "fullName": "Mật Khẩu Yếu",
                "role": "EMPLOYEE",
            },
        )
        assert r.status_code == 422

    def test_email_trung_tra_409(self, client, make_user, login):
        da_ton_tai = make_user(email="da.co@company.com")
        c = login(make_user(role=UserRole.ADMIN))

        r = c.post(
            "/api/v1/users",
            json={
                "email": da_ton_tai.email,
                "password": MAT_KHAU_HOP_LE,
                "fullName": "Trùng Email",
                "role": "EMPLOYEE",
            },
        )
        assert r.status_code == 409

    def test_phong_ban_khong_ton_tai_tra_422_khong_phai_500(self, client, make_user, login):
        c = login(make_user(role=UserRole.ADMIN))

        r = c.post(
            "/api/v1/users",
            json={
                "email": "phongban@company.com",
                "password": MAT_KHAU_HOP_LE,
                "fullName": "Phòng Ban Lạ",
                "role": "EMPLOYEE",
                "departmentId": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert r.status_code == 422


class TestKhoaTaiKhoan:
    def test_khoa_thi_THU_HOI_TOAN_BO_refresh_token(self, client, db, make_user, login):
        """★ AC quan trọng nhất của US-07. Thiếu bước này, người vừa bị khoá
        vẫn đổi được access token mới suốt 7 ngày — tức là khoá tài khoản
        không có tác dụng với đúng kịch bản cần nó nhất."""
        nan_nhan = make_user()
        login(nan_nhan)  # sinh refresh token thật trong DB

        con_song = (
            db.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == nan_nhan.id, RefreshToken.revoked_at.is_(None)
                )
            )
            .scalars()
            .all()
        )
        assert len(con_song) >= 1, "chưa có refresh token nào để kiểm chứng"

        c = login(make_user(role=UserRole.ADMIN))
        r = c.post(f"/api/v1/users/{nan_nhan.id}/deactivate")
        assert r.status_code == 200, r.text
        assert r.json()["isActive"] is False

        con_lai = (
            db.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == nan_nhan.id, RefreshToken.revoked_at.is_(None)
                )
            )
            .scalars()
            .all()
        )
        assert con_lai == []

    def test_tai_khoan_bi_khoa_KHONG_dang_nhap_duoc_nua(self, client, make_user, login):
        nan_nhan = make_user()
        c = login(make_user(role=UserRole.ADMIN))
        c.post(f"/api/v1/users/{nan_nhan.id}/deactivate")

        del client.headers["Authorization"]
        r = client.post(
            "/api/v1/auth/login", json={"email": nan_nhan.email, "password": "MatKhau123"}
        )
        assert r.status_code == 403

    def test_mo_khoa_lai_thi_dang_nhap_duoc(self, client, make_user, login):
        nan_nhan = make_user(is_active=False)
        c = login(make_user(role=UserRole.ADMIN))

        r = c.post(f"/api/v1/users/{nan_nhan.id}/activate")
        assert r.status_code == 200
        assert r.json()["isActive"] is True

        del client.headers["Authorization"]
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": nan_nhan.email, "password": "MatKhau123"}
            ).status_code
            == 200
        )

    def test_admin_KHONG_tu_khoa_duoc_chinh_minh(self, client, make_user, login):
        admin = make_user(role=UserRole.ADMIN)
        c = login(admin)

        r = c.post(f"/api/v1/users/{admin.id}/deactivate")
        assert r.status_code == 422
        assert "chính mình" in r.json()["error"]["message"]


class TestGiuLaiItNhatMotAdmin:
    def test_KHONG_khoa_duoc_admin_dang_hoat_dong_cuoi_cung(self, client, db, make_user, login):
        # Dọn sạch admin có sẵn từ seed để dựng đúng tình huống "chỉ còn một"
        for u in db.execute(select(User).where(User.role == UserRole.ADMIN)).scalars().all():
            u.is_active = False
        db.flush()

        admin_cuoi = make_user(role=UserRole.ADMIN)
        nguoi_thao_tac = make_user(role=UserRole.ADMIN)
        c = login(nguoi_thao_tac)

        # Khoá `nguoi_thao_tac` trước ⇒ chỉ còn `admin_cuoi`
        db.refresh(nguoi_thao_tac)
        r = c.post(f"/api/v1/users/{admin_cuoi.id}/deactivate")
        assert r.status_code == 200, "còn 2 admin thì khoá 1 phải được"

        # Giờ `nguoi_thao_tac` là admin hoạt động duy nhất — tự khoá bị chặn
        r = c.post(f"/api/v1/users/{nguoi_thao_tac.id}/deactivate")
        assert r.status_code == 422

    def test_KHONG_ha_vai_tro_admin_hoat_dong_cuoi_cung(self, client, db, make_user, login):
        for u in db.execute(select(User).where(User.role == UserRole.ADMIN)).scalars().all():
            u.is_active = False
        db.flush()

        admin_duy_nhat = make_user(role=UserRole.ADMIN)
        c = login(admin_duy_nhat)

        r = c.patch(f"/api/v1/users/{admin_duy_nhat.id}", json={"role": "EMPLOYEE"})
        assert r.status_code == 422
        assert "cuối cùng" in r.json()["error"]["message"]

    def test_ha_vai_tro_duoc_khi_van_con_admin_khac(self, client, db, make_user, login):
        for u in db.execute(select(User).where(User.role == UserRole.ADMIN)).scalars().all():
            u.is_active = False
        db.flush()

        admin_a = make_user(role=UserRole.ADMIN)
        admin_b = make_user(role=UserRole.ADMIN)
        c = login(admin_a)

        r = c.patch(f"/api/v1/users/{admin_b.id}", json={"role": "IT_AGENT"})
        assert r.status_code == 200
        assert r.json()["role"] == "IT_AGENT"


class TestTimKiemVaSapXep:
    def test_tim_theo_ten_va_email(self, client, make_user, login):
        make_user(full_name="Lê Thị Đặc Biệt", email="dacbiet@company.com")
        c = login(make_user(role=UserRole.ADMIN))

        assert c.get("/api/v1/users?q=Đặc Biệt").json()["pagination"]["totalItems"] == 1
        assert c.get("/api/v1/users?q=dacbiet@").json()["pagination"]["totalItems"] == 1
        assert c.get("/api/v1/users?q=khongtontai").json()["pagination"]["totalItems"] == 0

    def test_loc_theo_vai_tro_va_trang_thai(self, client, make_user, login):
        make_user(role=UserRole.IT_AGENT, full_name="Agent Đang Hoạt Động")
        make_user(role=UserRole.IT_AGENT, full_name="Agent Bị Khoá", is_active=False)
        c = login(make_user(role=UserRole.ADMIN))

        ket_qua = c.get("/api/v1/users?role=IT_AGENT&isActive=false").json()["data"]
        assert all(u["role"] == "IT_AGENT" and u["isActive"] is False for u in ket_qua)
        assert any(u["fullName"] == "Agent Bị Khoá" for u in ket_qua)

    def test_sap_xep_theo_ten_dao_chieu_dung(self, client, make_user, login):
        """★ KHÔNG so với `sorted()` của Python.

        Thứ tự chữ cái tiếng Việt do COLLATION của PostgreSQL quyết định, còn
        `sorted()` của Python so theo mã ký tự Unicode. Hai bảng này khác
        nhau thật: "Người Dùng" và "Nguyễn Văn" đảo chỗ giữa hai cách so.
        Lấy Python làm chuẩn là test sai đề — nó sẽ đỏ dù backend hoàn toàn
        đúng, và người sau sẽ "sửa" backend cho vừa với test.

        Tính chất đúng bất kể collation: đảo chiều phải cho ra đúng dãy ngược.
        """
        c = login(make_user(role=UserRole.ADMIN, full_name="Zz Quản Trị Kiểm Thử"))

        tang_res = c.get("/api/v1/users?sortBy=fullName&sortDir=asc").json()
        giam_res = c.get("/api/v1/users?sortBy=fullName&sortDir=desc").json()
        if tang_res["pagination"]["totalItems"] > tang_res["pagination"]["pageSize"]:
            return  # nhiều hơn một trang thì hai chiều không phải là dãy ngược của nhau

        tang = [u["fullName"] for u in tang_res["data"]]
        giam = [u["fullName"] for u in giam_res["data"]]

        assert len(tang) >= 2
        assert giam == list(reversed(tang))

    def test_sortBy_la_ten_cot_LA_khong_lam_vo_truy_van(self, client, make_user, login):
        """Danh sách trắng phải nuốt giá trị lạ và rơi về mặc định, không được
        nối thẳng vào ORDER BY."""
        c = login(make_user(role=UserRole.ADMIN))

        r = c.get("/api/v1/users?sortBy=password_hash; DROP TABLE users--")
        assert r.status_code == 200
        assert r.json()["pagination"]["totalItems"] >= 1


class TestKhongTuNangQuyen:
    def test_PATCH_users_me_KHONG_doi_duoc_vai_tro(self, auth_client):
        r = auth_client.patch("/api/v1/users/me", json={"role": "ADMIN"})
        assert r.status_code == 422  # extra="forbid" chặn ở tầng schema

    def test_PATCH_admin_KHONG_doi_duoc_email_hay_mat_khau(self, client, make_user, login):
        nguoi_khac = make_user()
        c = login(make_user(role=UserRole.ADMIN))

        assert (
            c.patch(f"/api/v1/users/{nguoi_khac.id}", json={"email": "doi@company.com"}).status_code
            == 422
        )
        assert (
            c.patch(f"/api/v1/users/{nguoi_khac.id}", json={"password": "Abcdef123"}).status_code
            == 422
        )
        assert (
            c.patch(f"/api/v1/users/{nguoi_khac.id}", json={"isActive": False}).status_code == 422
        )
