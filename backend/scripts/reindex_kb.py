"""Dựng lại chỉ mục RAG từ bài viết trong database.

★ ĐÂY LÀ ĐƯỜNG PHỤC HỒI BẮT BUỘC của hệ thống RAG. Phải chạy thử thành công
ít nhất một lần trước khi demo — một đường phục hồi chưa từng chạy thì không
tồn tại.

Dùng:
    python scripts/reindex_kb.py --all        # index lại TẤT CẢ bài PUBLISHED
    python scripts/reindex_kb.py --stale      # chỉ index bài chưa/cũ hơn nội dung
    python scripts/reindex_kb.py --slug xyz   # index một bài cụ thể
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.ai.embedding.openai_embedding import build_embedding_client  # noqa: E402
from app.core.config import settings  # noqa: E402
# Nạp TOÀN BỘ model để SQLAlchemy phân giải được mọi quan hệ khoá ngoại.
# Thiếu dòng này, script chỉ import một vài model sẽ lỗi
# "could not find table 'users'" khi model đó có FK tới bảng khác.
from app.db import all_models  # noqa: E402,F401
from app.db.session import session_scope  # noqa: E402
from app.modules.knowledge.indexing import IndexingService  # noqa: E402
from app.modules.knowledge.models import KbArticle  # noqa: E402


async def run(mode: str, slug: str | None) -> int:
    with session_scope() as db:
        service = IndexingService(db, build_embedding_client())
        print(f"Provider embedding: {settings.LLM_PROVIDER} · model: {service.embedding.model_name}")

        if mode == "slug":
            article = db.execute(
                select(KbArticle).where(KbArticle.slug == slug)
            ).scalar_one_or_none()
            if article is None:
                print(f"✗ Không tìm thấy bài viết có slug {slug!r}")
                return 1
            results = [await service.index_article(article.id)]
        else:
            results = await service.reindex_all(only_stale=(mode == "stale"))

        total_chunks = service.count_chunks()

    ok = [r for r in results if r.was_indexed]
    skipped = [r for r in results if not r.was_indexed]

    print()
    for r in ok:
        print(f"  ✓ {r.slug:<32} {r.chunks_created:>3} chunk  ({r.latency_ms} ms)")
    for r in skipped:
        print(f"  · {r.slug or '(không rõ)':<32} bỏ qua — {r.skipped_reason}")

    print(f"\n✓ Index {len(ok)} bài · bỏ qua {len(skipped)} · tổng {total_chunks} chunk trong DB")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Index lại toàn bộ bài PUBLISHED")
    group.add_argument("--stale", action="store_true", help="Chỉ index bài chưa/cũ hơn nội dung")
    group.add_argument("--slug", type=str, help="Index một bài theo slug")
    args = parser.parse_args()

    mode = "all" if args.all else "stale" if args.stale else "slug"
    sys.exit(asyncio.run(run(mode, args.slug)))
