from uuid import UUID

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.content import load_prompt, load_skills, skill_catalog
from models import Message
from models.enums import MessageRole
from services.multimodal import analyze_with_vlm
from services.storage import get_object_bytes
from services.uploads import get_owned_upload, list_session_uploads
from services.vector import hybrid_search


def _openai_base_url(chat_completions_url: str) -> str:
    suffix = "/chat/completions"
    url = chat_completions_url.rstrip("/")
    return url[: -len(suffix)] if url.endswith(suffix) else url


def create_chat_model() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=_openai_base_url(settings.llm_api_url),
        temperature=0.2,
        streaming=True,
        stream_usage=False,
        timeout=120,
        max_retries=2,
    )


def _format_search_results(query: str) -> str:
    return f"No shared guideline results were found for: {query}"


def build_agent_tools(db: AsyncSession, *, user_id: UUID, session_id: UUID) -> list[BaseTool]:
    @tool
    async def load_skill(name: str) -> str:
        """Load detailed instructions for an available specialized skill by exact name."""
        try:
            skill = load_skills().get(name)
            if skill is None:
                return f"Tool error: unknown skill '{name}'. Available: {', '.join(load_skills())}"
            return skill.content
        except Exception:
            return "Tool error: the requested skill could not be loaded."

    @tool
    async def search_medical_guidelines(query: str) -> str:
        """Hybrid-search the admin-managed shared medical guidelines for relevant evidence."""
        try:
            hits = await hybrid_search(query)
            if not hits:
                return _format_search_results(query)
            return "\n\n".join(
                "\n".join(
                    [
                        f"[Result {index}]",
                        f"Title: {hit.title}",
                        f"Source: {hit.source}",
                        f"Year: {hit.publication_year or 'not provided'}",
                        f"Chunk: {hit.chunk_index}",
                        f"Score: {hit.score:.4f}",
                        f"Content: {hit.content}",
                    ]
                )
                for index, hit in enumerate(hits, start=1)
            )
        except Exception:
            return "Tool error: shared medical guideline search is currently unavailable."

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

    return [load_skill, search_medical_guidelines, inspect_session_file]


async def build_system_prompt(db: AsyncSession, *, user_id: UUID, session_id: UUID) -> str:
    uploads = await list_session_uploads(db, user_id, session_id)
    if uploads:
        files = "\n".join(
            f"- {upload.id}: {upload.original_filename} ({upload.content_type})"
            for upload in uploads
        )
    else:
        files = "- No files are attached to this session."
    return "\n\n".join(
        [
            load_prompt("medical_assistant"),
            "## Available Skills\n" + skill_catalog(),
            "## Current Session Files\n" + files,
        ]
    )


async def load_chat_history(db: AsyncSession, session_id: UUID) -> list[BaseMessage]:
    limit = get_settings().chat_history_limit
    rows = list(
        await db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.sequence_number.desc())
            .limit(limit)
        )
    )
    messages: list[BaseMessage] = []
    for message in reversed(rows):
        if message.role == MessageRole.USER:
            messages.append(HumanMessage(content=message.content))
        elif message.content:
            messages.append(AIMessage(content=message.content))
    return messages


async def create_session_agent(db: AsyncSession, *, user_id: UUID, session_id: UUID):
    return create_agent(
        model=create_chat_model(),
        tools=build_agent_tools(db, user_id=user_id, session_id=session_id),
        system_prompt=await build_system_prompt(db, user_id=user_id, session_id=session_id),
        name="mudawi_medical_agent",
    )
