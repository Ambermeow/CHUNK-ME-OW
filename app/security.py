"""密码哈希（argon2）、JWT、Fernet 加密与掩码。密码/密钥任何环节不落明文、不进日志。"""
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet
from passlib.context import CryptContext

from .config import (ACCESS_TOKEN_TTL_MIN, FERNET_KEY, JWT_SECRET,
                     REFRESH_TOKEN_TTL_DAYS)

_pwd_ctx = CryptContext(schemes=["argon2"], deprecated="auto")
_fernet = Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)


def hash_password(password: str) -> str:
    return _pwd_ctx.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_ctx.verify(password, password_hash)
    except ValueError:
        return False


def create_token(user_id: int, typ: str) -> str:
    now = datetime.now(timezone.utc)
    ttl = (timedelta(minutes=ACCESS_TOKEN_TTL_MIN) if typ == "access"
           else timedelta(days=REFRESH_TOKEN_TTL_DAYS))
    payload = {"sub": str(user_id), "typ": typ, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str, expected_typ: str) -> int | None:
    """返回 user_id；无效/类型不符返回 None。"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != expected_typ:
        return None
    try:
        return int(payload.get("sub", ""))
    except (TypeError, ValueError):
        return None


def encrypt_str(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()


def decrypt_str(cipher: str) -> str:
    return _fernet.decrypt(cipher.encode()).decode()


def mask_api_key(plain: str) -> str:
    """只回显掩码 sk-****abcd，永不回传原文。"""
    tail = plain[-4:] if len(plain) >= 4 else ""
    return f"sk-****{tail}"
