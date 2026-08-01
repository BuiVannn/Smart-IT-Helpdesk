"""Embedding client thật, gọi API của nhà cung cấp.

Mọi lời gọi đều đi qua lớp chống chịu ở app/ai/resilience.py — timeout,
retry có jitter, circuit breaker. Không gọi thẳng HTTP ở đây.
"""

import time

import httpx

from app.ai.cost_guard import UsageRecord, cost_guard
from app.ai.resilience import CircuitBreaker, RetryConfig, with_retry
from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Gửi theo lô để giảm số lời gọi mạng. 32 là mức an toàn với hầu hết provider.
BATCH_SIZE = 32


class OpenAiEmbeddingClient:
    """Cài đặt EmbeddingClient dùng API tương thích OpenAI."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._api_key = api_key or settings.LLM_API_KEY
        self._model = model or settings.EMBEDDING_MODEL
        self._base_url = base_url.rstrip("/")
        self._breaker = CircuitBreaker(failure_threshold=5, recovery_seconds=60)

        if not self._api_key:
            raise ExternalServiceError(
                "Chưa cấu hình LLM_API_KEY. Đặt LLM_PROVIDER=fake để chạy không cần khoá."
            )

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return settings.EMBEDDING_DIMENSIONS

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Sinh embedding cho danh sách văn bản, giữ nguyên thứ tự đầu vào."""
        if not texts:
            return []

        cost_guard.check_budget()
        vectors: list[list[float]] = []

        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            vectors.extend(await self._embed_batch(batch))

        return vectors

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        async def _call() -> list[list[float]]:
            started = time.perf_counter()
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_EMBED) as client:
                response = await client.post(
                    f"{self._base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"model": self._model, "input": batch},
                )
                if response.status_code == 429:
                    raise ConnectionError("Provider giới hạn tốc độ (429)")
                if response.status_code >= 500:
                    raise ConnectionError(f"Provider lỗi {response.status_code}")
                response.raise_for_status()
                payload = response.json()

            usage = payload.get("usage", {})
            cost_guard.record(
                UsageRecord(
                    model=self._model,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=0,
                )
            )
            logger.info(
                "embedding batch xong",
                extra={
                    "extra_fields": {
                        "count": len(batch),
                        "latency_ms": round((time.perf_counter() - started) * 1000),
                    }
                },
            )

            # API không bảo đảm thứ tự trả về ⇒ sắp lại theo index
            items = sorted(payload["data"], key=lambda d: d["index"])
            return [item["embedding"] for item in items]

        return await self._breaker.call(
            lambda: with_retry(_call, RetryConfig(max_attempts=3), operation="embed"),
            operation="embed",
        )


def build_embedding_client():
    """Chọn cài đặt theo cấu hình. Mặc định là fake — không cần API key."""
    if settings.LLM_PROVIDER == "fake":
        from app.ai.embedding.fake_embedding import FakeEmbeddingClient

        return FakeEmbeddingClient()
    return OpenAiEmbeddingClient()
