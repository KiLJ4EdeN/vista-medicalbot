import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from langchain_core.tools import BaseTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.skills import load_prompt, skill_catalog
from models import ChatMessage
from models.enums import MessageRole
from services.tools import load_skill, make_file_tool, search_medical_guidelines
from services.uploads import list_session_uploads


async def complete_chat(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.llm_api_url,
            headers={
                "Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            json={"model": settings.llm_model, "messages": messages, "temperature": 0.2},
            timeout=120,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise RuntimeError("The language model returned an invalid response")
    return content


def build_agent_tools(db: AsyncSession, *, user_id: UUID, session_id: UUID) -> list[BaseTool]:
    return [
        load_skill,
        search_medical_guidelines,
        make_file_tool(db, user_id=user_id, session_id=session_id),
    ]


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


async def load_chat_history(db: AsyncSession, session_id: UUID) -> list[dict[str, str]]:
    limit = get_settings().chat_history_limit
    rows = list(
        await db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.sequence_number.desc())
            .limit(limit)
        )
    )
    messages: list[dict[str, str]] = []
    for message in reversed(rows):
        if message.role == MessageRole.USER:
            messages.append({"role": "user", "content": message.content})
        elif message.content:
            messages.append({"role": "assistant", "content": message.content})
    return messages


_REACT_INSTRUCTION = """You have access to these tools:

{tool_descriptions}

To use a tool, respond with exactly these two lines:
Action: tool_name
Action Input: {{"arg1": "value1", "arg2": "value2"}}

After you receive the tool result, continue. When you have all
information needed, end with:
Final Answer: your response"""


@dataclass(frozen=True, slots=True)
class AgentEvent:
    event: str
    content: str = ""


class ReActAgent:
    def __init__(self, tools: list[BaseTool], system_prompt: str):
        self.tools: dict[str, BaseTool] = {t.name: t for t in tools}
        tool_descriptions = "\n".join(f"- {t.name}: {t.description}" for t in tools)
        self.system_prompt = (
            f"{system_prompt}\n\n{_REACT_INSTRUCTION.format(tool_descriptions=tool_descriptions)}"
        )

    async def astream(
        self, history: list[dict[str, str]], *, recursion_limit: int
    ) -> AsyncIterator[AgentEvent]:
        messages = [{"role": "system", "content": self.system_prompt}, *history]

        for _ in range(recursion_limit):
            full_content = await complete_chat(messages)

            if "Final Answer:" in full_content:
                final = full_content.split("Final Answer:", 1)[1].strip()
                yield AgentEvent("final", final)
                return

            action = self._parse_action(full_content)
            if action is not None:
                name, args = action
                yield AgentEvent("tool_started", name)

                tool = self.tools.get(name)
                if tool is not None:
                    try:
                        result = await tool.ainvoke(args)
                    except Exception as exc:
                        result = f"Tool error: {exc}"
                else:
                    result = f"Tool error: unknown tool '{name}'"

                yield AgentEvent("tool_finished")
                messages.append({"role": "assistant", "content": full_content})
                messages.append({"role": "user", "content": f"[Tool result]\n{result}"})
                continue

            yield AgentEvent("final", full_content)
            return

        yield AgentEvent("final", "Agent reached maximum recursion limit.")

    @staticmethod
    def _parse_action(content: str) -> tuple[str, dict[str, Any]] | None:
        lines = content.strip().split("\n")
        action_line = None
        input_line = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Action:"):
                action_line = stripped[len("Action:") :].strip()
            elif stripped.startswith("Action Input:"):
                input_line = stripped[len("Action Input:") :].strip()
        if action_line and input_line:
            try:
                return action_line, json.loads(input_line)
            except (json.JSONDecodeError, TypeError, ValueError):
                return action_line, {"query": input_line.strip("\"'")}
        return None


async def create_session_agent(db: AsyncSession, *, user_id: UUID, session_id: UUID) -> ReActAgent:
    return ReActAgent(
        tools=build_agent_tools(db, user_id=user_id, session_id=session_id),
        system_prompt=await build_system_prompt(db, user_id=user_id, session_id=session_id),
    )
