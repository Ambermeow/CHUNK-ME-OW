"""注册 / 登录 / 刷新（§5、§8）。限速防爆破，密码不落明文。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import check_auth_rate_limit, get_current_user
from ..models import User, UserSettings
from ..schemas import LoginIn, RefreshIn, RegisterIn, TokenPair
from ..security import create_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue(user_id: int) -> TokenPair:
    return TokenPair(access_token=create_token(user_id, "access"),
                     refresh_token=create_token(user_id, "refresh"))


@router.post("/register", response_model=TokenPair)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    check_auth_rate_limit(request)
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="该邮箱已注册")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    db.add(UserSettings(user_id=user.id))
    db.commit()
    return _issue(user.id)


@router.post("/login", response_model=TokenPair)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    check_auth_rate_limit(request)
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    return _issue(user.id)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    user_id = decode_token(body.refresh_token, "refresh")
    if user_id is None or db.get(User, user_id) is None:
        raise HTTPException(status_code=401, detail="刷新令牌无效")
    return _issue(user_id)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email}
