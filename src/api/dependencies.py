from datetime import UTC, datetime
from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from db.session import get_db
from models import User
from models.enums import ChatLanguage

bearer_scheme = HTTPBearer(auto_error=False)
admin_api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
ChatLanguageHeader = Annotated[ChatLanguage, Header(alias="X-Language")]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    session: DatabaseSession,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    user = await session.scalar(select(User).where(User.api_token == credentials.credentials))
    if user is None:
        raise unauthorized
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    user.last_activity_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(
    supplied_key: Annotated[str | None, Security(admin_api_key_header)],
) -> None:
    configured_key = get_settings().admin_api_key.get_secret_value()
    if (
        not configured_key
        or supplied_key is None
        or not compare_digest(supplied_key, configured_key)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin API key"
        )


AdminAccess = Annotated[None, Depends(require_admin)]
