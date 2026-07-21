from functools import lru_cache

from minio import Minio

from core.config import get_settings


@lru_cache
def get_minio_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key.get_secret_value(),
        secure=settings.minio_secure,
    )


@lru_cache
def get_minio_public_client() -> Minio:
    settings = get_settings()
    secure = (
        settings.minio_secure
        if settings.minio_public_secure is None
        else settings.minio_public_secure
    )
    return Minio(
        settings.minio_public_endpoint or settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key.get_secret_value(),
        secure=secure,
    )
