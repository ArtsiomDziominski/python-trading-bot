import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    new_jti,
    safe_decode_token,
    verify_password,
)
from app.models import PasswordResetToken, RefreshToken, User
from app.models.enums import UserRole
from app.services import email_service


def _telegram_bot_token() -> str:
    s = get_settings()
    return s.telegram_login_bot_token or s.telegram_bot_token


def verify_telegram_widget(data: dict) -> bool:
    bot_token = _telegram_bot_token()
    if not bot_token:
        return False
    check_hash = data.get("hash")
    if not check_hash:
        return False
    pairs = []
    for k in sorted(data.keys()):
        if k == "hash":
            continue
        pairs.append(f"{k}={data[k]}")
    data_check_string = "\n".join(pairs)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return h == check_hash


async def register_user(db: AsyncSession, email: str, password: str, name: str | None) -> User:
    existing = await db.execute(select(User).where(User.email == email.lower()))
    if existing.scalar_one_or_none():
        raise ValueError("Email already registered")
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        name=name,
        role=UserRole.USER,
    )
    db.add(user)
    await db.flush()
    return user


async def login_user(db: AsyncSession, email: str, password: str) -> tuple[User, str, str]:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")
    if not user.is_active:
        raise ValueError("User inactive")
    return await issue_tokens(db, user)


async def issue_tokens(db: AsyncSession, user: User) -> tuple[User, str, str]:
    jti = new_jti()
    settings = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    db.add(RefreshToken(user_id=user.id, jti=jti, expires_at=exp, revoked=False))
    access = create_access_token(str(user.id), {"role": user.role.value})
    refresh = create_refresh_token(jti, str(user.id))
    return user, access, refresh


async def refresh_session(db: AsyncSession, refresh_token: str) -> tuple[User, str, str]:
    payload = safe_decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise ValueError("Invalid refresh token")
    jti = payload.get("jti")
    sub = payload.get("sub")
    if not jti or not sub:
        raise ValueError("Invalid refresh token")
    result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    row = result.scalar_one_or_none()
    if row is None or row.revoked:
        raise ValueError("Invalid refresh token")
    if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise ValueError("Expired refresh token")
    user = await db.get(User, int(sub))
    if user is None or not user.is_active:
        raise ValueError("User missing")
    row.revoked = True
    return await issue_tokens(db, user)


async def request_password_reset(db: AsyncSession, email: str) -> None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if user is None:
        return
    raw = secrets.token_urlsafe(32)
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    db.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(raw), expires_at=exp))
    settings = get_settings()
    link = f"{settings.frontend_base_url}/reset-password?token={raw}"
    email_service.send_email(user.email, "Password reset", f"Reset link (valid 1h):\n{link}")


async def confirm_password_reset(db: AsyncSession, token: str, new_password: str) -> None:
    th = hash_token(token)
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == th))
    row = result.scalar_one_or_none()
    if row is None or row.used_at is not None:
        raise ValueError("Invalid token")
    if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise ValueError("Expired token")
    user = await db.get(User, row.user_id)
    if user is None:
        raise ValueError("Invalid token")
    user.password_hash = hash_password(new_password)
    row.used_at = datetime.now(timezone.utc)


async def google_exchange_code(db: AsyncSession, code: str, redirect_uri: str | None) -> tuple[User, str, str]:
    s = get_settings()
    if not s.google_client_id or not s.google_client_secret:
        raise ValueError("Google OAuth not configured")
    uri = redirect_uri or s.google_redirect_uri
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": s.google_client_id,
                "client_secret": s.google_client_secret,
                "redirect_uri": uri,
                "grant_type": "authorization_code",
            },
        )
        r.raise_for_status()
        access = r.json().get("access_token")
        if not access:
            raise ValueError("No access token from Google")
        u = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access}"},
        )
        u.raise_for_status()
        info = u.json()
    email = info.get("email")
    sub = info.get("sub")
    if not email or not sub:
        raise ValueError("Invalid Google profile")
    result = await db.execute(select(User).where(User.google_sub == sub))
    user = result.scalar_one_or_none()
    if user is None:
        result = await db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()
        if user:
            user.google_sub = sub
        else:
            user = User(email=email.lower(), google_sub=sub, name=info.get("name"), role=UserRole.USER)
            db.add(user)
            await db.flush()
    return await issue_tokens(db, user)


def google_authorize_url(state: str | None = None) -> str:
    s = get_settings()
    q = {
        "client_id": s.google_client_id,
        "redirect_uri": s.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        q["state"] = state
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(q)


async def telegram_login(db: AsyncSession, data: dict) -> tuple[User, str, str]:
    if not verify_telegram_widget(data):
        raise ValueError("Invalid Telegram data")
    tid = str(data["id"])
    result = await db.execute(select(User).where(User.telegram_id == tid))
    user = result.scalar_one_or_none()
    if user is None:
        email = f"tg_{tid}@telegram.local"
        user = User(
            email=email,
            password_hash=None,
            name=data.get("first_name"),
            telegram_id=tid,
            role=UserRole.USER,
        )
        db.add(user)
        await db.flush()
    return await issue_tokens(db, user)
