import base64
from typing import Any

import httpx
from fastapi import UploadFile

from core.config import get_settings
from core.exceptions import ExternalServiceError, InvalidInputError

TRANSCRIPTION_PROMPT = """Transcribe this audio verbatim in its original language.
Preserve medical terms, names, numbers, and units. Return only the transcript.
Do not translate, summarize, explain, or answer the speech."""


def _detect_audio_format(data: bytes) -> str | None:
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "wav"
    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0):
        return "mp3"
    if data.startswith(b"OggS"):
        return "ogg"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "m4a"
    return None


def _response_text(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ExternalServiceError("Speech-to-text returned an invalid response") from error
    if isinstance(content, list):
        content = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        raise ExternalServiceError("Speech-to-text returned an empty transcript")
    return content.strip()


async def transcribe_audio(file: UploadFile) -> str:
    settings = get_settings()
    data = await file.read(settings.max_audio_bytes + 1)
    if not data:
        raise InvalidInputError("Audio file is empty")
    if len(data) > settings.max_audio_bytes:
        raise InvalidInputError(f"Audio exceeds the {settings.max_audio_bytes}-byte upload limit")
    audio_format = _detect_audio_format(data)
    if audio_format is None:
        raise InvalidInputError("Supported audio formats are WAV, MP3, OGG, WebM, and M4A")

    body = {
        "model": settings.multimodal_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": TRANSCRIPTION_PROMPT},
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(data).decode("ascii"),
                            "format": audio_format,
                        },
                    },
                ],
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
            return _response_text(response.json())
    except httpx.HTTPError as error:
        raise ExternalServiceError("Speech-to-text request failed") from error
