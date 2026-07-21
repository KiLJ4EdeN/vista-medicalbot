from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from api.dependencies import AdminAccess, DatabaseSession
from schemas.admin import AdminDashboardResponse, AdminUserListResponse, AdminUserResponse
from services.admin import dashboard_stats, get_user, list_users, set_user_active

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=AdminUserListResponse)
async def get_users(
    db: DatabaseSession,
    _admin: AdminAccess,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=320)] = None,
    is_active: bool | None = None,
) -> AdminUserListResponse:
    items, total = await list_users(
        db,
        offset=offset,
        limit=limit,
        search=search,
        is_active=is_active,
    )
    return AdminUserListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user_details(
    user_id: UUID, db: DatabaseSession, _admin: AdminAccess
) -> AdminUserResponse:
    return AdminUserResponse.model_validate(await get_user(db, user_id))


@router.post("/users/{user_id}/activate", response_model=AdminUserResponse)
async def activate_user(
    user_id: UUID, db: DatabaseSession, _admin: AdminAccess
) -> AdminUserResponse:
    return AdminUserResponse.model_validate(await set_user_active(db, user_id, is_active=True))


@router.post("/users/{user_id}/deactivate", response_model=AdminUserResponse)
async def deactivate_user(
    user_id: UUID, db: DatabaseSession, _admin: AdminAccess
) -> AdminUserResponse:
    return AdminUserResponse.model_validate(await set_user_active(db, user_id, is_active=False))


@router.get("/stats", response_model=AdminDashboardResponse)
async def get_dashboard_stats(db: DatabaseSession, _admin: AdminAccess) -> AdminDashboardResponse:
    return AdminDashboardResponse.model_validate(await dashboard_stats(db), from_attributes=True)
