import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import hash_password, verify_password, create_access_token, get_current_user
from app.core.database import get_db
from app.models.db_models import User

router = APIRouter(prefix="/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 8


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(user_id=str(uuid.uuid4()), email=email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # signup race on the unique email index
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    return TokenResponse(access_token=create_access_token(user.user_id), email=user.email)


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password flow — `username` carries the email."""
    email = form.username.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    # Same error for both cases — never reveal whether the email exists.
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    return TokenResponse(access_token=create_access_token(user.user_id), email=user.email)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user_id": user.user_id, "email": user.email, "created_at": user.created_at}
