"""Application constants and default values."""

# API Defaults
DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_MODEL = "meta/llama-3.1-70b-instruct"

# ChromaDB Defaults
DEFAULT_CHROMA_HOST = "localhost"
DEFAULT_CHROMA_PORT = 8000

# Server Defaults
DEFAULT_API_HOST = "0.0.0.0"
DEFAULT_API_PORT = 8000
DEFAULT_KEEPALIVE_TIMEOUT = 120

# Logging Defaults
DEFAULT_LOG_LEVEL = "INFO"

# LLM Defaults
DEFAULT_LLM_TEMPERATURE = 0.1
DEFAULT_LLM_MAX_TOKENS = 4096

# Search Defaults
DEFAULT_SEARCH_MAX_RESULTS = 10
DEFAULT_SEARCH_RETRIES = 3

# Memory Defaults
MEMORY_COLLECTION_NAME = "competitive_research"
DEFAULT_MEMORY_RESULTS = 5
DEFAULT_MEMORY_RETRIES = 3

# Generic company name blacklist
GENERIC_COMPANY_NAMES = frozenset({
    "company",
    "business",
    "startup",
    "enterprise",
    "corporation",
    "firm",
    "organization",
    "organisation",
    "corp",
    "inc",
    "llc",
    "ltd",
})
