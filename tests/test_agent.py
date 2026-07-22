import pytest
from langchain_core.tools import tool

import services.agent as agent_service
from services.agent import ReActAgent


@pytest.mark.asyncio
async def test_agent_emits_tool_and_final_events(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            'Action: lookup\nAction Input: {"query": "aspirin"}',
            "Final Answer: Use the retrieved result.",
        ]
    )
    requests: list[list[dict[str, str]]] = []

    async def complete_chat(messages: list[dict[str, str]]) -> str:
        requests.append(messages.copy())
        return next(responses)

    @tool
    async def lookup(query: str) -> str:
        """Look up a test value."""
        return f"result for {query}"

    monkeypatch.setattr(agent_service, "complete_chat", complete_chat)
    agent = ReActAgent([lookup], "system prompt")

    events = [event async for event in agent.astream([], recursion_limit=3)]

    assert [(event.event, event.content) for event in events] == [
        ("tool_started", "lookup"),
        ("tool_finished", ""),
        ("final", "Use the retrieved result."),
    ]
    assert requests[1][-1] == {"role": "user", "content": "[Tool result]\nresult for aspirin"}
