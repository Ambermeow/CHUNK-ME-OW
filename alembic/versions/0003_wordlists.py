"""wordlists: 词库层（系统预制母本 user_id=NULL + 用户词库），N 移到词库

- words / practice_sessions 增加 wordlist_id，唯一约束改为含词库维度
- 每个现有用户建默认词库「自定义词库」，N 从 user_settings 拷入
- user_settings.new_words_per_day 废弃删除
- SQLite 用原生 DDL 重建表（反射约束名为 None，batch 不可靠）

Revision ID: 0003
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

DEFAULT_NAME = "自定义词库"


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    op.create_table(
        "wordlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="custom"),
        sa.Column("new_words_per_day", sa.Integer(), nullable=True),
        sa.Column("created_on", sa.Date(), nullable=False),
        sa.UniqueConstraint("user_id", "name"),
    )
    op.create_index("ix_wordlists_user_id", "wordlists", ["user_id"])

    # 每个用户一个默认词库，N 从 user_settings 拷贝（无设置行则 NULL=环境变量默认）
    bind.execute(sa.text(
        "INSERT INTO wordlists (user_id, name, kind, new_words_per_day, created_on) "
        "SELECT u.id, :name, 'custom', s.new_words_per_day, CURRENT_DATE "
        "FROM users u LEFT JOIN user_settings s ON s.user_id = u.id"
    ), {"name": DEFAULT_NAME})

    op.add_column("words", sa.Column("wordlist_id", sa.Integer(), nullable=True))
    op.add_column("practice_sessions",
                  sa.Column("wordlist_id", sa.Integer(), nullable=True))

    # 回填：用户全部现有数据归入其默认词库
    bind.execute(sa.text(
        "UPDATE words SET wordlist_id = ("
        "SELECT wl.id FROM wordlists wl WHERE wl.user_id = words.user_id)"
    ))
    bind.execute(sa.text(
        "UPDATE practice_sessions SET wordlist_id = ("
        "SELECT wl.id FROM wordlists wl "
        "WHERE wl.user_id = practice_sessions.user_id)"
    ))

    if is_sqlite:
        _rebuild_sqlite()
    else:
        _rebuild_pg()

    with op.batch_alter_table("user_settings") as batch:
        batch.drop_column("new_words_per_day")


def _rebuild_sqlite() -> None:
    op.execute("PRAGMA legacy_alter_table = ON")  # 重命名不联动，避免误改引用
    # ---- words ----
    op.execute("""
        CREATE TABLE words_new (
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
        "INSERT INTO words_new (id, user_id, wordlist_id, word, cn, ex, added_on, audio) "
        "SELECT id, user_id, wordlist_id, word, cn, ex, added_on, audio FROM words"
    )
    op.execute("DROP TABLE words")
    op.execute("ALTER TABLE words_new RENAME TO words")
    op.create_index("ix_words_user_id", "words", ["user_id"])
    op.create_index("ix_words_wordlist_id", "words", ["wordlist_id"])

    # ---- practice_sessions ----
    op.execute("""
        CREATE TABLE practice_sessions_new (
            id INTEGER NOT NULL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            wordlist_id INTEGER NOT NULL REFERENCES wordlists(id),
            date DATE NOT NULL,
            total INTEGER DEFAULT '0',
            one_shot INTEGER DEFAULT '0',
            retry INTEGER DEFAULT '0',
            created_at DATETIME,
            UNIQUE (user_id, wordlist_id, date)
        )
    """)
    op.execute(
        "INSERT INTO practice_sessions_new "
        "(id, user_id, wordlist_id, date, total, one_shot, retry, created_at) "
        "SELECT id, user_id, wordlist_id, date, total, one_shot, retry, created_at "
        "FROM practice_sessions"
    )
    op.execute("DROP TABLE practice_sessions")
    op.execute("ALTER TABLE practice_sessions_new RENAME TO practice_sessions")
    op.create_index("ix_practice_sessions_user_id", "practice_sessions", ["user_id"])
    op.create_index("ix_practice_sessions_wordlist_id", "practice_sessions", ["wordlist_id"])
    op.execute("PRAGMA legacy_alter_table = OFF")


def _rebuild_pg() -> None:
    op.alter_column("words", "wordlist_id", nullable=False)
    op.alter_column("words", "user_id", nullable=True)
    op.drop_constraint("words_user_id_word_key", "words")
    op.create_unique_constraint("words_user_id_wordlist_id_word_key",
                                "words", ["user_id", "wordlist_id", "word"])
    op.create_index("ix_words_wordlist_id", "words", ["wordlist_id"])

    op.alter_column("practice_sessions", "wordlist_id", nullable=False)
    op.drop_constraint("practice_sessions_user_id_date_key", "practice_sessions")
    op.create_unique_constraint("practice_sessions_user_id_wordlist_id_date_key",
                                "practice_sessions", ["user_id", "wordlist_id", "date"])
    op.create_index("ix_practice_sessions_wordlist_id",
                    "practice_sessions", ["wordlist_id"])


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    op.add_column("user_settings",
                  sa.Column("new_words_per_day", sa.Integer(), nullable=True))
    # N 尽力还原：取该用户任一词库的设置值
    bind.execute(sa.text(
        "UPDATE user_settings SET new_words_per_day = ("
        "SELECT wl.new_words_per_day FROM wordlists wl "
        "WHERE wl.user_id = user_settings.user_id AND wl.new_words_per_day IS NOT NULL "
        "LIMIT 1)"
    ))

    if is_sqlite:
        op.execute("PRAGMA legacy_alter_table = ON")
        op.execute("""
            CREATE TABLE words_old (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                word VARCHAR(255) NOT NULL,
                cn VARCHAR(512),
                ex VARCHAR(1024),
                added_on DATE NOT NULL,
                audio VARCHAR(64),
                UNIQUE (user_id, word)
            )
        """)
        # 预制词（user_id NULL）在旧结构中无归宿，尽力反向时丢弃
        op.execute(
            "INSERT INTO words_old (id, user_id, word, cn, ex, added_on, audio) "
            "SELECT id, user_id, word, cn, ex, added_on, audio FROM words "
            "WHERE user_id IS NOT NULL"
        )
        op.execute("DROP TABLE words")
        op.execute("ALTER TABLE words_old RENAME TO words")
        op.create_index("ix_words_user_id", "words", ["user_id"])

        op.execute("""
            CREATE TABLE practice_sessions_old (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                date DATE NOT NULL,
                total INTEGER DEFAULT '0',
                one_shot INTEGER DEFAULT '0',
                retry INTEGER DEFAULT '0',
                created_at DATETIME,
                UNIQUE (user_id, date)
            )
        """)
        op.execute(
            "INSERT INTO practice_sessions_old "
            "(id, user_id, date, total, one_shot, retry, created_at) "
            "SELECT id, user_id, date, total, one_shot, retry, created_at "
            "FROM practice_sessions"
        )
        op.execute("DROP TABLE practice_sessions")
        op.execute("ALTER TABLE practice_sessions_old RENAME TO practice_sessions")
        op.create_index("ix_practice_sessions_user_id",
                        "practice_sessions", ["user_id"])
        op.execute("PRAGMA legacy_alter_table = OFF")
    else:
        op.drop_index("ix_practice_sessions_wordlist_id", "practice_sessions")
        op.drop_constraint("practice_sessions_user_id_wordlist_id_date_key",
                           "practice_sessions")
        op.create_unique_constraint("practice_sessions_user_id_date_key",
                                    "practice_sessions", ["user_id", "date"])
        op.drop_column("practice_sessions", "wordlist_id")

        op.drop_index("ix_words_wordlist_id", "words")
        op.drop_constraint("words_user_id_wordlist_id_word_key", "words")
        op.create_unique_constraint("words_user_id_word_key",
                                    "words", ["user_id", "word"])
        op.alter_column("words", "user_id", nullable=False)
        op.drop_column("words", "wordlist_id")

    op.drop_index("ix_wordlists_user_id", "wordlists")
    op.drop_table("wordlists")
