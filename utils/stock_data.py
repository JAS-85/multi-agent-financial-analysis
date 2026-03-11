import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def fetch_stock_data(ticker: str, period: str = "1mo") -> dict:
    """
    Fetch stock price data for a ticker symbol.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL", "MSFT").
        period: Data period — "1d", "5d", "1mo", "3mo", "6mo", "1y", "5y".

    Returns:
        Dict with price data, or error info if fetch fails.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        return {"error": "yfinance not installed", "ticker": ticker}

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)

        if hist.empty:
            return {"error": f"No data found for ticker '{ticker}'", "ticker": ticker}

        info = stock.info or {}

        # Build summary
        latest = hist.iloc[-1]
        earliest = hist.iloc[0]
        price_change = latest["Close"] - earliest["Close"]
        pct_change = (price_change / earliest["Close"]) * 100

        return {
            "ticker": ticker,
            "period": period,
            "current_price": round(latest["Close"], 2),
            "period_open": round(earliest["Open"], 2),
            "period_close": round(latest["Close"], 2),
            "period_high": round(hist["High"].max(), 2),
            "period_low": round(hist["Low"].min(), 2),
            "price_change": round(price_change, 2),
            "pct_change": round(pct_change, 2),
            "avg_volume": int(hist["Volume"].mean()),
            "company_name": info.get("shortName", ticker),
            "sector": info.get("sector", "Unknown"),
            "market_cap": info.get("marketCap"),
            "data_points": len(hist),
            "date_range": {
                "start": str(hist.index[0].date()),
                "end": str(hist.index[-1].date()),
            },
        }

    except Exception as e:
        logger.error(f"Failed to fetch stock data for {ticker}: {e}")
        return {"error": str(e), "ticker": ticker}


def fetch_multiple_stocks(tickers: list[str], period: str = "1mo") -> list[dict]:
    """Fetch data for multiple tickers."""
    return [fetch_stock_data(t, period) for t in tickers]


def format_stock_summary(data: dict) -> str:
    """Format stock data as readable text for agent consumption."""
    if "error" in data:
        return f"Error fetching {data['ticker']}: {data['error']}"

    return (
        f"Stock: {data['company_name']} ({data['ticker']})\n"
        f"Sector: {data['sector']}\n"
        f"Period: {data['date_range']['start']} to {data['date_range']['end']}\n"
        f"Current Price: ${data['current_price']}\n"
        f"Period Change: ${data['price_change']} ({data['pct_change']}%)\n"
        f"Period High: ${data['period_high']} | Low: ${data['period_low']}\n"
        f"Average Volume: {data['avg_volume']:,}\n"
        f"Market Cap: ${data['market_cap']:,}" if data.get('market_cap') else ""
    )
