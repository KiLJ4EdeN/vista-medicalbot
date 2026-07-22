from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_permanent_token_follows_account_status(
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    email = f"auth-{uuid4().hex[:8]}@example.com"
    password = "testpass123"
    registration = await client.post(
        "/auth/register",
        json={"email": email, "full_name": "Auth User", "password": password},
    )
    assert registration.status_code == 201
    user_id = registration.json()["user"]["id"]
    token = registration.json()["token"]
    assert token.startswith("mwd_")

    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    assert login.json()["token"] == token

    bearer_headers = {"Authorization": f"Bearer {token}"}
    password_change = await client.post(
        "/profile/password",
        json={"current_password": password, "new_password": "newtestpass123"},
        headers=bearer_headers,
    )
    assert password_change.status_code == 204

    login_after_change = await client.post(
        "/auth/login",
        json={"email": email, "password": "newtestpass123"},
    )
    assert login_after_change.status_code == 200
    assert login_after_change.json()["token"] == token

    deactivated = await client.post(f"/admin/users/{user_id}/deactivate", headers=admin_headers)
    assert deactivated.status_code == 200
    blocked = await client.get("/profile", headers=bearer_headers)
    assert blocked.status_code == 403

    reactivated = await client.post(f"/admin/users/{user_id}/activate", headers=admin_headers)
    assert reactivated.status_code == 200
    restored = await client.get("/profile", headers=bearer_headers)
    assert restored.status_code == 200
