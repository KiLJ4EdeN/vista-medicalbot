from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.exceptions import AuthenticationError, ConflictError, InactiveUserError, TokenError
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from models import RefreshToken, User


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int


def _new_token_pair(
    user_id: UUID, family_id: UUID | None = None
) -> tuple[IssuedTokens, RefreshToken]:
    settings = get_settings()
    token_id = uuid4()
    family_id = family_id or uuid4()
    encoded_refresh, expires_at = create_refresh_token(user_id, token_id, family_id)
    token_record = RefreshToken(
        id=token_id,
        user_id=user_id,
        token_hash=hash_token(encoded_refresh),
        family_id=family_id,
        expires_at=expires_at,
    )
    tokens = IssuedTokens(
        access_token=create_access_token(user_id),
        refresh_token=encoded_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )
    return tokens, token_record


async def register_user(
    session: AsyncSession, *, email: str, full_name: str, password: str
) -> tuple[User, IssuedTokens]:
    normalized_email = email.lower()
    existing = await session.scalar(
        select(User.id).where(func.lower(User.email) == normalized_email)
    )
    if existing is not None:
        raise ConflictError("An account with this email already exists")

    now = datetime.now(UTC)
    user = User(
        email=normalized_email,
        full_name=full_name,
        password_hash=hash_password(password),
        last_activity_at=now,
    )
    session.add(user)
    await session.flush()
    tokens, refresh_record = _new_token_pair(user.id)
    session.add(refresh_record)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise ConflictError("An account with this email already exists") from error
    return user, tokens


async def login_user(
    session: AsyncSession, *, email: str, password: str
) -> tuple[User, IssuedTokens]:
    normalized_email = email.lower()
    user = await session.scalar(select(User).where(func.lower(User.email) == normalized_email))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password")
    if not user.is_active:
        raise InactiveUserError("Account is inactive")

    user.last_activity_at = datetime.now(UTC)
    tokens, refresh_record = _new_token_pair(user.id)
    session.add(refresh_record)
    await session.commit()
    return user, tokens


async def rotate_refresh_token(session: AsyncSession, encoded_token: str) -> IssuedTokens:
    payload = decode_token(encoded_token, "refresh")
    try:
        token_id = UUID(payload["jti"])
        user_id = UUID(payload["sub"])
        family_id = UUID(payload["family"])
    except (KeyError, TypeError, ValueError) as error:
        raise TokenError("Invalid refresh token claims") from error

    token_record = await session.scalar(
        select(RefreshToken).where(RefreshToken.id == token_id).with_for_update()
    )
    if (
        token_record is None
        or token_record.user_id != user_id
        or token_record.family_id != family_id
        or token_record.token_hash != hash_token(encoded_token)
    ):
        raise TokenError("Refresh token is not recognized")

    now = datetime.now(UTC)
    if token_record.revoked_at is not None:
        await _revoke_family(session, family_id, "reuse_detected", now)
        await session.commit()
        raise TokenError("Refresh token reuse detected")
    if token_record.expires_at <= now:
        token_record.revoked_at = now
        token_record.revoke_reason = "expired"
        await session.commit()
        raise TokenError("Refresh token has expired")

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        await _revoke_family(session, family_id, "user_inactive", now)
        await session.commit()
        raise InactiveUserError("Account is inactive")

    tokens, replacement = _new_token_pair(user.id, family_id)
    token_record.revoked_at = now
    token_record.revoke_reason = "rotated"
    token_record.replaced_by_id = replacement.id
    user.last_activity_at = now
    session.add(replacement)
    await session.commit()
    return tokens


async def logout_user(session: AsyncSession, encoded_token: str) -> None:
    payload = decode_token(encoded_token, "refresh")
    try:
        token_id = UUID(payload["jti"])
    except (KeyError, TypeError, ValueError) as error:
        raise TokenError("Invalid refresh token claims") from error

    token_record = await session.scalar(
        select(RefreshToken).where(RefreshToken.id == token_id).with_for_update()
    )
    if token_record is None or token_record.token_hash != hash_token(encoded_token):
        raise TokenError("Refresh token is not recognized")
    if token_record.revoked_at is None:
        token_record.revoked_at = datetime.now(UTC)
        token_record.revoke_reason = "logout"
        await session.commit()


async def update_profile(
    session: AsyncSession, user: User, *, email: str | None, full_name: str | None
) -> User:
    if email is not None and email.lower() != user.email:
        normalized_email = email.lower()
        existing = await session.scalar(
            select(User.id).where(
                func.lower(User.email) == normalized_email,
                User.id != user.id,
            )
        )
        if existing is not None:
            raise ConflictError("An account with this email already exists")
        user.email = normalized_email
    if full_name is not None:
        user.full_name = full_name

    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise ConflictError("An account with this email already exists") from error
    return user


async def change_password(
    session: AsyncSession, user: User, *, current_password: str, new_password: str
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AuthenticationError("Current password is incorrect")

    now = datetime.now(UTC)
    user.password_hash = hash_password(new_password)
    user.password_changed_at = now
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason="password_changed")
    )
    await session.commit()


async def _revoke_family(
    session: AsyncSession, family_id: UUID, reason: str, revoked_at: datetime
) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=revoked_at, revoke_reason=reason)
    )
