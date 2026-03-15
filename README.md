# Multi-Agent Financial Analysis Tool

A local, privacy-preserving system for financial analysis using multiple specialized language models coordinated by an orchestrator agent. All inference runs on your machine via [Ollama](https://ollama.ai).

## Features

- **Five specialized agents** — orchestrator, data extractor, trend analyzer, sentiment analyzer, validator
- **Multiple data sources** — documents, live stock data, web search, news feeds, SEC filings, macroeconomic indicators from US, EU and Sweden
- **Robust JSON pipeline** — 5-step recovery handles whitespace compaction, trailing commas, unescaped chars, prettified output, and truncated responses
- **Web UI** — Streamlit interface for interactive use
- **CLI** — scriptable from the command line
- **Privacy-first** — no data leaves your machine; LLM inference is entirely local

## Architecture

```
User Query
    │
    ▼
Orchestrator (llama3.1:8b) ── plans which agents to invoke
    │
    ├─► Data Extractor (phi3:mini) ── structured extraction from documents + stock data
    ├─► Trend Analyzer (mistral:7b) ── patterns, growth rates, macro correlation
    ├─► Sentiment Analyzer (mistral:7b) ── news/search sentiment signals
    └─► Validator (phi3:mini) ── cross-checks consistency
    │
    ▼
Orchestrator ── synthesizes final report
```

Agents run sequentially (one model loaded at a time) to fit in 16 GB RAM.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.ai) installed and running
- 8 GB RAM minimum (standard context), 16 GB recommended (extended context)
- ~12 GB storage for models

## Installation

```bash
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt

ollama pull llama3.1:8b
ollama pull mistral:7b
ollama pull phi3:mini
```

## Usage

### Web UI

```bash
python -m streamlit run app.py
```

### CLI

```bash
# Stock data
python main.py "Outlook for Pfizer" --tickers PFE

# European tickers (use exchange suffix)
python main.py "SSAB revenue trend" --tickers SSAB-B.ST --news --macro

# Multiple tickers across exchanges
python main.py "Compare pharma" --tickers PFE NOVO-B.CO --search --news --macro

# All data sources
python main.py "Pfizer 2025 outlook" --tickers PFE --search --news --sec --macro

# Extended context (16k windows — use when 8-10 GB RAM is free)
python main.py "Pfizer 2025 outlook" --tickers PFE --news --sec --extended-ctx

# Analyze a document
python main.py "Summarize key financials" report.pdf
```

### Flags

| Flag | Description |
|------|-------------|
| `--tickers` | Live stock prices via Yahoo Finance (supports all exchanges: AAPL, ERIC-B.ST, SAP.DE) |
| `--search` | Web search (DuckDuckGo) |
| `--news` | RSS: Yahoo Finance, CNBC, MarketWatch, Motley Fool, Dagens Industri |
| `--sec` | SEC EDGAR 10-K / 10-Q filings (US tickers only, auto-skipped for non-US) |
| `--macro` | FRED, ECB, Riksbanken, World Bank macro indicators |
| `--extended-ctx` | 16k/8k context windows instead of 8k/4k |

All data sources are free and require no API keys.

### Macro data sources (`--macro`)

| Source | Coverage |
|--------|----------|
| FRED | US GDP, CPI, Fed Funds Rate, unemployment, S&P 500, inflation expectations |
| ECB | Eurozone HICP inflation, EUR/USD/SEK/GBP rates, refinancing & deposit facility rates |
| Riksbanken | Swedish repo rate, USD/SEK, EUR/SEK |
| World Bank | GDP growth, CPI inflation, unemployment for SE, US, DE, FR, GB, EU |

Macro data is cached locally for 24 hours to avoid redundant API calls.

### Exchange suffixes

| Exchange | Suffix | Example |
|----------|--------|---------|
| NYSE / NASDAQ | *(none)* | AAPL, PFE |
| Nasdaq Stockholm | .ST | ERIC-B.ST, SSAB-B.ST |
| Nasdaq Helsinki | .HE | NOKIA.HE |
| Nasdaq Copenhagen | .CO | NOVO-B.CO |
| XETRA Frankfurt | .DE | SAP.DE |
| London Stock Exchange | .L | HSBA.L |
| Euronext Paris | .PA | DSY.PA |

## Configuration

All settings in `config/config.py`:

- **Model assignments** — which Ollama model each agent uses
- **Context lengths** — standard (8k/4k) and extended (16k/8k) modes
- **GPU/CPU** — `NUM_GPU_LAYERS`, `NUM_THREADS`
- **User-Agent** — `DEFAULT_USER_AGENT` for all external API requests (update before use if you plan to query SEC EDGAR)

## Testing

```bash
python -m pytest tests/ -v
```

40 tests covering agents, JSON repair pipeline, cache, utilities, and end-to-end workflows. All mocked — no Ollama required.

Failed LLM responses are saved to `logs/` for post-mortem analysis.

## Disclaimer

This tool is for educational and research purposes only. It does not constitute financial advice. The authors are not responsible for any investment decisions made based on the output of this system. Always consult a qualified financial advisor before making investment decisions.

## License

MIT
