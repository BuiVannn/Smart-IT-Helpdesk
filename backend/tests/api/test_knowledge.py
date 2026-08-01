"""Test API kho tài liệu — US-28, US-29, US-30, US-31, US-32."""

import pytest

from app.modules.users.constants import UserRole

BASE = "/api/v1/kb"

ARTICLE = {
    "title": "Hướng dẫn cấu hình máy in mạng",
    "contentMd": (
        "## Bước 1\nMở Cài đặt > Máy in.\n\n"
        "## Bước 2\nNhập địa chỉ máy chủ in của công ty và chọn model tương ứng."
    ),
    "summary": "Các bước thêm máy in mạng trên máy tính công ty.",
}


@pytest.fixture
def admin_client(client, make_user, login):
    return login(make_user(role=UserRole.ADMIN))


@pytest.fixture
def kb_category(db):
    from app.modules.knowledge.models import KbCategory

    category = KbCategory(slug=f"chu-de-test-{id(db)}", name="Chủ đề kiểm thử")
    db.add(category)
    db.flush()
    return category


def create_article(c, **overrides) -> dict:
    response = c.post(f"{BASE}/articles", json={**ARTICLE, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


class TestSoanThao:
    """US-28 — Soạn và đăng bài hướng dẫn."""

    def test_bai_moi_LUON_o_trang_thai_nhap(self, admin_client):
        """★ Tạo thẳng ở PUBLISHED nghĩa là một cú lưu nhầm sẽ đẩy bản nháp
        dở dang vào miệng chatbot. Xuất bản phải là hành động riêng."""
        body = create_article(admin_client)
        assert body["status"] == "DRAFT"
        assert body["publishedAt"] is None

    def test_slug_tu_sinh_khong_dau(self, admin_client):
        body = create_article(admin_client)
        assert body["slug"] == "huong-dan-cau-hinh-may-in-mang"

    def test_slug_trung_thi_them_hau_to(self, admin_client):
        first = create_article(admin_client)
        second = create_article(admin_client)
        assert (
            second["slug"] == f"{first['slug']}-2"
        ), "trùng tiêu đề là chuyện bình thường, không được ném lỗi khoá trùng"

    def test_nhan_vien_KHONG_soan_duoc(self, client, make_user, login):
        login(make_user(role=UserRole.EMPLOYEE))
        assert client.post(f"{BASE}/articles", json=ARTICLE).status_code == 403

    def test_agent_cung_KHONG_soan_duoc(self, client, make_user, login):
        login(make_user(role=UserRole.IT_AGENT))
        assert client.post(f"{BASE}/articles", json=ARTICLE).status_code == 403

    def test_noi_dung_qua_ngan_bi_tu_choi(self, admin_client):
        response = admin_client.post(f"{BASE}/articles", json={**ARTICLE, "contentMd": "ngắn"})
        assert response.status_code == 422

    def test_sua_bai_tang_version(self, admin_client):
        article = create_article(admin_client)
        response = admin_client.patch(
            f"{BASE}/articles/{article['id']}",
            json={"title": "Hướng dẫn cấu hình máy in mạng (bản mới)", "version": 1},
        )
        assert response.status_code == 200
        assert response.json()["version"] == 2

    def test_sai_version_thi_409(self, admin_client):
        article = create_article(admin_client)
        response = admin_client.patch(
            f"{BASE}/articles/{article['id']}",
            json={"summary": "x", "version": 99},
        )
        assert response.status_code == 409
        assert response.json()["error"]["details"]["currentVersion"] == 1


class TestXuatBan:
    """US-28, US-29 — Xuất bản và đưa vào chỉ mục chatbot."""

    def test_xuat_ban_dat_moc_thoi_gian(self, admin_client):
        article = create_article(admin_client)
        response = admin_client.post(f"{BASE}/articles/{article['id']}/publish")

        assert response.status_code == 200
        assert response.json()["status"] == "PUBLISHED"
        assert response.json()["publishedAt"] is not None

    def test_xuat_ban_KICH_HOAT_index(self, admin_client, monkeypatch):
        """★ MẮT XÍCH CUỐI CỦA PIPELINE RAG.

        Xuất bản là lúc DUY NHẤT chatbot học được nội dung mới. Thiếu lời gọi
        này, bài viết nằm im trong database và trợ lý ảo mãi mãi không biết
        tới nó — không lỗi nào được ghi ra.
        """
        from app.modules.knowledge import tasks

        called: list[str] = []
        monkeypatch.setattr(
            tasks.index_article,
            "apply_async",
            lambda args, **kw: called.append(args[0]),
        )

        article = create_article(admin_client)
        admin_client.post(f"{BASE}/articles/{article['id']}/publish")

        assert called == [article["id"]], "xuất bản mà KHÔNG xếp hàng index"

    def test_sua_bai_da_xuat_ban_thi_index_lai(self, admin_client, monkeypatch):
        """Không có bước này, chatbot trả lời theo bản cũ vô thời hạn."""
        from app.modules.knowledge import tasks

        article = create_article(admin_client)
        admin_client.post(f"{BASE}/articles/{article['id']}/publish")

        called: list[str] = []
        monkeypatch.setattr(
            tasks.index_article,
            "apply_async",
            lambda args, **kw: called.append(args[0]),
        )
        admin_client.patch(
            f"{BASE}/articles/{article['id']}",
            json={"contentMd": ARTICLE["contentMd"] + "\n\nBổ sung bước 3.", "version": 2},
        )
        assert called == [article["id"]]

    def test_go_xuat_ban_cung_kich_hoat_index_de_xoa_chunk(self, admin_client, monkeypatch):
        from app.modules.knowledge import tasks

        article = create_article(admin_client)
        admin_client.post(f"{BASE}/articles/{article['id']}/publish")

        called: list[str] = []
        monkeypatch.setattr(
            tasks.index_article,
            "apply_async",
            lambda args, **kw: called.append(args[0]),
        )
        response = admin_client.post(f"{BASE}/articles/{article['id']}/unpublish")

        assert response.json()["status"] == "ARCHIVED"
        assert called == [article["id"]], "gỡ bài mà không xoá khỏi chỉ mục chatbot"

    def test_hang_doi_hong_KHONG_lam_hong_viec_xuat_ban(self, admin_client, monkeypatch):
        """Redis chết thì bài vẫn phải xuất bản được — chỉ là chatbot biết muộn.
        Job đối soát định kỳ sẽ nhặt lại."""
        from app.modules.knowledge import tasks

        def explode(*_args, **_kwargs):
            raise ConnectionError("Redis không phản hồi")

        monkeypatch.setattr(tasks.index_article, "apply_async", explode)

        article = create_article(admin_client)
        response = admin_client.post(f"{BASE}/articles/{article['id']}/publish")
        assert response.status_code == 200

    def test_xuat_ban_hai_lan_tra_409(self, admin_client):
        article = create_article(admin_client)
        admin_client.post(f"{BASE}/articles/{article['id']}/publish")
        assert admin_client.post(f"{BASE}/articles/{article['id']}/publish").status_code == 409

    def test_canh_bao_chi_muc_cu(self, admin_client):
        """Người soạn thảo cần thấy chatbot đang dùng bản nào — sửa bài xong
        mà trợ lý vẫn trả lời kiểu cũ là tình huống bối rối nhất khi vận hành."""
        article = create_article(admin_client)
        assert article["isIndexStale"] is False, "bản nháp thì không tính là cũ"

        published = admin_client.post(f"{BASE}/articles/{article['id']}/publish").json()
        assert published["isIndexStale"] is True, "vừa xuất bản, chưa index xong"


class TestQuyenXem:
    """BR-11 — bản nháp không lọt ra ngoài."""

    def test_nhan_vien_KHONG_thay_ban_nhap_trong_danh_sach(self, client, make_user, login):
        login(make_user(role=UserRole.ADMIN))
        create_article(client)

        client.headers.pop("Authorization", None)
        login(make_user(role=UserRole.EMPLOYEE))
        body = client.get(f"{BASE}/articles", params={"q": "máy in mạng"}).json()
        assert all(a["status"] == "PUBLISHED" for a in body["data"])

    def test_ep_status_DRAFT_van_khong_thay(self, client, make_user, login):
        """★ Truyền ?status=DRAFT là cách rẻ nhất để thử vượt rào."""
        login(make_user(role=UserRole.ADMIN))
        created = create_article(client)

        client.headers.pop("Authorization", None)
        login(make_user(role=UserRole.EMPLOYEE))
        body = client.get(f"{BASE}/articles", params={"status": "DRAFT"}).json()
        assert created["slug"] not in [a["slug"] for a in body["data"]]

    def test_mo_thang_ban_nhap_tra_404_KHONG_phai_403(self, client, make_user, login):
        login(make_user(role=UserRole.ADMIN))
        article = create_article(client)

        client.headers.pop("Authorization", None)
        login(make_user(role=UserRole.EMPLOYEE))
        assert client.get(f"{BASE}/articles/{article['slug']}").status_code == 404

    def test_admin_thay_ban_nhap(self, admin_client):
        article = create_article(admin_client)
        assert admin_client.get(f"{BASE}/articles/{article['slug']}").status_code == 200


class TestTimKiem:
    """US-30 — Tìm kiếm tài liệu."""

    def test_tim_khong_dau_van_ra_ket_qua(self, admin_client):
        article = create_article(admin_client)
        admin_client.post(f"{BASE}/articles/{article['id']}/publish")

        body = admin_client.get(f"{BASE}/articles", params={"q": "may in mang"}).json()
        assert article["slug"] in [
            a["slug"] for a in body["data"]
        ], "người Việt gõ không dấu phải tìm ra bài có dấu"

    def test_dem_luot_xem(self, admin_client):
        article = create_article(admin_client)
        admin_client.post(f"{BASE}/articles/{article['id']}/publish")

        admin_client.get(f"{BASE}/articles/{article['slug']}")
        body = admin_client.get(f"{BASE}/articles/{article['slug']}").json()
        assert body["viewCount"] >= 1

    def test_ban_nhap_khong_dem_luot_xem(self, admin_client):
        article = create_article(admin_client)
        admin_client.get(f"{BASE}/articles/{article['slug']}")
        body = admin_client.get(f"{BASE}/articles/{article['slug']}").json()
        assert body["viewCount"] == 0

    def test_goi_y_chi_tra_bai_da_xuat_ban(self, admin_client):
        """US-32 — gợi ý bản nháp cho nhân viên là làm lộ tài liệu chưa duyệt."""
        article = create_article(admin_client)
        body = admin_client.get(f"{BASE}/articles/suggest", params={"q": "máy in"}).json()
        assert article["slug"] not in [a["slug"] for a in body]

        admin_client.post(f"{BASE}/articles/{article['id']}/publish")
        body = admin_client.get(f"{BASE}/articles/suggest", params={"q": "máy in"}).json()
        assert article["slug"] in [a["slug"] for a in body]

    def test_tu_khoa_qua_ngan_bi_tu_choi(self, admin_client):
        assert admin_client.get(f"{BASE}/articles/suggest", params={"q": "ab"}).status_code == 422

    def test_duong_dan_suggest_khong_bi_hieu_thanh_slug(self, admin_client):
        """ "/articles/suggest" phải khai báo TRƯỚC "/articles/{slug}"."""
        response = admin_client.get(f"{BASE}/articles/suggest", params={"q": "máy in"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestChuDe:
    """US-31 — Phân loại tài liệu theo chủ đề."""

    def test_danh_sach_kem_so_bai(self, admin_client, kb_category):
        article = create_article(admin_client, kbCategoryId=str(kb_category.id))
        admin_client.post(f"{BASE}/articles/{article['id']}/publish")

        rows = admin_client.get(f"{BASE}/categories").json()
        mine = next(c for c in rows if c["id"] == str(kb_category.id))
        assert mine["articleCount"] == 1

    def test_loc_theo_chu_de(self, admin_client, kb_category):
        article = create_article(admin_client, kbCategoryId=str(kb_category.id))
        admin_client.post(f"{BASE}/articles/{article['id']}/publish")

        body = admin_client.get(
            f"{BASE}/articles", params={"categoryId": str(kb_category.id)}
        ).json()
        assert [a["slug"] for a in body["data"]] == [article["slug"]]

    def test_chu_de_khong_ton_tai_bi_tu_choi(self, admin_client):
        response = admin_client.post(
            f"{BASE}/articles",
            json={**ARTICLE, "kbCategoryId": "00000000-0000-0000-0000-000000000000"},
        )
        assert response.status_code == 422

    def test_nhan_vien_khong_tao_duoc_chu_de(self, client, make_user, login):
        login(make_user(role=UserRole.EMPLOYEE))
        assert client.post(f"{BASE}/categories", json={"name": "Chủ đề lậu"}).status_code == 403
