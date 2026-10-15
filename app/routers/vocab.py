"""词库导入（§5）：查重写库 + 缺失音频即时生成。"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User, Word
from ..schemas import ImportIn, ImportOut
from ..services.audio import ensure_audio, lib_name

router = APIRouter(tags=["vocab"])


@router.post("/vocab/import", response_model=ImportOut)
def import_vocab(body: ImportIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    existing = {w.word for w in db.query(Word).filter(Word.user_id == user.id).all()}
    today = date.today()
    inserted = 0
    skipped = []
    seen = set()
    audio_failed = []
    for item in body.words:
        word = item.word.strip()
        if not word or word in existing or word in seen:
            if word and (word in existing or word in seen):
                skipped.append(word)
            continue
        seen.add(word)
        db.add(Word(user_id=user.id, word=word, cn=item.cn.strip(),
                    ex=item.ex.strip(), added_on=today, audio=lib_name(word)))
        inserted += 1
    db.commit()

    for word in seen:
        if not ensure_audio(word):
            audio_failed.append(word)

    total = db.query(Word).filter(Word.user_id == user.id).count()
    return ImportOut(inserted=inserted, total=total,
                     audio_ok=not audio_failed, audio_failed=audio_failed,
                     skipped=sorted(set(skipped)))
