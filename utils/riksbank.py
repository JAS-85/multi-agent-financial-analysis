"""
Riksbanken (Swedish central bank) data fetcher.

Uses the SWEA REST API — no API key required.
Fetches the policy rate (reporänta) and SEK exchange rates.
"""
import logging
import time
from datetime import date, timedelta

import requests

from config.config import (
    RIKSBANK_BASE_URL,
    RIKSBANK_SERIES,
    RIKSBANK_TIMEOUT,
    RIKSBANK_RETRIES,
)

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "FinancialAnalysisSystem/1.0 contact@example.com"}


def _fetch_series(series_id: str, label: str, n_latest: int = 5) -> str | None:
    """
    Fetch the latest N observations for one Riksbanken series.

    Endpoint: GET /Observations/{serieId}/{from}/{to}
    Returns JSON array: [{"date": "YYYY-MM-DD", "value": float}, ...]
    """
    # Fetch last 3 months to ensure we get n_latest data points
    date_to = date.today().isoformat()
    date_from = (date.today() - timedelta(days=90)).isoformat()
    url = f"{RIKSBANK_BASE_URL}/Observations/{series_id}/{date_from}/{date_to}"
    last_error = None

    for attempt in range(1 + RIKSBANK_RETRIES):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=RIKSBANK_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            return _parse_observations(data, label, n_latest)
        except Exception as e:
            last_error = e
            if attempt < RIKSBANK_RETRIES:
                logger.warning(
                    f"Riksbanken {series_id} attempt {attempt + 1} failed: {e} — retrying"
                )
                time.sleep(2)

    logger.warning(f"Failed to fetch Riksbanken series {series_id}: {last_error}")
    return None


def _parse_observations(data, label: str, n: int) -> str | None:
    """
    Parse Riksbanken SWEA observations response.

    Expected format: list of {"date": "YYYY-MM-DD", "value": float}
    or possibly {"observations": [...]} wrapper.
    """
    try:
        # Handle both bare list and wrapped {"observations": [...]}
        if isinstance(data, dict):
            data = data.get("observations", data.get("data", []))
        if not isinstance(data, list) or not data:
            return None

        # Sort by date, take latest n
        sorted_data = sorted(data, key=lambda x: x.get("date", ""))[-n:]

        rows = []
        for entry in sorted_data:
            d = entry.get("date", "")
            v = entry.get("value")
            if d and v is not None:
                rows.append(f"  {d}: {v}")

        if not rows:
            return None

        return f"{label}:\n" + "\n".join(rows)

    except Exception as e:
        logger.warning(f"Riksbanken parse error ({label}): {e}")
        return None


def fetch_riksbank_indicators(series_keys: list[str] | None = None, cache_hours: float = 24.0) -> str:
    """
    Fetch Swedish macroeconomic indicators from Riksbanken (no API key required).
    Uses file cache to avoid redundant API calls within cache_hours.
    """
    from utils.cache import get_cached, set_cached

    cache_key = "riksbank"
    if series_keys is None:
        cached = get_cached(cache_key, max_age_hours=cache_hours)
        if cached:
            return cached

    keys = series_keys or list(RIKSBANK_SERIES.keys())
    logger.info(f"Fetching Riksbanken data: {keys}")

    parts = ["=== Swedish Macroeconomic Indicators (Riksbanken) ==="]
    for key in keys:
        label = RIKSBANK_SERIES.get(key)
        if not label:
            continue
        result = _fetch_series(key, label)
        if result:
            parts.append(result)

    if len(parts) == 1:
        return ""

    combined = "\n\n".join(parts)
    logger.info(f"Riksbanken: fetched {len(parts) - 1} series ({len(combined)} chars)")

    if series_keys is None:
        set_cached(cache_key, combined)

    return combined
