"""Auth router: local admin login -> JWT."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ..config import Settings, get_settings
from ..models import LoginRequest, LoginResponse, UserInfo
from ..security import (
    create_access_token,
    get_current_user,
    verify_credentials,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    if not verify_credentials(body.username, body.password, settings):
        logger.warning("event=auth.login.failed username=%s", body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token, ttl = create_access_token(body.username, settings)
    logger.info("event=auth.login.ok username=%s", body.username)
    return LoginResponse(access_token=token, expires_in=ttl)


@router.get("/me", response_model=UserInfo)
async def me(username: str = Depends(get_current_user)) -> UserInfo:
    return UserInfo(username=username)
