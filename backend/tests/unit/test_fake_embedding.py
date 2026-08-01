"""Tính chất của embedding giả (P0-3).

★ VÌ SAO CÓ FILE NÀY. Bản trước sinh vector bằng `sha256(text)` và docstring
tự khẳng định "văn bản giống nhau cho vector gần nhau". Không test nào kiểm
khẳng định đó, nên nó sống suốt nhiều tuần trong khi RAG có recall@5 = 0.

Test dưới đây khẳng định thẳng vào TÍNH CHẤT, không vào cách cài đặt: đổi
thuật toán thoải mái, miễn là các tính chất còn đúng.
"""

import asyncio

import pytest

from app.ai.embedding.fake_embedding import FakeEmbeddingClient


def cosine(a: list[float], b: list[float]) -> float:
    """Vector đã chuẩn hoá L2 nên tích vô hướng chính là cosine."""
    return sum(x * y for x, y in zip(a, b, strict=True))


@pytest.fixture
def nhung():
    client = FakeEmbeddingClient(dimensions=1536)

    def _nhung(*texts: str) -> list[list[float]]:
        return asyncio.run(client.embed(list(texts)))

    return _nhung


class TestVanBanGiongNhauThiGanNhau:
    def test_hai_cau_gan_dong_nghia_gan_nhau(self, nhung):
        a, b = nhung(
            "Cách đổi mật khẩu email công ty",
            "Hướng dẫn đổi mật khẩu email công ty",
        )
        assert cosine(a, b) > 0.6

    def test_hai_cau_khong_lien_quan_xa_nhau(self, nhung):
        a, b = nhung("Cách đổi mật khẩu email công ty", "Máy in tầng 3 bị kẹt giấy")
        assert cosine(a, b) < 0.2

    def test_gan_nhau_HON_han_so_voi_khong_lien_quan(self, nhung):
        """★ Đây chính là tính chất đã SAI ở bản cũ: hai câu gần đồng nghĩa
        cho -0,21 còn hai câu không liên quan cho -0,04, tức là cặp không liên
        quan lại GẦN HƠN."""
        goc, gan, xa = nhung(
            "Cách đổi mật khẩu email công ty",
            "Hướng dẫn đổi mật khẩu email công ty",
            "Máy in tầng 3 bị kẹt giấy",
        )
        assert cosine(goc, gan) > cosine(goc, xa) + 0.4


class TestTiengVietKhongDau:
    """`docs/design/07` §7 xếp "tiếng Việt không dấu, viết tắt" là rủi ro mức
    Trung bình. Người dùng gõ vội thường bỏ dấu hoàn toàn."""

    @pytest.mark.parametrize(
        ("co_dau", "khong_dau"),
        [
            ("quên mật khẩu", "quen mat khau"),
            ("wifi không kết nối được", "wifi khong ket noi duoc"),
            ("máy in bị kẹt giấy", "may in bi ket giay"),
        ],
    )
    def test_co_dau_va_khong_dau_la_MOT(self, nhung, co_dau, khong_dau):
        a, b = nhung(co_dau, khong_dau)
        assert cosine(a, b) == pytest.approx(1.0, abs=1e-9)


class TestTinhChatCoBan:
    def test_tat_dinh(self, nhung):
        a, b = nhung("Máy in kẹt giấy", "Máy in kẹt giấy")
        assert a == b

    def test_da_chuan_hoa_do_dai_1(self, nhung):
        (v,) = nhung("Một câu bất kỳ để kiểm tra chuẩn hoá")
        assert cosine(v, v) == pytest.approx(1.0, abs=1e-9)

    def test_dung_so_chieu_khai_bao(self, nhung):
        (v,) = nhung("x")
        assert len(v) == 1536

    def test_van_ban_rong_khong_lam_no(self, nhung):
        a, b = nhung("", "   !!!   ")
        assert len(a) == len(b) == 1536
        assert all(x == 0.0 for x in a)


class TestTuDung:
    def test_hai_cau_chi_chung_tu_dung_nam_DUOI_nguong_truy_hoi(self, nhung):
        """ "Tôi muốn hỏi làm sao để..." xuất hiện ở gần như mọi câu hỏi. Nếu
        các từ đó mang trọng số ngang từ khoá thật thì mọi câu hỏi đều giống
        nhau — đó chính là lý do "Lương tháng này khi nào được trả?" từng vượt
        ngưỡng và lấy về tài liệu IT.

        Khẳng định so với `RAG_SIMILARITY_THRESHOLD` chứ không so với một con
        số tự đặt: ngưỡng đó mới là ranh giới quyết định thật, và buộc test
        phải đỏ nếu ai đó nới ngưỡng mà quên hệ quả.
        """
        from app.core.config import settings

        a, b = nhung(
            "Tôi muốn hỏi làm sao để cài đặt VPN",
            "Tôi muốn hỏi làm sao để xin nghỉ phép",
        )
        assert cosine(a, b) < settings.RAG_SIMILARITY_THRESHOLD

    def test_cau_toan_tu_dung_van_cho_ra_vector_khac_0(self, nhung):
        """Bỏ hết từ dừng mà trả về vector rỗng thì câu đó sẽ khớp với MỌI
        thứ — im lặng và rất khó lần ra."""
        (v,) = nhung("tôi có thể như thế nào")
        assert any(x != 0.0 for x in v)

    def test_KHONG_bo_tu_phu_dinh(self, nhung):
        """ "wifi kết nối được" và "wifi không kết nối được" là hai sự việc
        trái ngược. Nếu "không" bị coi là từ dừng, hai câu này thành một."""
        a, b = nhung("wifi kết nối được", "wifi không kết nối được")
        assert cosine(a, b) < 0.999
