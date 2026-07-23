from typing import cast

from fastapi import APIRouter, status

from api.dependencies import DatabaseSession
from schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from schemas.user import UserResponse
from services.auth import login_user, register_user

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: DatabaseSession) -> AuthResponse:
    user = await register_user(
        session,
        email=str(payload.email),
        full_name=payload.full_name,
        password=payload.password,
    )
    return AuthResponse(
        user=UserResponse.model_validate(user),
        token=cast(str, user.api_token),
    )


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, session: DatabaseSession) -> AuthResponse:
    user = await login_user(session, email=str(payload.email), password=payload.password)
    return AuthResponse(
        user=UserResponse.model_validate(user),
        token=cast(str, user.api_token),
    )
