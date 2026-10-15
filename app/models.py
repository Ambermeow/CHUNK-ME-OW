"""数据库 Schema（§4）。所有业务表带 user_id，查询强制过滤。"""
from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, ForeignKey, Integer,
                        String, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    llm_model: Mapped[str | None] = mapped_column(String(128))
    api_key_encrypted: Mapped[str | None] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship()


class Word(Base):
    __tablename__ = "words"
    __table_args__ = (UniqueConstraint("user_id", "word"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    cn: Mapped[str | None] = mapped_column(String(512))
    ex: Mapped[str | None] = mapped_column(String(1024))
    added_on: Mapped[date] = mapped_column(Date, nullable=False)
    audio: Mapped[str | None] = mapped_column(String(64))

    progress: Mapped["WordProgress | None"] = relationship(
        back_populates="word", uselist=False)


class WordProgress(Base):
    __tablename__ = "word_progress"
    __table_args__ = (UniqueConstraint("user_id", "word_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), nullable=False)
    started: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phase: Mapped[str | None] = mapped_column(String(8))          # 'cycle' | 'daily'
    cycle_start: Mapped[date | None] = mapped_column(Date)
    last_done: Mapped[date | None] = mapped_column(Date)
    s1: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    s2: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    s4: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    s7: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    s15: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    word: Mapped[Word] = relationship(back_populates="progress")


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (UniqueConstraint("user_id", "date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0)
    one_shot: Mapped[int] = mapped_column(Integer, default=0)
    retry: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SessionItem(Base):
    __tablename__ = "session_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("practice_sessions.id"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    errors: Mapped[list | None] = mapped_column(JSON)             # 当日历次错误输入
    one_shot: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status_before: Mapped[str | None] = mapped_column(String(8))
    status_after: Mapped[str | None] = mapped_column(String(8))
