# Multi-Agent Financial Analysis Tool

A local, privacy-preserving system for financial analysis using multiple specialized language models coordinated by an orchestrator agent. All inference runs on your machine via [Ollama](https://ollama.ai).

## Features

- **Five specialized agents** — orchestrator, data extractor, trend analyzer, sentiment analyzer, validator
- **Multiple data sources** — documents, live stock data, web search, news feeds, SEC filings, macroeconomic indicators
- **Web UI** — Streamlit interface for interactive use
- **CLI** — scriptable from the command line
- **Privacy-first** — no data leaves your machine; LLM inference is entirely local

## Requirements

- Python 3.10+
- [Ollama](https://ollama.ai) installed and running
- 16 GB RAM
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

# Web search + news + SEC filings + macro data
python main.py "Pfizer 2025 outlook" --tickers PFE --search --news --sec --macro

# Extended context (16k windows — use when 8-10 GB RAM is free)
python main.py "Pfizer 2025 outlook" --tickers PFE --news --sec --extended-ctx

# Analyze a document
python main.py "Summarize key financials" report.pdf
```

### Flags

| Flag | Description |
|------|-------------|
| `--tickers` | Live stock prices via Yahoo Finance |
| `--search` | Web search (DuckDuckGo) |
| `--news` | RSS: Yahoo Finance, Reuters, MarketWatch, Motley Fool |
| `--sec` | SEC EDGAR 10-K / 10-Q filings |
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

## Testing

```bash
python -m pytest tests/ -v
```

## License

MIT
