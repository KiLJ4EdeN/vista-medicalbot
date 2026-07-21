from uuid import UUID

from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession

from services.storage import get_object_bytes
from services.uploads import get_owned_upload
from services.vlm import analyze_with_vlm


def make_file_tool(db: AsyncSession, *, user_id: UUID, session_id: UUID) -> BaseTool:
    @tool
    async def inspect_session_file(upload_id: str, instruction: str) -> str:
        """OCR or analyze one current-session PDF/image using its exact upload UUID."""
        try:
            parsed_id = UUID(upload_id)
        except ValueError:
            return "Tool error: upload_id must be a valid UUID from the session file list."
        try:
            upload = await get_owned_upload(db, user_id, parsed_id)
            if upload.session_id != session_id:
                return "Tool error: that upload does not belong to the current session."
            data = await get_object_bytes(upload.object_key)
            result = await analyze_with_vlm(
                data,
                upload.content_type,
                upload.original_filename,
                instruction,
            )
            return f"File: {upload.original_filename}\n\n{result}"
        except Exception:
            return "Tool error: the session file could not be analyzed."

    return inspect_session_file
