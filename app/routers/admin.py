"""管理员端点（§5）：查看全部词库（系统 + 用户）、词条详情/编辑/删除。

管理员编辑的是系统词库母本，普通用户编辑的是自己 clone 的私人词库。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User, Word, Wordlist
from ..schemas import AdminWordOut, AdminWordlistOut, AdminWordUpdate
from ..services import wordlists as wl_svc

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


@router.get("/wordlists", response_model=list[AdminWordlistOut])
def admin_wordlists(_: User = Depends(require_admin),
                    db: Session = Depends(get_db)):
    counts = dict(
        db.query(Word.wordlist_id, func.count(Word.id))
        .group_by(Word.wordlist_id).all()
    )
    owners = {u.id: u.email for u in db.query(User).all()}
    out = []
    for wl in db.query(Wordlist).order_by(Wordlist.id).all():
        owner = "系统" if wl.user_id is None else owners.get(wl.user_id, f"用户{wl.user_id}")
        out.append(AdminWordlistOut(
            id=wl.id, name=wl.name, kind=wl.kind, owner=owner,
            total=counts.get(wl.id, 0), created_on=wl.created_on))
    return out


@router.get("/wordlists/{wordlist_id}/words", response_model=list[AdminWordOut])
def admin_words(wordlist_id: int, _: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    if db.get(Wordlist, wordlist_id) is None:
        raise HTTPException(status_code=404)
    out = []
    for w in (db.query(Word).filter(Word.wordlist_id == wordlist_id)
              .order_by(Word.id).all()):
        out.append(AdminWordOut(
            id=w.id, word=w.word, cn=w.cn or "",
            example_en=w.example_en or "", example_cn=w.example_cn or "",
            valid_flag=w.valid_flag, added_on=w.added_on))
    return out


@router.put("/words/{word_id}", response_model=AdminWordOut)
def admin_update_word(word_id: int, body: AdminWordUpdate,
                      _: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    word = db.get(Word, word_id)
    if word is None:
        raise HTTPException(status_code=404)
    data = body.model_dump(exclude_unset=True)
    for field in ("word", "cn", "example_en", "example_cn", "valid_flag"):
        if field in data:
            setattr(word, field, data[field])
    db.commit()
    return AdminWordOut(
        id=word.id, word=word.word, cn=word.cn or "",
        example_en=word.example_en or "", example_cn=word.example_cn or "",
        valid_flag=word.valid_flag, added_on=word.added_on)


@router.delete("/words/{word_id}", status_code=204)
def admin_delete_word(word_id: int, _: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    word = db.get(Word, word_id)
    if word is None:
        raise HTTPException(status_code=404)
    wl_svc.delete_word_cascade(db, word_id)
    db.commit()
