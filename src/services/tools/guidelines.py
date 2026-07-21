from langchain_core.tools import tool

from services.vector import hybrid_search


def _format_search_results(query: str) -> str:
    return f"No shared guideline results were found for: {query}"


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
                    f"Chunk: {hit.chunk_index}",
                    f"Score: {hit.score:.4f}",
                    f"Content: {hit.content}",
                ]
            )
            for index, hit in enumerate(hits, start=1)
        )
    except Exception:
        return "Tool error: shared medical guideline search is currently unavailable."
