import logging
from urllib.parse import urlparse

import requests

from config.config import DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15
DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT
}


def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Fetch text content from a URL. Returns raw text, not HTML parsing."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    logger.info(f"Fetching URL: {url}")
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()

    return response.text


def fetch_multiple(urls: list[str], timeout: int = DEFAULT_TIMEOUT) -> list[dict]:
    """Fetch multiple URLs. Returns list of results with status for each."""
    results = []
    for url in urls:
        try:
            content = fetch_url(url, timeout)
            results.append({"url": url, "status": "success", "content": content})
            logger.info(f"Fetched: {url} ({len(content)} chars)")
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            results.append({"url": url, "status": "error", "error": str(e)})
    return results


def extract_text_from_html(html: str) -> str:
    """Basic text extraction from HTML — strips tags and excess whitespace."""
    import re

    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
