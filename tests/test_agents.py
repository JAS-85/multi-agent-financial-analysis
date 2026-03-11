import json

import pytest

from tests.conftest import make_ollama_response
from agents.base_agent import BaseAgent
from agents.data_extractor import DataExtractorAgent
from agents.trend_analyzer import TrendAnalyzerAgent
from agents.sentiment_analyzer import SentimentAnalyzerAgent
from agents.validator import ValidatorAgent
from agents.orchestrator import OrchestratorAgent


class TestBaseAgent:
    def test_parse_valid_json(self, mock_ollama):
        data = {"key": "value", "number": 42}
        mock_ollama.return_value = make_ollama_response(data)

        agent = BaseAgent(model="test", system_prompt="test")
        result = agent.run("test prompt")

        assert result == data

    def test_parse_json_with_surrounding_text(self, mock_ollama):
        raw = 'Here is the result: {"key": "value"} Hope that helps!'
        mock_ollama.return_value = make_ollama_response(raw)

        agent = BaseAgent(model="test", system_prompt="test")
        result = agent.run("test prompt")

        assert result == {"key": "value"}

    def test_parse_non_json_falls_back(self, mock_ollama):
        mock_ollama.return_value = make_ollama_response("Just plain text, no JSON here.")

        agent = BaseAgent(model="test", system_prompt="test")
        result = agent.run("test prompt")

        assert "raw_response" in result
        assert "plain text" in result["raw_response"]

    def test_context_included_in_messages(self, mock_ollama):
        mock_ollama.return_value = make_ollama_response({"ok": True})

        agent = BaseAgent(model="test", system_prompt="system")
        agent.run("prompt", context={"prior": "data"})

        call_args = mock_ollama.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 3  # system + context + user
        assert "prior" in messages[1]["content"]

    def test_connection_error_raised(self, mock_ollama):
        mock_ollama.side_effect = Exception("Connection refused")

        agent = BaseAgent(model="test", system_prompt="test")
        with pytest.raises(ConnectionError):
            agent.run("test")


class TestDataExtractor:
    def test_extract_returns_structured_data(self, mock_ollama, sample_extracted_data):
        mock_ollama.return_value = make_ollama_response(sample_extracted_data)

        agent = DataExtractorAgent()
        result = agent.extract("Some financial text")

        assert result["company"] == "Acme Corp"
        assert result["metrics"]["revenue"]["value"] == 5200000

    def test_extract_with_instructions(self, mock_ollama, sample_extracted_data):
        mock_ollama.return_value = make_ollama_response(sample_extracted_data)

        agent = DataExtractorAgent()
        agent.extract("Some text", instructions="Focus on revenue only")

        prompt = mock_ollama.call_args.kwargs["messages"][-1]["content"]
        assert "Focus on revenue only" in prompt


class TestTrendAnalyzer:
    def test_analyze_returns_trends(self, mock_ollama, sample_trend_data):
        mock_ollama.return_value = make_ollama_response(sample_trend_data)

        agent = TrendAnalyzerAgent()
        result = agent.analyze({"revenue": 5200000})

        assert len(result["trends"]) == 1
        assert result["trends"][0]["direction"] == "increasing"


class TestSentimentAnalyzer:
    def test_analyze_returns_sentiment(self, mock_ollama, sample_sentiment_data):
        mock_ollama.return_value = make_ollama_response(sample_sentiment_data)

        agent = SentimentAnalyzerAgent()
        result = agent.analyze("Company X had a great quarter.")

        assert result["overall_sentiment"] == "bullish"
        assert len(result["positive_signals"]) > 0


class TestValidator:
    def test_validate_consistent_results(self, mock_ollama, sample_validation_data):
        mock_ollama.return_value = make_ollama_response(sample_validation_data)

        agent = ValidatorAgent()
        result = agent.validate({"data_extractor": {}, "trend_analyzer": {}})

        assert result["is_consistent"] is True
        assert len(result["issues"]) == 0


class TestOrchestrator:
    def test_plan_returns_agents_needed(self, mock_ollama):
        plan = {
            "agents_needed": ["data_extractor", "trend_analyzer"],
            "reasoning": "Query asks about trends in financial data",
            "instructions": {
                "data_extractor": "Extract revenue figures",
                "trend_analyzer": "Analyze revenue growth",
            },
        }
        mock_ollama.return_value = make_ollama_response(plan)

        agent = OrchestratorAgent()
        result = agent.plan("What is the revenue trend?", {"has_documents": True})

        assert "data_extractor" in result["agents_needed"]
        assert "trend_analyzer" in result["agents_needed"]

    def test_synthesize_returns_summary(self, mock_ollama):
        synthesis = {
            "summary": "Revenue is growing at 12% YoY.",
            "key_findings": ["Strong revenue growth"],
            "confidence": "medium",
            "caveats": [],
        }
        mock_ollama.return_value = make_ollama_response(synthesis)

        agent = OrchestratorAgent()
        result = agent.synthesize("What is the trend?", {"data": "test"})

        assert "Revenue" in result["summary"]
        assert result["confidence"] == "medium"
