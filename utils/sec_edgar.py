import logging
import time

import requests

from config.config import SEC_USER_AGENT, SEC_MAX_RESULTS, SEC_MAX_CHARS
from utils.web_scraper import extract_text_from_html

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}
_TICKER_CIK_URL = "https://www.sec.gov/files/company_tickers.json"
_EFTS_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=10-K,10-Q"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_FILING_BASE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{primary_doc}"

# EDGAR rate limit: max 10 req/s; 0.5s delay keeps us well within limits
_REQUEST_DELAY = 0.5


def _get_cik(ticker: str) -> str | None:
    """Look up the SEC CIK number for a ticker symbol.
    Tries company_tickers.json first; falls back to EFTS full-text search if blocked.
    """
    ticker_upper = ticker.upper()

    # Primary: bulk ticker → CIK map
    try:
        time.sleep(_REQUEST_DELAY)
        r = requests.get(_TICKER_CIK_URL, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                return str(entry["cik_str"]).zfill(10)
        logger.warning(f"Ticker {ticker} not found in company_tickers.json")
    except Exception as e:
        logger.warning(f"company_tickers.json failed for {ticker}: {e} — trying EFTS fallback")

    # Fallback: EDGAR full-text search API
    try:
        time.sleep(_REQUEST_DELAY)
        url = _EFTS_URL.format(ticker=ticker_upper)
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])
        for hit in hits:
            src = hit.get("_source", {})
            entity_id = src.get("entity_id", "")
            if entity_id:
                return str(entity_id).zfill(10)
    except Exception as e:
        logger.error(f"EFTS CIK lookup failed for {ticker}: {e}")

    return None


def _get_recent_filings(cik: str, forms: tuple = ("10-K", "10-Q")) -> list[dict]:
    """Return metadata for recent filings of the given types."""
    try:
        time.sleep(_REQUEST_DELAY)
        url = _SUBMISSIONS_URL.format(cik=cik)
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()

        recent = data.get("filings", {}).get("recent", {})
        form_list = recent.get("form", [])
        accession_list = recent.get("accessionNumber", [])
        date_list = recent.get("filingDate", [])
        doc_list = recent.get("primaryDocument", [])

        filings = []
        for form, acc, date, doc in zip(form_list, accession_list, date_list, doc_list):
            if form in forms:
                filings.append({"form": form, "accession": acc, "date": date, "doc": doc})
            if len(filings) >= SEC_MAX_RESULTS:
                break

        return filings
    except Exception as e:
        logger.error(f"Failed to fetch filings for CIK {cik}: {e}")
        return []


_FINANCIAL_KEYWORDS = (
    "total revenue", "net revenue", "net sales", "net income",
    "earnings per share", "diluted eps", "gross profit",
    "operating income", "total assets", "total liabilities",
    "stockholders' equity", "cash and cash equivalents",
    "cost of revenue", "gross margin", "operating expenses",
    "income from operations", "revenue", "net earnings",
)


def _extract_financial_sections(full_text: str, max_chars: int) -> str:
    """Extract text around financial keywords instead of taking the first N chars.

    Searches for sections containing financial data and returns windows around
    those positions, merged to avoid overlaps.
    """
    lower = full_text.lower()

    # Collect hit positions
    hits = set()
    for kw in _FINANCIAL_KEYWORDS:
        pos = lower.find(kw)
        while pos != -1:
            hits.add(pos)
            pos = lower.find(kw, pos + len(kw))

    if not hits:
        return full_text[:max_chars]

    # Build windows around each hit
    window = 400
    ranges = sorted(
        (max(0, p - window), min(len(full_text), p + window)) for p in hits
    )

    # Merge overlapping ranges
    merged = [list(ranges[0])]
    for start, end in ranges[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    # Extract sections within budget
    sections = []
    used = 0
    for start, end in merged:
        chunk = full_text[start:end].strip()
        if not chunk:
            continue
        if used + len(chunk) > max_chars:
            remaining = max_chars - used
            if remaining > 200:
                sections.append(chunk[:remaining])
            break
        sections.append(chunk)
        used += len(chunk)

    return "\n[...]\n".join(sections) if sections else full_text[:max_chars]


def _fetch_filing_text(cik: str, accession: str, doc: str) -> str:
    """Fetch and extract text from a specific SEC filing document."""
    time.sleep(_REQUEST_DELAY)
    acc_no_dashes = accession.replace("-", "")
    url = _FILING_BASE.format(cik=cik.lstrip("0"), accession_no_dashes=acc_no_dashes, primary_doc=doc)
    try:
        r = requests.get(url, headers={**_HEADERS, "Accept": "text/html"}, timeout=20)
        r.raise_for_status()
        text = extract_text_from_html(r.text)
        return _extract_financial_sections(text, SEC_MAX_CHARS)
    except Exception as e:
        logger.warning(f"Could not fetch filing document {url}: {e}")
        return ""


def fetch_sec_filings(ticker: str) -> str:
    """
    Fetch recent 10-K and 10-Q filings for a ticker from SEC EDGAR.
    Returns formatted text ready to pass to agents.
    """
    logger.info(f"Fetching SEC filings for {ticker}")
    cik = _get_cik(ticker)
    if not cik:
        logger.warning(f"No CIK found for ticker {ticker}")
        return ""

    filings = _get_recent_filings(cik)
    if not filings:
        logger.warning(f"No filings found for {ticker} (CIK {cik})")
        return ""

    parts = [f"=== SEC EDGAR Filings for {ticker.upper()} ==="]
    for filing in filings:
        logger.info(f"Fetching {filing['form']} from {filing['date']}")
        text = _fetch_filing_text(cik, filing["accession"], filing["doc"])
        if text:
            parts.append(
                f"--- {filing['form']} filed {filing['date']} ---\n{text}"
            )

    if len(parts) == 1:
        return ""

    result = "\n\n".join(parts)
    logger.info(f"SEC EDGAR: fetched {len(parts)-1} filings for {ticker} ({len(result)} chars)")
    return result
