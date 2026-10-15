"""公共依赖：当前用户解析（仅信任 token 内 user_id）、登录限速。"""
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import AUTH_RATE_LIMIT, AUTH_RATE_WINDOW_SEC
from .database import get_db
from .models import User
from .security import decode_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="未授权")
    user_id = decode_token(creds.credentials, "access")
    if user_id is None:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


# —— 登录/注册限速：内存滑动窗口，按 客户端IP 计 ——
_rate_buckets: dict[str, deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_auth_rate_limit(request: Request) -> None:
    key = f"auth:{client_ip(request)}"
    now = time.monotonic()
    bucket = _rate_buckets[key]
    while bucket and now - bucket[0] > AUTH_RATE_WINDOW_SEC:
        bucket.popleft()
    if len(bucket) >= AUTH_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="尝试过于频繁，请稍后再试")
    bucket.append(now)
