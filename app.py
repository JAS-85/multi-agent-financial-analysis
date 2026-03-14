import logging
from pathlib import Path

import streamlit as st

from main import FinancialAnalysisSystem
from utils.report_generator import generate_report

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/analysis.log", encoding="utf-8"),
    ],
)

st.set_page_config(
    page_title="Financial Analysis System",
    page_icon="📊",
    layout="wide",
)

st.title("Multi-Agent Financial Analysis")
st.caption("Local, privacy-preserving analysis using specialized AI agents")


@st.cache_resource
def get_system():
    return FinancialAnalysisSystem()


# --- Sidebar ---
with st.sidebar:
    st.header("About")
    st.markdown(
        "This system uses **5 specialized AI agents** running locally via Ollama:\n"
        "1. **Orchestrator** (Llama 3.1 8B) — plans & synthesizes\n"
        "2. **Data Extractor** (Phi 3.8B) — extracts figures\n"
        "3. **Trend Analyzer** (Mistral 7B) — finds patterns\n"
        "4. **Sentiment Analyzer** (Mistral 7B) — reads signals\n"
        "5. **Validator** (Phi 3.8B) — checks consistency"
    )
    st.divider()
    st.subheader("Context Mode")
    context_mode = st.radio(
        "Context window size",
        options=["Standard (8k / 4k)", "Extended (16k / 8k)"],
        index=0,
        help=(
            "**Standard**: 8k tokens for Llama/Mistral, 4k for Phi. "
            "Safe with browser + VSCode open (~6 GB peak).\n\n"
            "**Extended**: 16k / 8k tokens. "
            "Better for long SEC filings and multi-source analyses. "
            "Requires ~8–10 GB free RAM."
        ),
    )
    extended_context = context_mode.startswith("Extended")
    st.divider()
    with st.expander("Exchange suffixes reference"):
        st.markdown(
            "| Market | Suffix |\n"
            "|--------|--------|\n"
            "| NYSE / NASDAQ (US) | *(none)* |\n"
            "| Nasdaq Stockholm (SE) | `.ST` |\n"
            "| Nasdaq Helsinki (FI) | `.HE` |\n"
            "| Nasdaq Copenhagen (DK) | `.CO` |\n"
            "| Oslo Bors (NO) | `.OL` |\n"
            "| XETRA Frankfurt (DE) | `.DE` |\n"
            "| London Stock Exchange (UK) | `.L` |\n"
            "| Euronext Paris (FR) | `.PA` |\n"
            "| Euronext Amsterdam (NL) | `.AS` |\n"
            "| Euronext Milan (IT) | `.MI` |\n"
            "| Bolsa Madrid (ES) | `.MC` |\n"
            "| SIX Swiss Exchange (CH) | `.SW` |\n"
        )
    st.divider()
    st.markdown("All processing happens **locally**. No data leaves your machine.")

# --- Main Input ---
query = st.text_area(
    "What would you like to analyze?",
    placeholder="e.g. What is the revenue trend for Ericsson over the last three years?",
    height=100,
)

col1, col2 = st.columns(2)

with col1:
    uploaded_files = st.file_uploader(
        "Upload documents (PDF, CSV, TXT)",
        type=["pdf", "csv", "txt"],
        accept_multiple_files=True,
    )

with col2:
    text_input = st.text_area(
        "Or paste text directly",
        placeholder="Paste news articles, financial data, or any text to analyze...",
        height=120,
    )
    ticker_input = st.text_input(
        "Stock tickers (comma-separated)",
        placeholder="e.g. AAPL, ERIC-B.ST, NOVO-B.CO, SAP.DE",
        help=(
            "Include the exchange suffix directly in the ticker for non-US stocks. "
            "See **Exchange suffixes reference** in the sidebar for a full list. "
            "US tickers (NYSE/NASDAQ) need no suffix."
        ),
    )

# Parse tickers — no suffix logic, used as written
tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()] if ticker_input else []

# --- Data Sources ---
st.markdown("**Data Sources**")

src_global, src_us, src_eu = st.columns(3)

with src_global:
    st.markdown("*Global*")
    enable_web_search = st.checkbox(
        "Web search (DuckDuckGo)",
        value=False,
        help="Search the web for news and information related to your query.",
    )
    enable_news = st.checkbox(
        "News headlines (RSS)",
        value=False,
        help=(
            "Fetch latest headlines from CNBC, MarketWatch, Motley Fool, "
            "Dagens Industri, and Realtid. Also fetches Yahoo Finance RSS per ticker."
        ),
    )

with src_us:
    st.markdown("*United States*")
    enable_sec = st.checkbox(
        "SEC filings (EDGAR)",
        value=False,
        help=(
            "Fetch recent 10-K and 10-Q filings from SEC EDGAR. "
            "Only works for US-listed companies — non-US tickers will be skipped."
        ),
    )
    enable_macro = st.checkbox(
        "US macro indicators (FRED)",
        value=False,
        help="GDP, CPI, Fed Funds Rate, unemployment, S&P 500 from FRED.",
    )

with src_eu:
    st.markdown("*Europe & Global Macro*")
    enable_ecb = st.checkbox(
        "ECB rates & inflation",
        value=False,
        help=(
            "European Central Bank: HICP inflation, EUR/USD, EUR/SEK, EUR/GBP, "
            "and ECB main refinancing rate."
        ),
    )
    enable_riksbank = st.checkbox(
        "Riksbanken (Sweden)",
        value=False,
        help="Swedish repo rate (reporänta), USD/SEK and EUR/SEK from Riksbanken.",
    )
    enable_worldbank = st.checkbox(
        "World Bank (global)",
        value=False,
        help=(
            "GDP growth, CPI inflation, and unemployment for Sweden, US, Germany, "
            "France, UK, and the EU from World Bank Open Data."
        ),
    )

# --- Run Analysis ---
if st.button("Run Analysis", type="primary", disabled=not query):
    any_source = (
        uploaded_files or text_input or tickers
        or enable_web_search or enable_news or enable_macro
        or enable_ecb or enable_riksbank or enable_worldbank
    )
    if not any_source:
        st.error("Please upload documents, paste text, enter stock tickers, or select a data source.")
    else:
        # Save uploaded files to temp directory
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)
        doc_paths = []

        for uploaded_file in uploaded_files:
            temp_path = temp_dir / uploaded_file.name
            temp_path.write_bytes(uploaded_file.getvalue())
            doc_paths.append(str(temp_path))

        system = get_system()

        with st.status("Running analysis...", expanded=True) as status:
            if enable_web_search:
                st.write("Searching the web...")
            if enable_news:
                st.write("Fetching news headlines...")
            if enable_sec:
                st.write("Fetching SEC filings...")
            if enable_macro:
                st.write("Fetching US macro indicators (FRED)...")
            if enable_ecb:
                st.write("Fetching ECB rates and inflation...")
            if enable_riksbank:
                st.write("Fetching Riksbanken data...")
            if enable_worldbank:
                st.write("Fetching World Bank global macro data...")
            st.write("Planning analysis strategy...")
            result = system.analyze(
                query=query,
                documents=doc_paths if doc_paths else None,
                text=text_input if text_input else None,
                tickers=tickers if tickers else None,
                web_search=enable_web_search,
                fetch_news=enable_news,
                fetch_sec=enable_sec,
                fetch_macro=enable_macro,
                fetch_ecb=enable_ecb,
                fetch_riksbank=enable_riksbank,
                fetch_worldbank=enable_worldbank,
                extended_context=extended_context,
            )
            status.update(label="Analysis complete!", state="complete")

        # Clean up temp files
        for path in doc_paths:
            Path(path).unlink(missing_ok=True)
        if temp_dir.exists() and not any(temp_dir.iterdir()):
            temp_dir.rmdir()

        # --- Display Results ---
        if "error" in result:
            st.error(result["error"])
        else:
            st.header("Results")

            # Summary
            if result.get("summary"):
                st.subheader("Summary")
                st.write(result["summary"])

            # Key Findings
            if result.get("key_findings"):
                st.subheader("Key Findings")
                for finding in result["key_findings"]:
                    st.markdown(f"- {finding}")

            # Macro Context
            if result.get("macro_context"):
                st.subheader("Macroeconomic Context")
                st.write(result["macro_context"])

            # Meta row: confidence, sources, currency
            meta_col1, meta_col2 = st.columns(2)
            with meta_col1:
                if result.get("confidence"):
                    confidence = result["confidence"]
                    color = {"high": "green", "medium": "orange", "low": "red"}.get(confidence, "gray")
                    st.markdown(f"**Confidence:** :{color}[{confidence}]")
                if result.get("currency_note") and result["currency_note"] not in (None, "null"):
                    st.caption(f"Currency note: {result['currency_note']}")
            with meta_col2:
                if result.get("data_sources_used"):
                    st.markdown(f"**Sources used:** {', '.join(result['data_sources_used'])}")

            # Caveats
            if result.get("caveats"):
                with st.expander("Caveats & limitations"):
                    for caveat in result["caveats"]:
                        st.markdown(f"- {caveat}")

            # Detailed Results in Tabs
            tab_data, tab_trends, tab_sentiment, tab_validation, tab_raw = st.tabs(
                ["Extracted Data", "Trends", "Sentiment", "Validation", "Raw JSON"]
            )

            with tab_data:
                if result.get("extracted_data"):
                    st.json(result["extracted_data"])
                else:
                    st.info("No data extraction was performed.")

            with tab_trends:
                if result.get("trends"):
                    st.json(result["trends"])
                else:
                    st.info("No trend analysis was performed.")

            with tab_sentiment:
                if result.get("sentiment"):
                    st.json(result["sentiment"])
                else:
                    st.info("No sentiment analysis was performed.")

            with tab_validation:
                if result.get("validation"):
                    st.json(result["validation"])
                else:
                    st.info("No validation was performed.")

            with tab_raw:
                st.json(result)

            # Download report
            report_md = generate_report(result, query)
            st.download_button(
                label="Download Report (Markdown)",
                data=report_md,
                file_name="financial_analysis_report.md",
                mime="text/markdown",
            )
