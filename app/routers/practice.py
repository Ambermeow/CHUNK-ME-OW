"""当日队列 / 结果提交 / 明日词库（§5）。"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import PracticeSession, User
from ..schemas import NextOut, SubmitIn, SubmitOut, TodayItem, TodayOut
from ..services.ebbinghaus import select_queue
from ..services.submit import apply_results

router = APIRouter(tags=["practice"])


def _queue_items(db: Session, user_id: int, due: date):
    review, new_words = select_queue(db, user_id, due)
    queue = review + new_words
    items = [
        TodayItem(i=idx + 1, audio_url=f"/api/voice/{w.audio or ''}",
                  correct=w.word, cn=w.cn or "", ex=w.ex or "")
        for idx, w in enumerate(queue)
    ]
    return queue, items


@router.get("/today", response_model=TodayOut)
def today(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = date.today()
    _, items = _queue_items(db, user.id, day)
    session = (
        db.query(PracticeSession)
        .filter(PracticeSession.user_id == user.id, PracticeSession.date == day)
        .first()
    )
    summary = None
    if session is not None:
        summary = {"total": session.total, "one_shot": session.one_shot,
                   "retry": session.retry}
    return TodayOut(date=day, items=items, has_local_draft_hint=session is not None,
                    submitted_summary=summary)


@router.post("/today/submit", response_model=SubmitOut)
def submit(body: SubmitIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    summary = apply_results(db, user.id, body.date, body.results)
    return SubmitOut(**summary)


@router.get("/next", response_model=NextOut)
def next_review(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tomorrow = date.today() + timedelta(days=1)
    queue, _ = _queue_items(db, user.id, tomorrow)
    return NextOut(date=tomorrow, count=len(queue),
                   items=[{"word": w.word, "cn": w.cn or ""} for w in queue])
