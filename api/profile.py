from fastapi import APIRouter, Response, status

from api.dependencies import CurrentUser, DatabaseSession
from schemas.user import PasswordChangeRequest, ProfileUpdateRequest, UserResponse
from services.auth import change_password, update_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=UserResponse)
async def get_profile(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch("", response_model=UserResponse)
async def patch_profile(
    payload: ProfileUpdateRequest, user: CurrentUser, session: DatabaseSession
) -> UserResponse:
    updated_user = await update_profile(
        session,
        user,
        email=str(payload.email) if payload.email is not None else None,
        full_name=payload.full_name,
    )
    return UserResponse.model_validate(updated_user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def update_password(
    payload: PasswordChangeRequest, user: CurrentUser, session: DatabaseSession
) -> Response:
    await change_password(
        session,
        user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
