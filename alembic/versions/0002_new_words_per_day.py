"""user_settings: add new_words_per_day

Revision ID: 0002
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("new_words_per_day", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("user_settings") as batch:
        batch.drop_column("new_words_per_day")
