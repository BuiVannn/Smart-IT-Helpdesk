"""Nạp bài viết kho tri thức từ `seeds/kb/*.md` vào database.

PHẢI IDEMPOTENT: chạy nhiều lần không sinh trùng. Bài đã có thì cập nhật
nội dung và tăng `version`; bài chưa có thì tạo mới.

Chạy:
    docker compose exec api python scripts/seed_kb.py
    docker compose exec api python scripts/seed_kb.py --dry-run   # chỉ kiểm tra, không ghi DB

Sau khi nạp, chạy tiếp `python scripts/reindex_kb.py --all` để tạo embedding
cho chatbot RAG (script đó thuộc task T21).
"""

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db import all_models  # noqa: E402,F401
from app.db.session import session_scope  # noqa: E402
from app.modules.knowledge.constants import ArticleStatus  # noqa: E402
from app.modules.knowledge.models import KbArticle, KbCategory  # noqa: E402
from app.modules.tickets.models import TicketCategory  # noqa: E402
from app.modules.users.constants import UserRole  # noqa: E402
from app.modules.users.models import User  # noqa: E402

KB_DIR = Path(__file__).resolve().parent.parent / "seeds" / "kb"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Tách frontmatter YAML đơn giản khỏi nội dung Markdown.

    Chỉ hỗ trợ đúng cú pháp dùng trong seeds/kb: `khoá: giá trị` và
    `khoá: [a, b, c]`. Không dùng thư viện YAML để tránh thêm dependency
    chỉ vì một script seed.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("Thiếu khối frontmatter --- ở đầu file")

    raw, body = match.groups()
    meta: dict[str, Any] = {}

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"Dòng frontmatter không hợp lệ: {line!r}")

        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()

        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("'\"") for v in value[1:-1].split(",")]
            meta[key] = [v for v in items if v]
        else:
            meta[key] = value.strip("'\"")

    return meta, body.strip()


# slugify đã chuyển sang app/modules/knowledge/slug.py để API tạo bài viết và
# script này dùng CHUNG một cách sinh slug. Bản ở đây vốn không được gọi lần
# nào — giữ lại chỉ tạo cơ hội cho hai bản trôi khác nhau.

REQUIRED_FIELDS = ("slug", "title", "category")


def load_articles() -> list[dict[str, Any]]:
    """Đọc và kiểm tra toàn bộ file Markdown trong seeds/kb."""
    if not KB_DIR.exists():
        raise SystemExit(f"Không tìm thấy thư mục {KB_DIR}")

    articles: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()

    for path in sorted(KB_DIR.glob("*.md")):
        try:
            meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise SystemExit(f"{path.name}: {exc}") from exc

        missing = [f for f in REQUIRED_FIELDS if not meta.get(f)]
        if missing:
            raise SystemExit(f"{path.name}: thiếu trường bắt buộc {missing}")

        slug = meta["slug"]
        if slug != path.stem:
            raise SystemExit(
                f"{path.name}: slug trong frontmatter ({slug!r}) khác tên file ({path.stem!r})"
            )
        if slug in seen_slugs:
            raise SystemExit(f"{path.name}: slug {slug!r} bị trùng")
        seen_slugs.add(slug)

        if len(body) < 20:
            raise SystemExit(f"{path.name}: nội dung quá ngắn (tối thiểu 20 ký tự)")

        articles.append({
            "slug": slug,
            "title": meta["title"],
            "summary": meta.get("summary"),
            "content_md": body,
            "kb_category_slug": meta["category"],
            "ticket_category_slug": meta.get("ticket_category"),
            "tags": meta.get("tags", []),
            "file": path.name,
        })

    return articles


def seed(dry_run: bool = False) -> None:
    articles = load_articles()
    print(f"Đọc được {len(articles)} bài viết từ {KB_DIR}")

    if dry_run:
        for a in articles:
            print(f"  ✓ {a['slug']:<32} {len(a['content_md']):>5} ký tự  [{a['kb_category_slug']}]")
        print("\n(dry-run — không ghi vào database)")
        return

    created = updated = skipped = 0

    with session_scope() as db:
        author = db.execute(
            select(User).where(User.role == UserRole.ADMIN).order_by(User.created_at)
        ).scalars().first()
        if author is None:
            raise SystemExit(
                "Chưa có tài khoản ADMIN nào trong database.\n"
                "Chạy `python scripts/seed.py` trước."
            )

        kb_categories = {c.slug: c for c in db.execute(select(KbCategory)).scalars().all()}
        ticket_categories = {
            c.slug: c for c in db.execute(select(TicketCategory)).scalars().all()
        }

        for item in articles:
            kb_cat = kb_categories.get(item["kb_category_slug"])
            if kb_cat is None:
                print(f"  ⚠ {item['file']}: không có chủ đề {item['kb_category_slug']!r}, bỏ qua")
                skipped += 1
                continue

            ticket_cat = ticket_categories.get(item["ticket_category_slug"] or "")
            now = datetime.now(UTC)

            existing = db.execute(
                select(KbArticle).where(KbArticle.slug == item["slug"])
            ).scalar_one_or_none()

            if existing is None:
                db.add(KbArticle(
                    slug=item["slug"],
                    title=item["title"],
                    summary=item["summary"],
                    content_md=item["content_md"],
                    status=ArticleStatus.PUBLISHED,
                    kb_category_id=kb_cat.id,
                    ticket_category_id=ticket_cat.id if ticket_cat else None,
                    tags=item["tags"],
                    author_id=author.id,
                    published_at=now,
                    indexed_at=None,   # buộc chạy lại chỉ mục RAG
                ))
                created += 1
            elif existing.content_md != item["content_md"] or existing.title != item["title"]:
                existing.title = item["title"]
                existing.summary = item["summary"]
                existing.content_md = item["content_md"]
                existing.tags = item["tags"]
                existing.kb_category_id = kb_cat.id
                existing.ticket_category_id = ticket_cat.id if ticket_cat else None
                existing.version += 1
                existing.indexed_at = None   # nội dung đổi ⇒ phải index lại
                updated += 1
            else:
                skipped += 1

    print(f"\n✓ Tạo mới: {created} · Cập nhật: {updated} · Không đổi: {skipped}")
    if created or updated:
        print("\n⚠ Có bài viết mới hoặc thay đổi. Chạy tiếp để chatbot dùng được:")
        print("    python scripts/reindex_kb.py --all")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Chỉ kiểm tra file, không ghi database"
    )
    args = parser.parse_args()
    seed(dry_run=args.dry_run)
