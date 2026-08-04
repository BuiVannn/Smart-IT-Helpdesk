"""them deleted_at cho ticket_comments

Revision ID: 0006_comment_deleted_at
Revises: 0005
Create Date: ...
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_comment_deleted_at"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ticket_comments",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ticket_comments", "deleted_at")
