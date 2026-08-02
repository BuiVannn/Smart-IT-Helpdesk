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
from app.core.exceptions import ExternalServiceError, RateLimitedError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _kiem_tra_phan_hoi(response, model: str, base_url: str) -> None:
    """Dịch mã HTTP sang lỗi mà lớp chuyển dự phòng hiểu được.

    ★ 400/401/403/404 CŨNG PHẢI CHO CHUYỂN NHÀ CUNG CẤP. Với nhà cung cấp
    miễn phí, nguyên nhân phổ biến nhất của bốn mã này không phải là prompt
    sai mà là: khoá hết hạn, model bị gỡ khỏi danh sách free, hoặc nhà cung
    cấp không hiểu `response_format` mình gửi. Cả ba đều được giải quyết bằng
    cách sang chỗ khác, còn dừng lại thì cả tính năng chết.

    Kèm nguyên văn phần đầu phản hồi vào thông điệp: không có nó thì "400 Bad
    Request" là một câu vô nghĩa và người sửa phải đoán.
    """
    if response.status_code < 400:
        return

    chi_tiet = response.text[:300].replace("\n", " ")

    if response.status_code == 429:
        # KHÔNG dùng ConnectionError ở đây: nó nằm trong `RETRYABLE` nên sẽ bị
        # thử lại ba lần với chính nhà cung cấp vừa nói "hết hạn mức".
        raise RateLimitedError(f"Nhà cung cấp giới hạn tốc độ (429) — {chi_tiet}")
    if response.status_code >= 500:
        raise ConnectionError(f"Nhà cung cấp lỗi {response.status_code} — {chi_tiet}")

    raise ExternalServiceError(
        f"Nhà cung cấp từ chối ({response.status_code}) tại {base_url} "
        f"với model {model!r} — {chi_tiet}"
    )


def _lay_noi_dung(body: dict, model: str) -> str:
    """Lấy phần trả lời, chịu được cả MODEL SUY LUẬN.

    ★ VẤN ĐỀ ĐÃ ĐO ĐƯỢC. `nemotron-3-nano:30b` và `gpt-oss` là model suy luận:
    chúng viết quá trình suy nghĩ vào trường phi chuẩn `message.reasoning`
    TRƯỚC, rồi mới viết câu trả lời vào `message.content`. Nếu `max_tokens`
    hết trong lúc còn đang suy luận thì `content` về RỖNG trong khi HTTP vẫn
    200 và `finish_reason` vẫn là `stop` — nhìn mọi dấu hiệu đều như thành
    công. Hậu quả: `json.loads("")` nổ, `_validate()` loại kết quả, và mọi
    ticket lặng lẽ rơi xuống tầng luật dự phòng.

    Ưu tiên `content`; chỉ mượn `reasoning` khi `content` rỗng, vì `reasoning`
    là văn xuôi tự do chứ không phải câu trả lời đã định dạng.
    """
    message = body["choices"][0]["message"]
    content = (message.get("content") or "").strip()
    if content:
        return content

    du_phong = (message.get("reasoning") or "").strip()
    if du_phong:
        logger.warning(
            "model trả `content` rỗng, dùng tạm `reasoning` — hãy tăng max_tokens",
            extra={"extra_fields": {"model": model, "reasoning_len": len(du_phong)}},
        )
        return du_phong

    raise ExternalServiceError(
        f"Model {model!r} trả về nội dung rỗng "
        f"(finish_reason={body['choices'][0].get('finish_reason')!r}). "
        "Với model suy luận, thường là do max_tokens quá nhỏ."
    )


def _go_rao_markdown(content: str) -> str:
    """Gỡ rào ```json ... ``` quanh phần JSON.

    Model mở rất hay bọc JSON trong rào markdown dù đã được dặn không. Với
    `LLM_JSON_MODE=none` thì gần như chắc chắn. Gỡ ở đây rẻ hơn nhiều so với
    việc cả đường phân loại hỏng vì ba dấu backtick.
    """
    text = content.strip()
    if not text.startswith("```"):
        return text

    text = text[3:]
    if text[:4].lower() == "json":
        text = text[4:]
    return text.rsplit("```", 1)[0].strip() if "```" in text else text.strip()


class OpenAiLlmClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        json_mode: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.LLM_API_KEY
        self._model = model or settings.LLM_MODEL
        self._base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self._json_mode = json_mode or settings.LLM_JSON_MODE
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
            # Ràng buộc đầu ra bằng JSON thay vì phân tích văn bản tự do.
            #
            # ★ `json_schema` là đặc sản của OpenAI. Ollama Cloud và phần lớn
            # model mở chỉ hiểu `json_object`; gửi `json_schema` cho chúng là
            # nhận 400 và cả đường phân loại chết. Vì vậy cách ràng buộc là
            # CẤU HÌNH, không phải hằng số — xem `LLM_JSON_MODE`.
            #
            # Dùng `json_object` hoặc `none` vẫn an toàn vì
            # `TicketClassifier._validate()` từ chối slug lạ, priority sai và
            # confidence ngoài [0,1] — đầu ra của model không bao giờ được tin.
            if self._json_mode == "json_schema":
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "result", "strict": True, "schema": schema},
                }
            elif self._json_mode == "json_object":
                payload["response_format"] = {"type": "json_object"}

        async def _call() -> LlmResponse:
            started = time.perf_counter()
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_CLASSIFY) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                _kiem_tra_phan_hoi(response, self._model, self._base_url)
                body = response.json()

            content = _lay_noi_dung(body, self._model)
            usage = body.get("usage", {})
            latency = round((time.perf_counter() - started) * 1000)

            cost_guard.record(
                UsageRecord(
                    model=self._model,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                )
            )

            parsed: dict[str, Any] | None = None
            if schema is not None:
                try:
                    parsed = json.loads(_go_rao_markdown(content))
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

    async def stream(self, *, system: str, user: str, max_tokens: int = 800) -> AsyncIterator[str]:
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
                _kiem_tra_phan_hoi(response, self._model, self._base_url)
                da_ket_thuc_dung_cach = False
                da_phat_chu_nao = False

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        da_ket_thuc_dung_cach = True
                        break
                    try:
                        delta = json.loads(data)["choices"][0]["delta"]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if content := delta.get("content"):
                        da_phat_chu_nao = True
                        yield content

            # ★ Nhà cung cấp chết GIỮA CHỪNG thì kết nối đóng êm và vòng lặp
            # trên kết thúc bình thường — người dùng nhận một câu trả lời CỤT
            # mà không có lỗi nào. Không thể thử lại (sẽ viết lại từ đầu giữa
            # màn hình) và không thể chuyển nhà cung cấp, nên thứ duy nhất làm
            # được là ghi lại để người vận hành biết chuyện đã xảy ra.
            if da_phat_chu_nao and not da_ket_thuc_dung_cach:
                logger.warning(
                    "luồng trả lời kết thúc mà KHÔNG có [DONE] — câu trả lời có thể bị cụt",
                    extra={"extra_fields": {"provider": self._base_url, "model": self._model}},
                )
        except Exception as exc:
            self._breaker.record_failure()
            raise ExternalServiceError(f"Lỗi khi sinh câu trả lời: {type(exc).__name__}") from exc
        else:
            self._breaker.record_success()


def build_llm_client():
    """Dựng chuỗi nhà cung cấp theo cấu hình. Mặc định fake — không cần khoá.

    Trả về `FailoverLlmClient` khi có cấu hình dự phòng, còn không thì trả
    thẳng client đơn — không bọc thừa một lớp chỉ để chứa đúng một phần tử.
    """
    if settings.LLM_PROVIDER == "fake":
        from app.ai.llm.fake_client import FakeLlmClient

        return FakeLlmClient()

    from app.ai.failover import FailoverLlmClient, NhaCungCap

    chinh = OpenAiLlmClient()
    if not settings.LLM_FALLBACK_API_KEY:
        logger.info(
            "LLM chạy một nhà cung cấp duy nhất, không có dự phòng",
            extra={"extra_fields": {"base_url": settings.LLM_BASE_URL}},
        )
        return chinh

    du_phong = OpenAiLlmClient(
        api_key=settings.LLM_FALLBACK_API_KEY,
        model=settings.LLM_FALLBACK_MODEL or settings.LLM_MODEL,
        base_url=settings.LLM_FALLBACK_BASE_URL or settings.LLM_BASE_URL,
    )
    logger.info(
        "LLM có dự phòng",
        extra={
            "extra_fields": {
                "chinh": f"{settings.LLM_BASE_URL} · {settings.LLM_MODEL}",
                "du_phong": f"{settings.LLM_FALLBACK_BASE_URL} · {settings.LLM_FALLBACK_MODEL}",
            }
        },
    )
    return FailoverLlmClient(
        [
            NhaCungCap(ten=_ten_gon(settings.LLM_BASE_URL), client=chinh),
            NhaCungCap(ten=_ten_gon(settings.LLM_FALLBACK_BASE_URL), client=du_phong),
        ]
    )


def _ten_gon(base_url: str) -> str:
    """Tên đọc được cho log: `https://openrouter.ai/api/v1` -> `openrouter.ai`."""
    return base_url.split("//")[-1].split("/")[0] or base_url
