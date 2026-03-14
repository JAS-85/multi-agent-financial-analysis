import logging
import time
from io import StringIO

import pandas as pd
import requests

from config.config import FRED_SERIES, FRED_TIMEOUT, FRED_RETRIES

logger = logging.getLogger(__name__)

_FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
_HEADERS = {"User-Agent": "FinancialAnalysisSystem/1.0 contact@example.com"}


def _fetch_series(series_id: str, label: str, n_latest: int = 4) -> str | None:
    """Fetch the latest N observations for a FRED series via CSV endpoint.
    Retries up to FRED_RETRIES times on failure.
    """
    url = _FRED_CSV_URL.format(series_id=series_id)
    last_error = None

    for attempt in range(1 + FRED_RETRIES):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=FRED_TIMEOUT)
            r.raise_for_status()
            df = pd.read_csv(StringIO(r.text))
            df.columns = ["date", "value"]
            df = df.dropna(subset=["value"])
            latest = df.tail(n_latest)
            rows = [f"  {row['date']}: {row['value']}" for _, row in latest.iterrows()]
            return f"{label} ({series_id}):\n" + "\n".join(rows)
        except Exception as e:
            last_error = e
            if attempt < FRED_RETRIES:
                logger.warning(f"FRED {series_id} attempt {attempt + 1} failed: {e} — retrying")
                time.sleep(2)

    logger.warning(f"Failed to fetch FRED series {series_id}: {last_error}")
    return None


def fetch_macro_indicators(series_keys: list[str] | None = None) -> str:
    """
    Fetch key macroeconomic indicators from FRED (no API key required).
    series_keys: subset of FRED_SERIES keys to fetch; defaults to all.
    Returns formatted text ready to pass to agents.
    """
    keys = series_keys or list(FRED_SERIES.keys())
    logger.info(f"Fetching FRED macro data: {keys}")

    parts = ["=== Macroeconomic Indicators (FRED) ==="]
    for key in keys:
        label = FRED_SERIES.get(key)
        if not label:
            continue
        result = _fetch_series(key, label)
        if result:
            parts.append(result)

    if len(parts) == 1:
        return ""

    combined = "\n\n".join(parts)
    logger.info(f"FRED: fetched {len(parts)-1} series ({len(combined)} chars)")
    return combined
