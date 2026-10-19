"""词库管理（§5）：列表/新建/改名与 N/删除；系统预制词库展示与复制。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User, Word, Wordlist
from ..schemas import (PresetOut, WordlistCreate, WordlistOut, WordlistUpdate)
from ..services import wordlists as wl_svc
from ..services.ebbinghaus import _rows, effective_new_cap

router = APIRouter(prefix="/wordlists", tags=["wordlists"])


def _to_out(db: Session, user_id: int, wl: Wordlist) -> WordlistOut:
    total = mastered = unstarted = 0
    for _, p in _rows(db, user_id, wl.id):
        total += 1
        if p is None or not p.started:
            unstarted += 1
        elif p.mastered:
            mastered += 1
    return WordlistOut(id=wl.id, name=wl.name, kind=wl.kind,
                       new_words_per_day=effective_new_cap(wl),
                       total=total, mastered=mastered, unstarted=unstarted,
                       created_on=wl.created_on)


@router.get("/system", response_model=list[PresetOut])
def list_presets(user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    presets = (db.query(Wordlist)
               .filter(Wordlist.user_id.is_(None), Wordlist.kind == "system")
               .order_by(Wordlist.id).all())
    out = []
    for wl in presets:
        total = (db.query(Word)
                 .filter(Word.wordlist_id == wl.id, Word.user_id.is_(None))
                 .count())
        out.append(PresetOut(id=wl.id, name=wl.name, total=total))
    return out


@router.get("", response_model=list[WordlistOut])
def list_wordlists(user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    wls = (db.query(Wordlist)
           .filter(Wordlist.user_id == user.id)
           .order_by(Wordlist.id).all())
    return [_to_out(db, user.id, wl) for wl in wls]


@router.post("", response_model=WordlistOut)
def create_wordlist(body: WordlistCreate, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    wl = wl_svc.create_custom(db, user.id, body.name)
    out = _to_out(db, user.id, wl)
    db.commit()
    return out


@router.put("/{wordlist_id}", response_model=WordlistOut)
def update_wordlist(wordlist_id: int, body: WordlistUpdate,
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    wl = wl_svc.get_owned(db, user.id, wordlist_id)
    if body.name is not None:
        wl.name = wl_svc.unique_name(db, user.id, body.name, exclude_id=wl.id)
    if body.new_words_per_day is not None:
        wl.new_words_per_day = body.new_words_per_day
    db.commit()
    return _to_out(db, user.id, wl)


@router.delete("/{wordlist_id}")
def delete_wordlist(wordlist_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    wl_svc.delete_wordlist(db, user.id, wordlist_id)
    return {"ok": True}


@router.post("/{preset_id}/add", response_model=WordlistOut)
def add_preset(preset_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    wl = wl_svc.add_preset(db, user.id, preset_id)
    return _to_out(db, user.id, wl)
