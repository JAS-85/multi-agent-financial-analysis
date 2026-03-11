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
    return {
        "company": "Acme Corp",
        "period": "Q4 2024",
        "metrics": {
            "revenue": {"value": 5200000, "unit": "USD", "period": "Q4 2024"},
            "net_income": {"value": 780000, "unit": "USD", "period": "Q4 2024"},
            "eps": {"value": 2.15, "unit": "USD", "period": "Q4 2024"},
            "growth_rates": {"revenue_yoy": "12%"},
        },
        "raw_figures": [
            {"label": "Total Revenue", "value": "5,200,000", "context": "Q4 2024 earnings"},
        ],
        "notes": "Strong quarter driven by product expansion.",
    }


@pytest.fixture
def sample_trend_data():
    return {
        "trends": [
            {
                "metric": "Revenue",
                "direction": "increasing",
                "magnitude": "12% year-over-year growth",
                "period": "Q4 2024",
            }
        ],
        "anomalies": [],
        "outlook": "Continued growth expected based on current trajectory.",
        "confidence": "medium",
    }


@pytest.fixture
def sample_sentiment_data():
    return {
        "overall_sentiment": "bullish",
        "confidence": "medium",
        "positive_signals": ["Strong earnings beat", "New product launch"],
        "negative_signals": ["Rising costs"],
        "risk_factors": ["Market volatility"],
        "forward_guidance": "Management raised full-year guidance.",
        "summary": "Generally positive outlook with some cost concerns.",
    }


@pytest.fixture
def sample_validation_data():
    return {
        "is_consistent": True,
        "issues": [],
        "verified_claims": ["Revenue figure matches source", "Growth rate is plausible"],
        "overall_confidence": "medium",
        "recommendation": "Results appear reliable.",
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
