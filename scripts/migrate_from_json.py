#!/usr/bin/env python3
"""存量数据迁移（§10）

用法:
  python scripts/migrate_from_json.py <vocab.json> <progress.json> --user <email>

- vocab.json 每行 → words（audio 原样）；并把 <vocab所在目录>/_voice/lib 的
  音频文件复制进当前 AUDIO_DIR。
- progress.json → word_progress（stages 字典 → s1..s15；缺 last_done 用
  attempts_history 末条日期回填）。
- attempts_history → practice_sessions/session_items 尽量还原；无法还原
  status_before/after 的置空，曲线从迁移日起算。
- 迁移后校验：词数、各状态计数打印。

需先用该 email 注册账号（或加 --create-password 自动建号）。
"""
import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import and_  # noqa: E402

from app.config import AUDIO_DIR  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import _run_migrations  # noqa: E402
from app.models import (PracticeSession, SessionItem, User, UserSettings,  # noqa: E402
                        Word, WordProgress)
from app.security import hash_password  # noqa: E402
from app.services.ebbinghaus import word_status  # noqa: E402

STAGE_MAP = {"1": "s1", "2": "s2", "4": "s4", "7": "s7", "15": "s15"}


def d(s):
    return date.fromisoformat(s) if s else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vocab")
    ap.add_argument("progress")
    ap.add_argument("--user", required=True)
    ap.add_argument("--create-password", help="用户不存在时用该密码建号")
    args = ap.parse_args()

    vocab = json.loads(Path(args.vocab).read_text(encoding="utf-8"))
    progress = json.loads(Path(args.progress).read_text(encoding="utf-8"))

    _run_migrations()
    db = SessionLocal()
    user = db.query(User).filter(User.email == args.user.lower()).first()
    if user is None:
        if not args.create_password:
            sys.exit(f"用户 {args.user} 不存在；先注册或加 --create-password")
        user = User(email=args.user.lower(), password_hash=hash_password(args.create_password))
        db.add(user)
        db.flush()
        db.add(UserSettings(user_id=user.id))
        db.commit()

    # —— 音频库复制 ——
    old_lib = Path(args.vocab).parent / "_voice" / "lib"
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    if old_lib.is_dir():
        for f in old_lib.glob("*.mp3"):
            dst = AUDIO_DIR / f.name
            if not dst.exists() or dst.stat().st_size == 0:
                shutil.copy2(f, dst)
                copied += 1

    # —— words ——
    existing = {w.word for w in db.query(Word).filter(Word.user_id == user.id).all()}
    wmap = {}
    added_words = 0
    for v in vocab:
        word = v.get("word", "").strip()
        if not word or word in existing:
            continue
        w = Word(user_id=user.id, word=word, cn=v.get("cn", ""), ex=v.get("ex", ""),
                 added_on=d(v.get("added_on")) or date.today(), audio=v.get("audio"))
        db.add(w)
        db.flush()
        wmap[word] = w
        added_words += 1

    # —— word_progress ——
    added_prog = 0
    for word, rec in progress.items():
        w = wmap.get(word) or db.query(Word).filter(
            Word.user_id == user.id, Word.word == word).first()
        if w is None:
            continue
        p = db.query(WordProgress).filter(and_(WordProgress.user_id == user.id,
                                               WordProgress.word_id == w.id)).one_or_none()
        if p is not None:
            continue
        stages = rec.get("stages", {})
        last_done = d(rec.get("last_done"))
        if last_done is None:
            hist = rec.get("attempts_history") or []
            if hist:
                last_done = d(hist[-1].get("date"))
        p = WordProgress(
            user_id=user.id, word_id=w.id,
            started=bool(rec.get("started")),
            phase=rec.get("phase"),
            cycle_start=d(rec.get("cycle_start")),
            last_done=last_done,
            s1=bool(stages.get("1")), s2=bool(stages.get("2")),
            s4=bool(stages.get("4")), s7=bool(stages.get("7")),
            s15=bool(stages.get("15")),
            mastered=bool(rec.get("mastered")),
        )
        db.add(p)
        added_prog += 1

    # —— attempts_history → sessions/items（status 无法还原，置空） ——
    sess_cache = {}
    n_items = 0
    for word, rec in progress.items():
        w = wmap.get(word) or db.query(Word).filter(
            Word.user_id == user.id, Word.word == word).first()
        if w is None:
            continue
        for h in rec.get("attempts_history") or []:
            dt = d(h.get("date"))
            if dt is None:
                continue
            key = dt
            if key not in sess_cache:
                s = db.query(PracticeSession).filter(
                    PracticeSession.user_id == user.id,
                    PracticeSession.date == dt).one_or_none()
                if s is None:
                    s = PracticeSession(user_id=user.id, date=dt, total=0,
                                        one_shot=0, retry=0)
                    db.add(s)
                    db.flush()
                sess_cache[key] = s
            s = sess_cache[key]
            attempts = int(h.get("attempts", 1))
            one_shot = attempts == 1
            db.add(SessionItem(session_id=s.id, word_id=w.id, attempts=attempts,
                               errors=[], one_shot=one_shot,
                               status_before=None, status_after=None))
            s.total += 1
            s.one_shot += 1 if one_shot else 0
            s.retry += 0 if one_shot else 1
            n_items += 1

    db.commit()

    # —— 校验打印 ——
    total = db.query(Word).filter(Word.user_id == user.id).count()
    counts = {}
    for w, p in (db.query(Word, WordProgress)
                 .outerjoin(WordProgress, and_(WordProgress.word_id == Word.id,
                                               WordProgress.user_id == user.id))
                 .filter(Word.user_id == user.id).all()):
        counts[word_status(p)] = counts.get(word_status(p), 0) + 1
    print(f"迁移完成：新增词 {added_words}（词库总数 {total}），"
          f"进度 {added_prog}，历史条目 {n_items}，音频复制 {copied}")
    print("状态计数：", json.dumps(counts, ensure_ascii=False))
    print(f"原系统词数 {len(vocab)} / 进度记录 {len(progress)} —— 请核对一致")
    db.close()


if __name__ == "__main__":
    main()
