"""词库总览与记忆曲线数据（§5、§7）。越权访问返回 404。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc, outerjoin
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (PracticeSession, SessionItem, User, Word, WordProgress)
from ..schemas import HistoryPoint, WordOut, WordValidIn
from ..services import wordlists as wl_svc
from ..services.ebbinghaus import _rows, word_status

router = APIRouter(tags=["words"])

_FILTERS = {"all", "started", "mastered", "cycling", "daily", "unstarted"}


@router.get("/words", response_model=list[WordOut])
def list_words(sort: str = Query("added_on", pattern="^(added_on|word)$"),
               dirn: str = Query("desc", alias="dir", pattern="^(asc|desc)$"),
               filter: str = Query("all", alias="filter"),
               wordlist_id: int | None = Query(default=None),
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if filter not in _FILTERS:
        raise HTTPException(status_code=422, detail="非法 filter")
    wl = wl_svc.resolve(db, user.id, wordlist_id)
    out = []
    # 总览含已停用词（否则无法恢复），背词队列才只取有效词
    for word, p in _rows(db, user.id, wl.id, only_valid=False):
        st = word_status(p)
        if filter == "started" and not (p and p.started):
            continue
        if filter == "mastered" and not (p and p.mastered):
            continue
        if filter == "cycling" and not (p and p.phase == "cycle" and not p.mastered):
            continue
        if filter == "daily" and not (p and p.phase == "daily"):
            continue
        if filter == "unstarted" and (p and p.started):
            continue
        out.append(WordOut(id=word.id, word=word.word, cn=word.cn or "",
                           added_on=word.added_on, status=st,
                           valid=word.valid_flag))
    key = (lambda w: w.added_on) if sort == "added_on" else (lambda w: w.word.lower())
    out.sort(key=lambda w: (key(w), w.id), reverse=(dirn == "desc"))
    return out


@router.patch("/words/{word_id}/valid", response_model=WordOut)
def set_word_valid(word_id: int, body: WordValidIn,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """临时删除（valid=false）/ 恢复（valid=true）。"""
    word = db.get(Word, word_id)
    if word is None or word.user_id != user.id:
        raise HTTPException(status_code=404)
    word.valid_flag = body.valid
    db.commit()
    p = (db.query(WordProgress)
         .filter(WordProgress.word_id == word_id,
                 WordProgress.user_id == user.id).first())
    return WordOut(id=word.id, word=word.word, cn=word.cn or "",
                   added_on=word.added_on, status=word_status(p),
                   valid=word.valid_flag)


@router.delete("/words/{word_id}", status_code=204)
def delete_word(word_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """永久删除词条（级联进度与会话明细）。"""
    word = db.get(Word, word_id)
    if word is None or word.user_id != user.id:
        raise HTTPException(status_code=404)
    wl_svc.delete_word_cascade(db, word_id)
    db.commit()


@router.get("/words/{word_id}/history", response_model=list[HistoryPoint])
def word_history(word_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    word = db.get(Word, word_id)
    if word is None or word.user_id != user.id:
        raise HTTPException(status_code=404)
    rows = (
        db.query(PracticeSession.date, SessionItem.status_after)
        .join(SessionItem, SessionItem.session_id == PracticeSession.id)
        .filter(PracticeSession.user_id == user.id,
                SessionItem.word_id == word_id)
        .order_by(PracticeSession.date, SessionItem.id)
        .all()
    )
    return [HistoryPoint(date=d, status=s) for d, s in rows]
