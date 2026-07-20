import base64
from typing import Any

import httpx

from core.config import get_settings
from core.exceptions import ExternalServiceError

OCR_PROMPT = """Extract all readable text from this medical document verbatim.
Preserve headings, table labels, measurements, units, and the original language.
Return only extracted text. Do not summarize or add medical advice."""


async def extract_text_with_vlm(data: bytes, content_type: str, filename: str) -> str:
    return await analyze_with_vlm(data, content_type, filename, OCR_PROMPT)


async def analyze_with_vlm(data: bytes, content_type: str, filename: str, instruction: str) -> str:
    settings = get_settings()
    encoded = base64.b64encode(data).decode("ascii")
    data_url = f"data:{content_type};base64,{encoded}"
    if content_type == "application/pdf":
        attachment: dict[str, Any] = {
            "type": "file",
            "file": {"filename": filename, "file_data": data_url},
        }
    else:
        attachment = {"type": "image_url", "image_url": {"url": data_url}}

    body = {
        "model": settings.multimodal_model,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": instruction}, attachment],
            }
        ],
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {settings.multimodal_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(settings.multimodal_api_url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise ExternalServiceError("Multimodal OCR request failed") from error

    if isinstance(content, list):
        content = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        raise ExternalServiceError("Multimodal OCR returned no text")
    return content.strip()
