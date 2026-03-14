"""
Simple file-based cache for macro data (FRED, ECB, Riksbanken, World Bank).

Stores fetched text in .cache/ with a timestamp. If cached data is younger
than max_age_hours, returns it instead of making new API calls.
"""
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(".cache")


def get_cached(source: str, max_age_hours: float = 24.0) -> str | None:
    """Return cached text for a source if it exists and is fresh enough."""
    path = _CACHE_DIR / f"{source}.json"
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = data.get("cached_at", 0)
        age_hours = (time.time() - cached_at) / 3600

        if age_hours > max_age_hours:
            logger.info(f"Cache expired for {source} ({age_hours:.1f}h old)")
            return None

        text = data.get("text", "")
        if text:
            logger.info(f"Using cached {source} data ({age_hours:.1f}h old, {len(text)} chars)")
            return text
    except Exception as e:
        logger.warning(f"Cache read error for {source}: {e}")

    return None


def set_cached(source: str, text: str) -> None:
    """Save fetched text to cache."""
    if not text:
        return

    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        path = _CACHE_DIR / f"{source}.json"
        path.write_text(
            json.dumps({"cached_at": time.time(), "text": text}, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Cached {source} data ({len(text)} chars)")
    except Exception as e:
        logger.warning(f"Cache write error for {source}: {e}")
