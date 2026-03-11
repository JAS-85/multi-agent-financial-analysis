import json
import logging
import ollama
from config.config import OLLAMA_TIMEOUT, NUM_GPU_LAYERS, CONTEXT_LENGTH

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all specialist agents."""

    def __init__(self, model: str, system_prompt: str, temperature: float = 0.3, agent_key: str | None = None):
        self.model = model
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.num_ctx = CONTEXT_LENGTH.get(agent_key, 2048) if agent_key else 2048

    def run(self, user_prompt: str, context: dict | None = None) -> dict:
        """Send a prompt to the model and return parsed JSON response."""
        messages = [{"role": "system", "content": self.system_prompt}]

        if context:
            messages.append({
                "role": "user",
                "content": f"Context from previous agents:\n{json.dumps(context, indent=2)}"
            })

        messages.append({"role": "user", "content": user_prompt})

        logger.info(f"[{self.__class__.__name__}] Calling model {self.model}")

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": self.temperature,
                    "num_predict": 2048,
                    "num_ctx": self.num_ctx,
                    "num_gpu": NUM_GPU_LAYERS,
                },
            )
        except ollama.ResponseError as e:
            logger.error(f"[{self.__class__.__name__}] Ollama error: {e}")
            raise
        except Exception as e:
            if "refused" in str(e).lower() or "connect" in str(e).lower():
                raise ConnectionError(
                    f"Cannot connect to Ollama at localhost:11434. Is 'ollama serve' running?"
                ) from e
            raise

        raw = response["message"]["content"]
        logger.debug(f"[{self.__class__.__name__}] Raw response: {raw}")

        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> dict:
        """Extract JSON from model response. Falls back to wrapping raw text."""
        # Try to find JSON block in the response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass

        logger.warning(f"[{self.__class__.__name__}] Could not parse JSON, wrapping raw text")
        return {"raw_response": raw}
