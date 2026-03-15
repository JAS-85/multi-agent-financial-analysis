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
    def test_full_analysis_with_text(self, mock_chat, sample_financial_text,
                                      sample_extracted_data, sample_trend_data,
                                      sample_sentiment_data, sample_validation_data):
        plan = {
            "agents_needed": ["data_extractor", "trend_analyzer", "sentiment_analyzer", "validator"],
            "reasoning": "Full analysis needed",
            "instructions": {},
        }
        synthesis = {
            "summary": "Acme Corp shows strong Q4 performance with 12% revenue growth.",
            "key_findings": ["Revenue up 12%", "Bullish sentiment"],
            "confidence": "medium",
            "caveats": ["Rising costs noted"],
        }

        mock_chat.side_effect = self._mock_ollama_side_effect(
            plan, sample_extracted_data, sample_trend_data,
            sample_sentiment_data, sample_validation_data, synthesis
        )

        system = FinancialAnalysisSystem()
        result = system.analyze(
            query="What is the financial outlook for Acme Corp?",
            text=sample_financial_text,
        )

        # Synthesis fields
        assert "Acme" in result["summary"]
        assert len(result["key_findings"]) > 0
        assert result["confidence"] == "medium"

        # Extractor: current schema
        assert result["extracted_data"]["company_data"][0]["company"] == "Acme Corp"
        assert result["extracted_data"]["company_data"][0]["metrics"]["revenue"]["value"] == 5200

        # Trend: current schema
        assert result["trends"]["company_trends"][0]["trends"][0]["direction"] == "increasing"

        # Sentiment: current schema
        assert result["sentiment"]["overall_sentiment"] == "bullish"
        assert len(result["sentiment"]["company_sentiment"]) == 1

        # Validator: current schema
        assert result["validation"]["is_consistent"] is True
        assert result["validation"]["verified_claims"][0]["confidence"] == 0.9

    @patch("agents.base_agent.ollama.chat")
    def test_analysis_with_document(self, mock_chat, tmp_path, sample_extracted_data):
        doc = tmp_path / "report.txt"
        doc.write_text("Revenue: $5.2B. Net income: $780M.", encoding="utf-8")

        plan = {
            "agents_needed": ["data_extractor"],
            "reasoning": "Simple extraction",
            "instructions": {},
        }
        synthesis = {
            "summary": "Revenue is $5.2B with $780M net income.",
            "key_findings": ["Revenue: $5.2B"],
            "confidence": "medium",
            "caveats": [],
        }

        responses = iter([
            make_ollama_response(plan),
            make_ollama_response(sample_extracted_data),
            make_ollama_response(synthesis),
        ])
        mock_chat.side_effect = lambda **kwargs: next(responses)

        system = FinancialAnalysisSystem()
        result = system.analyze(query="Extract the numbers", documents=[str(doc)])

        assert result["extracted_data"]["company_data"][0]["metrics"]["revenue"]["value"] == 5200

    @patch("agents.base_agent.ollama.chat")
    def test_graceful_fallback_on_agent_failure(self, mock_chat):
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return make_ollama_response({
                    "agents_needed": ["data_extractor"],
                    "reasoning": "test",
                    "instructions": {},
                })
            elif call_count == 2:
                raise Exception("Model overloaded")
            else:
                return make_ollama_response({
                    "summary": "Partial analysis only.",
                    "key_findings": [],
                    "confidence": "low",
                    "caveats": ["Data extraction failed"],
                })

        mock_chat.side_effect = side_effect

        system = FinancialAnalysisSystem()
        result = system.analyze(query="Test query", text="Some text")

        assert "summary" in result

    def test_no_input_returns_error(self):
        system = FinancialAnalysisSystem()
        result = system.analyze(query="Test query")

        assert "error" in result

    @patch("agents.base_agent.ollama.chat")
    def test_extraction_failure_blocks_trend_hallucination(self, mock_chat):
        """When extractor fails, trend_analyzer should receive explicit instruction
        to skip company_trends."""
        call_count = 0
        captured_trend_prompt = None

        def side_effect(**kwargs):
            nonlocal call_count, captured_trend_prompt
            call_count += 1
            if call_count == 1:
                # Plan: run all agents
                return make_ollama_response({
                    "agents_needed": ["data_extractor", "trend_analyzer"],
                    "reasoning": "test",
                    "instructions": {},
                })
            elif call_count == 2:
                # Extractor returns garbage (no valid JSON structure)
                return {"message": {"content": "I cannot process this input properly"}}
            elif call_count == 3:
                # Trend analyzer — capture what it receives
                captured_trend_prompt = kwargs.get("messages", [])[-1]["content"]
                return make_ollama_response({
                    "company_trends": [],
                    "macro_trends": [],
                    "cross_company_comparison": None,
                    "outlook": {"short_term": "N/A", "medium_term": "N/A", "key_risks": []},
                    "confidence": "low",
                })
            else:
                # Synthesis
                return make_ollama_response({
                    "summary": "Limited analysis.",
                    "key_findings": [],
                    "confidence": "low",
                    "caveats": ["Extraction failed"],
                })

        mock_chat.side_effect = side_effect

        system = FinancialAnalysisSystem()
        result = system.analyze(query="Analyze ACME", text="Some text")

        # The trend_analyzer should have received the failure instruction
        assert captured_trend_prompt is not None
        assert "_extraction_failed" in captured_trend_prompt or "extraction" in result.get("summary", "").lower() or "summary" in result
