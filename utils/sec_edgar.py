import logging

import requests

from config.config import SEC_USER_AGENT, SEC_MAX_RESULTS, SEC_MAX_CHARS
from utils.web_scraper import extract_text_from_html

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}
_TICKER_CIK_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_FILING_BASE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{primary_doc}"


def _get_cik(ticker: str) -> str | None:
    """Look up the SEC CIK number for a ticker symbol."""
    try:
        r = requests.get(_TICKER_CIK_URL, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        ticker_upper = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                return str(entry["cik_str"]).zfill(10)
    except Exception as e:
        logger.error(f"CIK lookup failed for {ticker}: {e}")
    return None


def _get_recent_filings(cik: str, forms: tuple = ("10-K", "10-Q")) -> list[dict]:
    """Return metadata for recent filings of the given types."""
    try:
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


def _fetch_filing_text(cik: str, accession: str, doc: str) -> str:
    """Fetch and extract text from a specific SEC filing document."""
    acc_no_dashes = accession.replace("-", "")
    url = _FILING_BASE.format(cik=cik.lstrip("0"), accession_no_dashes=acc_no_dashes, primary_doc=doc)
    try:
        r = requests.get(url, headers={**_HEADERS, "Accept": "text/html"}, timeout=20)
        r.raise_for_status()
        text = extract_text_from_html(r.text)
        return text[:SEC_MAX_CHARS]
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
