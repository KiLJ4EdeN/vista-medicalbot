import asyncio
from datetime import timedelta
from typing import BinaryIO

from minio.error import S3Error

from core.config import get_settings
from core.exceptions import ExternalServiceError
from db.storage import get_minio_client, get_minio_public_client

_bucket_lock = asyncio.Lock()
_bucket_ready = False


async def _ensure_bucket() -> None:
    global _bucket_ready
    if _bucket_ready:
        return

    async with _bucket_lock:
        if _bucket_ready:
            return
        client = get_minio_client()
        bucket = get_settings().minio_bucket
        try:
            exists = await asyncio.to_thread(client.bucket_exists, bucket)
            if not exists:
                await asyncio.to_thread(client.make_bucket, bucket)
        except S3Error as error:
            if error.code in {"BucketAlreadyExists", "BucketAlreadyOwnedByYou"}:
                _bucket_ready = True
                return
            raise ExternalServiceError("Object storage is unavailable") from error
        except Exception as error:
            raise ExternalServiceError("Object storage is unavailable") from error
        _bucket_ready = True


async def put_object(object_key: str, data: BinaryIO, *, length: int, content_type: str) -> None:
    await _ensure_bucket()
    settings = get_settings()
    client = get_minio_client()
    try:
        await asyncio.to_thread(
            client.put_object,
            settings.minio_bucket,
            object_key,
            data,
            length,
            content_type=content_type,
        )
    except S3Error as error:
        raise ExternalServiceError("Failed to store uploaded file") from error
    except Exception as error:
        raise ExternalServiceError("Failed to store uploaded file") from error


async def remove_object(object_key: str) -> None:
    await _ensure_bucket()
    settings = get_settings()
    client = get_minio_client()
    try:
        await asyncio.to_thread(client.remove_object, settings.minio_bucket, object_key)
    except S3Error as error:
        raise ExternalServiceError("Failed to remove stored file") from error
    except Exception as error:
        raise ExternalServiceError("Failed to remove stored file") from error


def _read_object(bucket: str, object_key: str) -> bytes:
    response = get_minio_client().get_object(bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


async def get_object_bytes(object_key: str) -> bytes:
    await _ensure_bucket()
    try:
        return await asyncio.to_thread(_read_object, get_settings().minio_bucket, object_key)
    except Exception as error:
        raise ExternalServiceError("Failed to read stored file") from error


async def presigned_download_url(object_key: str, *, expires: timedelta) -> str:
    await _ensure_bucket()
    settings = get_settings()
    client = get_minio_public_client()
    try:
        return await asyncio.to_thread(
            client.presigned_get_object,
            settings.minio_bucket,
            object_key,
            expires=expires,
        )
    except S3Error as error:
        raise ExternalServiceError("Failed to create a download URL") from error
    except Exception as error:
        raise ExternalServiceError("Failed to create a download URL") from error
