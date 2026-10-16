"""艾宾浩斯选词与状态口径（§2.3 / §2.4），规则与原 build_daily.py 完全一致。"""
from datetime import date

from sqlalchemy import and_, outerjoin
from sqlalchemy.orm import Session

from ..config import INTERVALS, MAX_REVIEW_PER_DAY, NEW_WORDS_PER_DAY
from ..models import UserSettings, Word, WordProgress

# 阶段列名与「已完成该阶段后的展示档」
_STAGE_ATTRS = ["s1", "s2", "s4", "s7", "s15"]
_STAGE_DONE_LABEL = {"s1": "D2", "s2": "D4", "s4": "D7", "s7": "D15", "s15": "COM"}


def word_status(p: WordProgress | None) -> str:
    """D0 未学 | REP 回炉 | D1 首天一遍过 | D2/D4/D7/D15 逐级 | COM 五阶段全过"""
    if p is None or not p.started:
        return "D0"
    if p.phase == "daily":
        return "REP"
    last = "D1"
    for attr in _STAGE_ATTRS:
        if getattr(p, attr):
            last = _STAGE_DONE_LABEL[attr]
        else:
            break
    return last


def _rows(db: Session, user_id: int):
    """当前用户全部词 + 进度（左连接），按加入顺序。"""
    return (
        db.query(Word, WordProgress)
        .outerjoin(
            WordProgress,
            and_(WordProgress.word_id == Word.id, WordProgress.user_id == user_id),
        )
        .filter(Word.user_id == user_id)
        .order_by(Word.id)
        .all()
    )


def effective_new_cap(db: Session, user_id: int) -> int:
    """每日新词上限 N：用户账户设置优先，未设置时回落到环境变量默认。"""
    s = db.get(UserSettings, user_id)
    return (s.new_words_per_day if s and s.new_words_per_day else NEW_WORDS_PER_DAY)


def select_queue(db: Session, user_id: int, due: date, new_cap: int | None = None):
    """返回 (review_words, new_words)，均为 Word 对象列表。

    - 回炉词（phase=daily）优先全进；
    - 周期词按 last_done + 第一个未完成阶段间隔 <= due 判到期，补足到 40；
    - 新词（started=false）独立名额取 N（用户配置，缺省环境变量），复习积压不得挤占。
    """
    if new_cap is None:
        new_cap = effective_new_cap(db, user_id)
    daily: list[Word] = []
    cycle_due: list[Word] = []
    new_pool: list[Word] = []

    for word, p in _rows(db, user_id):
        if p is None or not p.started:
            new_pool.append(word)
            continue
        if p.phase == "daily":
            daily.append(word)
            continue
        if p.phase == "cycle":
            for k, attr in zip(INTERVALS, _STAGE_ATTRS):
                if not getattr(p, attr):
                    # 到期基准 = 上次练成日 last_done，无记录退回 cycle_start/added_on
                    base = p.last_done or p.cycle_start or word.added_on or due
                    if (due - base).days >= int(k):
                        cycle_due.append(word)
                    break

    daily_set = {w.id for w in daily}
    review = daily + [w for w in cycle_due if w.id not in daily_set][
        : max(0, MAX_REVIEW_PER_DAY - len(daily))
    ]
    return review, new_pool[:new_cap]


def dashboard_stats(db: Session, user_id: int, next_review_count: int,
                    new_cap: int | None = None) -> dict:
    if new_cap is None:
        new_cap = effective_new_cap(db, user_id)
    total = started = mastered = cycling = daily = unstarted = 0
    for _, p in _rows(db, user_id):
        total += 1
        if p is None or not p.started:
            unstarted += 1
            continue
        started += 1
        if p.mastered:
            mastered += 1
        if p.phase == "cycle" and not p.mastered:
            cycling += 1
        elif p.phase == "daily":
            daily += 1
    remaining = total - mastered
    est_days = -(-remaining // new_cap)
    return {
        "total": total,
        "started": started,
        "mastered": mastered,
        "cycling": cycling,
        "daily": daily,
        "unstarted": unstarted,
        "est_days": est_days,
        "new_words_per_day": new_cap,
        "next_review_count": next_review_count,
    }
