import ctypes
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

# Windows power management — prevent system sleep during long analyses
_ES_CONTINUOUS      = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


def _prevent_sleep() -> None:
    """Tell Windows not to sleep while the process is running."""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
    except Exception:
        pass  # Non-Windows or permission issue — silently ignore


def _allow_sleep() -> None:
    """Release the sleep-prevention lock."""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
    except Exception:
        pass


def _write_json(path: Path, data: dict) -> None:
    """Write a dict to a JSON file, silently skipping on error."""
    try:
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Could not write {path}: {e}")


from agents.orchestrator import OrchestratorAgent
from agents.data_extractor import DataExtractorAgent
from agents.trend_analyzer import TrendAnalyzerAgent
from agents.sentiment_analyzer import SentimentAnalyzerAgent
from agents.validator import ValidatorAgent
from utils.pdf_reader import read_document
from utils.data_formatter import merge_results, truncate_text
from utils.report_generator import generate_report
from utils.stock_data import fetch_stock_data, format_stock_summary
from utils.search import web_search
from utils.sec_edgar import fetch_sec_filings
from utils.rss_reader import fetch_ticker_news, fetch_market_news
from utils.fred import fetch_macro_indicators
from utils.ecb import fetch_ecb_indicators
from utils.riksbank import fetch_riksbank_indicators
from utils.worldbank import fetch_worldbank_indicators
from config.config import CONTEXT_LENGTH, CONTEXT_LENGTH_EXTENDED

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/analysis.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# Which data blocks each text-consuming agent should receive.
# trend_analyzer and validator receive structured JSON from prior agents, not raw text.
_EXTRACTOR_SOURCES = ("documents", "text", "stock_data", "sec_filings", "macro")
_SENTIMENT_SOURCES = ("news", "web_search", "text", "stock_data")

# Stop words for search term extraction
_SEARCH_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "ought",
    "which", "that", "this", "these", "those", "what", "who", "whom",
    "where", "when", "why", "how", "and", "or", "but", "nor", "not",
    "so", "yet", "both", "either", "neither", "each", "every", "all",
    "any", "few", "more", "most", "other", "some", "such", "no", "only",
    "own", "same", "than", "too", "very", "also", "just", "about",
    "above", "after", "again", "against", "at", "before", "below",
    "between", "by", "for", "from", "in", "into", "of", "off", "on",
    "out", "over", "through", "to", "under", "until", "up", "with",
    "looking", "considering", "assuming", "provided", "listed", "here",
    "likely", "possible", "reasonable", "certainly", "otherwise",
    "returned", "investors", "investment", "invest", "company",
    "companies", "it", "its", "we", "our", "us", "i", "my", "me",
})


class FinancialAnalysisSystem:
    """Main entry point for the multi-agent financial analysis system."""

    def __init__(self):
        self.orchestrator = OrchestratorAgent()
        self.agents = {
            "data_extractor": DataExtractorAgent(),
            "trend_analyzer": TrendAnalyzerAgent(),
            "sentiment_analyzer": SentimentAnalyzerAgent(),
            "validator": ValidatorAgent(),
        }

    def _apply_context_mode(self, extended: bool) -> None:
        """Set context lengths on all agents based on selected mode."""
        lengths = CONTEXT_LENGTH_EXTENDED if extended else CONTEXT_LENGTH
        self.orchestrator.num_ctx = lengths["orchestrator"]
        for key, agent in self.agents.items():
            agent.num_ctx = lengths.get(key, 2048)

    @staticmethod
    def _report_slug(query: str) -> str:
        """Create a short filesystem-safe name from the first words of the query."""
        words = query.strip().split()[:6]
        slug = "_".join(re.sub(r"[^a-z0-9]", "", w.lower()) for w in words)
        return (slug or "analysis")[:50]

    # ------------------------------------------------------------------
    # Input budgeting
    # ------------------------------------------------------------------

    def _input_budget_chars(self, agent_key: str) -> int:
        """Max input characters for an agent based on its context window.

        Reserves tokens for: system prompt (~800 for extractor with few-shot),
        output (num_predict = 60% of num_ctx), overhead (~200).
        Uses ~4 chars/token as a conservative estimate.
        """
        agent = self.agents.get(agent_key)
        if not agent:
            return 8000
        num_predict = max(1536, min(agent.num_ctx * 3 // 5, 4096))
        reserved_tokens = 800 + num_predict + 200
        available_tokens = max(agent.num_ctx - reserved_tokens, 512)
        return available_tokens * 4  # ~4 chars per token

    @staticmethod
    def _build_agent_input(source_keys: tuple, data_blocks: dict, budget_chars: int) -> str:
        """Assemble input text from selected data blocks, truncated to budget."""
        relevant = [(k, v) for k, v in data_blocks.items() if k in source_keys and v]
        if not relevant:
            return ""

        # Distribute budget evenly across blocks
        per_block = max(budget_chars // len(relevant), 500)
        parts = []
        for _key, text in relevant:
            if len(text) <= per_block:
                parts.append(text)
            else:
                truncated = text[:per_block]
                last_period = truncated.rfind(".")
                if last_period > per_block * 0.5:
                    truncated = truncated[: last_period + 1]
                parts.append(truncated + "\n[... truncated]")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Web search — focused queries instead of full paragraph
    # ------------------------------------------------------------------

    def _fetch_web_search(self, query: str, tickers: list[str] | None = None) -> str:
        """Run focused web searches and return formatted results."""
        search_queries = []

        # Per-ticker search (max 4)
        if tickers:
            for ticker in tickers[:4]:
                clean = ticker.split(".")[0].replace("-", " ")
                search_queries.append(f"{clean} stock financial outlook analysis")

        # Only add a general query if we have no per-ticker searches
        if not search_queries:
            terms = self._extract_search_terms(query)
            if terms:
                search_queries.append(terms)
            else:
                search_queries.append(query[:120])

        all_results = []
        per_query_max = max(2, 5 // len(search_queries))

        for q in search_queries:
            try:
                result = web_search(q, max_results=per_query_max)
                if result:
                    all_results.append(result)
            except Exception as e:
                logger.warning(f"Web search failed for '{q}': {e}")

        return "\n\n".join(all_results) if all_results else ""

    @staticmethod
    def _extract_search_terms(query: str) -> str:
        """Extract a focused search query from a verbose user question."""
        words = query.lower().split()
        meaningful = [
            w for w in words
            if w.isalpha() and w not in _SEARCH_STOP_WORDS and len(w) > 2
        ]
        return " ".join(meaningful[:8]) if meaningful else ""

    # ------------------------------------------------------------------
    # Main analysis pipeline
    # ------------------------------------------------------------------

    def analyze(
        self,
        query: str,
        documents: list[str] | None = None,
        text: str | None = None,
        tickers: list[str] | None = None,
        web_search: bool = False,
        fetch_news: bool = False,
        fetch_sec: bool = False,
        fetch_macro: bool = False,
        fetch_ecb: bool = False,
        fetch_riksbank: bool = False,
        fetch_worldbank: bool = False,
        extended_context: bool = False,
    ) -> dict:
        """Run a financial analysis with per-agent input filtering and budgeting."""
        self._apply_context_mode(extended_context)
        _prevent_sleep()

        # Create per-run report directory
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = Path("reports") / f"{self._report_slug(query)}_{ts}"
        run_dir.mkdir(parents=True, exist_ok=True)
        agents_dir = run_dir / "agents"
        agents_dir.mkdir(exist_ok=True)

        # Per-run log handler
        run_log_handler = logging.FileHandler(run_dir / "analysis.log", encoding="utf-8")
        run_log_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        )
        logging.getLogger().addHandler(run_log_handler)

        logger.info(f"Starting analysis: {query} [context={'extended' if extended_context else 'standard'}]")
        logger.info(f"Run directory: {run_dir}")

        try:
            # ==============================================================
            # Step 1: Collect data into labeled blocks
            # ==============================================================
            data_blocks: dict[str, str] = {}

            # Documents
            document_texts = self._load_documents_separate(documents)
            if document_texts:
                data_blocks["documents"] = self._combine_inputs(document_texts, None)

            # Pasted text
            if text:
                data_blocks["text"] = f"=== Additional Text ===\n{text}"

            # Live stock data
            stock_text = self._fetch_stock_context(tickers)
            if stock_text:
                data_blocks["stock_data"] = stock_text

            # Web search (focused queries)
            if web_search:
                ws = self._fetch_web_search(query, tickers)
                if ws:
                    data_blocks["web_search"] = ws

            # RSS news
            if fetch_news:
                news_parts = []
                if tickers:
                    for ticker in tickers:
                        t = fetch_ticker_news(ticker)
                        if t:
                            news_parts.append(t)
                market = fetch_market_news()
                if market:
                    news_parts.append(market)
                if news_parts:
                    data_blocks["news"] = "\n\n".join(news_parts)

            # SEC filings — only for US-listed tickers (no exchange suffix)
            _NON_US_SUFFIXES = (".ST", ".HE", ".CO", ".OL", ".DE", ".L", ".PA", ".AS", ".MI", ".MC", ".SW")
            if fetch_sec and tickers:
                sec_parts = []
                for ticker in tickers:
                    if any(ticker.upper().endswith(s) for s in _NON_US_SUFFIXES):
                        logger.info(f"Skipping SEC for non-US ticker: {ticker}")
                        continue
                    t = fetch_sec_filings(ticker)
                    if t:
                        sec_parts.append(t)
                if sec_parts:
                    data_blocks["sec_filings"] = "\n\n".join(sec_parts)

            # Macro data (collected together for trend_analyzer)
            macro_parts = []
            if fetch_macro:
                t = fetch_macro_indicators()
                if t:
                    macro_parts.append(t)
            if fetch_ecb:
                t = fetch_ecb_indicators()
                if t:
                    macro_parts.append(t)
            if fetch_riksbank:
                t = fetch_riksbank_indicators()
                if t:
                    macro_parts.append(t)
            if fetch_worldbank:
                t = fetch_worldbank_indicators()
                if t:
                    macro_parts.append(t)
            if macro_parts:
                data_blocks["macro"] = "\n\n".join(macro_parts)

            if not data_blocks:
                return {"error": "No input provided. Supply documents, text, or tickers to analyze."}

            # Log block sizes for debugging
            for bk, bv in data_blocks.items():
                logger.info(f"Data block '{bk}': {len(bv)} chars")

            # ==============================================================
            # Step 2: Orchestrator plans which agents to use
            # ==============================================================
            all_text_preview = "\n\n".join(
                truncate_text(v, 300) for v in data_blocks.values()
            )
            available_data = {
                "has_documents": bool(documents),
                "has_text": bool(text),
                "has_stock_data": bool(tickers),
                "has_web_search": web_search,
                "has_news": fetch_news,
                "has_sec_filings": fetch_sec,
                "has_macro_data": fetch_macro,
                "has_ecb_data": fetch_ecb,
                "has_riksbank_data": fetch_riksbank,
                "has_worldbank_data": fetch_worldbank,
                "document_count": len(document_texts),
                "tickers": tickers or [],
                "text_preview": truncate_text(all_text_preview, 800),
            }

            plan = self._run_with_fallback(
                "orchestrator.plan",
                lambda: self.orchestrator.plan(query, available_data),
                fallback={"agents_needed": ["data_extractor"], "instructions": {}},
            )
            logger.info(f"Orchestrator plan: {json.dumps(plan, indent=2)}")
            _write_json(agents_dir / "orchestrator_plan.json", plan)

            agents_needed = plan.get("agents_needed", ["data_extractor"])
            instructions = plan.get("instructions", {})

            # ==============================================================
            # Step 3: Run agents sequentially with filtered input
            # ==============================================================
            agent_results = {}

            # Multi-document cross-referencing
            if "data_extractor" in agents_needed and len(document_texts) > 1:
                per_doc = self._extract_per_document(document_texts, instructions)
                agent_results["data_extractor"] = {
                    "cross_reference": True,
                    "documents": per_doc,
                }
                agents_needed = [a for a in agents_needed if a != "data_extractor"]

            for agent_name in agents_needed:
                if agent_name not in self.agents:
                    logger.warning(f"Agent '{agent_name}' not recognized, skipping")
                    continue

                agent_result = self._run_agent(agent_name, data_blocks, agent_results, instructions)

                if agent_result is not None:
                    # Early abort check: detect hallucinated raw_response
                    self._check_failed_output(agent_result, agent_name)
                    agent_results[agent_name] = agent_result
                    _write_json(agents_dir / f"{agent_name}.json", agent_result)

            # Save cross-reference result if not saved in loop
            if "data_extractor" in agent_results and not (agents_dir / "data_extractor.json").exists():
                _write_json(agents_dir / "data_extractor.json", agent_results["data_extractor"])

            # ==============================================================
            # Step 4: Orchestrator synthesizes all results
            # ==============================================================

            # Truncate agent results before synthesis to avoid overflowing orchestrator context
            synthesis_budget = self._input_budget_chars("data_extractor")  # conservative
            merged = self._prepare_synthesis_input(agent_results, synthesis_budget)

            synthesis = self._run_with_fallback(
                "orchestrator.synthesize",
                lambda: self.orchestrator.synthesize(query, merged),
                fallback={"summary": "Synthesis unavailable. See individual agent results.", "key_findings": [], "confidence": "low"},
            )
            _write_json(agents_dir / "orchestrator_synthesis.json", synthesis)

            result = {
                "summary": synthesis.get("summary", ""),
                "key_findings": synthesis.get("key_findings", []),
                "confidence": synthesis.get("confidence", "unknown"),
                "macro_context": synthesis.get("macro_context"),
                "currency_note": synthesis.get("currency_note"),
                "data_sources_used": synthesis.get("data_sources_used", []),
                "caveats": synthesis.get("caveats", []),
                "extracted_data": agent_results.get("data_extractor", {}),
                "trends": agent_results.get("trend_analyzer", {}),
                "sentiment": agent_results.get("sentiment_analyzer", {}),
                "validation": agent_results.get("validator", {}),
            }

            # Save full result and report
            _write_json(run_dir / "result.json", {"query": query, "timestamp": ts, "result": result})
            generate_report(result, query, output_path=str(run_dir / "report.md"))
            generate_report(result, query, output_path="reports/latest_report.md")
            logger.info(f"Results saved to {run_dir}")

        finally:
            _allow_sleep()
            logging.getLogger().removeHandler(run_log_handler)
            run_log_handler.close()

        return result

    # ------------------------------------------------------------------
    # Agent execution
    # ------------------------------------------------------------------

    def _run_agent(self, agent_name: str, data_blocks: dict, prior_results: dict, instructions: dict) -> dict | None:
        """Run a single agent with filtered input and error handling."""
        agent = self.agents[agent_name]
        agent_instruction = instructions.get(agent_name, "")

        def execute():
            if agent_name == "data_extractor":
                budget = self._input_budget_chars("data_extractor")
                text = self._build_agent_input(_EXTRACTOR_SOURCES, data_blocks, budget)
                if not text:
                    return {"company_data": [], "macro_data": [], "notes": "No relevant input data available."}
                return agent.extract(text, agent_instruction)

            elif agent_name == "trend_analyzer":
                extracted = prior_results.get("data_extractor", {})
                extraction_failed = extracted.get("_extraction_failed", False)

                # Attach raw macro data so trend_analyzer can see numbers directly
                macro_text = data_blocks.get("macro", "")
                budget = self._input_budget_chars("trend_analyzer")
                if macro_text:
                    macro_truncated = truncate_text(macro_text, budget // 3)
                    extracted = {**extracted, "_raw_macro_data": macro_truncated}

                # If extraction failed, instruct trend_analyzer to only analyse macro data
                trend_instruction = agent_instruction
                if extraction_failed:
                    logger.warning("Extraction failed — trend_analyzer will skip company_trends")
                    trend_instruction = (
                        "IMPORTANT: The data extractor failed. There is NO reliable company data. "
                        "Set company_trends to an empty array []. "
                        "Only analyse macro_trends from _raw_macro_data if available. "
                        "Do NOT invent or estimate any company metrics."
                    )

                return agent.analyze(extracted, trend_instruction)

            elif agent_name == "sentiment_analyzer":
                budget = self._input_budget_chars("sentiment_analyzer")
                text = self._build_agent_input(_SENTIMENT_SOURCES, data_blocks, budget)
                if not text:
                    return {"overall_sentiment": "neutral", "summary": "No text sources available for sentiment analysis."}
                return agent.analyze(text, agent_instruction)

            elif agent_name == "validator":
                # Truncate prior results to fit validator context
                budget = self._input_budget_chars("validator")
                truncated_results = self._prepare_synthesis_input(prior_results, budget)
                return agent.validate(truncated_results, agent_instruction)

            else:
                return agent.run(
                    self._build_agent_input(
                        tuple(data_blocks.keys()), data_blocks,
                        self._input_budget_chars(agent_name)
                    ),
                    context=prior_results,
                )

        return self._run_with_fallback(agent_name, execute, fallback=None)

    @staticmethod
    def _check_failed_output(result: dict, agent_name: str) -> None:
        """Replace hallucinated raw_response with a minimal stub so downstream agents get clean input."""
        if "raw_response" not in result:
            return

        raw = result.get("raw_response", "")
        # raw_response as only key means JSON parse failed entirely
        if len(result) == 1 and len(raw) > 500:
            logger.warning(
                f"[{agent_name}] Produced unstructured output ({len(raw)} chars) — "
                f"replacing with stub to protect downstream agents."
            )
            result.clear()
            result.update({
                "_extraction_failed": True,
                "company_data": [],
                "macro_data": [],
                "notes": f"{agent_name} failed to produce structured output. "
                         f"Results based on this agent's work will be degraded.",
            })

    @staticmethod
    def _prepare_synthesis_input(agent_results: dict, budget_chars: int) -> dict:
        """Truncate agent results to fit within a character budget for synthesis/validation."""
        merged = merge_results(agent_results)
        total = sum(len(json.dumps(v, default=str)) for v in merged.values())

        if total <= budget_chars:
            return merged

        # Distribute budget across agents proportionally
        per_agent = budget_chars // max(len(merged), 1)
        truncated = {}
        for name, data in merged.items():
            serialized = json.dumps(data, default=str)
            if len(serialized) <= per_agent:
                truncated[name] = data
            else:
                # Keep the structure but truncate raw_response fields
                if isinstance(data, dict) and "raw_response" in data:
                    truncated[name] = {
                        **{k: v for k, v in data.items() if k != "raw_response"},
                        "raw_response": data["raw_response"][:per_agent] + " [... truncated]",
                    }
                else:
                    # Last resort: serialize and truncate
                    truncated[name] = {"_truncated": serialized[:per_agent] + " [...]"}

        return truncated

    def _run_with_fallback(self, name: str, fn, fallback):
        """Execute a function with logging and error handling."""
        try:
            logger.info(f"Running: {name}")
            result = fn()
            preview = json.dumps(result, default=str)[:300].replace("\n", " ")
            logger.info(f"Completed: {name} | output preview: {preview}")
            return result
        except ConnectionError:
            logger.error(f"[{name}] Cannot connect to Ollama. Is 'ollama serve' running?")
            return fallback
        except Exception as e:
            logger.error(f"[{name}] Failed: {e}")
            return fallback

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_per_document(self, document_texts: dict[str, str], instructions: dict) -> list[dict]:
        """Run data extraction on each document separately for cross-referencing."""
        extractor = self.agents["data_extractor"]
        instruction = instructions.get("data_extractor", "")
        budget = self._input_budget_chars("data_extractor")
        results = []

        for doc_name, doc_text in document_texts.items():
            logger.info(f"Extracting from: {doc_name}")
            truncated_doc = truncate_text(doc_text, budget)
            result = self._run_with_fallback(
                f"data_extractor ({doc_name})",
                lambda t=truncated_doc: extractor.extract(t, instruction),
                fallback={"error": f"Extraction failed for {doc_name}"},
            )
            result["source_document"] = doc_name
            results.append(result)

        return results

    def _load_documents_separate(self, documents: list[str] | None) -> dict[str, str]:
        """Read each document into a dict keyed by filename."""
        if not documents:
            return {}

        result = {}
        for doc_path in documents:
            try:
                content = read_document(doc_path)
                result[doc_path] = content
                logger.info(f"Loaded document: {doc_path}")
            except (FileNotFoundError, ValueError) as e:
                logger.error(f"Failed to load {doc_path}: {e}")

        return result

    def _combine_inputs(self, document_texts: dict[str, str], raw_text: str | None) -> str:
        """Combine all document texts and raw text into a single string."""
        parts = []
        for doc_name, content in document_texts.items():
            parts.append(f"=== {doc_name} ===\n{content}")
        if raw_text:
            parts.append(f"=== Additional Text ===\n{raw_text}")
        return "\n\n".join(parts)

    def _fetch_stock_context(self, tickers: list[str] | None) -> str:
        """Fetch live stock data and format as text for agents."""
        if not tickers:
            return ""

        parts = ["=== Live Stock Data ==="]
        for ticker in tickers:
            data = fetch_stock_data(ticker)
            summary = format_stock_summary(data)
            if summary:
                parts.append(summary)

        return "\n\n".join(parts)


if __name__ == "__main__":
    system = FinancialAnalysisSystem()

    if len(sys.argv) < 2:
        print("Usage: python main.py <query> [doc.pdf] [--tickers AAPL] [--search] [--news] [--sec] [--macro] [--ecb] [--riksbank] [--worldbank] [--extended-ctx]")
        print('Example: python main.py "Ericsson outlook" --tickers ERIC-B.ST --news --ecb --riksbank --worldbank')
        sys.exit(1)

    # Parse args
    args = sys.argv[1:]
    query = args[0]
    docs = []
    tickers = []
    do_web_search = False
    do_news = False
    do_sec = False
    do_macro = False
    do_ecb = False
    do_riksbank = False
    do_worldbank = False
    do_extended_ctx = False
    parsing_tickers = False

    for arg in args[1:]:
        if arg == "--tickers":
            parsing_tickers = True
        elif arg in ("--search", "--news", "--sec", "--macro", "--ecb", "--riksbank", "--worldbank", "--extended-ctx"):
            if arg == "--search":       do_web_search = True
            if arg == "--news":         do_news = True
            if arg == "--sec":          do_sec = True
            if arg == "--macro":        do_macro = True
            if arg == "--ecb":          do_ecb = True
            if arg == "--riksbank":     do_riksbank = True
            if arg == "--worldbank":    do_worldbank = True
            if arg == "--extended-ctx": do_extended_ctx = True
            parsing_tickers = False
        elif parsing_tickers:
            tickers.append(arg)
        else:
            docs.append(arg)

    result = system.analyze(
        query=query,
        documents=docs if docs else None,
        tickers=tickers if tickers else None,
        web_search=do_web_search,
        fetch_news=do_news,
        fetch_sec=do_sec,
        fetch_macro=do_macro,
        fetch_ecb=do_ecb,
        fetch_riksbank=do_riksbank,
        fetch_worldbank=do_worldbank,
        extended_context=do_extended_ctx,
    )

    # Print the latest report (already auto-saved inside analyze())
    print(generate_report(result, query))
