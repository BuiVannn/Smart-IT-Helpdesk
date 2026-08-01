"""Interface cho LLM client.

Mọi thứ chạm ra ngoài tiến trình đều nằm sau một Protocol. Nhờ vậy test
dùng cài đặt giả (FakeLlmClient), KHÔNG cần API key và KHÔNG tốn tiền —
điều kiện bắt buộc để CI chạy được trên mọi PR.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class LlmResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    parsed: dict[str, Any] | None = None  # có giá trị khi dùng JSON schema


class LlmClient(Protocol):
    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.0,
    ) -> LlmResponse: ...

    async def stream(
        self, *, system: str, user: str, max_tokens: int = 800
    ) -> AsyncIterator[str]: ...
