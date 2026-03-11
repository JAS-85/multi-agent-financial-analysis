import logging
from io import StringIO

import pandas as pd
import requests

from config.config import FRED_SERIES

logger = logging.getLogger(__name__)

_FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
_HEADERS = {"User-Agent": "FinancialAnalysisSystem/1.0 research@localhost"}


def _fetch_series(series_id: str, label: str, n_latest: int = 4) -> str | None:
    """Fetch the latest N observations for a FRED series via CSV endpoint."""
    url = _FRED_CSV_URL.format(series_id=series_id)
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        df.columns = ["date", "value"]
        df = df.dropna(subset=["value"])
        latest = df.tail(n_latest)
        rows = [f"  {row['date']}: {row['value']}" for _, row in latest.iterrows()]
        return f"{label} ({series_id}):\n" + "\n".join(rows)
    except Exception as e:
        logger.warning(f"Failed to fetch FRED series {series_id}: {e}")
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
