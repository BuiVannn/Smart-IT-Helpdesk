"""Trigger cập nhật tsvector cho tìm kiếm toàn văn (ADR-0004).

Dùng cấu hình 'simple' + unaccent vì PostgreSQL không có bộ phân tích hình
thái tiếng Việt. unaccent cho phép gõ "mat khau" tìm ra "mật khẩu" — vấn đề
thực tế của người dùng Việt.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # unaccent() mặc định không IMMUTABLE nên không dùng trực tiếp trong index
    # được; bọc lại thành hàm immutable để dùng trong trigger và truy vấn.
    op.execute("""
        CREATE OR REPLACE FUNCTION immutable_unaccent(text)
        RETURNS text AS $$
            SELECT public.unaccent('public.unaccent', $1)
        $$ LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION tickets_search_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('simple',
                    immutable_unaccent(coalesce(NEW.title, ''))), 'A') ||
                setweight(to_tsvector('simple',
                    immutable_unaccent(coalesce(NEW.description, ''))), 'B');
            RETURN NEW;
        END $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_tickets_search
            BEFORE INSERT OR UPDATE OF title, description ON tickets
            FOR EACH ROW EXECUTE FUNCTION tickets_search_trigger()
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION articles_search_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('simple',
                    immutable_unaccent(coalesce(NEW.title, ''))), 'A') ||
                setweight(to_tsvector('simple',
                    immutable_unaccent(coalesce(NEW.summary, ''))), 'B') ||
                setweight(to_tsvector('simple',
                    immutable_unaccent(coalesce(NEW.content_md, ''))), 'C');
            RETURN NEW;
        END $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_articles_search
            BEFORE INSERT OR UPDATE OF title, summary, content_md ON kb_articles
            FOR EACH ROW EXECUTE FUNCTION articles_search_trigger()
    """)

    # Sequence sinh mã ticket dạng HD-YYYYMM-NNNNN (BR-20)
    op.execute("CREATE SEQUENCE IF NOT EXISTS ticket_code_seq START 1")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS ticket_code_seq")
    op.execute("DROP TRIGGER IF EXISTS trg_articles_search ON kb_articles")
    op.execute("DROP TRIGGER IF EXISTS trg_tickets_search ON tickets")
    op.execute("DROP FUNCTION IF EXISTS articles_search_trigger()")
    op.execute("DROP FUNCTION IF EXISTS tickets_search_trigger()")
    op.execute("DROP FUNCTION IF EXISTS immutable_unaccent(text)")
