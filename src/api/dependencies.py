from datetime import UTC, datetime
from hmac import compare_digest
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.exceptions import TokenError
from core.security import decode_token
from db.session import get_db
from models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
admin_api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: DatabaseSession
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token, "access")
        user_id = UUID(payload["sub"])
    except (KeyError, TypeError, ValueError, TokenError) as error:
        raise unauthorized from error

    user = await session.get(User, user_id)
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
