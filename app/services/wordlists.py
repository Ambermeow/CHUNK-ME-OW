"""词库服务：默认词库、命名去重（同用户内唯一）、预制复制、删除级联。"""
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (PracticeSession, SessionItem, Word, WordProgress,
                      Wordlist)

DEFAULT_NAME = "自定义词库"


def get_owned(db: Session, user_id: int, wordlist_id: int) -> Wordlist:
    """取用户名下词库；越权或不存在一律 404。"""
    wl = db.get(Wordlist, wordlist_id)
    if wl is None or wl.user_id != user_id:
        raise HTTPException(status_code=404, detail="词库不存在")
    return wl


def resolve(db: Session, user_id: int, wordlist_id: int | None) -> Wordlist:
    """接口未指明词库时回退到第一个词库；完全没有则自动建默认词库。"""
    if wordlist_id is not None:
        return get_owned(db, user_id, wordlist_id)
    wl = (db.query(Wordlist)
          .filter(Wordlist.user_id == user_id)
          .order_by(Wordlist.id)
          .first())
    if wl is None:
        wl = Wordlist(user_id=user_id, name=DEFAULT_NAME, kind="custom",
                      created_on=date.today())
        db.add(wl)
        db.commit()
    return wl


def unique_name(db: Session, user_id: int, base: str,
                exclude_id: int | None = None) -> str:
    """同用户内词库名唯一；冲突统一加 ·{uid} 后缀，再冲突追加 ·2/·3…"""
    def taken(name: str) -> bool:
        q = db.query(Wordlist).filter(
            Wordlist.user_id == user_id, Wordlist.name == name)
        if exclude_id is not None:
            q = q.filter(Wordlist.id != exclude_id)
        return q.first() is not None

    if not taken(base):
        return base
    cand = f"{base}·{user_id}"
    if not taken(cand):
        return cand
    i = 2
    while True:
        cand = f"{base}·{user_id}·{i}"
        if not taken(cand):
            return cand
        i += 1


def create_custom(db: Session, user_id: int, name: str) -> Wordlist:
    """新建自定义词库（仅 flush，调用方负责 commit）。"""
    wl = Wordlist(user_id=user_id, name=unique_name(db, user_id, name),
                  kind="custom", created_on=date.today())
    db.add(wl)
    db.flush()
    return wl


def add_preset(db: Session, user_id: int, preset_id: int) -> Wordlist:
    """添加预制词库 = 复制一份母本词条进用户账户，进度从零开始。"""
    preset = db.get(Wordlist, preset_id)
    if preset is None or preset.kind != "system" or preset.user_id is not None:
        raise HTTPException(status_code=404, detail="预制词库不存在")
    wl = Wordlist(user_id=user_id, name=unique_name(db, user_id, preset.name),
                  kind="custom", created_on=date.today())
    db.add(wl)
    db.flush()
    today = date.today()
    src = (db.query(Word)
           .filter(Word.wordlist_id == preset.id, Word.user_id.is_(None))
           .order_by(Word.id).all())
    for w in src:
        db.add(Word(user_id=user_id, wordlist_id=wl.id, word=w.word,
                    cn=w.cn, ex=w.ex, added_on=today, audio=w.audio))
    db.commit()
    return wl


def delete_wordlist(db: Session, user_id: int, wordlist_id: int) -> None:
    """删除词库并级联清理：词条、进度、会话与明细。"""
    wl = get_owned(db, user_id, wordlist_id)
    word_ids = [r[0] for r in db.query(Word.id)
                .filter(Word.wordlist_id == wl.id).all()]
    session_ids = [r[0] for r in db.query(PracticeSession.id)
                   .filter(PracticeSession.wordlist_id == wl.id).all()]
    if word_ids:
        db.query(WordProgress).filter(
            WordProgress.word_id.in_(word_ids)).delete(synchronize_session=False)
        db.query(SessionItem).filter(
            SessionItem.word_id.in_(word_ids)).delete(synchronize_session=False)
    if session_ids:
        db.query(SessionItem).filter(
            SessionItem.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(PracticeSession).filter(
            PracticeSession.id.in_(session_ids)).delete(synchronize_session=False)
    db.query(Word).filter(Word.wordlist_id == wl.id).delete(synchronize_session=False)
    db.delete(wl)
    db.commit()
