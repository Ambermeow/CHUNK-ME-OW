"""词库总览与记忆曲线数据（§5、§7）。越权访问返回 404。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc, outerjoin
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (PracticeSession, SessionItem, User, Word, WordProgress)
from ..schemas import HistoryPoint, WordOut
from ..services.ebbinghaus import _rows, word_status

router = APIRouter(tags=["words"])

_FILTERS = {"all", "started", "mastered", "cycling", "daily", "unstarted"}


@router.get("/words", response_model=list[WordOut])
def list_words(sort: str = Query("added_on", pattern="^(added_on|word)$"),
               dirn: str = Query("desc", alias="dir", pattern="^(asc|desc)$"),
               filter: str = Query("all", alias="filter"),
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if filter not in _FILTERS:
        raise HTTPException(status_code=422, detail="非法 filter")
    out = []
    for word, p in _rows(db, user.id):
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
                           added_on=word.added_on, status=st))
    key = (lambda w: w.added_on) if sort == "added_on" else (lambda w: w.word.lower())
    out.sort(key=lambda w: (key(w), w.id), reverse=(dirn == "desc"))
    return out


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
