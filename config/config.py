# Model assignments
ORCHESTRATOR_MODEL = "mistral:7b"
DATA_EXTRACTOR_MODEL = "phi3:mini"
TREND_ANALYZER_MODEL = "mistral:7b"
SENTIMENT_ANALYZER_MODEL = "mistral:7b"
VALIDATOR_MODEL = "phi3:mini"

# Ollama settings
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT = 300  # seconds

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

# Context length per agent call (reduce if running out of memory)
CONTEXT_LENGTH = {
    "orchestrator": 8192,
    "data_extractor": 4096,
    "trend_analyzer": 8192,
    "sentiment_analyzer": 8192,
    "validator": 4096,
}

# Web search settings
WEB_SEARCH_MAX_RESULTS = 5      # Number of search results to fetch
WEB_SEARCH_MAX_CHARS = 2000     # Max characters to extract per page

# SEC EDGAR settings (no API key required)
# EDGAR requires a descriptive User-Agent: https://www.sec.gov/os/accessing-edgar-data
SEC_USER_AGENT = "FinancialAnalysisSystem research@localhost"
SEC_MAX_RESULTS = 3             # Number of filings to fetch
SEC_MAX_CHARS = 4000            # Max characters to extract per filing

# RSS news feeds (no API key required)
RSS_MAX_ITEMS = 5               # Articles per feed
RSS_MAX_CHARS = 800             # Max characters per article
RSS_FEEDS = {
    "reuters_business": "https://feeds.reuters.com/reuters/businessNews",
    "marketwatch_top":  "https://feeds.marketwatch.com/marketwatch/topstories",
    "motley_fool":      "https://www.fool.com/feeds/index.aspx",
}

# FRED macroeconomic data (no API key — uses public CSV endpoint)
FRED_SERIES = {
    "GDP":      "US GDP (Quarterly, Billions USD)",
    "CPIAUCSL": "US CPI Inflation (Monthly)",
    "DFF":      "Federal Funds Rate (%)",
    "UNRATE":   "US Unemployment Rate (%)",
    "T10YIE":   "10-Year Inflation Expectations (%)",
    "SP500":    "S&P 500 Index",
}
