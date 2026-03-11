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
- ~8 GB storage for models

## Installation

```bash
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt

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

# Analyze a document
python main.py "Summarize key financials" report.pdf
```

### Data source flags

| Flag | Source |
|------|--------|
| `--tickers` | Live stock prices via Yahoo Finance |
| `--search` | Web search (DuckDuckGo) |
| `--news` | RSS: Yahoo Finance, Reuters, MarketWatch, Motley Fool |
| `--sec` | SEC EDGAR 10-K / 10-Q filings |
| `--macro` | FRED: GDP, CPI, Fed Funds Rate, unemployment, S&P 500 |

All sources are free and require no API keys.

## Testing

```bash
python -m pytest tests/ -v
```

## License

MIT
