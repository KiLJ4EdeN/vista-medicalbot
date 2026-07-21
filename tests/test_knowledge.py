import asyncio
from pathlib import Path

import httpx
import pytest

from tests.conftest import KNOWLEDGE_PDF

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not Path(KNOWLEDGE_PDF).is_file(), reason="data/NCCN.pdf not found"),
]


@pytest.mark.asyncio
async def test_knowledge_upload_and_search(
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    pdf_path = Path(KNOWLEDGE_PDF)
    assert pdf_path.is_file()

    files = {
        "file": ("NCCN.pdf", pdf_path.read_bytes(), "application/pdf"),
        "title": (None, "NCCN Breast Cancer Guidelines"),
    }
    r = await client.post("/knowledge", files=files, headers=admin_headers)
    assert r.status_code == 202, f"Upload failed: {r.text}"
    entry = r.json()
    entry_id = entry["id"]
    assert entry["status"] == "pending"

    for _ in range(60):
        await asyncio.sleep(2)
        r2 = await client.get(f"/knowledge/{entry_id}", headers=admin_headers)
        assert r2.status_code == 200
        status = r2.json()["status"]
        if status == "ready":
            break
        if status == "failed":
            pytest.fail(f"Knowledge processing failed: {r2.json().get('processing_error')}")
    else:
        pytest.fail("Knowledge processing did not complete within 120 seconds")

    r3 = await client.post(
        "/knowledge/search/test",
        json={"query": "breast cancer screening mammography", "limit": 5},
        headers=admin_headers,
    )
    assert r3.status_code == 200, f"Search failed: {r3.text}"
    hits = r3.json()["items"]
    assert len(hits) > 0, "Expected at least one search result"
    assert any("breast" in hit["content"].lower() for hit in hits)

    r4 = await client.post(
        "/knowledge/search/test",
        json={"query": "adjuvant endocrine therapy tamoxifen", "limit": 5},
        headers=admin_headers,
    )
    assert r4.status_code == 200
    hits2 = r4.json()["items"]
    assert len(hits2) > 0

    r5 = await client.delete(f"/knowledge/{entry_id}", headers=admin_headers)
    assert r5.status_code == 204
