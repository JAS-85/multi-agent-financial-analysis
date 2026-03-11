import json
import logging
import sys
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
        "1. **Orchestrator** (Mistral 7B) — plans & synthesizes\n"
        "2. **Data Extractor** (Phi 3.8B) — extracts figures\n"
        "3. **Trend Analyzer** (Mistral 7B) — finds patterns\n"
        "4. **Sentiment Analyzer** (Mistral 7B) — reads signals\n"
        "5. **Validator** (Phi 3.8B) — checks consistency"
    )
    st.divider()
    st.markdown("All processing happens **locally**. No data leaves your machine.")

# --- Main Input ---
query = st.text_area(
    "What would you like to analyze?",
    placeholder="e.g. What is the revenue trend for Company X based on this report?",
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
        height=150,
    )
    ticker_input = st.text_input(
        "Stock tickers (comma-separated)",
        placeholder="e.g. AAPL, MSFT, GOOGL",
    )
    enable_web_search = st.checkbox(
        "Search the web (DuckDuckGo)",
        value=False,
        help="Search the web for news and information related to your query.",
    )
    enable_news = st.checkbox(
        "Fetch news headlines (RSS)",
        value=False,
        help="Fetch latest headlines from Reuters, MarketWatch, Motley Fool, and Yahoo Finance per ticker.",
    )
    enable_sec = st.checkbox(
        "Fetch SEC filings (EDGAR)",
        value=False,
        help="Fetch recent 10-K and 10-Q filings from SEC EDGAR for provided tickers.",
    )
    enable_macro = st.checkbox(
        "Fetch macro indicators (FRED)",
        value=False,
        help="Fetch key macroeconomic indicators: GDP, CPI, Fed Funds Rate, unemployment, S&P 500.",
    )

# Parse tickers
tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()] if ticker_input else []

# --- Run Analysis ---
if st.button("Run Analysis", type="primary", disabled=not query):
    if not uploaded_files and not text_input and not tickers and not enable_web_search and not enable_news and not enable_macro:
        st.error("Please upload documents, paste text, or enter stock tickers.")
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
                st.write("Fetching macro indicators...")
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

            # Confidence
            if result.get("confidence"):
                confidence = result["confidence"]
                color = {"high": "green", "medium": "orange", "low": "red"}.get(confidence, "gray")
                st.markdown(f"**Confidence:** :{color}[{confidence}]")

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
