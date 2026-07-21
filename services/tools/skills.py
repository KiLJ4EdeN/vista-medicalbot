from typing import Literal

from langchain_core.tools import tool

from core.content import load_skills


@tool
async def load_skill(name: Literal["document-analysis", "guideline-retrieval"]) -> str:
    """Load detailed instructions for an available specialized skill by exact name."""
    try:
        skill = load_skills().get(name)
        if skill is None:
            return f"Tool error: unknown skill '{name}'. Available: {', '.join(load_skills())}"
        return skill.content
    except Exception:
        return "Tool error: the requested skill could not be loaded."
