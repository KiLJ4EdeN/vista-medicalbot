from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from core.config import get_settings
from core.exceptions import TokenError

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_password: str) -> bool:
    return password_hash.verify(password, encoded_password)


def hash_token(token: str) -> str:
    """SHA-256 hex digest of a JWT string.

    Used instead of storing the raw token in the database so a DB
    breach leaks only hashes, not usable refresh tokens.
    """
    return sha256(token.encode()).hexdigest()


def create_access_token(user_id: UUID) -> str:
    """Short-lived JWT (minutes) carrying user identity.

    Payload: sub (user_id), type: "access", iat, exp.
    The type claim prevents this from being used as a refresh token.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: UUID, token_id: UUID, family_id: UUID) -> tuple[str, datetime]:
    """Long-lived JWT (days) with rotation tracking fields.

    Payload: sub, type: "refresh", jti (token_id for lookup),
    family (theft-detection group), iat, exp.
    The token string is hashed before storage; only the hash persists.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(token_id),
        "family": str(family_id),
        "iat": now,
        "exp": expires_at,
    }
    encoded = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return encoded, expires_at


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """Verify JWT signature, expiry, required claims, and type field.

    Shared by both access and refresh token paths. The caller specifies
    expected_type ("access" or "refresh") so a token of one type cannot
    be used against endpoints expecting the other.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "type", "iat", "exp"]},
        )
    except InvalidTokenError as error:
        raise TokenError("Invalid or expired token") from error

    if payload.get("type") != expected_type:
        raise TokenError("Invalid token type")
    return payload
