"""LLM giả — dùng cho TOÀN BỘ test và cho chế độ chạy offline.

Trả về kết quả đặt trước theo từ khoá xuất hiện trong prompt. Tất định,
nhanh, miễn phí. Nếu test cần API key thật thì sẽ có người bỏ qua test,
và test bị bỏ qua là test không tồn tại.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from app.ai.llm.base import LlmResponse

DEFAULT_CLASSIFICATION = {
    "category_slug": "other",
    "priority": "MEDIUM",
    "confidence": 0.75,
    "reasoning": "Phản hồi mặc định từ FakeLlmClient",
}

# ★ THỨ TỰ CÓ Ý NGHĨA — luật đầu tiên khớp là thắng.
#
# Bảo mật phải đứng ĐẦU. Một ticket "phần mềm diệt virus báo phát hiện mã độc"
# khớp cả "phần mềm" lẫn "virus"; để bảo mật ở cuối bảng thì sự cố mã độc bị
# xếp vào `software` — đã gặp đúng tình huống này khi chạy thử. Cùng lý do với
# cờ `dominant` ở RuleBasedClassifier: chậm một giờ với mã độc đắt hơn nhiều
# so với gán nhầm một ticket phần mềm.
KEYWORD_RULES: list[tuple[tuple[str, ...], dict[str, Any]]] = [
    (("virus", "mã độc", "bảo mật", "lừa đảo", "phishing"),
     {"category_slug": "security", "priority": "URGENT", "confidence": 0.95}),
    (("wifi", "mạng", "internet", "vpn", "kết nối"),
     {"category_slug": "network", "priority": "HIGH", "confidence": 0.92}),
    (("mật khẩu", "password", "đăng nhập", "tài khoản"),
     {"category_slug": "account", "priority": "MEDIUM", "confidence": 0.88}),
    (("máy in", "màn hình", "chuột", "bàn phím", "laptop"),
     {"category_slug": "hardware", "priority": "MEDIUM", "confidence": 0.85}),
    (("phần mềm", "cài đặt", "office", "excel"),
     {"category_slug": "software", "priority": "LOW", "confidence": 0.80}),
]


class FakeLlmClient:
    """Cài đặt giả của LlmClient.

    Truyền `responses` để ép câu trả lời cụ thể trong test:
        FakeLlmClient(responses={"đổi mật khẩu": "Bạn vào portal..."})
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        *,
        should_fail: bool = False,
        delay_seconds: float = 0.0,
    ) -> None:
        self.responses = responses or {}
        self.should_fail = should_fail
        self.delay_seconds = delay_seconds
        self.last_prompt: str = ""
        # Đếm RIÊNG hai loại lời gọi. Test cần phân biệt được:
        # - complete() dùng để phân loại và viết lại câu hỏi (rẻ, chấp nhận được)
        # - stream()   dùng để SINH CÂU TRẢ LỜI — tuyệt đối không được gọi khi
        #              không tìm thấy tài liệu liên quan (chống bịa đặt)
        self.complete_count = 0
        self.stream_count = 0

    @property
    def call_count(self) -> int:
        return self.complete_count + self.stream_count

    @property
    def model_name(self) -> str:
        return "fake-model"

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.0,
    ) -> LlmResponse:
        self.complete_count += 1
        self.last_prompt = f"{system}\n{user}"
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.should_fail:
            raise ConnectionError("FakeLlmClient được cấu hình để lỗi")

        if schema is not None:
            parsed = self._classify(user)
            return LlmResponse(
                content=json.dumps(parsed, ensure_ascii=False),
                model="fake-model",
                prompt_tokens=len(self.last_prompt.split()),
                completion_tokens=30,
                latency_ms=5,
                parsed=parsed,
            )

        text = self._lookup(user)
        return LlmResponse(
            content=text,
            model="fake-model",
            prompt_tokens=len(self.last_prompt.split()),
            completion_tokens=len(text.split()),
            latency_ms=5,
        )

    async def stream(
        self, *, system: str, user: str, max_tokens: int = 800
    ) -> AsyncIterator[str]:
        self.stream_count += 1
        self.last_prompt = f"{system}\n{user}"
        if self.should_fail:
            raise ConnectionError("FakeLlmClient được cấu hình để lỗi")
        for word in self._lookup(user).split():
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            yield word + " "

    def _lookup(self, user: str) -> str:
        lowered = user.lower()
        for key, value in self.responses.items():
            if key.lower() in lowered:
                return value
        return "Đây là câu trả lời mẫu từ FakeLlmClient dùng cho môi trường phát triển."

    def _classify(self, user: str) -> dict[str, Any]:
        lowered = self._ticket_text(user).lower()
        for keywords, result in KEYWORD_RULES:
            if any(k in lowered for k in keywords):
                return {**DEFAULT_CLASSIFICATION, **result,
                        "reasoning": f"Khớp từ khoá: {keywords[0]}"}
        return dict(DEFAULT_CLASSIFICATION)

    @staticmethod
    def _ticket_text(user: str) -> str:
        """Chỉ lấy phần NỘI DUNG TICKET, bỏ danh sách loại sự cố ở đầu prompt.

        ★ Không có bước này, mọi ticket đều bị phân loại là `network`: prompt
        phân loại luôn kèm danh sách category, trong đó có dòng
        "- network: Mạng & Internet", và từ khoá "mạng"/"internet" khớp ngay
        ở đó trước khi chạm tới mô tả thật của người dùng.

        Hậu quả không nhìn thấy trong test đơn lẻ nhưng rất rõ khi demo: mặc
        định `LLM_PROVIDER=fake`, nên đây chính là bộ não mà người xem nhìn
        thấy khi chưa cắm API key thật.
        """
        marker = "Tiêu đề:"
        index = user.rfind(marker)
        return user[index:] if index != -1 else user
