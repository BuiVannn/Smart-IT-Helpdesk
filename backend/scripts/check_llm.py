"""Kiểm tra nhà cung cấp LLM và embedding có THẬT SỰ hoạt động không.

    python scripts/check_llm.py              # kiểm tra theo .env hiện tại
    python scripts/check_llm.py --models     # kèm danh sách model khả dụng

VÌ SAO CẦN SCRIPT NÀY thay vì "cắm khoá rồi chạy thử ứng dụng": độ phủ test
của đường LLM thật chỉ 24% vì toàn bộ test chạy `LLM_PROVIDER=fake`. Lần đầu
cắm khoá rất có thể là lần đầu đoạn code đó được thực thi. Phát hiện sai cấu
hình ở đây tốn 10 giây; phát hiện lúc demo tốn cả buổi.

Script gọi API THẬT nên có tốn một lượng token rất nhỏ (một câu phân loại và
một câu embedding).
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.ai.embedding.openai_embedding import build_embedding_client  # noqa: E402
from app.ai.llm.openai_client import build_llm_client  # noqa: E402
from app.core.config import settings  # noqa: E402

CAU_HOI_THU = "Máy in tầng 3 bị kẹt giấy, in mãi không ra"
SCHEMA_THU = {
    "type": "object",
    "properties": {
        "category_slug": {"type": "string"},
        "priority": {"type": "string"},
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["category_slug", "priority", "confidence", "reasoning"],
    "additionalProperties": False,
}


def dong(nhan: str, gia_tri: str) -> None:
    print(f"  {nhan:26s} {gia_tri}")


def in_cau_hinh() -> None:
    print("\n── Cấu hình đang dùng ──")
    dong("LLM_PROVIDER", settings.LLM_PROVIDER)
    dong("LLM_BASE_URL", settings.LLM_BASE_URL)
    dong("LLM_MODEL", settings.LLM_MODEL)
    dong("LLM_API_KEY", "(đã đặt)" if settings.LLM_API_KEY else "(TRỐNG)")
    dong("LLM_JSON_MODE", settings.LLM_JSON_MODE)
    print()
    co_du_phong = bool(settings.LLM_FALLBACK_API_KEY)
    dong("Dự phòng", "có" if co_du_phong else "KHÔNG — chỉ một nhà cung cấp")
    if co_du_phong:
        dong("  base URL", settings.LLM_FALLBACK_BASE_URL or "(dùng lại của chính)")
        dong("  model", settings.LLM_FALLBACK_MODEL or "(dùng lại của chính)")
    print()
    dong("EMBEDDING_BASE_URL", settings.EMBEDDING_BASE_URL or "(dùng lại của LLM)")
    dong("EMBEDDING_MODEL", settings.EMBEDDING_MODEL)
    dong("EMBEDDING_DIMENSIONS", str(settings.EMBEDDING_DIMENSIONS))


def liet_ke_model(base_url: str, api_key: str, ten: str) -> None:
    """Gọi `/v1/models` — cách duy nhất đáng tin để biết tên model nào còn sống.

    ★ Danh sách model miễn phí thay đổi liên tục: OpenRouter rút từ 20 xuống
    15 endpoint `:free` trong chín ngày (tháng 7/2026), xoá hẳn tầng Llama và
    Qwen. Cứng hoá tên model trong tài liệu là cách chắc chắn để một ngày nào
    đó hệ thống chết mà không ai hiểu vì sao.
    """
    print(f"\n── Model khả dụng tại {ten} ──")
    if not api_key:
        print("  (bỏ qua — chưa có khoá)")
        return
    try:
        res = httpx.get(
            f"{base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20,
        )
        res.raise_for_status()
        ids = sorted(m["id"] for m in res.json().get("data", []))
    except Exception as exc:
        print(f"  ✗ không lấy được: {type(exc).__name__}: {exc}")
        return

    print(f"  {len(ids)} model. Vài cái đầu:")
    for mid in ids[:15]:
        print(f"    {mid}")
    if len(ids) > 15:
        print(f"    … còn {len(ids) - 15} model nữa")


async def thu_phan_loai() -> bool:
    print("\n── Thử phân loại thật (US-19) ──")
    if settings.LLM_PROVIDER == "fake":
        print("  ⚠ LLM_PROVIDER=fake — đang đo FakeLlmClient, KHÔNG phải model thật.")

    client = build_llm_client()
    dong("Chuỗi nhà cung cấp", ", ".join(getattr(client, "ten_cac_nha_cung_cap", ["(đơn lẻ)"])))

    bat_dau = time.perf_counter()
    try:
        res = await client.complete(
            system="Bạn phân loại ticket hỗ trợ IT. Chỉ trả về JSON.",
            user=(
                "Loại hợp lệ: network, hardware, software, account, access, "
                "email, security, other.\n"
                "Mức ưu tiên hợp lệ: LOW, MEDIUM, HIGH, URGENT.\n"
                f"Tiêu đề: {CAU_HOI_THU}"
            ),
            schema=SCHEMA_THU,
        )
    except Exception as exc:
        print(f"  ✗ HỎNG: {type(exc).__name__}: {exc}")
        return False

    do_tre = round((time.perf_counter() - bat_dau) * 1000)
    dong("Model trả lời", res.model)
    dong("Độ trễ", f"{do_tre} ms")
    dong("Token vào/ra", f"{res.prompt_tokens}/{res.completion_tokens}")
    dong("Kết quả", str(res.parsed))

    if not res.parsed or "category_slug" not in res.parsed:
        print("  ✗ Model không trả về JSON đúng cấu trúc — thử đổi LLM_JSON_MODE")
        return False
    print("  ✓ Phân loại hoạt động")
    return True


async def thu_embedding() -> bool:
    print("\n── Thử embedding thật (F4/RAG) ──")
    client = build_embedding_client()

    bat_dau = time.perf_counter()
    try:
        vectors = await client.embed([CAU_HOI_THU, "Hướng dẫn đổi mật khẩu email"])
    except Exception as exc:
        print(f"  ✗ HỎNG: {type(exc).__name__}: {exc}")
        if settings.LLM_BASE_URL.startswith("https://ollama.com"):
            print(
                "  ⚠ Ollama Cloud KHÔNG có model embedding nào. Trỏ EMBEDDING_BASE_URL\n"
                "    sang OpenRouter (https://openrouter.ai/api/v1) hoặc Ollama chạy máy."
            )
        return False

    do_tre = round((time.perf_counter() - bat_dau) * 1000)
    so_chieu = len(vectors[0])
    dong("Model", client.model_name)
    dong("Độ trễ", f"{do_tre} ms")
    dong("Số chiều thực tế", str(so_chieu))
    dong("Số chiều cấu hình", str(settings.EMBEDDING_DIMENSIONS))

    if so_chieu != settings.EMBEDDING_DIMENSIONS:
        print(
            f"  ✗ LỆCH SỐ CHIỀU. Cột `article_chunks.embedding` là vector"
            f"({settings.EMBEDDING_DIMENSIONS}); mọi lệnh index sẽ lỗi.\n"
            f"    Sửa EMBEDDING_DIMENSIONS={so_chieu} rồi tạo migration đổi kiểu cột."
        )
        return False

    # Kiểm tra nhanh vector có mang ngữ nghĩa không — hai câu không liên quan
    # mà giống nhau tuyệt đối nghĩa là nhà cung cấp trả về rác.
    tich = sum(a * b for a, b in zip(vectors[0], vectors[1], strict=True))
    dong("Tương đồng hai câu khác chủ đề", f"{tich:.4f}")
    print("  ✓ Embedding hoạt động")
    return True


def canh_bao_reindex() -> None:
    print("\n── Nhắc bắt buộc ──")
    print(
        "  Sau khi ĐỔI nhà cung cấp hoặc model embedding, phải chạy lại:\n"
        "      python scripts/reindex_kb.py --all\n"
        "  Vector của hai model khác nhau KHÔNG so sánh được. Retriever lọc chunk\n"
        "  theo `embedding_model` nên nếu quên, chatbot sẽ trả lời 'không tìm thấy\n"
        "  tài liệu' thay vì bịa — an toàn, nhưng RAG coi như không hoạt động."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Kiểm tra LLM và embedding có chạy thật không")
    parser.add_argument("--models", action="store_true", help="Liệt kê model khả dụng")
    args = parser.parse_args()

    in_cau_hinh()

    if args.models:
        liet_ke_model(settings.LLM_BASE_URL, settings.LLM_API_KEY, "nhà cung cấp CHÍNH")
        if settings.LLM_FALLBACK_API_KEY:
            liet_ke_model(
                settings.LLM_FALLBACK_BASE_URL or settings.LLM_BASE_URL,
                settings.LLM_FALLBACK_API_KEY,
                "nhà cung cấp DỰ PHÒNG",
            )

    ok_llm = asyncio.run(thu_phan_loai())
    ok_embed = asyncio.run(thu_embedding())
    canh_bao_reindex()

    print()
    if ok_llm and ok_embed:
        print("KẾT LUẬN: cả LLM và embedding đều hoạt động.\n")
        sys.exit(0)
    print("KẾT LUẬN: CÓ THÀNH PHẦN KHÔNG HOẠT ĐỘNG — xem chi tiết ở trên.\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
