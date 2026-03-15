import json
from unittest.mock import patch, MagicMock

import pytest


def make_ollama_response(content: dict | str) -> dict:
    """Create a mock Ollama chat response."""
    if isinstance(content, dict):
        content = json.dumps(content)
    return {"message": {"content": content}}


@pytest.fixture
def mock_ollama():
    """Patch ollama.chat to return controlled responses."""
    with patch("agents.base_agent.ollama.chat") as mock_chat:
        yield mock_chat


@pytest.fixture
def sample_extracted_data():
    """Matches current extractor prompt schema."""
    return {
        "company_data": [
            {
                "company": "Acme Corp",
                "ticker": "ACME",
                "period": "Q4 2024",
                "currency": "USD",
                "metrics": {
                    "revenue": {"value": 5200, "unit": "millions"},
                    "net_income": {"value": 780, "unit": "millions"},
                    "gross_margin": {"value": 45.2, "unit": "%"},
                    "eps": {"value": 2.15, "unit": "per share"},
                    "pe_ratio": {"value": 22.3, "unit": "x"},
                    "market_cap": {"value": 8.5, "unit": "billions"},
                    "current_price": {"value": 47.50, "unit": "per share"},
                    "52w_high": {"value": 55.00, "unit": "per share"},
                    "52w_low": {"value": 38.20, "unit": "per share"},
                    "dividend_yield": {"value": 1.8, "unit": "%"},
                },
                "raw_figures": [],
                "notes": "All metrics from yfinance live data",
            }
        ],
        "macro_data": [],
        "notes": "Single company, USD only",
    }


@pytest.fixture
def sample_trend_data():
    """Matches current trend prompt schema."""
    return {
        "company_trends": [
            {
                "company": "Acme Corp",
                "ticker": "ACME",
                "trends": [
                    {
                        "metric": "Revenue",
                        "direction": "increasing",
                        "direction_strength": "moderate",
                        "change_rate": "+12% YoY",
                        "time_horizon": "medium",
                        "period": "Q4 2024",
                        "note": "Consistent growth over 3 quarters",
                    }
                ],
                "anomalies": [],
            }
        ],
        "macro_trends": [],
        "cross_company_comparison": None,
        "outlook": {
            "short_term": "Continued growth expected",
            "medium_term": "Stable with margin expansion potential",
            "key_risks": ["Rising costs", "Market volatility"],
        },
        "confidence": "medium",
    }


@pytest.fixture
def sample_sentiment_data():
    """Matches current sentiment prompt schema."""
    return {
        "overall_sentiment": "bullish",
        "confidence": 0.75,
        "company_sentiment": [
            {
                "company": "Acme Corp",
                "ticker": "ACME",
                "sentiment": "bullish",
                "confidence": 0.75,
                "key_drivers": ["Strong earnings beat", "New product launch"],
            }
        ],
        "positive_signals": [
            {"signal": "Revenue beat expectations", "source": "Q4 earnings report", "confidence": 0.8}
        ],
        "negative_signals": [
            {"signal": "Rising raw material costs", "source": "Management commentary", "confidence": 0.6}
        ],
        "forward_guidance": {
            "management": "Raised full-year guidance",
            "analyst_signals": None,
            "macro_outlook": None,
        },
        "geographic_note": None,
        "summary": "Bullish outlook driven by strong Q4 earnings and product expansion.",
    }


@pytest.fixture
def sample_validation_data():
    """Matches current validator prompt schema."""
    return {
        "is_consistent": True,
        "data_quality": "medium",
        "issues": [],
        "verified_claims": [
            {
                "claim": "Revenue $5.2B matches extractor output",
                "supported_by": "data_extractor metrics.revenue",
                "confidence": 0.9,
            }
        ],
        "overall_confidence": "medium",
        "recommendation": "Results appear reliable with minor data gaps.",
    }


@pytest.fixture
def sample_financial_text():
    return (
        "Acme Corp reported Q4 2024 earnings today. Total revenue was $5.2 million, "
        "up 12% year-over-year. Net income reached $780,000 with earnings per share of $2.15. "
        "The company attributed growth to its new product line expansion. "
        "Management raised full-year guidance citing strong demand. "
        "However, rising raw material costs remain a concern for margins going forward."
    )
