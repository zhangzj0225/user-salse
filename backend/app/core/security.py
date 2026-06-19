from datetime import datetime, timedelta, timezone
from typing import Optional

import hmac
import hashlib
import secrets

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.admin_user import AdminUser
from app.models.user import User

# Base62 字符表
_BASE62_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _base62_encode(num: int) -> str:
    """将整数编码为 Base62 字符串。"""
    if num == 0:
        return _BASE62_CHARS[0]
    result = []
    while num > 0:
        result.append(_BASE62_CHARS[num % 62])
        num //= 62
    return "".join(reversed(result))


def _base62_decode(s: str) -> int:
    """将 Base62 字符串解码为整数。"""
    result = 0
    for c in s:
        idx = _BASE62_CHARS.find(c)
        if idx == -1:
            raise ValueError(f"Invalid Base62 character: {c!r}")
        result = result * 62 + idx
    return result


def generate_invite_code(user_id: int, nonce: str | None = None) -> str:
    """生成统一类型邀请码：Base62(user_id).nonce.HMAC-SHA256[:16]

    格式: {base62_user_id}.{nonce}.{hmac_hex_first_16_chars}
    签名密钥: settings.INVITE_CODE_SECRET
    nonce 默认随机生成（8 hex chars），支持同一用户生成多个邀请码
    """
    if nonce is None:
        nonce = secrets.token_hex(4)
    payload = f"{user_id}:{nonce}".encode("utf-8")
    secret = settings.INVITE_CODE_SECRET.encode("utf-8")
    signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()[:16]
    return f"{_base62_encode(user_id)}.{nonce}.{signature}"


def verify_invite_code_signature(code: str) -> tuple[bool, int | None]:
    """验证邀请码签名。

    返回: (valid, user_id)
    - valid=True: 签名匹配，user_id 为生成者 ID
    - valid=False: 签名不匹配或格式错误，user_id=None
    """
    parts = code.split(".")
    if len(parts) != 3:
        return (False, None)

    base62_uid, nonce, signature = parts
    if not base62_uid or not nonce or not signature:
        return (False, None)

    try:
        user_id = _base62_decode(base62_uid)
    except (ValueError, IndexError):
        return (False, None)

    payload = f"{user_id}:{nonce}".encode("utf-8")
    secret = settings.INVITE_CODE_SECRET.encode("utf-8")
    expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()[:16]

    if not hmac.compare_digest(signature, expected_sig):
        return (False, None)

    return (True, user_id)

security_scheme = HTTPBearer(auto_error=False)

_NO_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def create_access_token(subject: int, role: str, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(subject),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "role", "type"]},
        )
    except PyJWTError:
        raise ValueError("Invalid token")


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise _NO_CREDENTIALS
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("type") != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User token required",
        )

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    if not credentials:
        raise _NO_CREDENTIALS
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    try:
        admin_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found",
        )
    return admin
