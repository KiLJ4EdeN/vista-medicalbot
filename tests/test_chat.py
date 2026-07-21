import asyncio
import json
from pathlib import Path

import httpx
import pytest

from tests.conftest import KNOWLEDGE_PDF, skip_if_no_llm

OUTPUT = Path(__file__).parent / "output"
OUTPUT.mkdir(exist_ok=True)

pytestmark = [pytest.mark.integration, skip_if_no_llm]


def _save_sse(name: str, response: httpx.Response) -> None:
    events = []
    for line in response.text.strip().splitlines():
        if line.startswith("event: "):
            events.append({"event": line[7:]})
        elif line.startswith("data: ") and events:
            try:
                events[-1]["data"] = json.loads(line[6:])
            except json.JSONDecodeError:
                events[-1]["data"] = line[6:]
    (OUTPUT / f"{name}.json").write_text(
        json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_chat_flow(
    client: httpx.AsyncClient,
    user_token: str,
    session_id: str,
) -> None:
    headers = {"Authorization": f"Bearer {user_token}"}

    r = await client.post(
        f"/sessions/{session_id}/messages",
        json={"content": "Hello, what can you help me with?"},
        headers=headers,
    )
    assert r.status_code == 200, f"Chat failed: {r.text[:500]}"
    _save_sse("test_chat_flow", r)

    assert "message_started" in r.text
    assert "message_completed" in r.text
    assert "token" in r.text

    r2 = await client.get(f"/sessions/{session_id}/messages", headers=headers)
    assert r2.status_code == 200
    msgs = r2.json()["items"]
    assert len(msgs) >= 2

    assistant_msgs = [m for m in msgs if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1
    assert len(assistant_msgs[-1]["content"]) > 0


@pytest.mark.asyncio
async def test_chat_with_knowledge_search(
    client: httpx.AsyncClient,
    user_token: str,
    session_id: str,
    admin_headers: dict[str, str],
) -> None:
    pdf_path = Path(KNOWLEDGE_PDF)
    if not pdf_path.is_file():
        pytest.skip("data/NCCN.pdf not found")

    files = {
        "file": ("NCCN.pdf", pdf_path.read_bytes(), "application/pdf"),
        "title": (None, "NCCN Breast Cancer Guidelines"),
        "source": (None, "NCCN"),
    }
    r = await client.post("/knowledge", files=files, headers=admin_headers)
    assert r.status_code == 202

    entry_id = r.json()["id"]
    for _ in range(30):
        await asyncio.sleep(2)
        r2 = await client.get(f"/knowledge/{entry_id}", headers=admin_headers)
        status = r2.json()["status"]
        if status == "ready":
            break
        if status == "failed":
            pytest.fail("Processing failed")
    else:
        pytest.fail("Processing did not complete within 60 seconds")

    headers = {"Authorization": f"Bearer {user_token}"}
    r3 = await client.post(
        f"/sessions/{session_id}/messages",
        json={"content": "What are the NCCN recommendations for breast cancer screening?"},
        headers=headers,
    )
    assert r3.status_code == 200
    assert "message_completed" in r3.text
    _save_sse("test_chat_with_knowledge_search", r3)

    r4 = await client.delete(f"/knowledge/{entry_id}", headers=admin_headers)
    assert r4.status_code == 204
