"""LLM client thật, gọi API tương thích OpenAI.

Mọi lời gọi đi qua lớp chống chịu: timeout, retry có jitter, circuit breaker.
Không gọi thẳng HTTP ở đây.
"""

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.ai.cost_guard import UsageRecord, cost_guard
from app.ai.llm.base import LlmResponse
from app.ai.resilience import CircuitBreaker, RetryConfig, with_retry
from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAiLlmClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._api_key = api_key or settings.LLM_API_KEY
        self._model = model or settings.LLM_MODEL
        self._base_url = base_url.rstrip("/")
        self._breaker = CircuitBreaker(failure_threshold=5, recovery_seconds=60)

        if not self._api_key:
            raise ExternalServiceError(
                "Chưa cấu hình LLM_API_KEY. Đặt LLM_PROVIDER=fake để chạy không cần khoá."
            )

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.0,
    ) -> LlmResponse:
        cost_guard.check_budget()

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if schema is not None:
            # Ràng buộc đầu ra bằng JSON schema thay vì phân tích văn bản tự do:
            # model buộc phải trả đúng cấu trúc, tầng gọi không phải viết parser mong manh.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "result", "strict": True, "schema": schema},
            }

        async def _call() -> LlmResponse:
            started = time.perf_counter()
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_CLASSIFY) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                if response.status_code == 429:
                    raise ConnectionError("Provider giới hạn tốc độ (429)")
                if response.status_code >= 500:
                    raise ConnectionError(f"Provider lỗi {response.status_code}")
                response.raise_for_status()
                body = response.json()

            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})
            latency = round((time.perf_counter() - started) * 1000)

            cost_guard.record(UsageRecord(
                model=self._model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            ))

            parsed: dict[str, Any] | None = None
            if schema is not None:
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as exc:
                    # Không tin đầu ra của LLM — JSON hỏng coi như lời gọi thất bại
                    raise ExternalServiceError("LLM trả về JSON không hợp lệ") from exc

            return LlmResponse(
                content=content,
                model=self._model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                latency_ms=latency,
                parsed=parsed,
            )

        return await self._breaker.call(
            lambda: with_retry(_call, RetryConfig(max_attempts=3), operation="llm.complete"),
            operation="llm.complete",
        )

    async def stream(
        self, *, system: str, user: str, max_tokens: int = 800
    ) -> AsyncIterator[str]:
        """Sinh câu trả lời theo luồng — người dùng thấy token đầu tiên < 3 giây.

        KHÔNG retry ở đây: một khi đã bắt đầu stream mà lỗi giữa chừng thì
        thử lại sẽ khiến người dùng thấy câu trả lời bị lặp lại từ đầu.
        """
        cost_guard.check_budget()

        if self._breaker.is_open:
            raise ExternalServiceError("Trợ lý ảo đang tạm ngưng do lỗi liên tục, thử lại sau")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "stream": True,
        }

        try:
            async with (
                httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_CHAT) as client,
                client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0]["delta"]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if content := delta.get("content"):
                        yield content
        except Exception as exc:
            self._breaker.record_failure()
            raise ExternalServiceError(f"Lỗi khi sinh câu trả lời: {type(exc).__name__}") from exc
        else:
            self._breaker.record_success()


def build_llm_client():
    """Chọn cài đặt theo cấu hình. Mặc định là fake — không cần API key."""
    if settings.LLM_PROVIDER == "fake":
        from app.ai.llm.fake_client import FakeLlmClient

        return FakeLlmClient()
    return OpenAiLlmClient()
