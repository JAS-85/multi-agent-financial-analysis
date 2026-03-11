import json
import logging
from pathlib import Path

from agents.base_agent import BaseAgent
from config.config import VALIDATOR_MODEL

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "validator_prompt.txt"


class ValidatorAgent(BaseAgent):
    """Fact-checks and validates consistency across agent results."""

    def __init__(self):
        system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        super().__init__(
            model=VALIDATOR_MODEL,
            system_prompt=system_prompt,
            temperature=0.1,
            agent_key="validator",
        )

    def validate(self, agent_results: dict, instructions: str = "") -> dict:
        """Validate consistency and accuracy of all agent results."""
        prompt = "Validate the following agent results for consistency, accuracy, and contradictions.\n\n"
        if instructions:
            prompt += f"Specific instructions: {instructions}\n\n"
        prompt += f"Agent results:\n{json.dumps(agent_results, indent=2)}"
        return self.run(prompt)
