"""Embedding client thật, gọi API của nhà cung cấp.

Mọi lời gọi đều đi qua lớp chống chịu ở app/ai/resilience.py — timeout,
retry có jitter, circuit breaker. Không gọi thẳng HTTP ở đây.
"""

import time

import httpx

from app.ai.cost_guard import UsageRecord, cost_guard
from app.ai.llm.openai_client import _kiem_tra_phan_hoi
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
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.EMBEDDING_API_KEY or settings.LLM_API_KEY
        self._model = model or settings.EMBEDDING_MODEL
        self._base_url = (base_url or settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL).rstrip(
            "/"
        )
        self._breaker = CircuitBreaker(failure_threshold=5, recovery_seconds=60)

        if not self._api_key:
            raise ExternalServiceError(
                "Chưa cấu hình khoá cho embedding (EMBEDDING_API_KEY hoặc LLM_API_KEY). "
                "Đặt LLM_PROVIDER=fake để chạy không cần khoá."
            )

    @property
    def model_name(self) -> str:
        """★ Kèm host vào tên model, và giá trị này được ghi vào cột
        `article_chunks.embedding_model`.

        Vì sao không chỉ ghi tên model: `text-embedding-3-small` gọi qua
        OpenAI và gọi qua OpenRouter có thể ra vector khác nhau (khác phiên
        bản, khác nhà cung cấp phía sau). Ghi kèm host thì lúc đổi nhà cung
        cấp, `Retriever` nhận ra ngay là kho đang index bằng thứ khác và từ
        chối so sánh, thay vì trả về điểm tương đồng vô nghĩa.
        """
        host = self._base_url.split("//")[-1].split("/")[0]
        return f"{host}/{self._model}"

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
                _kiem_tra_phan_hoi(response, self._model, self._base_url)
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
    """Dựng chuỗi nhà cung cấp embedding. Mặc định fake — không cần khoá.

    ★ EMBEDDING PHẢI CẤU HÌNH RIÊNG KHỎI LLM. Ollama Cloud **không có model
    embedding nào** (lọc cloud+embedding trên ollama.com trả về rỗng), nên
    cấu hình phổ biến nhất của dự án này là: chat qua Ollama Cloud, embedding
    qua OpenRouter. Gộp chung một khoá thì hoặc chat hỏng, hoặc RAG hỏng.

    Dự phòng embedding CÓ nhưng nguy hiểm hơn dự phòng chat — xem cảnh báo ở
    `FailoverEmbeddingClient`. Lưới an toàn nằm ở `Retriever`.
    """
    if settings.LLM_PROVIDER == "fake":
        from app.ai.embedding.fake_embedding import FakeEmbeddingClient

        return FakeEmbeddingClient()

    from app.ai.failover import FailoverEmbeddingClient, NhaCungCap

    chinh = OpenAiEmbeddingClient()
    if not settings.LLM_FALLBACK_API_KEY:
        return chinh

    du_phong = OpenAiEmbeddingClient(
        api_key=settings.LLM_FALLBACK_API_KEY,
        base_url=settings.LLM_FALLBACK_BASE_URL or None,
    )
    return FailoverEmbeddingClient(
        [
            NhaCungCap(ten=chinh.model_name, client=chinh),
            NhaCungCap(ten=du_phong.model_name, client=du_phong),
        ]
    )
