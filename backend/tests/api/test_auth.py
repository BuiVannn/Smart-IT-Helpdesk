"""Test API xác thực — US-01 → US-06.

Mỗi test bám sát một tiêu chí chấp nhận trong docs/design/02-user-stories.md.
Tên test viết bằng tiếng Việt để khi CI đỏ, người đọc biết NGHIỆP VỤ nào hỏng
chứ không phải hàm nào hỏng.
"""

from app.modules.users.constants import UserRole

BASE = "/api/v1/auth"
GOOD_PASSWORD = "MatKhau123"


def register_payload(**overrides) -> dict:
    payload = {
        "email": "nhan.vien@company.com",
        "password": GOOD_PASSWORD,
        "fullName": "Nguyễn Văn A",
    }
    payload.update(overrides)
    return payload


class TestDangKy:
    """US-01 — Đăng ký tài khoản."""

    def test_dang_ky_thanh_cong_mac_dinh_la_EMPLOYEE(self, client):
        response = client.post(f"{BASE}/register", json=register_payload())

        assert response.status_code == 201
        body = response.json()
        assert body["role"] == UserRole.EMPLOYEE
        assert body["isActive"] is True
        assert body["fullName"] == "Nguyễn Văn A"

    def test_khong_the_tu_chon_vai_tro_khi_dang_ky(self, client):
        """Leo thang đặc quyền kinh điển: gửi kèm role=ADMIN lúc đăng ký.

        `extra="forbid"` phải TỪ CHỐI thẳng, chứ không phải âm thầm bỏ qua —
        bỏ qua thì hôm nào đó có người thêm field `role` vào schema là thủng.
        """
        response = client.post(
            f"{BASE}/register", json=register_payload(role="ADMIN")
        )
        assert response.status_code == 422

    def test_email_trung_tra_ve_409(self, client):
        client.post(f"{BASE}/register", json=register_payload())
        response = client.post(f"{BASE}/register", json=register_payload())

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CONFLICT"

    def test_email_khong_phan_biet_hoa_thuong(self, client):
        client.post(f"{BASE}/register", json=register_payload())
        response = client.post(
            f"{BASE}/register", json=register_payload(email="NHAN.VIEN@company.com")
        )
        assert response.status_code == 409, "chữ hoa/thường không được tạo ra tài khoản thứ hai"

    def test_mat_khau_yeu_bi_tu_choi(self, client):
        for weak in ["short1A", "khongcochuhoa1", "KHONGCOCHUTHUONG1", "KhongCoSo"]:
            response = client.post(
                f"{BASE}/register", json=register_payload(password=weak)
            )
            assert response.status_code == 422, f"mật khẩu yếu lọt qua: {weak}"

    def test_response_khong_bao_gio_chua_mat_khau(self, client):
        response = client.post(f"{BASE}/register", json=register_payload())
        assert "password" not in response.text.lower()
        assert GOOD_PASSWORD not in response.text


class TestDangNhap:
    """US-02 — Đăng nhập nhận JWT."""

    def test_dang_nhap_thanh_cong(self, client, make_user):
        user = make_user()
        response = client.post(
            f"{BASE}/login", json={"email": user.email, "password": GOOD_PASSWORD}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["accessToken"]
        assert body["tokenType"] == "Bearer"
        assert body["expiresIn"] == 15 * 60
        assert body["user"]["email"] == user.email

    def test_refresh_token_nam_trong_cookie_HttpOnly_khong_nam_trong_body(
        self, client, make_user
    ):
        """★ Nếu refresh token lọt vào body thì JavaScript đọc được, và một lỗ
        hổng XSS bất kỳ là mất phiên 7 ngày của người dùng."""
        user = make_user()
        response = client.post(
            f"{BASE}/login", json={"email": user.email, "password": GOOD_PASSWORD}
        )

        assert "refreshToken" not in response.json()
        assert "refresh_token" not in response.json()

        set_cookie = response.headers["set-cookie"]
        assert "refresh_token=" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "SameSite=strict" in set_cookie.replace("samesite", "SameSite")

    def test_sai_mat_khau_va_sai_email_tra_ve_CUNG_MOT_thong_diep(self, client, make_user):
        """Khác thông điệp là tự khai email nào có thật trong công ty."""
        user = make_user()

        sai_mat_khau = client.post(
            f"{BASE}/login", json={"email": user.email, "password": "SaiHoanToan1"}
        )
        sai_email = client.post(
            f"{BASE}/login",
            json={"email": "khong-ton-tai@company.com", "password": GOOD_PASSWORD},
        )

        assert sai_mat_khau.status_code == sai_email.status_code == 401
        assert sai_mat_khau.json()["error"]["code"] == "INVALID_CREDENTIALS"
        assert sai_mat_khau.json()["error"]["message"] == sai_email.json()["error"]["message"]

    def test_tai_khoan_bi_khoa_tra_ve_403(self, client, make_user):
        user = make_user(is_active=False)
        response = client.post(
            f"{BASE}/login", json={"email": user.email, "password": GOOD_PASSWORD}
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"

    def test_qua_nhieu_lan_sai_thi_khoa_tam_KE_CA_khi_mat_khau_dung(
        self, client, make_user
    ):
        """★ TEST QUAN TRỌNG NHẤT CỦA MODULE NÀY.

        Nếu mật khẩu đúng vẫn cho vào sau 5 lần sai, nghĩa là kẻ dò mật khẩu
        đã tìm ra mật khẩu rồi — giới hạn số lần thử chẳng ngăn được gì.
        Phải chặn TRƯỚC khi so mật khẩu.
        """
        user = make_user()
        for _ in range(5):
            client.post(
                f"{BASE}/login", json={"email": user.email, "password": "SaiHoanToan1"}
            )

        response = client.post(
            f"{BASE}/login", json={"email": user.email, "password": GOOD_PASSWORD}
        )

        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"
        assert int(response.headers["retry-after"]) > 0

    def test_dang_nhap_dung_thi_xoa_bo_dem_that_bai(self, client, make_user):
        user = make_user()
        for _ in range(4):
            client.post(
                f"{BASE}/login", json={"email": user.email, "password": "SaiHoanToan1"}
            )

        assert client.post(
            f"{BASE}/login", json={"email": user.email, "password": GOOD_PASSWORD}
        ).status_code == 200

        # 4 lần sai trước đó phải bị quên đi, không cộng dồn sang lần sau
        for _ in range(4):
            client.post(
                f"{BASE}/login", json={"email": user.email, "password": "SaiHoanToan1"}
            )
        assert client.post(
            f"{BASE}/login", json={"email": user.email, "password": GOOD_PASSWORD}
        ).status_code == 200


class TestXoayVongToken:
    """US-03 — Làm mới phiên bằng refresh token."""

    def test_refresh_tra_ve_token_moi(self, client, make_user, login):
        login(make_user())
        response = client.post(f"{BASE}/refresh")

        assert response.status_code == 200
        assert response.json()["accessToken"]

    def test_khong_co_cookie_thi_401(self, client):
        assert client.post(f"{BASE}/refresh").status_code == 401

    def test_refresh_token_cu_bi_vo_hieu_sau_khi_xoay_vong(self, client, make_user, login):
        """Mỗi refresh token dùng được ĐÚNG MỘT LẦN."""
        login(make_user())
        cu = client.cookies["refresh_token"]

        assert client.post(f"{BASE}/refresh").status_code == 200
        moi = client.cookies["refresh_token"]
        assert moi != cu, "token phải đổi sau mỗi lần refresh"

    def test_dung_lai_token_da_thu_hoi_thi_thu_hoi_TOAN_BO_phien(
        self, client, make_user, login
    ):
        """★ Phát hiện token bị đánh cắp.

        Token đã bị thay thế mà xuất hiện lần nữa thì chỉ có hai khả năng: bị
        đánh cắp, hoặc client lỗi. Cả hai đều xử lý như nhau — thu hồi sạch,
        bắt đăng nhập lại. Thà phiền một lần còn hơn để kẻ trộm dùng tiếp.
        """
        login(make_user())
        cu = client.cookies["refresh_token"]
        client.post(f"{BASE}/refresh")            # xoay vòng, `cu` bị thu hồi
        moi = client.cookies["refresh_token"]

        client.cookies.clear()
        client.cookies.set("refresh_token", cu, path="/api/v1/auth")
        tai_su_dung = client.post(f"{BASE}/refresh")
        assert tai_su_dung.status_code == 401

        # Token hợp lệ của phiên hiện tại cũng phải chết theo
        client.cookies.clear()
        client.cookies.set("refresh_token", moi, path="/api/v1/auth")
        assert client.post(f"{BASE}/refresh").status_code == 401, (
            "token của kẻ trộm bị chặn nhưng phiên còn lại vẫn sống — chưa thu hồi hết"
        )


class TestDangXuat:
    """US-04 — Đăng xuất."""

    def test_dang_xuat_thu_hoi_phien_hien_tai(self, client, make_user, login):
        login(make_user())
        assert client.post(f"{BASE}/logout").status_code == 204
        assert client.post(f"{BASE}/refresh").status_code == 401

    def test_dang_xuat_khi_khong_co_phien_van_thanh_cong(self, client):
        """Đăng xuất phải luôn thành công — báo lỗi chỉ làm người dùng mắc kẹt."""
        assert client.post(f"{BASE}/logout").status_code == 204

    def test_dang_xuat_toan_bo_thiet_bi(self, client, make_user, login):
        user = make_user()
        login(user)
        assert client.post(f"{BASE}/logout-all").status_code == 204
        assert client.post(f"{BASE}/refresh").status_code == 401


class TestDoiMatKhau:
    """US-05 — Đổi mật khẩu."""

    def test_doi_mat_khau_thanh_cong_va_thu_hoi_moi_phien(self, client, make_user, login):
        user = make_user()
        login(user)

        response = client.post(
            f"{BASE}/change-password",
            json={"currentPassword": GOOD_PASSWORD, "newPassword": "MatKhauMoi456"},
        )
        assert response.status_code == 204

        # Người đổi mật khẩu thường vì nghi bị lộ — để phiên cũ sống tiếp thì
        # việc đổi mật khẩu trở nên vô nghĩa.
        assert client.post(f"{BASE}/refresh").status_code == 401

        client.headers.pop("Authorization", None)
        assert client.post(
            f"{BASE}/login", json={"email": user.email, "password": "MatKhauMoi456"}
        ).status_code == 200

    def test_sai_mat_khau_hien_tai_thi_tu_choi(self, client, make_user, login):
        login(make_user())
        response = client.post(
            f"{BASE}/change-password",
            json={"currentPassword": "SaiHoanToan1", "newPassword": "MatKhauMoi456"},
        )
        assert response.status_code == 401

    def test_mat_khau_moi_trung_mat_khau_cu_thi_tu_choi(self, client, make_user, login):
        login(make_user())
        response = client.post(
            f"{BASE}/change-password",
            json={"currentPassword": GOOD_PASSWORD, "newPassword": GOOD_PASSWORD},
        )
        assert response.status_code == 422

    def test_mat_khau_moi_phai_dat_chinh_sach(self, client, make_user, login):
        """Chính sách mật khẩu phải áp cả ở đổi mật khẩu, không chỉ ở đăng ký."""
        login(make_user())
        response = client.post(
            f"{BASE}/change-password",
            json={"currentPassword": GOOD_PASSWORD, "newPassword": "yeuqua"},
        )
        assert response.status_code == 422


class TestPhanQuyen:
    """US-06 — Phân quyền theo vai trò."""

    def test_khong_co_token_thi_401(self, client):
        assert client.get("/api/v1/users/me").status_code == 401

    def test_token_rac_thi_401(self, client):
        response = client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer khong-phai-jwt"}
        )
        assert response.status_code == 401

    def test_co_token_thi_lay_duoc_thong_tin_ca_nhan(self, client, make_user, login):
        user = make_user(role=UserRole.IT_AGENT)
        login(user)

        body = client.get("/api/v1/users/me").json()
        assert body["email"] == user.email
        assert body["role"] == UserRole.IT_AGENT

    def test_tai_khoan_bi_khoa_sau_khi_da_dang_nhap_thi_mat_quyen_ngay(
        self, client, db, make_user, login
    ):
        """Admin khoá tài khoản xong mà access token cũ vẫn dùng được thêm 15
        phút là một lỗ hổng thật — nên phải kiểm tra `is_active` mỗi request."""
        user = make_user()
        login(user)
        assert client.get("/api/v1/users/me").status_code == 200

        user.is_active = False
        db.flush()

        assert client.get("/api/v1/users/me").status_code == 403

    def test_khong_the_tu_nang_quyen_qua_PATCH_users_me(self, client, make_user, login):
        login(make_user())
        response = client.patch("/api/v1/users/me", json={"role": "ADMIN"})
        assert response.status_code == 422, "schema phải từ chối field `role`"

    def test_cap_nhat_ho_so_ca_nhan(self, client, make_user, login):
        login(make_user())
        response = client.patch("/api/v1/users/me", json={"fullName": "Tên Mới"})
        assert response.status_code == 200
        assert response.json()["fullName"] == "Tên Mới"
