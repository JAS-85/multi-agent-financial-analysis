import logging
from pathlib import Path

from agents.base_agent import BaseAgent
from config.config import SENTIMENT_ANALYZER_MODEL

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "sentiment_prompt.txt"


class SentimentAnalyzerAgent(BaseAgent):
    """Analyzes text for market sentiment and financial signals."""

    def __init__(self):
        system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        super().__init__(
            model=SENTIMENT_ANALYZER_MODEL,
            system_prompt=system_prompt,
            temperature=0.3,
            agent_key="sentiment_analyzer",
        )

    def analyze(self, text: str, instructions: str = "") -> dict:
        """Analyze text for sentiment and market signals."""
        prompt = "Analyze the following text for financial sentiment and market signals.\n\n"
        if instructions:
            prompt += f"Specific instructions: {instructions}\n\n"
        prompt += f"Text:\n{text}"
        return self.run(prompt)
