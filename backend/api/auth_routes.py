"""
Authentication API routes — signup, login, Google OAuth, and user info.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from backend.db.database import SessionLocal
from backend.db.models import User
from backend.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    verify_google_token,
    get_current_user_id,
)

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Request / Response schemas ────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: str
    password: str
    name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    id_token: str

class AuthResponse(BaseModel):
    token: str
    user: dict


# ── Signup ────────────────────────────────────────────────────────────────────

@auth_router.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest):
    """Register a new user with email and password."""
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == req.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="An account with this email already exists")

        user = User(
            email=req.email,
            name=req.name or req.email.split("@")[0],
            hashed_password=hash_password(req.password),
            auth_provider="local",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token({"sub": str(user.id), "email": user.email})
        return AuthResponse(
            token=token,
            user={"id": user.id, "email": user.email, "name": user.name, "provider": user.auth_provider},
        )
    finally:
        db.close()


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest):
    """Login with email and password, returns JWT."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == req.email).first()
        if not user or not user.hashed_password:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not verify_password(req.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = create_access_token({"sub": str(user.id), "email": user.email})
        return AuthResponse(
            token=token,
            user={"id": user.id, "email": user.email, "name": user.name, "provider": user.auth_provider},
        )
    finally:
        db.close()


# ── Google OAuth ──────────────────────────────────────────────────────────────

@auth_router.post("/google", response_model=AuthResponse)
def google_auth(req: GoogleAuthRequest):
    """Login or register with a Google ID token."""
    google_info = verify_google_token(req.id_token)

    google_id = google_info.get("sub")
    email = google_info.get("email")
    name = google_info.get("name", "")

    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    db = SessionLocal()
    try:
        # Check if user already exists by google_id
        user = db.query(User).filter(User.google_id == google_id).first()

        if not user:
            # Check if user exists by email (maybe they signed up with password first)
            user = db.query(User).filter(User.email == email).first()
            if user:
                # Link Google to existing account
                user.google_id = google_id
                if not user.name:
                    user.name = name
                user.auth_provider = "google" if not user.hashed_password else user.auth_provider
                db.commit()
            else:
                # Create new user
                user = User(
                    email=email,
                    name=name,
                    auth_provider="google",
                    google_id=google_id,
                )
                db.add(user)
                db.commit()
                db.refresh(user)

        token = create_access_token({"sub": str(user.id), "email": user.email})
        return AuthResponse(
            token=token,
            user={"id": user.id, "email": user.email, "name": user.name, "provider": user.auth_provider},
        )
    finally:
        db.close()


# ── Current User Info ─────────────────────────────────────────────────────────

@auth_router.get("/me")
def get_me(user_id: int = Depends(get_current_user_id)):
    """Get the current authenticated user's info."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "provider": user.auth_provider,
        }
    finally:
        db.close()
