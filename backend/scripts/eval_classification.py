"""Chạy tập đánh giá phân loại (docs/design/07 §5.1).

    python scripts/eval_classification.py                  # dùng LLM theo cấu hình
    python scripts/eval_classification.py --rules-only     # chỉ đo đường dự phòng
    python scripts/eval_classification.py --difficulty tricky

KHÔNG CÓ TẬP ĐÁNH GIÁ THÌ MỌI THAY ĐỔI PROMPT CHỈ LÀ CẢM TÍNH. Quy trình bắt
buộc mỗi lần sửa `app/modules/tickets/prompts.py`:

    1. Chạy script này, ghi lại số
    2. Sửa prompt, tăng `CLASSIFY_PROMPT_VERSION`
    3. Chạy lại, so sánh
    4. Ghi kết quả vào bảng lịch sử ở cuối `prompts.py`

Mục tiêu (docs/design/07 §5.1):
    - Độ chính xác category      >= 70%
    - Độ chính xác priority ±1   >= 80%
    - Hiệu chỉnh độ tin cậy      confidence khi ĐÚNG phải cao hơn khi SAI
    - Độ trễ p95                 < 10 giây

Script KHÔNG tạo ticket nào trong database — nó chỉ đọc danh sách loại sự cố.
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.llm.fake_client import FakeLlmClient  # noqa: E402
from app.ai.llm.openai_client import build_llm_client  # noqa: E402
from app.ai.resilience import RetryConfig  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db import all_models  # noqa: E402,F401  — nạp đủ mapper cho khoá ngoại
from app.db.session import session_scope  # noqa: E402
from app.modules.tickets.classifier import (  # noqa: E402
    ClassificationSource,
    RuleBasedClassifier,
    TicketClassifier,
)
from app.modules.tickets.constants import TicketPriority  # noqa: E402
from app.modules.tickets.prompts import CLASSIFY_PROMPT_VERSION  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "tests/fixtures/classification_eval.jsonl"

# Thang bậc để tính "sai một bậc" — LOW và MEDIUM lệch nhau 1, LOW và URGENT lệch 3.
PRIORITY_RANK = {
    TicketPriority.LOW: 0,
    TicketPriority.MEDIUM: 1,
    TicketPriority.HIGH: 2,
    TicketPriority.URGENT: 3,
}

TARGETS = {
    "category": 0.70,
    "priority_within_1": 0.80,
    "latency_p95_seconds": 10.0,
}


class RulesOnlyLlm:
    """LLM luôn hỏng ⇒ ép TicketClassifier rơi xuống RuleBasedClassifier.

    Đo riêng đường dự phòng là việc đáng làm: đó là thứ chạy khi hết hạn mức
    miễn phí của nhà cung cấp, và là thứ dùng để demo khi không có API key.
    """

    @property
    def model_name(self) -> str:
        return "rule-based"

    async def complete(self, **_):
        raise ConnectionError("bỏ qua LLM theo yêu cầu --rules-only")

    async def stream(self, **_):  # pragma: no cover
        raise NotImplementedError
        yield ""


def load_cases(difficulty: str | None) -> list[dict]:
    if not FIXTURE.exists():
        sys.exit(f"Không tìm thấy tập đánh giá: {FIXTURE}")
    cases = [json.loads(line) for line in FIXTURE.read_text("utf-8").splitlines() if line.strip()]
    if difficulty:
        cases = [c for c in cases if c.get("difficulty") == difficulty]
    if not cases:
        sys.exit(f"Không có ca nào khớp difficulty={difficulty!r}")
    return cases


async def run(cases: list[dict], rules_only: bool) -> list[dict]:
    llm = RulesOnlyLlm() if rules_only else build_llm_client()
    # `--rules-only` biết chắc LLM sẽ hỏng, nên đừng đi qua vòng thử lại: ba
    # lần thử với backoff 2s + 6s là 8 giây MỖI CA, tức hơn sáu phút cho 50
    # ca. Một tập đánh giá chạy sáu phút là tập đánh giá không ai chạy.
    retry = RetryConfig(max_attempts=1) if rules_only else None
    results: list[dict] = []

    with session_scope() as db:
        classifier = TicketClassifier(db, llm, rules=RuleBasedClassifier(), retry=retry)

        for case in cases:
            started = time.perf_counter()
            suggestion, error = await classifier.suggest(case["title"], case["description"])
            elapsed = time.perf_counter() - started

            expected_priority = TicketPriority(case["expect_priority"])
            got_priority = suggestion.priority if suggestion else None

            results.append({
                "id": case["id"],
                "difficulty": case.get("difficulty", "clear"),
                "expected_category": case["expect_category"],
                "got_category": suggestion.category_slug if suggestion else None,
                "category_ok": bool(suggestion and suggestion.category_slug == case["expect_category"]),
                "expected_priority": expected_priority,
                "got_priority": got_priority,
                "priority_ok": got_priority == expected_priority,
                "priority_gap": (
                    abs(PRIORITY_RANK[got_priority] - PRIORITY_RANK[expected_priority])
                    if got_priority else None
                ),
                "confidence": suggestion.confidence if suggestion else None,
                "source": str(suggestion.source) if suggestion else None,
                "seconds": elapsed,
                "error": error,
            })

    return results


def report(results: list[dict]) -> bool:
    total = len(results)
    category_ok = sum(r["category_ok"] for r in results)
    priority_exact = sum(r["priority_ok"] for r in results)
    priority_near = sum(1 for r in results if r["priority_gap"] is not None and r["priority_gap"] <= 1)
    latencies = sorted(r["seconds"] for r in results)
    p95 = latencies[min(int(len(latencies) * 0.95), len(latencies) - 1)]

    print(f"\n{'═' * 68}")
    print(f"TẬP ĐÁNH GIÁ PHÂN LOẠI — {total} ca · prompt {CLASSIFY_PROMPT_VERSION}")
    print(f"Nhà cung cấp LLM: {settings.LLM_PROVIDER} · model {settings.LLM_MODEL}")
    print("═" * 68)

    rows = [
        ("Độ chính xác category", category_ok / total, TARGETS["category"]),
        ("Độ chính xác priority (chính xác)", priority_exact / total, None),
        ("Độ chính xác priority (±1 bậc)", priority_near / total, TARGETS["priority_within_1"]),
    ]
    for label, value, target in rows:
        mark = "" if target is None else ("  ✓" if value >= target else "  ✗ DƯỚI MỤC TIÊU")
        target_text = "" if target is None else f"  (mục tiêu {target:.0%})"
        print(f"{label:38s} {value:6.1%}{target_text}{mark}")

    latency_mark = "  ✓" if p95 < TARGETS["latency_p95_seconds"] else "  ✗ VƯỢT MỤC TIÊU"
    print(f"{'Độ trễ p95':38s} {p95:6.2f}s  (mục tiêu < 10s){latency_mark}")

    # ── Hiệu chỉnh độ tin cậy ──
    # Nếu ca sai lại tự tin ngang ca đúng thì ngưỡng 0,6 không lọc được gì —
    # đây là chỉ số dễ bị bỏ qua nhất mà lại quyết định toàn bộ tầng
    # LOW_CONFIDENCE có tác dụng hay không.
    right = [r["confidence"] for r in results if r["category_ok"] and r["confidence"] is not None]
    wrong = [r["confidence"] for r in results if not r["category_ok"] and r["confidence"] is not None]
    calibrated = True
    if right and wrong:
        mean_right, mean_wrong = statistics.mean(right), statistics.mean(wrong)
        if len(set(right) | set(wrong)) == 1:
            # Đường dự phòng đối chiếu từ khoá trả confidence CỐ ĐỊNH 0,4 theo
            # thiết kế, nên không có gì để hiệu chỉnh. Chấm nó "trượt" ở đây là
            # báo động giả, và báo động giả lặp lại thì không ai đọc báo cáo nữa.
            print(f"{'Hiệu chỉnh độ tin cậy':38s} không áp dụng (confidence cố định)")
        else:
            calibrated = mean_right > mean_wrong
            mark = "  ✓" if calibrated else "  ✗ NGƯỠNG 0,6 VÔ NGHĨA"
            print(
                f"{'Confidence khi ĐÚNG / khi SAI':38s} "
                f"{mean_right:.2f} / {mean_wrong:.2f}{mark}"
            )
    elif not wrong:
        print(f"{'Confidence khi ĐÚNG / khi SAI':38s} không có ca sai để so sánh")

    # ── Chia theo độ khó ──
    print(f"\n{'Theo độ khó':38s} {'đúng':>6s} {'tổng':>6s}")
    for level in ("clear", "ambiguous", "tricky"):
        subset = [r for r in results if r["difficulty"] == level]
        if subset:
            ok = sum(r["category_ok"] for r in subset)
            print(f"{'  ' + level:38s} {ok:6d} {len(subset):6d}")

    # ── Ca sai ──
    failures = [r for r in results if not r["category_ok"]]
    if failures:
        print(f"\nCÁC CA SAI ({len(failures)}):")
        for r in failures:
            conf = f"{r['confidence']:.2f}" if r["confidence"] is not None else "—"
            print(
                f"  {r['id']:8s} mong đợi {r['expected_category']:9s} "
                f"nhận {str(r['got_category']):9s} conf {conf}"
                + (f"  [{r['error'][:40]}]" if r["error"] else "")
            )

    fallbacks = sum(1 for r in results if r["source"] == str(ClassificationSource.RULES))
    if fallbacks:
        print(f"\n{fallbacks}/{total} ca phải dùng đường dự phòng đối chiếu từ khoá.")

    passed = (
        category_ok / total >= TARGETS["category"]
        and priority_near / total >= TARGETS["priority_within_1"]
        and p95 < TARGETS["latency_p95_seconds"]
        and calibrated
    )
    print(f"\n{'KẾT LUẬN: ĐẠT' if passed else 'KẾT LUẬN: CHƯA ĐẠT MỤC TIÊU'}\n")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Đánh giá chất lượng phân loại ticket")
    parser.add_argument("--rules-only", action="store_true",
                        help="Bỏ qua LLM, chỉ đo đường dự phòng đối chiếu từ khoá")
    parser.add_argument("--difficulty", choices=["clear", "ambiguous", "tricky"],
                        help="Chỉ chạy các ca thuộc một mức độ khó")
    args = parser.parse_args()

    if not args.rules_only and settings.LLM_PROVIDER == "fake":
        print(
            "⚠  LLM_PROVIDER=fake — đang đo FakeLlmClient, KHÔNG phải model thật.\n"
            "   Con số dưới đây không dùng để kết luận về chất lượng prompt.\n"
        )

    cases = load_cases(args.difficulty)
    results = asyncio.run(run(cases, args.rules_only))
    # Mã thoát khác 0 để CI dùng được script này như một cổng chất lượng.
    sys.exit(0 if report(results) else 1)


if __name__ == "__main__":
    main()
