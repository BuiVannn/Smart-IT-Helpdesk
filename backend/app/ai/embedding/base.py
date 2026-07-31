"""Interface cho embedding client."""

from typing import Protocol


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def model_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...
