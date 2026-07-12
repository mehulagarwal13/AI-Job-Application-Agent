"""
OAuth2 password-flow authentication with JWT bearer tokens.

- Passwords: salted PBKDF2-HMAC-SHA256 (200k iterations) — stdlib only,
  constant-time verification. Never stored or logged in plaintext.
- Tokens: HS256 JWTs carrying the user_id (sub) with expiry.
- get_current_user: FastAPI dependency that turns a Bearer token into a User
  row or raises 401 — every user-scoped endpoint depends on it.
"""

import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import JWT_SECRET, JWT_EXPIRE_MINUTES
from app.core.database import get_db
from app.models.db_models import User

_PBKDF2_ITERATIONS = 200_000

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------- passwords ----------

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    recomputed = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), _PBKDF2_ITERATIONS)
    return hmac.compare_digest(recomputed.hex(), digest_hex)


# ---------- tokens ----------

def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=401,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
    except jwt.PyJWTError:
        raise credentials_error

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise credentials_error
    return user
