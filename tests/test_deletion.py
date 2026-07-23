from uuid import UUID

import httpx
import pytest

from core.exceptions import ExternalServiceError
from db.session import async_session_factory
from models import Session, Upload
from services.storage import get_object_bytes

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_session_deletion_removes_rows_and_file(
    client: httpx.AsyncClient,
    user_token: str,
    session_id: str,
) -> None:
    headers = {"Authorization": f"Bearer {user_token}"}
    uploaded = await client.post(
        f"/uploads/sessions/{session_id}",
        files={"file": ("scan.jpg", b"\xff\xd8\xff" + b"\0" * 64, "image/jpeg")},
        headers=headers,
    )
    assert uploaded.status_code == 201
    upload_id = UUID(uploaded.json()["id"])

    async with async_session_factory() as db:
        upload = await db.get(Upload, upload_id)
        assert upload is not None
        object_key = str(upload.object_key)

    deleted = await client.delete(f"/sessions/{session_id}", headers=headers)
    assert deleted.status_code == 204

    async with async_session_factory() as db:
        assert await db.get(Session, UUID(session_id)) is None
        assert await db.get(Upload, upload_id) is None
    with pytest.raises(ExternalServiceError):
        await get_object_bytes(object_key)
