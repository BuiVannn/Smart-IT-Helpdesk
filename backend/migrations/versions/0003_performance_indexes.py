"""Index bộ phận và index hiệu năng theo docs/design/04 §5.1.

VÌ SAO TÁCH RIÊNG KHỎI 0002: Alembic autogenerate không sinh được partial
index (`WHERE ...`) và index HNSW cho pgvector. Phải viết tay.

VÌ SAO DÙNG PARTIAL INDEX: ticket đã đóng chiếm phần lớn bảng theo thời gian
nhưng gần như không bao giờ xuất hiện trong hàng chờ. Index bộ phận nhỏ hơn
nhiều, nằm gọn trong bộ nhớ, và không phải cập nhật khi ticket đã đóng bị sửa.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPEN_STATUSES = "'NEW', 'ASSIGNED', 'IN_PROGRESS', 'PENDING_REQUESTER'"


def upgrade() -> None:
    # ── tickets: hàng chờ của Agent (US-12) ──
    op.execute(f"""
        CREATE INDEX ix_tickets_assignee_open ON tickets
            (assignee_id, priority DESC, sla_resolution_due_at ASC)
            WHERE status IN ({OPEN_STATUSES})
    """)

    # ── tickets: ticket chưa giao (US-12) ──
    op.execute("""
        CREATE INDEX ix_tickets_unassigned ON tickets (created_at DESC)
            WHERE assignee_id IS NULL AND status = 'NEW'
    """)

    # ── tickets: job quét SLA chạy mỗi 5 phút (US-35) ──
    op.execute(f"""
        CREATE INDEX ix_tickets_sla_monitor ON tickets (sla_resolution_due_at)
            WHERE status IN ({OPEN_STATUSES})
    """)

    # ── tickets: hàng chờ phân loại thủ công + worker AI (US-19) ──
    op.execute("""
        CREATE INDEX ix_tickets_ai_pending ON tickets (created_at)
            WHERE ai_status IN ('PENDING', 'LOW_CONFIDENCE', 'FAILED')
    """)

    # ── tickets: dashboard gộp theo category + khoảng thời gian (US-37, US-38) ──
    op.execute("""
        CREATE INDEX ix_tickets_reporting ON tickets
            (created_at, category_id, status, priority)
    """)

    # ── bảng con của ticket: luôn truy vấn theo ticket_id ──
    op.execute("CREATE INDEX ix_comments_ticket ON ticket_comments (ticket_id, created_at)")
    op.execute("CREATE INDEX ix_attachments_ticket ON ticket_attachments (ticket_id)")
    op.execute("CREATE INDEX ix_events_ticket ON ticket_events (ticket_id, created_at)")
    op.execute("CREATE INDEX ix_events_type_time ON ticket_events (event_type, created_at)")

    # ── users ──
    op.execute("CREATE INDEX ix_users_role_active ON users (role) WHERE is_active = true")
    op.execute("CREATE INDEX ix_users_department ON users (department_id) WHERE is_active = true")
    op.execute("CREATE INDEX ix_users_name_trgm ON users USING GIN (full_name gin_trgm_ops)")

    # ── refresh token ──
    op.execute(
        "CREATE INDEX ix_rt_user_active ON refresh_tokens (user_id) WHERE revoked_at IS NULL"
    )
    op.execute("CREATE INDEX ix_rt_expires ON refresh_tokens (expires_at)")

    # ── thông báo: đếm chưa đọc chạy 30 giây/lần cho MỌI người đang online ──
    op.execute("CREATE INDEX ix_notifications_user ON notifications (user_id, created_at DESC)")

    # ── kho tri thức ──
    op.execute("""
        CREATE INDEX ix_articles_published ON kb_articles (published_at DESC)
            WHERE status = 'PUBLISHED'
    """)
    op.execute("""
        CREATE INDEX ix_articles_category ON kb_articles (kb_category_id)
            WHERE status = 'PUBLISHED'
    """)
    op.execute("CREATE INDEX ix_articles_tags ON kb_articles USING GIN (tags)")
    op.execute("""
        CREATE INDEX ix_articles_stale ON kb_articles (indexed_at)
            WHERE status = 'PUBLISHED'
    """)

    # ── vector search cho RAG (ADR-0005) ──
    # Ở 64 chunk thì quét tuần tự cũng chỉ vài mili-giây; index này để sẵn
    # cho lúc kho tài liệu lớn lên, chi phí gần bằng không ở quy mô hiện tại.
    op.execute("""
        CREATE INDEX ix_chunks_embedding ON article_chunks
            USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)
    """)
    op.execute("CREATE INDEX ix_chunks_article ON article_chunks (article_id)")

    # ── chat ──
    op.execute("CREATE INDEX ix_chat_sessions_user ON chat_sessions (user_id, created_at DESC)")
    op.execute("CREATE INDEX ix_chat_messages_sess ON chat_messages (session_id, created_at)")
    op.execute("""
        CREATE INDEX ix_chat_msg_nocontext ON chat_messages (created_at)
            WHERE no_context_found = true
    """)

    # ── chỉ số chất lượng AI (US-22) ──
    op.execute("CREATE INDEX ix_ai_class_ticket ON ai_classifications (ticket_id, created_at DESC)")
    op.execute("CREATE INDEX ix_ai_class_report ON ai_classifications (created_at, was_accepted)")

    # ── đánh giá & idempotency ──
    op.execute("CREATE INDEX ix_ratings_agent ON ticket_ratings (agent_id, created_at DESC)")
    op.execute("CREATE INDEX ix_idem_expires ON idempotency_keys (expires_at)")


INDEX_NAMES = [
    "ix_tickets_assignee_open",
    "ix_tickets_unassigned",
    "ix_tickets_sla_monitor",
    "ix_tickets_ai_pending",
    "ix_tickets_reporting",
    "ix_comments_ticket",
    "ix_attachments_ticket",
    "ix_events_ticket",
    "ix_events_type_time",
    "ix_users_role_active",
    "ix_users_department",
    "ix_users_name_trgm",
    "ix_rt_user_active",
    "ix_rt_expires",
    "ix_notifications_user",
    "ix_articles_published",
    "ix_articles_category",
    "ix_articles_tags",
    "ix_articles_stale",
    "ix_chunks_embedding",
    "ix_chunks_article",
    "ix_chat_sessions_user",
    "ix_chat_messages_sess",
    "ix_chat_msg_nocontext",
    "ix_ai_class_ticket",
    "ix_ai_class_report",
    "ix_ratings_agent",
    "ix_idem_expires",
]


def downgrade() -> None:
    for name in INDEX_NAMES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
