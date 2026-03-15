# Model assignments
ORCHESTRATOR_MODEL = "llama3.1:8b"
DATA_EXTRACTOR_MODEL = "phi3:mini"
TREND_ANALYZER_MODEL = "mistral:7b"
SENTIMENT_ANALYZER_MODEL = "mistral:7b"
VALIDATOR_MODEL = "phi3:mini"

# Ollama settings
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT = 300  # seconds

# Model keep_alive: how long Ollama holds a model in RAM after a call.
# The orchestrator (llama3.1:8b, ~4.7 GB) runs plan() then synthesize() — keeping
# it warm between calls is only useful if those calls are close together (<5 min).
# For analyses that run 30–90 min, it will be evicted anyway.
#
# specialist agents (mistral:7b ~4.4 GB, phi3:mini ~2.2 GB) each run once.
# Setting their keep_alive to 0 frees RAM immediately after each call.
#
# Risk: if orchestrator + any specialist are in RAM simultaneously = up to 9 GB
# of model weights + ~5 GB OS/apps = would exceed 16 GB on this machine.
# Ollama evicts LRU models automatically, but short keep_alive avoids the risk.
KEEP_ALIVE_ORCHESTRATOR = "5m"   # stays warm between plan() and synthesize()
KEEP_ALIVE_SPECIALIST   = "0"    # free RAM immediately after each specialist call

# System settings
LOG_LEVEL = "INFO"
CACHE_MODELS = True
SEQUENTIAL_EXECUTION = True  # Required for 16GB RAM — one model at a time

# GPU acceleration (Ollama handles GPU automatically if available)
# Set NUM_GPU_LAYERS = 0 to force CPU-only inference
# Set NUM_GPU_LAYERS = -1 to offload all layers to GPU (fastest, requires VRAM)
# Set NUM_GPU_LAYERS = N to offload N layers (partial GPU, useful for limited VRAM)
# Recommended: -1 if you have a dedicated GPU with 8GB+ VRAM, 0 for CPU-only
NUM_GPU_LAYERS = 0  # Default: CPU inference

# CPU thread count for inference (passed per-request, no Ollama restart needed).
# Benchmark on i7-1165G7 (4 physical / 8 logical cores):
#   4 threads: ~4.64 t/s (llama3.1), ~4.88 t/s (mistral), ~8.88 t/s (phi3)
#   6 threads: ~4.63 t/s (llama3.1), ~4.98 t/s (mistral), ~9.12 t/s (phi3)  <-- best
#   8 threads: ~3.90 t/s (llama3.1), ~4.34 t/s (mistral), ~7.86 t/s (phi3)  <-- worst
# Hyperthreading hurts LLM inference due to cache contention. Use physical+2 max.
NUM_THREADS = 6

# Context length per agent call (reduce if running out of memory)
# STANDARD: safe for 8 GB free RAM with browser + VSCode open
CONTEXT_LENGTH = {
    "orchestrator": 8192,
    "data_extractor": 4096,
    "trend_analyzer": 8192,
    "sentiment_analyzer": 8192,
    "validator": 4096,
}

# EXTENDED: up to ~6.5 GB peak (mistral:7b) — use when 8-10 GB is available
# Increases KV cache ~2x; improves retention of long SEC filings, multi-doc analyses
CONTEXT_LENGTH_EXTENDED = {
    "orchestrator": 16384,
    "data_extractor": 8192,
    "trend_analyzer": 16384,
    "sentiment_analyzer": 16384,
    "validator": 8192,
}

# Web search settings
WEB_SEARCH_MAX_RESULTS = 5      # Number of search results to fetch
WEB_SEARCH_MAX_CHARS = 2000     # Max characters to extract per page

# Shared User-Agent for all external API requests (FRED, ECB, Riksbanken, World Bank, SEC).
# SEC EDGAR requires: "Company Name contact@domain.com" — update before use.
DEFAULT_USER_AGENT = "FinancialAnalysisSystem/1.0 contact@example.com"

# SEC EDGAR settings (no API key required)
SEC_USER_AGENT = DEFAULT_USER_AGENT
SEC_MAX_RESULTS = 3             # Number of filings to fetch
SEC_MAX_CHARS = 4000            # Max characters to extract per filing

# RSS news feeds (no API key required)
RSS_MAX_ITEMS = 5               # Articles per feed
RSS_MAX_CHARS = 800             # Max characters per article
RSS_FEEDS = {
    # US / Global
    "cnbc_finance":    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "marketwatch_top": "https://feeds.marketwatch.com/marketwatch/topstories",
    "motley_fool":     "https://www.fool.com/feeds/index.aspx",
    # Nordic / European
    "di_se":           "https://digital.di.se/rss",
}

# FRED macroeconomic data (no API key — uses public CSV endpoint)
FRED_TIMEOUT = 15   # seconds per series request
FRED_RETRIES = 1    # single retry on timeout (FRED timeouts waste ~90s per failed series × 2 retries)

FRED_SERIES = {
    "GDP":      "US GDP (Quarterly, Billions USD)",
    "CPIAUCSL": "US CPI Inflation (Monthly)",
    "DFF":      "Federal Funds Rate (%)",
    "UNRATE":   "US Unemployment Rate (%)",
    "T10YIE":   "10-Year Inflation Expectations (%)",
    "SP500":    "S&P 500 Index",
}

# ECB (European Central Bank) — SDMX-JSON API, no key required
ECB_TIMEOUT = 20
ECB_RETRIES = 2
ECB_BASE_URL = "https://data-api.ecb.europa.eu/service/data"

# flowRef/seriesKey -> human-readable label
ECB_SERIES = {
    "ICP/M.U2.N.000000.4.ANR":   "Eurozone HICP Inflation (Monthly, YoY %)",
    "EXR/D.USD.EUR.SP00.A":      "EUR/USD Exchange Rate (Daily)",
    "EXR/D.SEK.EUR.SP00.A":      "EUR/SEK Exchange Rate (Daily)",
    "EXR/D.GBP.EUR.SP00.A":      "EUR/GBP Exchange Rate (Daily)",
    "FM/B.U2.EUR.4F.KR.MRR_FR.LEV":   "ECB Main Refinancing Rate (%)",
    "FM/B.U2.EUR.4F.KR.DFR.LEV":      "ECB Deposit Facility Rate (%)",
}

# Riksbanken (Swedish central bank) — SWEA REST API, no key required
RIKSBANK_TIMEOUT = 20
RIKSBANK_RETRIES = 2
RIKSBANK_BASE_URL = "https://api.riksbank.se/swea/v1"

# Series ID -> human-readable label
RIKSBANK_SERIES = {
    "SECBREPOEFF": "Swedish Repo Rate / Policy Rate (%)",
    "SEKUSDPMI":  "USD/SEK Exchange Rate (mid)",
    "SEKEURPMI":  "EUR/SEK Exchange Rate (mid)",
}

# World Bank Open Data — JSON API, no key required
WORLDBANK_TIMEOUT = 20
WORLDBANK_RETRIES = 2
WORLDBANK_BASE_URL = "https://api.worldbank.org/v2"

# Countries to include (ISO2 codes; EUU = European Union aggregate)
WORLDBANK_COUNTRIES = ["SE", "US", "DE", "FR", "GB", "EUU"]

# Indicator code -> human-readable label
WORLDBANK_INDICATORS = {
    "NY.GDP.MKTP.KD.ZG": "GDP Growth (Annual %)",
    "FP.CPI.TOTL.ZG":    "CPI Inflation (Annual %)",
    "SL.UEM.TOTL.ZS":    "Unemployment Rate (%)",
}
