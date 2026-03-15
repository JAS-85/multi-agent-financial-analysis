import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def fetch_stock_data(ticker: str, period: str = "1y") -> dict:
    """
    Fetch stock price data for a ticker symbol.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL", "ERIC-B.ST").
        period: Data period — "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y".

    Returns:
        Dict with price data and fundamentals, or error info if fetch fails.
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
            "currency": info.get("currency", "USD"),
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
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "data_points": len(hist),
            "date_range": {
                "start": str(hist.index[0].date()),
                "end": str(hist.index[-1].date()),
            },
            # Valuation
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            # Earnings
            "trailing_eps": info.get("trailingEps"),
            "forward_eps": info.get("forwardEps"),
            # Dividends
            "dividend_yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            # Price range
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            # Financials
            "total_revenue": info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "net_income": info.get("netIncomeToCommon"),
            "gross_margins": info.get("grossMargins"),
            "operating_margins": info.get("operatingMargins"),
            "profit_margins": info.get("profitMargins"),
            # Balance sheet
            "return_on_equity": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "free_cashflow": info.get("freeCashflow"),
            "book_value": info.get("bookValue"),
            "beta": info.get("beta"),
            # Analyst targets
            "target_mean_price": info.get("targetMeanPrice"),
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "recommendation_key": info.get("recommendationKey"),
            "number_of_analyst_opinions": info.get("numberOfAnalystOpinions"),
        }

    except Exception as e:
        logger.error(f"Failed to fetch stock data for {ticker}: {e}")
        return {"error": str(e), "ticker": ticker}



def format_stock_summary(data: dict) -> str:
    """Format stock data as readable text for agent consumption.

    Includes a structured JSON metrics block at the end so the data extractor
    can copy values directly instead of parsing prose.
    """
    if "error" in data:
        return f"Error fetching {data['ticker']}: {data['error']}"

    lines = [
        f"Stock: {data['company_name']} ({data['ticker']})",
        f"Sector: {data.get('sector', 'Unknown')}",
        f"Currency: {data.get('currency', 'USD')}",
        f"Period: {data['date_range']['start']} to {data['date_range']['end']} ({data['data_points']} trading days)",
        f"Current Price: {data['current_price']}",
        f"Period Change: {data['price_change']} ({data['pct_change']}%)",
        f"Period High: {data['period_high']} | Low: {data['period_low']}",
        f"Average Volume: {data['avg_volume']:,}",
    ]

    _OPTIONAL = [
        ("Market Cap", "market_cap", lambda v: f"{v:,}"),
        ("Trailing P/E", "trailing_pe", lambda v: f"{v:.2f}"),
        ("Forward P/E", "forward_pe", lambda v: f"{v:.2f}"),
        ("Price/Book", "price_to_book", lambda v: f"{v:.2f}"),
        ("Price/Sales", "price_to_sales", lambda v: f"{v:.2f}"),
        ("Trailing EPS", "trailing_eps", lambda v: f"{v:.2f}"),
        ("Forward EPS", "forward_eps", lambda v: f"{v:.2f}"),
        ("Dividend Yield", "dividend_yield", lambda v: f"{v * 100:.2f}%"),
        ("Dividend Rate", "dividend_rate", lambda v: f"{v:.2f}"),
        ("52-Week High", "fifty_two_week_high", lambda v: f"{v:.2f}"),
        ("52-Week Low", "fifty_two_week_low", lambda v: f"{v:.2f}"),
        ("Total Revenue", "total_revenue", lambda v: f"{v:,}"),
        ("Revenue Growth", "revenue_growth", lambda v: f"{v * 100:.2f}%"),
        ("Net Income", "net_income", lambda v: f"{v:,}"),
        ("Gross Margins", "gross_margins", lambda v: f"{v * 100:.2f}%"),
        ("Operating Margins", "operating_margins", lambda v: f"{v * 100:.2f}%"),
        ("Profit Margins", "profit_margins", lambda v: f"{v * 100:.2f}%"),
        ("Return on Equity", "return_on_equity", lambda v: f"{v * 100:.2f}%"),
        ("Debt/Equity", "debt_to_equity", lambda v: f"{v:.2f}"),
        ("Free Cashflow", "free_cashflow", lambda v: f"{v:,}"),
        ("Beta", "beta", lambda v: f"{v:.2f}"),
        ("Book Value", "book_value", lambda v: f"{v:.2f}"),
        ("Analyst Target (mean)", "target_mean_price", lambda v: f"{v:.2f}"),
        ("Analyst Target (high)", "target_high_price", lambda v: f"{v:.2f}"),
        ("Analyst Target (low)", "target_low_price", lambda v: f"{v:.2f}"),
        ("Recommendation", "recommendation_key", lambda v: str(v)),
        ("# Analyst Opinions", "number_of_analyst_opinions", lambda v: str(v)),
    ]

    for label, key, fmt in _OPTIONAL:
        val = data.get(key)
        if val is not None:
            try:
                lines.append(f"{label}: {fmt(val)}")
            except (TypeError, ValueError):
                lines.append(f"{label}: {val}")

    # Append compact structured metrics for the data extractor
    metrics = _extract_key_metrics(data)
    if metrics:
        lines.append(f"\nKey Metrics JSON: {json.dumps(metrics, separators=(',', ':'))}")

    return "\n".join(lines)


def _extract_key_metrics(data: dict) -> dict:
    """Build a compact dict of key financial metrics for structured consumption."""
    fields = {
        "ticker": data.get("ticker"),
        "currency": data.get("currency", "USD"),
        "current_price": data.get("current_price"),
        "market_cap": data.get("market_cap"),
        "trailing_pe": data.get("trailing_pe"),
        "forward_pe": data.get("forward_pe"),
        "trailing_eps": data.get("trailing_eps"),
        "forward_eps": data.get("forward_eps"),
        "dividend_yield": data.get("dividend_yield"),
        "52w_high": data.get("fifty_two_week_high"),
        "52w_low": data.get("fifty_two_week_low"),
        "total_revenue": data.get("total_revenue"),
        "revenue_growth": data.get("revenue_growth"),
        "net_income": data.get("net_income"),
        "gross_margins": data.get("gross_margins"),
        "operating_margins": data.get("operating_margins"),
        "profit_margins": data.get("profit_margins"),
        "return_on_equity": data.get("return_on_equity"),
        "debt_to_equity": data.get("debt_to_equity"),
        "free_cashflow": data.get("free_cashflow"),
        "beta": data.get("beta"),
        "target_mean_price": data.get("target_mean_price"),
        "recommendation": data.get("recommendation_key"),
    }
    return {k: v for k, v in fields.items() if v is not None}
