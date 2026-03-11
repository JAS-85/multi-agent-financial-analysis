import logging
from pathlib import Path

from agents.base_agent import BaseAgent
from config.config import DATA_EXTRACTOR_MODEL

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "extractor_prompt.txt"


class DataExtractorAgent(BaseAgent):
    """Extracts structured financial data from documents and text."""

    def __init__(self):
        system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        super().__init__(
            model=DATA_EXTRACTOR_MODEL,
            system_prompt=system_prompt,
            temperature=0.1,
            agent_key="data_extractor",
        )

    def extract(self, text: str, instructions: str = "") -> dict:
        """Extract financial data from the provided text."""
        prompt = "Extract all financial data from the following text.\n\n"
        if instructions:
            prompt += f"Specific instructions: {instructions}\n\n"
        prompt += f"Document text:\n{text}"
        return self.run(prompt)
