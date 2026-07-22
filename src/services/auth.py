from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import AuthenticationError, ConflictError, InactiveUserError
from core.security import create_api_token, hash_password, verify_password
from models import User


async def register_user(
    session: AsyncSession, *, email: str, full_name: str, password: str
) -> User:
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
        api_token=create_api_token(),
        last_activity_at=now,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise ConflictError("An account with this email already exists") from error
    await session.refresh(user)
    return user


async def login_user(session: AsyncSession, *, email: str, password: str) -> User:
    normalized_email = email.lower()
    user = await session.scalar(select(User).where(func.lower(User.email) == normalized_email))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password")
    if not user.is_active:
        raise InactiveUserError("Account is inactive")

    user.last_activity_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    return user


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
    await session.refresh(user)
    return user


async def change_password(
    session: AsyncSession, user: User, *, current_password: str, new_password: str
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AuthenticationError("Current password is incorrect")

    user.password_hash = hash_password(new_password)
    await session.commit()
