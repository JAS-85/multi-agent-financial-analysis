import json
from unittest.mock import patch

import pytest

from main import FinancialAnalysisSystem
from tests.conftest import make_ollama_response


class TestFullWorkflow:
    """End-to-end tests with mocked Ollama calls."""

    def _mock_ollama_side_effect(
        self, plan, extracted, trends, sentiment, validation, synthesis
    ):
        """Create a side_effect function that returns different responses per call."""
        responses = iter([
            make_ollama_response(plan),
            make_ollama_response(extracted),
            make_ollama_response(trends),
            make_ollama_response(sentiment),
            make_ollama_response(validation),
            make_ollama_response(synthesis),
        ])
        return lambda **kwargs: next(responses)

    @patch("agents.base_agent.ollama.chat")
    def test_full_analysis_with_text(self, mock_chat, sample_financial_text):
        plan = {
            "agents_needed": ["data_extractor", "trend_analyzer", "sentiment_analyzer", "validator"],
            "reasoning": "Full analysis needed",
            "instructions": {},
        }
        extracted = {
            "company": "Acme Corp",
            "period": "Q4 2024",
            "metrics": {"revenue": {"value": 5200000, "unit": "USD", "period": "Q4 2024"}},
            "raw_figures": [],
            "notes": "",
        }
        trends = {
            "trends": [{"metric": "Revenue", "direction": "increasing", "magnitude": "12% YoY", "period": "Q4 2024"}],
            "anomalies": [],
            "outlook": "Positive",
            "confidence": "medium",
        }
        sentiment = {
            "overall_sentiment": "bullish",
            "confidence": "medium",
            "positive_signals": ["Strong earnings"],
            "negative_signals": ["Rising costs"],
            "risk_factors": [],
            "forward_guidance": "Raised guidance",
            "summary": "Bullish outlook",
        }
        validation = {
            "is_consistent": True,
            "issues": [],
            "verified_claims": ["Revenue matches"],
            "overall_confidence": "medium",
            "recommendation": "Reliable",
        }
        synthesis = {
            "summary": "Acme Corp shows strong Q4 performance with 12% revenue growth.",
            "key_findings": ["Revenue up 12%", "Bullish sentiment"],
            "confidence": "medium",
            "caveats": ["Rising costs noted"],
        }

        mock_chat.side_effect = self._mock_ollama_side_effect(
            plan, extracted, trends, sentiment, validation, synthesis
        )

        system = FinancialAnalysisSystem()
        result = system.analyze(
            query="What is the financial outlook for Acme Corp?",
            text=sample_financial_text,
        )

        assert result["summary"] != ""
        assert "Acme" in result["summary"]
        assert len(result["key_findings"]) > 0
        assert result["confidence"] == "medium"
        assert result["extracted_data"]["company"] == "Acme Corp"
        assert result["trends"]["trends"][0]["direction"] == "increasing"
        assert result["sentiment"]["overall_sentiment"] == "bullish"
        assert result["validation"]["is_consistent"] is True

    @patch("agents.base_agent.ollama.chat")
    def test_analysis_with_document(self, mock_chat, tmp_path):
        # Create a test text file
        doc = tmp_path / "report.txt"
        doc.write_text("Revenue: $1M. Net income: $200K.", encoding="utf-8")

        plan = {
            "agents_needed": ["data_extractor"],
            "reasoning": "Simple extraction",
            "instructions": {},
        }
        extracted = {
            "company": "Unknown",
            "metrics": {"revenue": {"value": 1000000}},
            "raw_figures": [],
            "notes": "",
        }
        synthesis = {
            "summary": "Revenue is $1M with $200K net income.",
            "key_findings": ["Revenue: $1M"],
            "confidence": "medium",
            "caveats": [],
        }

        responses = iter([
            make_ollama_response(plan),
            make_ollama_response(extracted),
            make_ollama_response(synthesis),
        ])
        mock_chat.side_effect = lambda **kwargs: next(responses)

        system = FinancialAnalysisSystem()
        result = system.analyze(query="Extract the numbers", documents=[str(doc)])

        assert result["extracted_data"]["metrics"]["revenue"]["value"] == 1000000

    @patch("agents.base_agent.ollama.chat")
    def test_graceful_fallback_on_agent_failure(self, mock_chat):
        # Plan succeeds, but data_extractor fails
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Orchestrator plan
                return make_ollama_response({
                    "agents_needed": ["data_extractor"],
                    "reasoning": "test",
                    "instructions": {},
                })
            elif call_count == 2:
                # Data extractor fails
                raise Exception("Model overloaded")
            else:
                # Synthesis
                return make_ollama_response({
                    "summary": "Partial analysis only.",
                    "key_findings": [],
                    "confidence": "low",
                    "caveats": ["Data extraction failed"],
                })

        mock_chat.side_effect = side_effect

        system = FinancialAnalysisSystem()
        result = system.analyze(query="Test query", text="Some text")

        # Should not crash — returns partial results
        assert "summary" in result

    def test_no_input_returns_error(self):
        system = FinancialAnalysisSystem()
        result = system.analyze(query="Test query")

        assert "error" in result
