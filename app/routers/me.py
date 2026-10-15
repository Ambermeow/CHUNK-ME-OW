"""用户设置读写（§5）：api_key 写入即 Fernet 加密；GET 只回显掩码。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User, UserSettings
from ..schemas import SettingsIn, SettingsOut
from ..security import encrypt_str, mask_api_key

router = APIRouter(prefix="/me", tags=["me"])


def _get_or_create(db: Session, user_id: int) -> UserSettings:
    s = db.get(UserSettings, user_id)
    if s is None:
        s = UserSettings(user_id=user_id)
        db.add(s)
        db.flush()
    return s


@router.get("/settings", response_model=SettingsOut)
def get_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _get_or_create(db, user.id)
    masked = None
    if s.api_key_encrypted:
        from ..security import decrypt_str
        try:
            masked = mask_api_key(decrypt_str(s.api_key_encrypted))
        except Exception:
            masked = "sk-****"
    return SettingsOut(llm_model=s.llm_model, api_key_masked=masked)


@router.put("/settings", response_model=SettingsOut)
def put_settings(body: SettingsIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    s = _get_or_create(db, user.id)
    if body.llm_model is not None:
        s.llm_model = body.llm_model or None
    masked = None
    if body.api_key:
        s.api_key_encrypted = encrypt_str(body.api_key)
        masked = mask_api_key(body.api_key)
    db.commit()
    return SettingsOut(llm_model=s.llm_model, api_key_masked=masked)
