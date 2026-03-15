import json
import logging
import re
import ollama
from config.config import OLLAMA_TIMEOUT, NUM_GPU_LAYERS, CONTEXT_LENGTH, KEEP_ALIVE_SPECIALIST, NUM_THREADS

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all specialist agents."""

    def __init__(
        self,
        model: str,
        system_prompt: str,
        temperature: float = 0.3,
        agent_key: str | None = None,
        keep_alive: str = KEEP_ALIVE_SPECIALIST,
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.num_ctx = CONTEXT_LENGTH.get(agent_key, 2048) if agent_key else 2048
        self.keep_alive = keep_alive

    def run(self, user_prompt: str, context: dict | None = None, num_predict: int | None = None) -> dict:
        """Send a prompt to the model and return parsed JSON response."""
        messages = [{"role": "system", "content": self.system_prompt}]

        if context:
            messages.append({
                "role": "user",
                "content": f"Context from previous agents:\n{json.dumps(context, indent=2)}"
            })

        messages.append({"role": "user", "content": user_prompt})

        # Default num_predict: 60% of context window, clamped to [1536, 4096]
        # Previous 50% / min 1024 caused truncation on prettified extractor output
        if num_predict is None:
            num_predict = max(1536, min(self.num_ctx * 3 // 5, 4096))

        logger.info(f"[{self.__class__.__name__}] Calling model {self.model} (num_predict={num_predict}, num_ctx={self.num_ctx})")

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": self.temperature,
                    "num_predict": num_predict,
                    "num_ctx": self.num_ctx,
                    "num_gpu": NUM_GPU_LAYERS,
                    "num_thread": NUM_THREADS,
                },
                keep_alive=self.keep_alive,
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
        """Extract JSON from model response.

        Handles: markdown code fences, leading/trailing text, trailing commas,
        truncated output (open brackets/braces).
        """
        text = raw.strip()

        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        if text.startswith("```"):
            lines = text.splitlines()
            closing = next(
                (i for i, line in enumerate(lines[1:], 1) if line.strip() == "```"),
                len(lines),
            )
            text = "\n".join(lines[1:closing])

        # Find the outermost JSON object
        start = text.find("{")
        if start == -1:
            logger.warning(f"[{self.__class__.__name__}] No JSON object found in response")
            return {"raw_response": raw}

        end = text.rfind("}") + 1
        if end > start:
            candidate = text[start:end]

            # Attempt 0: compact whitespace (models often pretty-print despite instructions)
            compacted = self._compact_json_whitespace(candidate)

            # Attempt 1: direct parse (try compacted first, then original)
            for variant in (compacted, candidate) if compacted != candidate else (candidate,):
                try:
                    return json.loads(variant)
                except json.JSONDecodeError as e:
                    logger.debug(f"[{self.__class__.__name__}] Direct parse failed at pos {e.pos}: {e.msg}")

            # Attempt 2: strip trailing commas before } and ]
            cleaned = re.sub(r',\s*([}\]])', r'\1', compacted)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.debug(f"[{self.__class__.__name__}] Trailing-comma cleanup failed at pos {e.pos}: {e.msg}")

            # Attempt 3: also fix unescaped newlines inside strings
            cleaned2 = self._fix_string_escapes(cleaned)
            if cleaned2 != cleaned:
                try:
                    return json.loads(cleaned2)
                except json.JSONDecodeError as e:
                    logger.debug(f"[{self.__class__.__name__}] String-escape fix failed at pos {e.pos}: {e.msg}")

        # Attempt 4: repair truncated JSON (output may have hit num_predict limit)
        repaired = self._repair_truncated_json(text[start:])
        if repaired is not None:
            logger.info(f"[{self.__class__.__name__}] Recovered truncated JSON via repair")
            return repaired

        # Log diagnostic info for debugging
        snippet = text[start:start+200].replace('\n', '\\n')
        logger.warning(
            f"[{self.__class__.__name__}] All JSON parse attempts failed. "
            f"Response length: {len(raw)} chars. First 200: {snippet}"
        )
        return {"raw_response": raw}

    @staticmethod
    def _compact_json_whitespace(text: str) -> str:
        """Remove indentation and newlines outside of JSON string values.

        Models often pretty-print JSON despite being told not to. This wastes
        tokens and can cause truncation. Compacting before parsing recovers
        otherwise valid but truncated pretty-printed JSON.
        """
        result = []
        in_string = False
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '\\' and in_string and i + 1 < len(text):
                result.append(ch)
                result.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
            elif in_string:
                result.append(ch)
            elif ch in ' \t\n\r':
                # Skip whitespace outside strings
                pass
            else:
                result.append(ch)
            i += 1
        return ''.join(result)

    @staticmethod
    def _fix_string_escapes(text: str) -> str:
        """Fix unescaped control characters inside JSON string values."""
        result = []
        in_string = False
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '\\' and in_string and i + 1 < len(text):
                result.append(ch)
                result.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
            elif in_string and ch == '\n':
                result.append('\\n')
            elif in_string and ch == '\t':
                result.append('\\t')
            else:
                result.append(ch)
            i += 1
        return ''.join(result)

    @staticmethod
    def _repair_truncated_json(text: str) -> dict | None:
        """Try to repair JSON that was truncated mid-generation.

        Strategy: strip the last incomplete value/key, then close all open
        brackets and braces in correct nesting order. Also handles trailing commas.
        """
        in_string = False
        escape = False
        last_complete_pos = 0

        for i, ch in enumerate(text):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
            elif not in_string and ch in '{}[],':
                last_complete_pos = i + 1

        # Truncate to last complete structural token, strip trailing openers
        truncated = text[:last_complete_pos].rstrip()
        truncated = truncated.rstrip(',').rstrip()
        truncated = truncated.rstrip('{[').rstrip().rstrip(',')

        # Strip trailing commas inside the structure
        truncated = re.sub(r',\s*([}\]])', r'\1', truncated)

        # Recount nesting from cleaned text to get correct close order
        nesting_stack = []
        in_str = False
        esc = False
        for ch in truncated:
            if esc:
                esc = False
                continue
            if ch == '\\' and in_str:
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch == '{':
                    nesting_stack.append('}')
                elif ch == '[':
                    nesting_stack.append(']')
                elif ch in '}]' and nesting_stack:
                    nesting_stack.pop()

        if not nesting_stack:
            # Already balanced — try direct parse
            try:
                return json.loads(truncated)
            except json.JSONDecodeError:
                return None

        # Close open structures in reverse nesting order
        truncated += ''.join(reversed(nesting_stack))

        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            return None