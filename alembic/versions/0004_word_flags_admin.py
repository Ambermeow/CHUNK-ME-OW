"""words: valid_flag/example_en/example_cn；users: is_admin

- words 新增三列：valid_flag(默认 True)、example_en、example_cn（例句及中文，置空）
- users 新增 is_admin（默认 False），并把 miao@aa.com 设为管理员
- SQLite 原生 ADD COLUMN 即可（带 server_default 的 NOT NULL 列）

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    op.add_column("words", sa.Column(
        "valid_flag", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("words", sa.Column("example_en", sa.String(1024), nullable=True))
    op.add_column("words", sa.Column("example_cn", sa.String(1024), nullable=True))
    op.add_column("users", sa.Column(
        "is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))

    bind.execute(sa.text(
        "UPDATE users SET is_admin = 1 WHERE lower(email) = 'miao@aa.com'"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite 无法直接删列，原生 DDL 重建 words / users
        op.execute("PRAGMA legacy_alter_table = ON")

        op.execute("""
            CREATE TABLE words_old (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                wordlist_id INTEGER NOT NULL REFERENCES wordlists(id),
                word VARCHAR(255) NOT NULL,
                cn VARCHAR(512),
                ex VARCHAR(1024),
                added_on DATE NOT NULL,
                audio VARCHAR(64),
                UNIQUE (user_id, wordlist_id, word)
            )
        """)
        op.execute(
            "INSERT INTO words_old "
            "(id, user_id, wordlist_id, word, cn, ex, added_on, audio) "
            "SELECT id, user_id, wordlist_id, word, cn, ex, added_on, audio FROM words"
        )
        op.execute("DROP TABLE words")
        op.execute("ALTER TABLE words_old RENAME TO words")
        op.create_index("ix_words_user_id", "words", ["user_id"])
        op.create_index("ix_words_wordlist_id", "words", ["wordlist_id"])

        op.execute("""
            CREATE TABLE users_old (
                id INTEGER NOT NULL PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(512) NOT NULL,
                created_at DATETIME
            )
        """)
        op.execute(
            "INSERT INTO users_old (id, email, password_hash, created_at) "
            "SELECT id, email, password_hash, created_at FROM users"
        )
        op.execute("DROP TABLE users")
        op.execute("ALTER TABLE users_old RENAME TO users")
        op.execute("PRAGMA legacy_alter_table = OFF")
    else:
        op.drop_column("users", "is_admin")
        op.drop_column("words", "example_cn")
        op.drop_column("words", "example_en")
        op.drop_column("words", "valid_flag")
