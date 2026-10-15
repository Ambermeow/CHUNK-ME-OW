"""当日练习结果一次性写库（§2.3），规则与原 apply_results.py 一致。"""
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (PracticeSession, SessionItem, Word, WordProgress)
from .ebbinghaus import _STAGE_ATTRS, word_status


def apply_results(db: Session, user_id: int, day: date, results: list) -> dict:
    """results: [SubmitResult]。一遍过推进一档；有 errors 一律回 daily 清零。"""
    words = (
        db.query(Word)
        .filter(Word.user_id == user_id, Word.word.in_([r.word for r in results]))
        .all()
    )
    wmap = {w.word: w for w in words}
    missing = [r.word for r in results if r.word not in wmap]
    if missing:
        raise HTTPException(status_code=422, detail=f"词库中不存在: {missing[:5]}")

    one_shot_cnt = 0
    items_payload = []
    for r in results:
        word = wmap[r.word]
        # 服务端以 errors 为准推导一遍过（errors 为空 = 一遍过）
        one_shot = len(r.errors) == 0
        if one_shot:
            one_shot_cnt += 1

        p = (
            db.query(WordProgress)
            .filter(WordProgress.user_id == user_id, WordProgress.word_id == word.id)
            .one_or_none()
        )
        if p is None:
            p = WordProgress(user_id=user_id, word_id=word.id, started=False,
                             s1=False, s2=False, s4=False, s7=False, s15=False,
                             mastered=False)
            db.add(p)
            db.flush()

        status_before = word_status(p)
        p.started = True
        if one_shot:
            p.last_done = day
            if p.phase == "cycle":
                for attr in _STAGE_ATTRS:
                    if not getattr(p, attr):
                        setattr(p, attr, True)
                        break
                p.mastered = all(getattr(p, a) for a in _STAGE_ATTRS)
            else:
                p.phase = "cycle"
                p.cycle_start = day
                for attr in _STAGE_ATTRS:
                    setattr(p, attr, False)
                p.mastered = False
        else:
            p.phase = "daily"
            for attr in _STAGE_ATTRS:
                setattr(p, attr, False)
            p.mastered = False
            p.cycle_start = None

        items_payload.append((word, r, one_shot, status_before, word_status(p)))

    # 会话 upsert（同日重复提交覆盖明细，幂等）
    session = (
        db.query(PracticeSession)
        .filter(PracticeSession.user_id == user_id, PracticeSession.date == day)
        .one_or_none()
    )
    if session is None:
        session = PracticeSession(user_id=user_id, date=day)
        db.add(session)
        db.flush()
    else:
        db.query(SessionItem).filter(SessionItem.session_id == session.id).delete()
        db.flush()

    session.total = len(results)
    session.one_shot = one_shot_cnt
    session.retry = len(results) - one_shot_cnt

    for word, r, one_shot, sb, sa in items_payload:
        db.add(SessionItem(
            session_id=session.id, word_id=word.id, attempts=r.attempts,
            errors=list(r.errors), one_shot=one_shot,
            status_before=sb, status_after=sa,
        ))

    db.commit()
    return {"date": day, "total": len(results),
            "one_shot": one_shot_cnt, "retry": len(results) - one_shot_cnt}
