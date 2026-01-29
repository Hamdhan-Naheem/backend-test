from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from database import prisma
from core.config import get_settings
from core.security import hash_password, verify_password, create_access_token
from schemas.auth import SignUpRequest, SignInRequest, Token
from api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(body: SignUpRequest):
    """Register a new user. Returns JWT."""
    existing = await prisma.user.find_unique(where={"email": body.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = await prisma.user.create(
        data={
            "email": body.email,
            "passwordHash": hash_password(body.password),
        }
    )
    settings = get_settings()
    access_token = create_access_token(
        subject=user.id,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return Token(access_token=access_token, token_type="bearer")


@router.post("/signin", response_model=Token)
async def signin(body: SignInRequest):
    """Authenticate and return JWT."""
    user = await prisma.user.find_unique(where={"email": body.email})
    pwd_hash = getattr(user, "password_hash", None) or getattr(user, "passwordHash", None)
    if not user or not pwd_hash or not verify_password(body.password, pwd_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    settings = get_settings()
    access_token = create_access_token(
        subject=user.id,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me")
async def me(current_user=Depends(get_current_user)):
    """Return current user (protected)."""
    return {"id": current_user.id, "email": current_user.email}
