import json
import logging

logger = logging.getLogger(__name__)


def format_result(result: dict) -> str:
    """Pretty-print an agent result dict."""
    return json.dumps(result, indent=2, ensure_ascii=False)


def merge_results(agent_results: dict) -> dict:
    """Merge results from multiple agents into a single flat structure."""
    merged = {}
    for agent_name, result in agent_results.items():
        if isinstance(result, dict):
            merged[agent_name] = result
        else:
            merged[agent_name] = {"raw_response": str(result)}
    return merged


def truncate_text(text: str, max_chars: int = 4000) -> str:
    """Truncate text to fit within context limits, preserving complete sentences."""
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    last_period = truncated.rfind(".")
    if last_period > max_chars * 0.5:
        truncated = truncated[: last_period + 1]

    logger.info(f"Truncated text from {len(text)} to {len(truncated)} characters")
    return truncated + "\n[... truncated]"
