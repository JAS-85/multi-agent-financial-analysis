import json
import logging
from pathlib import Path

from agents.base_agent import BaseAgent
from config.config import ORCHESTRATOR_MODEL

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "orchestrator_prompt.txt"


class OrchestratorAgent(BaseAgent):
    """Coordinates the analysis pipeline — decides which agents to use and synthesizes results."""

    def __init__(self):
        system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        super().__init__(
            model=ORCHESTRATOR_MODEL,
            system_prompt=system_prompt,
            temperature=0.3,
            agent_key="orchestrator",
        )

    def plan(self, query: str, available_data: dict) -> dict:
        """Determine which agents are needed and generate instructions for each."""
        prompt = (
            f"PLANNING phase.\n\n"
            f"User query: {query}\n\n"
            f"Available data:\n{json.dumps(available_data, indent=2)}\n\n"
            f"Decide which agents to invoke and provide specific instructions for each."
        )
        return self.run(prompt)

    def synthesize(self, query: str, agent_results: dict) -> dict:
        """Combine all agent results into a final analysis."""
        prompt = (
            f"SYNTHESIS phase.\n\n"
            f"User query: {query}\n\n"
            f"Agent results:\n{json.dumps(agent_results, indent=2)}\n\n"
            f"Produce a final summary that directly answers the user's query."
        )
        return self.run(prompt)
