from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool
    last_activity_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int
    offset: int
    limit: int


class AdminDashboardResponse(BaseModel):
    total_users: int
    registrations_today: int
    active_users: int
    online_users: int
    sessions_total: int
    sessions_today: int
    chats_total: int
    chats_today: int
    generated_at: datetime
