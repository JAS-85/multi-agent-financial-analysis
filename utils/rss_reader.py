import logging
import xml.etree.ElementTree as ET

import requests

from config.config import DEFAULT_USER_AGENT, RSS_MAX_ITEMS, RSS_MAX_CHARS, RSS_FEEDS

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": DEFAULT_USER_AGENT}
_YAHOO_RSS = "https://finance.yahoo.com/rss/headline?s={ticker}"

# XML namespaces used in RSS/Atom feeds
ET.register_namespace("", "http://www.w3.org/2005/Atom")


def _parse_rss(xml_text: str, source_label: str, max_items: int = RSS_MAX_ITEMS) -> list[str]:
    """Parse RSS/Atom XML and return a list of formatted article strings."""
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning(f"RSS parse error ({source_label}): {e}")
        return []

    # Handle both RSS <item> and Atom <entry>
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item") or root.findall(".//atom:entry", ns)

    for item in items[:max_items]:
        title = (
            _text(item, "title") or
            _text(item, "atom:title", ns) or ""
        )
        desc = (
            _text(item, "description") or
            _text(item, "atom:summary", ns) or
            _text(item, "atom:content", ns) or ""
        )
        date = (
            _text(item, "pubDate") or
            _text(item, "atom:published", ns) or ""
        )
        if title or desc:
            body = desc[:RSS_MAX_CHARS]
            articles.append(f"**{title}** ({date})\n{body}")

    return articles


def _text(element, tag: str, ns: dict = None) -> str:
    """Safe text extraction from an XML element."""
    child = element.find(tag, ns) if ns else element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def _fetch_feed(url: str, label: str) -> list[str]:
    """Fetch and parse a single RSS feed URL."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return _parse_rss(r.text, label)
    except Exception as e:
        logger.warning(f"Failed to fetch RSS feed {label} ({url}): {e}")
        return []


def fetch_ticker_news(ticker: str) -> str:
    """
    Fetch latest news headlines for a specific ticker from Yahoo Finance RSS.
    Returns formatted text ready to pass to agents.
    """
    url = _YAHOO_RSS.format(ticker=ticker.upper())
    logger.info(f"Fetching Yahoo Finance RSS for {ticker}")
    articles = _fetch_feed(url, f"Yahoo Finance ({ticker})")

    if not articles:
        return ""

    header = f"=== News Headlines for {ticker.upper()} (Yahoo Finance) ==="
    return header + "\n\n" + "\n\n".join(articles)


def fetch_market_news(feed_keys: list[str] | None = None) -> str:
    """
    Fetch general financial news from configured RSS feeds.
    feed_keys: subset of RSS_FEEDS keys to fetch; defaults to all.
    Returns formatted text ready to pass to agents.
    """
    keys = feed_keys or list(RSS_FEEDS.keys())
    parts = ["=== Financial News (RSS) ==="]

    for key in keys:
        url = RSS_FEEDS.get(key)
        if not url:
            continue
        logger.info(f"Fetching RSS feed: {key}")
        articles = _fetch_feed(url, key)
        if articles:
            parts.append(f"-- {key.replace('_', ' ').title()} --\n" + "\n\n".join(articles))

    if len(parts) == 1:
        return ""

    return "\n\n".join(parts)
