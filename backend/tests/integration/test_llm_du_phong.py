"""Chuyển nhà cung cấp dự phòng — kiểm bằng MÁY CHỦ HTTP THẬT chạy cục bộ.

★ VÌ SAO KHÔNG MOCK. Cả tính năng này tồn tại để xử lý lỗi MẠNG và lỗi HTTP
của nhà cung cấp bên ngoài. Thay `httpx` bằng đồ giả là bỏ qua đúng cái tầng
cần kiểm — mã trạng thái, header, luồng SSE, cách `raise_for_status` hành xử.
Dựng một máy chủ nhỏ ở 127.0.0.1 tốn vài mili giây và kiểm được thật.

Không cần API key, không tốn tiền, chạy được trên CI.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.ai.embedding.openai_embedding import OpenAiEmbeddingClient
from app.ai.failover import FailoverEmbeddingClient, FailoverLlmClient, NhaCungCap
from app.ai.llm.openai_client import OpenAiLlmClient
from app.core.exceptions import ExternalServiceError

pytestmark = pytest.mark.anyio if False else []  # dùng asyncio_mode=auto của pytest.ini


class KichBan:
    """Điều khiển máy chủ giả trả về gì cho lần gọi tiếp theo."""

    def __init__(self, ma: int = 200, noi_dung: str = "xin chào", so_chieu: int = 1536) -> None:
        self.ma = ma
        self.noi_dung = noi_dung
        self.so_chieu = so_chieu
        self.so_lan_goi = 0
        self.dut_giua_chung = False


def _tao_handler(kich_ban: KichBan):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # im lặng, không làm bẩn output test
            pass

        def _doc_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):  # noqa: N802 — chữ ký của BaseHTTPRequestHandler
            if self.path.endswith("/models"):
                self._tra_json(200, {"data": [{"id": "model-thu-nghiem"}]})
            else:
                self._tra_json(404, {"error": "khong co"})

        def do_POST(self):  # noqa: N802
            kich_ban.so_lan_goi += 1
            body = self._doc_body()

            if kich_ban.ma != 200:
                self._tra_json(kich_ban.ma, {"error": f"kịch bản trả {kich_ban.ma}"})
                return

            if self.path.endswith("/embeddings"):
                so_luong = len(body.get("input", []))
                self._tra_json(
                    200,
                    {
                        "data": [
                            {"index": i, "embedding": [0.1] * kich_ban.so_chieu}
                            for i in range(so_luong)
                        ],
                        "usage": {"prompt_tokens": 3},
                    },
                )
                return

            if body.get("stream"):
                self._tra_sse()
                return

            self._tra_json(
                200,
                {
                    "choices": [{"message": {"content": kich_ban.noi_dung}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                },
            )

        def _tra_json(self, ma: int, payload: dict) -> None:
            data = json.dumps(payload).encode()
            self.send_response(ma)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _tra_sse(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for tu in kich_ban.noi_dung.split():
                khoi = {"choices": [{"delta": {"content": tu + " "}}]}
                self.wfile.write(f"data: {json.dumps(khoi)}\n\n".encode())
                self.wfile.flush()
                if kich_ban.dut_giua_chung:
                    # Đóng kết nối giữa chừng — mô phỏng nhà cung cấp chết khi
                    # đã phát ra vài token.
                    self.wfile.close()
                    return
            self.wfile.write(b"data: [DONE]\n\n")

    return Handler


class MayChuGia:
    def __init__(self, kich_ban: KichBan) -> None:
        self.kich_ban = kich_ban
        self._server = HTTPServer(("127.0.0.1", 0), _tao_handler(kich_ban))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> MayChuGia:
        self._thread.start()
        return self

    def __exit__(self, *_) -> None:
        self._server.shutdown()
        self._server.server_close()

    @property
    def base_url(self) -> str:
        cong = self._server.server_address[1]
        return f"http://127.0.0.1:{cong}/v1"


@pytest.fixture
def hai_may_chu() -> Iterator[tuple[MayChuGia, MayChuGia]]:
    chinh = KichBan(noi_dung="tra loi tu CHINH")
    du_phong = KichBan(noi_dung="tra loi tu DU PHONG")
    with MayChuGia(chinh) as a, MayChuGia(du_phong) as b:
        yield a, b


def dung_chuoi(chinh: MayChuGia, du_phong: MayChuGia) -> FailoverLlmClient:
    return FailoverLlmClient(
        [
            NhaCungCap("chinh", OpenAiLlmClient(api_key="k", model="m", base_url=chinh.base_url)),
            NhaCungCap(
                "du_phong", OpenAiLlmClient(api_key="k", model="m", base_url=du_phong.base_url)
            ),
        ]
    )


class TestChuyenSangDuPhong:
    async def test_chinh_chay_thi_KHONG_dung_du_phong(self, hai_may_chu):
        chinh, du_phong = hai_may_chu
        client = dung_chuoi(chinh, du_phong)

        res = await client.complete(system="s", user="u")

        assert res.content == "tra loi tu CHINH"
        assert du_phong.kich_ban.so_lan_goi == 0, "không được gọi dự phòng khi chính còn sống"

    @pytest.mark.parametrize("ma_loi", [429, 500, 502, 503])
    async def test_loi_tam_thoi_thi_chuyen(self, hai_may_chu, ma_loi):
        chinh, du_phong = hai_may_chu
        chinh.kich_ban.ma = ma_loi
        client = dung_chuoi(chinh, du_phong)

        res = await client.complete(system="s", user="u")

        assert res.content == "tra loi tu DU PHONG"

    @pytest.mark.parametrize("ma_loi", [400, 401, 403, 404])
    async def test_khoa_hong_hoac_model_bi_go_thi_CUNG_chuyen(self, hai_may_chu, ma_loi):
        """★ Với nhà cung cấp miễn phí, bốn mã này gần như luôn có nghĩa là
        "chỗ này không dùng được nữa": khoá hết hạn, model bị gỡ khỏi danh
        sách free, hoặc không hiểu `response_format`. Dừng lại ở đây là để cả
        tính năng chết trong khi bên cạnh có chỗ chạy được."""
        chinh, du_phong = hai_may_chu
        chinh.kich_ban.ma = ma_loi
        client = dung_chuoi(chinh, du_phong)

        res = await client.complete(system="s", user="u")

        assert res.content == "tra loi tu DU PHONG"

    async def test_ca_hai_hong_thi_bao_loi_ro_rang(self, hai_may_chu):
        chinh, du_phong = hai_may_chu
        chinh.kich_ban.ma = 503
        du_phong.kich_ban.ma = 503
        client = dung_chuoi(chinh, du_phong)

        with pytest.raises(ExternalServiceError, match="đều không dùng được"):
            await client.complete(system="s", user="u")


class TestLuongSSE:
    async def test_chuyen_duoc_khi_chinh_hong_TRUOC_token_dau_tien(self, hai_may_chu):
        chinh, du_phong = hai_may_chu
        chinh.kich_ban.ma = 503
        client = dung_chuoi(chinh, du_phong)

        van_ban = "".join([phan async for phan in client.stream(system="s", user="u")])

        assert "DU PHONG" in van_ban

    async def test_KHONG_chuyen_giua_chung_de_khoi_viet_lai_tu_dau(self, hai_may_chu, caplog):
        """★ Đã phát chữ cho người dùng rồi mà đổi nhà cung cấp và bắt đầu lại
        thì họ thấy câu trả lời viết lại từ đầu giữa chừng — tệ hơn hẳn một
        thông báo lỗi trung thực.

        Test này cũng ghi lại một HÀNH VI THẬT đáng biết: khi nhà cung cấp
        chết giữa luồng, kết nối đóng êm và vòng lặp đọc kết thúc bình thường
        — KHÔNG có ngoại lệ nào. Người dùng nhận một câu trả lời cụt trông
        như đã hoàn chỉnh. Không thể thử lại (viết lại từ đầu giữa màn hình)
        và không thể chuyển chỗ, nên thứ duy nhất làm được là ghi cảnh báo.
        """
        chinh, du_phong = hai_may_chu
        chinh.kich_ban.dut_giua_chung = True
        client = dung_chuoi(chinh, du_phong)

        thu_duoc = [phan async for phan in client.stream(system="s", user="u")]

        assert "".join(thu_duoc).strip() == "tra", "chỉ nhận được phần đã kịp gửi"
        assert du_phong.kich_ban.so_lan_goi == 0, "KHÔNG được gọi dự phòng khi đã stream dở"
        assert any(
            "[DONE]" in b.message for b in caplog.records
        ), "phải cảnh báo câu trả lời có thể bị cụt, nếu không sự cố này hoàn toàn vô hình"


class TestEmbeddingDuPhong:
    async def test_chuyen_duoc_va_model_name_PHAN_ANH_noi_thuc_su_phuc_vu(self, hai_may_chu):
        """★ `model_name` được ghi vào `article_chunks.embedding_model` và
        dùng để lọc lúc truy hồi. Trả tên của nhà cung cấp chính trong khi dự
        phòng mới là chỗ sinh vector sẽ làm hỏng đúng lưới an toàn đó."""
        chinh, du_phong = hai_may_chu
        chinh.kich_ban.ma = 503

        client = FailoverEmbeddingClient(
            [
                NhaCungCap(
                    "chinh",
                    OpenAiEmbeddingClient(
                        api_key="k", model="model-chinh", base_url=chinh.base_url
                    ),
                ),
                NhaCungCap(
                    "du_phong",
                    OpenAiEmbeddingClient(
                        api_key="k", model="model-du-phong", base_url=du_phong.base_url
                    ),
                ),
            ]
        )

        vectors = await client.embed(["xin chào"])

        assert len(vectors) == 1
        assert "model-du-phong" in client.model_name
        assert "model-chinh" not in client.model_name


class TestGoRaoMarkdown:
    """Model mở rất hay bọc JSON trong rào ```json dù đã được dặn không."""

    @pytest.mark.parametrize(
        "tra_ve",
        [
            '{"category_slug": "network"}',
            '```json\n{"category_slug": "network"}\n```',
            '```\n{"category_slug": "network"}\n```',
        ],
    )
    async def test_van_doc_duoc_JSON(self, tra_ve):
        kich_ban = KichBan(noi_dung=tra_ve)
        with MayChuGia(kich_ban) as may:
            client = OpenAiLlmClient(api_key="k", model="m", base_url=may.base_url)
            res = await client.complete(system="s", user="u", schema={"type": "object"})

        assert res.parsed == {"category_slug": "network"}
