"""
World Bank Open Data fetcher.

Uses the World Bank REST API — no API key required.
Fetches GDP growth, CPI inflation, and unemployment for major economies.
"""
import logging
import time

import requests

from config.config import (
    DEFAULT_USER_AGENT,
    WORLDBANK_BASE_URL,
    WORLDBANK_COUNTRIES,
    WORLDBANK_INDICATORS,
    WORLDBANK_TIMEOUT,
    WORLDBANK_RETRIES,
)

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": DEFAULT_USER_AGENT}

# Human-readable country names for display
_COUNTRY_NAMES = {
    "SE":  "Sweden",
    "US":  "United States",
    "DE":  "Germany",
    "FR":  "France",
    "GB":  "United Kingdom",
    "EUU": "European Union",
}


def _fetch_indicator(
    country: str,
    indicator: str,
    label: str,
    n_latest: int = 4,
) -> str | None:
    """
    Fetch the latest N annual values for one country + indicator from World Bank.

    Endpoint: GET /v2/country/{country}/indicator/{indicator}
    Response: [[metadata], [{"value": float, "date": "YYYY", ...}, ...]]
    """
    url = (
        f"{WORLDBANK_BASE_URL}/country/{country}/indicator/{indicator}"
        f"?format=json&mrv={n_latest}&per_page={n_latest}"
    )
    last_error = None

    for attempt in range(1 + WORLDBANK_RETRIES):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=WORLDBANK_TIMEOUT)
            r.raise_for_status()
            payload = r.json()

            # World Bank returns [metadata_dict, data_list]
            if not isinstance(payload, list) or len(payload) < 2:
                return None
            records = payload[1]
            if not records:
                return None

            # Sort ascending by date, skip nulls
            valid = [
                (rec["date"], rec["value"])
                for rec in records
                if rec.get("value") is not None
            ]
            valid.sort(key=lambda x: x[0])

            rows = [f"  {d}: {v:.2f}" for d, v in valid]
            if not rows:
                return None

            country_name = _COUNTRY_NAMES.get(country, country)
            return f"{country_name} — {label}:\n" + "\n".join(rows)

        except Exception as e:
            last_error = e
            if attempt < WORLDBANK_RETRIES:
                logger.warning(
                    f"WorldBank {country}/{indicator} attempt {attempt + 1} failed: {e} — retrying"
                )
                time.sleep(2)

    logger.warning(f"Failed to fetch World Bank {country}/{indicator}: {last_error}")
    return None


def fetch_worldbank_indicators(
    countries: list[str] | None = None,
    indicator_keys: list[str] | None = None,
    cache_hours: float = 24.0,
) -> str:
    """
    Fetch global macroeconomic data from the World Bank (no API key required).
    Uses file cache to avoid redundant API calls within cache_hours.
    """
    from utils.cache import get_cached, set_cached

    cache_key = "worldbank"
    if countries is None and indicator_keys is None:
        cached = get_cached(cache_key, max_age_hours=cache_hours)
        if cached:
            return cached

    countries = countries or WORLDBANK_COUNTRIES
    indicator_keys = indicator_keys or list(WORLDBANK_INDICATORS.keys())
    logger.info(f"Fetching World Bank data: {indicator_keys} for {countries}")

    parts = ["=== Global Macroeconomic Indicators (World Bank) ==="]

    for indicator in indicator_keys:
        label = WORLDBANK_INDICATORS.get(indicator)
        if not label:
            continue

        section_rows = []
        for country in countries:
            result = _fetch_indicator(country, indicator, label)
            if result:
                section_rows.append(result)

        if section_rows:
            parts.append(f"-- {label} --\n" + "\n\n".join(section_rows))

    if len(parts) == 1:
        return ""

    combined = "\n\n".join(parts)
    logger.info(f"World Bank: fetched data ({len(combined)} chars)")

    if countries is None and indicator_keys is None:
        set_cached(cache_key, combined)

    return combined
