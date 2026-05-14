import base64
import hashlib
import hmac
import json
import os
import re
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import SECRET_KEY
from app.db import get_db
from app.models import User
from app.repositories.users import UserRepository

SESSION_COOKIE_NAME = "resume_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 14
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_email(email: str) -> str:
    normalized = normalize_email(email)
    if not normalized or not _EMAIL_RE.match(normalized):
        raise HTTPException(status_code=400, detail="Введите корректный email")
    return normalized


def validate_password(password: str) -> str:
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть не короче 6 символов")
    return password


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2_sha256${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    if not password_hash:
        return False
    try:
        algorithm, salt_b64, digest_b64 = password_hash.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _sign(value: str) -> str:
    return hmac.new(SECRET_KEY.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def create_session_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "iat": int(time.time()),
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    return f"{encoded}.{_sign(encoded)}"


def read_session_user_id(request: Request) -> Optional[int]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(encoded)):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded.encode()).decode())
    except Exception:
        return None
    issued_at = int(payload.get("iat") or 0)
    if issued_at + SESSION_MAX_AGE_SECONDS < int(time.time()):
        return None
    user_id = payload.get("user_id")
    return int(user_id) if user_id else None


def get_optional_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    user_id = read_session_user_id(request)
    if not user_id:
        return None
    return UserRepository.get_user_by_id(db, user_id)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_optional_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Требуется вход в аккаунт")
    return user
