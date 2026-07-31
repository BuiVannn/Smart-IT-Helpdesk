"""Embedding giả — sinh vector TẤT ĐỊNH từ hash của văn bản.

Cùng một văn bản luôn cho cùng một vector, và văn bản giống nhau cho
vector gần nhau. Đủ để test toàn bộ luồng RAG mà không cần API key.
"""

import hashlib
import math

from app.core.config import settings


class FakeEmbeddingClient:
    def __init__(self, dimensions: int | None = None) -> None:
        self._dimensions = dimensions or settings.EMBEDDING_DIMENSIONS

    @property
    def model_name(self) -> str:
        return "fake-embedding"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.lower().encode()).digest()
        raw = [(digest[i % len(digest)] - 128) / 128.0 for i in range(self._dimensions)]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]   # chuẩn hoá để cosine similarity có ý nghĩa
