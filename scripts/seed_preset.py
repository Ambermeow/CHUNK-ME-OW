"""导入系统预制词库（幂等）：data/presets/*.csv → wordlists(user_id=NULL, kind='system')。

用法：
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/seed_preset.py          # 导入+生成发音
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/seed_preset.py --no-audio  # 只导入
"""
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import Word, Wordlist  # noqa: E402
from app.services.audio import ensure_audio, lib_name  # noqa: E402

PRESETS = [
    {"csv": ROOT / "data" / "presets" / "drama_catchphrases_kept.csv",
     "name": "当我美剧看多了，我的口头禅就变成了……"},
]


def seed_one(db, csv_path: Path, name: str) -> Wordlist:
    exists = (db.query(Wordlist)
              .filter(Wordlist.user_id.is_(None), Wordlist.name == name)
              .first())
    if exists is not None:
        print(f"skip (exists): {name} id={exists.id}")
        return exists
    wl = Wordlist(user_id=None, name=name, kind="system", created_on=date.today())
    db.add(wl)
    db.flush()
    seen, n = set(), 0
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            word = (row.get("Chunk") or "").strip()
            if not word or word in seen:
                continue
            seen.add(word)
            db.add(Word(user_id=None, wordlist_id=wl.id, word=word,
                        cn=(row.get("中文释义") or "").strip(),
                        ex=(row.get("例句") or "").strip(),
                        added_on=date.today(), audio=lib_name(word)))
            n += 1
    db.commit()
    print(f"imported {n} words -> {name} id={wl.id}")
    return wl


def gen_audio(db):
    words = (db.query(Word.word)
             .filter(Word.user_id.is_(None)).order_by(Word.id).all())
    ok = failed = 0
    for i, (word,) in enumerate(words, 1):
        if ensure_audio(word):
            ok += 1
        else:
            failed += 1
            print(f"audio FAILED: {word}")
        if i % 50 == 0:
            print(f"audio progress {i}/{len(words)}")
    print(f"audio done: ok={ok} failed={failed}")


def main():
    with SessionLocal() as db:
        for spec in PRESETS:
            seed_one(db, spec["csv"], spec["name"])
        if "--no-audio" not in sys.argv:
            gen_audio(db)


if __name__ == "__main__":
    main()
