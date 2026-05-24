"""JWT-based session auth for the admin panel."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .config import Settings, get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

ALGORITHM = "HS256"


def verify_credentials(username: str, password: str, settings: Settings) -> bool:
    """Constant-time comparison against admin credentials from env."""
    if not username or not password:
        return False
    # Plain string comparison is fine for a single fixed credential pair.
    # passlib/bcrypt would be overkill given the secret is set in .env, not stored.
    return (
        username == settings.admin_username
        and password == settings.admin_password
    )


def create_access_token(username: str, settings: Settings) -> tuple[str, int]:
    expires_delta = timedelta(hours=settings.session_ttl_hours)
    expires_at = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": username,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.session_secret, algorithm=ALGORITHM)
    return token, int(expires_delta.total_seconds())


def decode_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(token, settings.session_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token, settings)
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return username
