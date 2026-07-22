import asyncio
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from core.config import get_settings
from core.exceptions import InvalidInputError


@dataclass(frozen=True, slots=True)
class ValidatedDocument:
    data: bytes
    original_filename: str
    content_type: str
    suffix: str
    size_bytes: int
    sha256: str


def _detect_file_type(header: bytes) -> tuple[str, str] | None:
    if header.startswith(b"%PDF-"):
        return "application/pdf", ".pdf"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def _count_pdf_pages(data: bytes) -> int:
    try:
        return len(PdfReader(BytesIO(data), strict=False).pages)
    except (PdfReadError, OSError, ValueError) as error:
        raise InvalidInputError("The uploaded PDF is invalid or unreadable") from error


async def validate_document_upload(file: UploadFile) -> ValidatedDocument:
    settings = get_settings()
    data = await file.read(settings.max_upload_bytes + 1)
    if not data:
        raise InvalidInputError("Uploaded file is empty")
    if len(data) > settings.max_upload_bytes:
        raise InvalidInputError(f"File exceeds the {settings.max_upload_bytes}-byte upload limit")

    detected = _detect_file_type(data[:16])
    if detected is None:
        raise InvalidInputError("Only PDF, JPEG, PNG, and WebP files are supported")
    content_type, suffix = detected
    if content_type == "application/pdf":
        page_count = await asyncio.to_thread(_count_pdf_pages, data)
        if page_count > settings.max_pdf_pages:
            raise InvalidInputError(
                f"PDF exceeds the {settings.max_pdf_pages}-page processing limit"
            )

    original_filename = Path(file.filename or f"upload{suffix}").name
    original_filename = (original_filename or f"upload{suffix}")[:255]
    return ValidatedDocument(
        data=data,
        original_filename=original_filename,
        content_type=content_type,
        suffix=suffix,
        size_bytes=len(data),
        sha256=sha256(data).hexdigest(),
    )
