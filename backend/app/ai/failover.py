"""Chuyển sang nhà cung cấp dự phòng khi nhà cung cấp chính không dùng được.

★ VÌ SAO CẦN. Hạn mức miễn phí không ổn định theo bản chất: Ollama Cloud tính
theo thời gian GPU và reset theo phiên 5 giờ; OpenRouter thì gỡ model `:free`
liên tục (tháng 7/2026 rút từ 20 xuống 15 endpoint trong chín ngày, xoá hẳn
tầng Llama và Qwen). Cắm một nhà cung cấp duy nhất nghĩa là sẽ có ngày demo
không chạy, và đó thường là ngày quan trọng nhất.

★ CHỈ CHUYỂN KHI LỖI LÀ TẠM THỜI. Mất mạng, 429, 5xx, hoặc model không tồn
tại (404/400 do tên model bị gỡ) là lý do chính đáng để thử chỗ khác. Còn
prompt sai định dạng hay hết ngân sách thì chuyển sang nhà cung cấp khác cũng
hỏng y hệt, chỉ tốn thêm thời gian và tiền — những lỗi đó phải nổi lên ngay.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.ai.llm.base import LlmResponse
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Lỗi coi là TẠM THỜI ⇒ đáng thử nhà cung cấp kế tiếp.
LOI_TAM_THOI = (ConnectionError, TimeoutError, ExternalServiceError)


@dataclass
class NhaCungCap:
    ten: str
    client: Any


class FailoverLlmClient:
    """Gọi lần lượt các nhà cung cấp cho tới khi có một chỗ trả lời được."""

    def __init__(self, nha_cung_cap: list[NhaCungCap]) -> None:
        if not nha_cung_cap:
            raise ValueError("Cần ít nhất một nhà cung cấp LLM")
        self._nha_cung_cap = nha_cung_cap

    @property
    def model_name(self) -> str:
        return self._nha_cung_cap[0].client.model_name

    @property
    def ten_cac_nha_cung_cap(self) -> list[str]:
        return [n.ten for n in self._nha_cung_cap]

    async def complete(self, **kwargs) -> LlmResponse:
        loi_cuoi: Exception | None = None

        for thu_tu, nha in enumerate(self._nha_cung_cap):
            try:
                ket_qua = await nha.client.complete(**kwargs)
            except LOI_TAM_THOI as exc:
                loi_cuoi = exc
                logger.warning(
                    "nhà cung cấp LLM lỗi, thử chỗ tiếp theo",
                    extra={
                        "extra_fields": {
                            "provider": nha.ten,
                            "error": f"{type(exc).__name__}: {exc}",
                            "con_lai": len(self._nha_cung_cap) - thu_tu - 1,
                        }
                    },
                )
                continue

            if thu_tu > 0:
                # Ghi rõ khi chạy bằng dự phòng: người vận hành cần biết nhà
                # cung cấp chính đang hỏng, chứ không phải chỉ thấy mọi thứ
                # "vẫn chạy" rồi phát hiện hoá đơn ở chỗ khác.
                logger.warning(
                    "đang chạy bằng nhà cung cấp DỰ PHÒNG",
                    extra={"extra_fields": {"provider": nha.ten}},
                )
            return ket_qua

        raise ExternalServiceError(
            f"Toàn bộ {len(self._nha_cung_cap)} nhà cung cấp LLM đều không dùng được"
        ) from loi_cuoi

    async def stream(self, **kwargs) -> AsyncIterator[str]:
        """Sinh câu trả lời theo luồng.

        ★ CHỈ ĐƯỢC CHUYỂN NHÀ CUNG CẤP TRƯỚC TOKEN ĐẦU TIÊN. Đã phát ra chữ
        cho người dùng rồi mà đổi chỗ và bắt đầu lại thì họ sẽ thấy câu trả
        lời viết lại từ đầu giữa chừng — tệ hơn hẳn một thông báo lỗi trung
        thực. Vì vậy phải lấy được đoạn đầu tiên rồi mới coi là thành công.
        """
        loi_cuoi: Exception | None = None

        for thu_tu, nha in enumerate(self._nha_cung_cap):
            luong = nha.client.stream(**kwargs)
            try:
                dau_tien = await anext(luong)
            except StopAsyncIteration:
                # Trả về rỗng cũng là hỏng — coi như nhà cung cấp này im lặng.
                loi_cuoi = ExternalServiceError(f"{nha.ten} không trả về nội dung nào")
                continue
            except LOI_TAM_THOI as exc:
                loi_cuoi = exc
                logger.warning(
                    "nhà cung cấp LLM lỗi khi mở luồng, thử chỗ tiếp theo",
                    extra={
                        "extra_fields": {
                            "provider": nha.ten,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    },
                )
                continue

            if thu_tu > 0:
                logger.warning(
                    "đang chạy bằng nhà cung cấp DỰ PHÒNG",
                    extra={"extra_fields": {"provider": nha.ten}},
                )

            yield dau_tien
            # Từ đây trở đi lỗi sẽ nổi lên nguyên vẹn: không chuyển giữa chừng.
            async for phan in luong:
                yield phan
            return

        raise ExternalServiceError(
            f"Toàn bộ {len(self._nha_cung_cap)} nhà cung cấp LLM đều không dùng được"
        ) from loi_cuoi


class FailoverEmbeddingClient:
    """Như trên, nhưng cho embedding.

    ★ CẢNH BÁO QUAN TRỌNG. Vector của hai model KHÁC NHAU thì KHÔNG SO SÁNH
    ĐƯỢC. Nếu kho tài liệu được index bằng model A rồi câu hỏi lại được nhúng
    bằng model B (vì A đang hỏng), điểm tương đồng trở thành số ngẫu nhiên —
    và hệ thống vẫn trả lời tự tin. Đó là kiểu hỏng tệ nhất: im lặng và trông
    như đang hoạt động.

    Lưới an toàn nằm ở `Retriever`: nó lọc chunk theo đúng `embedding_model`
    của câu truy vấn, nên khi phải chạy dự phòng, kết quả là "không tìm thấy
    tài liệu" ⇒ chatbot từ chối trả lời. Thà nói không biết còn hơn bịa.
    """

    def __init__(self, nha_cung_cap: list[NhaCungCap]) -> None:
        if not nha_cung_cap:
            raise ValueError("Cần ít nhất một nhà cung cấp embedding")
        self._nha_cung_cap = nha_cung_cap
        self._dang_dung = nha_cung_cap[0]

    @property
    def model_name(self) -> str:
        """Tên model của nhà cung cấp ĐANG THỰC SỰ phục vụ.

        Không trả tên của nhà cung cấp chính: giá trị này được ghi vào cột
        `article_chunks.embedding_model` và được dùng để lọc lúc truy hồi, nên
        nó phải phản ánh sự thật, không phải ý định.
        """
        return self._dang_dung.client.model_name

    @property
    def dimensions(self) -> int:
        return self._dang_dung.client.dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        loi_cuoi: Exception | None = None

        for thu_tu, nha in enumerate(self._nha_cung_cap):
            try:
                ket_qua = await nha.client.embed(texts)
            except LOI_TAM_THOI as exc:
                loi_cuoi = exc
                logger.warning(
                    "nhà cung cấp embedding lỗi, thử chỗ tiếp theo",
                    extra={
                        "extra_fields": {
                            "provider": nha.ten,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    },
                )
                continue

            self._dang_dung = nha
            if thu_tu > 0:
                logger.warning(
                    "embedding đang chạy bằng DỰ PHÒNG — vector sinh ra KHÔNG so "
                    "sánh được với kho đã index; chạy lại reindex_kb.py sau khi "
                    "nhà cung cấp chính hoạt động trở lại",
                    extra={"extra_fields": {"provider": nha.ten, "model": self.model_name}},
                )
            return ket_qua

        raise ExternalServiceError(
            f"Toàn bộ {len(self._nha_cung_cap)} nhà cung cấp embedding đều không dùng được"
        ) from loi_cuoi
