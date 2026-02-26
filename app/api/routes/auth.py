from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm

from app import crud
from app.api.deps import CurrentUser, SessionDep, TokenDep
from app.core.config import settings
from app.core.limiter import limiter
from app.core.security import ALGORITHM, blacklist_token, create_access_token
from app.observability.metrics import auth_events_total
from app.schemas import Token, UserPublic

router = APIRouter(tags=["auth"])


@router.post("/login")
@limiter.limit("5/minute")
def login_access_token(
    request: Request,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """OAuth2 compatible token login, get an access token for future requests."""
    user = crud.authenticate(session=session, email=form_data.username, password=form_data.password)
    if not user:
        auth_events_total.labels(result="failure", reason="invalid_credentials").inc()
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not user.is_active:
        auth_events_total.labels(result="failure", reason="inactive_user").inc()
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    auth_events_total.labels(result="success", reason="login").inc()
    return Token(access_token=create_access_token(user.id, expires_delta=access_token_expires))


@router.post("/logout")
async def logout(token: TokenDep) -> dict:
    """Invalidate the current access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        auth_events_total.labels(result="success", reason="logout_invalid_token").inc()
        return {"message": "ok"}
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        ttl = int(exp - datetime.now(UTC).timestamp())
        if ttl > 0:
            await blacklist_token(jti, ttl)
    auth_events_total.labels(result="success", reason="logout").inc()
    return {"message": "ok"}


@router.post("/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> UserPublic:
    """Test access token validity."""
    return current_user
