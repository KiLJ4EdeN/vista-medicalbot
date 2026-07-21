import json
from typing import Any
from uuid import UUID, uuid4

import httpx
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import AsyncCallbackManagerForLLMRun, BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.content import load_prompt, skill_catalog
from models import ChatMessage
from models.enums import MessageRole
from services.tools import load_skill, make_file_tool, search_medical_guidelines
from services.uploads import list_session_uploads


def _to_openai_dict(msg: BaseMessage) -> dict[str, Any]:
    if isinstance(msg, HumanMessage):
        return {"role": "user", "content": msg.content}
    if isinstance(msg, AIMessage):
        return {"role": "assistant", "content": msg.content}
    if isinstance(msg, SystemMessage):
        return {"role": "system", "content": msg.content}
    if isinstance(msg, ToolMessage):
        return {"role": "user", "content": f"[Tool result]\n{msg.content}"}
    return {"role": "user", "content": str(msg.content)}


class Dr7ChatModel(BaseChatModel):
    api_url: str
    api_key: str
    model: str
    temperature: float = 0.2
    timeout: int = 120

    @property
    def _llm_type(self) -> str:
        return "dr7"

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        body = {
            "model": self.model,
            "messages": [_to_openai_dict(m) for m in messages],
            "temperature": self.temperature,
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=self.timeout,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            generation = ChatGeneration(message=AIMessage(content=content))
            return ChatResult(generations=[generation])

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError("dr7 only supports async generate")


def create_chat_model() -> Dr7ChatModel:
    settings = get_settings()
    return Dr7ChatModel(
        api_url=settings.llm_api_url,
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        temperature=0.2,
        timeout=120,
    )


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


async def load_chat_history(db: AsyncSession, session_id: UUID) -> list[BaseMessage]:
    limit = get_settings().chat_history_limit
    rows = list(
        await db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.sequence_number.desc())
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


_REACT_INSTRUCTION = """You have access to these tools:

{tool_descriptions}

To use a tool, respond with exactly these two lines:
Action: tool_name
Action Input: {{"arg1": "value1", "arg2": "value2"}}

After you receive the tool result, continue. When you have all
information needed, end with:
Final Answer: your response"""


class ReActAgent:
    def __init__(self, model: BaseChatModel, tools: list[BaseTool], system_prompt: str):
        self._loop_model = model
        self.tools: dict[str, BaseTool] = {t.name: t for t in tools}
        tool_descriptions = "\n".join(f"- {t.name}: {t.description}" for t in tools)
        self.system_prompt = (
            f"{system_prompt}\n\n{_REACT_INSTRUCTION.format(tool_descriptions=tool_descriptions)}"
        )

    async def ainvoke(
        self, inputs: dict[str, Any], config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        callbacks = config.get("callbacks", []) if config is not None else []
        recursion_limit = config.get("recursion_limit", 12) if config is not None else 12

        messages: list[BaseMessage] = [SystemMessage(content=self.system_prompt)]
        messages.extend(inputs.get("messages", []))

        for _ in range(recursion_limit):
            response = await self._loop_model.ainvoke(messages)
            raw = response.content
            full_content = raw if isinstance(raw, str) else str(raw)

            if "Final Answer:" in full_content:
                final = full_content.split("Final Answer:", 1)[1].strip()
                for cb in callbacks:
                    await cb.on_llm_new_token(final)
                return {"messages": [AIMessage(content=final)]}

            action = self._parse_action(full_content)
            if action is not None:
                name, args = action
                for cb in callbacks:
                    await cb.on_tool_start({"name": name}, str(args))

                tool = self.tools.get(name)
                if tool is not None:
                    try:
                        result = await tool.ainvoke(args)
                    except Exception as exc:
                        result = f"Tool error: {exc}"
                else:
                    result = f"Tool error: unknown tool '{name}'"

                for cb in callbacks:
                    await cb.on_tool_end(result)

                messages.append(AIMessage(content=full_content))
                messages.append(ToolMessage(content=result, tool_call_id=str(uuid4())))
                continue

            for cb in callbacks:
                await cb.on_llm_new_token(full_content)
            return {"messages": [AIMessage(content=full_content)]}

        return {"messages": [AIMessage(content="Agent reached maximum recursion limit.")]}

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
        model=create_chat_model(),
        tools=build_agent_tools(db, user_id=user_id, session_id=session_id),
        system_prompt=await build_system_prompt(db, user_id=user_id, session_id=session_id),
    )
