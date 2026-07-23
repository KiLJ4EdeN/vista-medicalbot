from typing import cast
from uuid import UUID

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import services.agent as agent_service
from models.enums import ChatLanguage

pytestmark = pytest.mark.integration


def _headers(token: str, language: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Language": language}


@pytest.mark.asyncio
async def test_sessions_are_partitioned_by_language(
    client: httpx.AsyncClient, user_token: str
) -> None:
    session_ids: dict[str, str] = {}
    for language in ChatLanguage:
        response = await client.post(
            "/sessions",
            json={"title": f"{language.value} session"},
            headers=_headers(user_token, language.value),
        )
        assert response.status_code == 201
        assert response.json()["language"] == language.value
        session_ids[language.value] = response.json()["id"]

    for language in ChatLanguage:
        response = await client.get("/sessions", headers=_headers(user_token, language.value))
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == [session_ids[language.value]]

    hidden = await client.get(
        f"/sessions/{session_ids['arabic']}", headers=_headers(user_token, "persian")
    )
    assert hidden.status_code == 404

    missing = await client.get("/sessions", headers={"Authorization": f"Bearer {user_token}"})
    assert missing.status_code == 422
    invalid = await client.get("/sessions", headers=_headers(user_token, "english"))
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_persona_prompt_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_uploads(*args: object, **kwargs: object) -> list[object]:
        return []

    monkeypatch.setattr(agent_service, "list_session_uploads", no_uploads)
    expected = {
        ChatLanguage.ARABIC: ("MUDAWI", "exclusively in Arabic"),
        ChatLanguage.PERSIAN: ("canci", "exclusively in Persian"),
        ChatLanguage.RUSSIAN: ("DR ONLINE", "exclusively in Russian"),
        ChatLanguage.TURKISH: ("DR ONLINE", "in English when it is in English"),
    }

    for language, phrases in expected.items():
        prompt = await agent_service.build_system_prompt(
            cast(AsyncSession, object()),
            user_id=UUID(int=0),
            session_id=UUID(int=1),
            language=language,
        )
        assert all(phrase in prompt for phrase in phrases)
        assert "written in any language" in prompt
