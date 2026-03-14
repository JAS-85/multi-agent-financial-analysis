"""
ECB (European Central Bank) data fetcher.

Uses the ECB SDMX-JSON API — no API key required.
Fetches inflation (HICP), EUR exchange rates, and ECB policy rate.
"""
import logging
import time

import requests

from config.config import (
    ECB_BASE_URL,
    ECB_SERIES,
    ECB_TIMEOUT,
    ECB_RETRIES,
)

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "FinancialAnalysisSystem/1.0 contact@example.com"}


def _fetch_series(flow_and_key: str, label: str, n_latest: int = 5) -> str | None:
    """
    Fetch the latest N observations for one ECB SDMX series.

    flow_and_key format: "FLOW_REF/SERIES_KEY"
    e.g. "EXR/D.USD.EUR.SP00.A"
    """
    url = (
        f"{ECB_BASE_URL}/{flow_and_key}"
        f"?format=jsondata&lastNObservations={n_latest}"
    )
    last_error = None

    for attempt in range(1 + ECB_RETRIES):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=ECB_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            result = _parse_sdmx(data, label, n_latest)
            return result
        except Exception as e:
            last_error = e
            if attempt < ECB_RETRIES:
                logger.warning(
                    f"ECB {flow_and_key} attempt {attempt + 1} failed: {e} — retrying"
                )
                time.sleep(2)

    logger.warning(f"Failed to fetch ECB series {flow_and_key}: {last_error}")
    return None


def _parse_sdmx(data: dict, label: str, n: int) -> str | None:
    """
    Parse ECB SDMX-JSON response into a human-readable string.

    Structure:
      data["dataSets"][0]["series"]["0:0:..."]["observations"] = {
          "0": [value, ...], "1": [value, ...], ...
      }
      data["structure"]["dimensions"]["observation"][0]["values"] = [
          {"id": "2024-01-02"}, ...
      ]
    """
    try:
        datasets = data.get("dataSets", [])
        structure = data.get("structure", {})
        if not datasets or not structure:
            return None

        series_dict = datasets[0].get("series", {})
        if not series_dict:
            return None

        # There is exactly one series per request
        observations = next(iter(series_dict.values())).get("observations", {})
        if not observations:
            return None

        # Time period labels from structure
        obs_dims = structure.get("dimensions", {}).get("observation", [])
        time_values = obs_dims[0].get("values", []) if obs_dims else []

        # Sort by integer index, take latest n
        sorted_obs = sorted(observations.items(), key=lambda x: int(x[0]))[-n:]

        rows = []
        for obs_key, obs_vals in sorted_obs:
            idx = int(obs_key)
            date = time_values[idx]["id"] if idx < len(time_values) else obs_key
            value = obs_vals[0] if obs_vals and obs_vals[0] is not None else None
            if value is not None:
                rows.append(f"  {date}: {value}")

        if not rows:
            return None

        return f"{label}:\n" + "\n".join(rows)

    except Exception as e:
        logger.warning(f"ECB SDMX parse error ({label}): {e}")
        return None


def fetch_ecb_indicators(series_keys: list[str] | None = None) -> str:
    """
    Fetch ECB macroeconomic indicators (no API key required).

    series_keys: subset of ECB_SERIES keys to fetch; defaults to all.
    Returns formatted text ready to pass to agents.
    """
    keys = series_keys or list(ECB_SERIES.keys())
    logger.info(f"Fetching ECB data: {keys}")

    parts = ["=== ECB Macroeconomic Indicators (European Central Bank) ==="]
    for key in keys:
        label = ECB_SERIES.get(key)
        if not label:
            continue
        result = _fetch_series(key, label)
        if result:
            parts.append(result)

    if len(parts) == 1:
        return ""

    combined = "\n\n".join(parts)
    logger.info(f"ECB: fetched {len(parts) - 1} series ({len(combined)} chars)")
    return combined
