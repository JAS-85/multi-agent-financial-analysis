import json
import logging
import sys
from pathlib import Path

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
    ) -> dict:
        """
        Run a financial analysis.

        Args:
            query:       The analysis question.
            documents:   Optional list of file paths (PDF, CSV, TXT).
            text:        Optional raw text input.
            tickers:     Optional stock ticker symbols for live price data.
            web_search:  Search the web via DuckDuckGo.
            fetch_news:  Fetch RSS news headlines (Yahoo Finance per ticker + market feeds).
            fetch_sec:   Fetch recent SEC EDGAR filings (10-K/10-Q) per ticker.
            fetch_macro: Fetch macroeconomic indicators from FRED.

        Returns:
            Dict with summary, extracted_data, trends, sentiment, validation.
        """
        logger.info(f"Starting analysis: {query}")

        # Step 1: Read documents individually (for cross-referencing)
        document_texts = self._load_documents_separate(documents)
        all_text = self._combine_inputs(document_texts, text)

        def _append(block: str):
            nonlocal all_text
            if block:
                all_text = all_text + "\n\n" + block if all_text else block

        # Step 1b: Fetch live stock data if tickers provided
        _append(self._fetch_stock_context(tickers))

        # Step 1c: Web search
        if web_search:
            _append(self._fetch_web_search(query))

        # Step 1d: RSS news
        if fetch_news:
            if tickers:
                for ticker in tickers:
                    _append(fetch_ticker_news(ticker))
            _append(fetch_market_news())

        # Step 1e: SEC EDGAR filings
        if fetch_sec and tickers:
            for ticker in tickers:
                _append(fetch_sec_filings(ticker))

        # Step 1f: FRED macroeconomic data
        if fetch_macro:
            _append(fetch_macro_indicators())

        if not all_text:
            return {"error": "No input provided. Supply documents, text, or tickers to analyze."}

        # Step 2: Orchestrator plans which agents to use
        available_data = {
            "has_documents": bool(documents),
            "has_text": bool(text),
            "has_stock_data": bool(tickers),
            "has_web_search": web_search,
            "has_news": fetch_news,
            "has_sec_filings": fetch_sec,
            "has_macro_data": fetch_macro,
            "document_count": len(document_texts),
            "tickers": tickers or [],
            "text_preview": truncate_text(all_text, 500),
        }

        plan = self._run_with_fallback(
            "orchestrator.plan",
            lambda: self.orchestrator.plan(query, available_data),
            fallback={"agents_needed": ["data_extractor"], "instructions": {}},
        )
        logger.info(f"Orchestrator plan: {json.dumps(plan, indent=2)}")

        agents_needed = plan.get("agents_needed", ["data_extractor"])
        instructions = plan.get("instructions", {})

        # Step 3: Run agents sequentially
        agent_results = {}

        # Multi-document cross-referencing: extract from each document separately
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

            result = self._run_agent(agent_name, all_text, agent_results, instructions)
            if result is not None:
                agent_results[agent_name] = result

        # Step 4: Orchestrator synthesizes all results
        merged = merge_results(agent_results)
        synthesis = self._run_with_fallback(
            "orchestrator.synthesize",
            lambda: self.orchestrator.synthesize(query, merged),
            fallback={"summary": "Synthesis unavailable. See individual agent results.", "key_findings": [], "confidence": "low"},
        )

        return {
            "summary": synthesis.get("summary", ""),
            "key_findings": synthesis.get("key_findings", []),
            "confidence": synthesis.get("confidence", "unknown"),
            "extracted_data": agent_results.get("data_extractor", {}),
            "trends": agent_results.get("trend_analyzer", {}),
            "sentiment": agent_results.get("sentiment_analyzer", {}),
            "validation": agent_results.get("validator", {}),
        }

    def _extract_per_document(self, document_texts: dict[str, str], instructions: dict) -> list[dict]:
        """Run data extraction on each document separately for cross-referencing."""
        extractor = self.agents["data_extractor"]
        instruction = instructions.get("data_extractor", "")
        results = []

        for doc_name, doc_text in document_texts.items():
            logger.info(f"Extracting from: {doc_name}")
            result = self._run_with_fallback(
                f"data_extractor ({doc_name})",
                lambda t=doc_text: extractor.extract(t, instruction),
                fallback={"error": f"Extraction failed for {doc_name}"},
            )
            result["source_document"] = doc_name
            results.append(result)

        return results

    def _run_agent(self, agent_name: str, all_text: str, prior_results: dict, instructions: dict) -> dict | None:
        """Run a single agent with error handling. Returns None on failure."""
        agent = self.agents[agent_name]
        agent_instruction = instructions.get(agent_name, "")

        def execute():
            if agent_name == "data_extractor":
                return agent.extract(all_text, agent_instruction)
            elif agent_name == "trend_analyzer":
                extracted = prior_results.get("data_extractor", {})
                return agent.analyze(extracted, agent_instruction)
            elif agent_name == "sentiment_analyzer":
                return agent.analyze(all_text, agent_instruction)
            elif agent_name == "validator":
                return agent.validate(prior_results, agent_instruction)
            else:
                return agent.run(all_text, context=prior_results)

        return self._run_with_fallback(agent_name, execute, fallback=None)

    def _run_with_fallback(self, name: str, fn, fallback):
        """Execute a function with logging and error handling."""
        try:
            logger.info(f"Running: {name}")
            result = fn()
            logger.info(f"Completed: {name}")
            return result
        except ConnectionError:
            logger.error(f"[{name}] Cannot connect to Ollama. Is 'ollama serve' running?")
            return fallback
        except Exception as e:
            logger.error(f"[{name}] Failed: {e}")
            return fallback

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

    def _fetch_web_search(self, query: str) -> str:
        """Run a web search and return formatted results as text."""
        try:
            return web_search(query)
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return ""

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
        print("Usage: python main.py <query> [doc.pdf] [--tickers AAPL] [--search] [--news] [--sec] [--macro]")
        print('Example: python main.py "Pfizer outlook" --tickers PFE --search --news --sec --macro')
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
    parsing_tickers = False

    for arg in args[1:]:
        if arg == "--tickers":
            parsing_tickers = True
        elif arg in ("--search", "--news", "--sec", "--macro"):
            if arg == "--search": do_web_search = True
            if arg == "--news":   do_news = True
            if arg == "--sec":    do_sec = True
            if arg == "--macro":  do_macro = True
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
    )

    # Generate and save report
    report = generate_report(result, query, output_path="reports/latest_report.md")
    print(report)
