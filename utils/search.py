import logging

from config.config import WEB_SEARCH_MAX_RESULTS, WEB_SEARCH_MAX_CHARS
from utils.web_scraper import fetch_url, extract_text_from_html

logger = logging.getLogger(__name__)


def web_search(query: str, max_results: int = WEB_SEARCH_MAX_RESULTS) -> str:
    """
    Search the web using DuckDuckGo and return extracted text from top results.
    Returns a formatted string ready to pass to agents.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        logger.error("ddgs not installed. Run: pip install ddgs")
        return ""

    logger.info(f"Searching web for: {query}")
    results = []

    try:
        with DDGS() as ddgs:
            hits = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return ""

    for hit in hits:
        url = hit.get("href", "")
        title = hit.get("title", "")
        snippet = hit.get("body", "")

        # Try to fetch full page text; fall back to snippet if fetch fails
        page_text = snippet
        if url:
            try:
                html = fetch_url(url, timeout=10)
                page_text = extract_text_from_html(html)[:WEB_SEARCH_MAX_CHARS]
            except Exception:
                page_text = snippet

        if page_text:
            results.append(f"### {title}\nSource: {url}\n{page_text}")
            logger.info(f"Fetched: {url} ({len(page_text)} chars)")

    if not results:
        return ""

    combined = "\n\n".join(results)
    logger.info(f"Web search complete: {len(results)} results, {len(combined)} total chars")
    return f"=== Web Search Results for: {query} ===\n\n{combined}"
