from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from api.dependencies import DatabaseSession
from schemas.auth import AuthResponse, LogoutRequest, RefreshRequest, RegisterRequest, TokenPair
from schemas.user import UserResponse
from services.auth import IssuedTokens, login_user, logout_user, register_user, rotate_refresh_token

router = APIRouter(prefix="/auth", tags=["authentication"])


def _token_pair(tokens: IssuedTokens) -> TokenPair:
    return TokenPair(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


def _auth_response(user: UserResponse, tokens: IssuedTokens) -> AuthResponse:
    return AuthResponse(
        user=user,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: DatabaseSession) -> AuthResponse:
    user, tokens = await register_user(
        session,
        email=str(payload.email),
        full_name=payload.full_name,
        password=payload.password,
    )
    return _auth_response(UserResponse.model_validate(user), tokens)


@router.post("/login", response_model=AuthResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], session: DatabaseSession
) -> AuthResponse:
    user, tokens = await login_user(session, email=form.username, password=form.password)
    return _auth_response(UserResponse.model_validate(user), tokens)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, session: DatabaseSession) -> TokenPair:
    return _token_pair(await rotate_refresh_token(session, payload.refresh_token))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, session: DatabaseSession) -> Response:
    await logout_user(session, payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
