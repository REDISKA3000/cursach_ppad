import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories.conversations import ConversationRepository
from app.repositories.resumes import SourceResumeRepository
from app.repositories.users import UserRepository
from app.services.auth_service import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    create_session_token,
    get_optional_current_user,
    hash_password,
    normalize_email,
    validate_email,
    validate_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _auth_payload(db: Session, user) -> dict:
    source = SourceResumeRepository.get_current(db, user.id)
    conversations = ConversationRepository.get_user_conversations(db, user.id)
    conversation = conversations[0] if conversations else ConversationRepository.create_conversation(db, user.id)
    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "email": user.email or user.username,
        },
        "user_id": user.id,
        "conversation_id": conversation.id,
        "has_source_resume": bool(source),
    }


def _set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(user_id),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
    )


@router.post("/api/auth/register")
async def register(
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(""),
    db: Session = Depends(get_db),
):
    normalized_email = validate_email(email)
    password = validate_password(password)
    if password_confirm and password_confirm != password:
        raise HTTPException(status_code=400, detail="Пароли не совпадают")
    if UserRepository.get_user_by_email(db, normalized_email):
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

    user = UserRepository.create_registered_user(db, normalized_email, hash_password(password))
    _set_session_cookie(response, user.id)
    return {"status": "ok", **_auth_payload(db, user)}


@router.post("/api/auth/login")
async def login(
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    normalized_email = normalize_email(email)
    user = UserRepository.get_user_by_email(db, normalized_email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    _set_session_cookie(response, user.id)
    return {"status": "ok", **_auth_payload(db, user)}


@router.post("/api/auth/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"status": "ok"}


@router.get("/api/auth/session")
async def session(
    db: Session = Depends(get_db),
    user=Depends(get_optional_current_user),
):
    if not user:
        return {
            "authenticated": False,
            "user": None,
            "user_id": None,
            "conversation_id": None,
            "has_source_resume": False,
        }
    return {"status": "ok", **_auth_payload(db, user)}
