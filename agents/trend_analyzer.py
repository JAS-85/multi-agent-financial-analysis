import json
import logging
from pathlib import Path

from agents.base_agent import BaseAgent
from config.config import TREND_ANALYZER_MODEL

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "trend_prompt.txt"


class TrendAnalyzerAgent(BaseAgent):
    """Identifies patterns, growth rates, and anomalies in financial data."""

    def __init__(self):
        system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        super().__init__(
            model=TREND_ANALYZER_MODEL,
            system_prompt=system_prompt,
            temperature=0.15,
            agent_key="trend_analyzer",
        )

    def analyze(self, extracted_data: dict, instructions: str = "") -> dict:
        """Analyze extracted financial data for trends and anomalies."""
        prompt = "Analyze the following financial data for trends, growth rates, and anomalies.\n\n"
        if instructions:
            prompt += f"Specific instructions: {instructions}\n\n"
        prompt += f"Extracted data:\n{json.dumps(extracted_data, indent=2)}"
        return self.run(prompt)
