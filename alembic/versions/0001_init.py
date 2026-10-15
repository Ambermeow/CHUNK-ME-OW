"""init: users / user_settings / words / word_progress / practice_sessions / session_items

Revision ID: 0001
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("llm_model", sa.String(128), nullable=True),
        sa.Column("api_key_encrypted", sa.String(512), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "words",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("word", sa.String(255), nullable=False),
        sa.Column("cn", sa.String(512), nullable=True),
        sa.Column("ex", sa.String(1024), nullable=True),
        sa.Column("added_on", sa.Date(), nullable=False),
        sa.Column("audio", sa.String(64), nullable=True),
        sa.UniqueConstraint("user_id", "word"),
    )
    op.create_index("ix_words_user_id", "words", ["user_id"])
    op.create_table(
        "word_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("word_id", sa.Integer(), sa.ForeignKey("words.id"), nullable=False),
        sa.Column("started", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("phase", sa.String(8), nullable=True),
        sa.Column("cycle_start", sa.Date(), nullable=True),
        sa.Column("last_done", sa.Date(), nullable=True),
        sa.Column("s1", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("s2", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("s4", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("s7", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("s15", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("mastered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("user_id", "word_id"),
    )
    op.create_index("ix_word_progress_user_id", "word_progress", ["user_id"])
    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("total", sa.Integer(), server_default="0"),
        sa.Column("one_shot", sa.Integer(), server_default="0"),
        sa.Column("retry", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "date"),
    )
    op.create_index("ix_practice_sessions_user_id", "practice_sessions", ["user_id"])
    op.create_table(
        "session_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("practice_sessions.id"), nullable=False),
        sa.Column("word_id", sa.Integer(), sa.ForeignKey("words.id"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="1"),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("one_shot", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status_before", sa.String(8), nullable=True),
        sa.Column("status_after", sa.String(8), nullable=True),
    )
    op.create_index("ix_session_items_session_id", "session_items", ["session_id"])


def downgrade() -> None:
    op.drop_table("session_items")
    op.drop_table("practice_sessions")
    op.drop_table("word_progress")
    op.drop_table("words")
    op.drop_table("user_settings")
    op.drop_table("users")
