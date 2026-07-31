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

KEYWORD_RULES: list[tuple[tuple[str, ...], dict[str, Any]]] = [
    (("wifi", "mạng", "internet", "vpn", "kết nối"),
     {"category_slug": "network", "priority": "HIGH", "confidence": 0.92}),
    (("mật khẩu", "password", "đăng nhập", "tài khoản"),
     {"category_slug": "account", "priority": "MEDIUM", "confidence": 0.88}),
    (("máy in", "màn hình", "chuột", "bàn phím", "laptop"),
     {"category_slug": "hardware", "priority": "MEDIUM", "confidence": 0.85}),
    (("phần mềm", "cài đặt", "office", "excel"),
     {"category_slug": "software", "priority": "LOW", "confidence": 0.80}),
    (("virus", "bảo mật", "lừa đảo", "phishing"),
     {"category_slug": "security", "priority": "URGENT", "confidence": 0.95}),
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
        self.call_count = 0
        self.last_prompt: str = ""

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.0,
    ) -> LlmResponse:
        self.call_count += 1
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
        self.call_count += 1
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
        lowered = user.lower()
        for keywords, result in KEYWORD_RULES:
            if any(k in lowered for k in keywords):
                return {**DEFAULT_CLASSIFICATION, **result,
                        "reasoning": f"Khớp từ khoá: {keywords[0]}"}
        return dict(DEFAULT_CLASSIFICATION)
