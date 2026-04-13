"""
Configuration module for the Multi-Agent Procurement Management System.

All configuration values are loaded from environment variables with sensible
defaults. This prevents hardcoding and makes the system easy to configure
in different deployment environments.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present (useful for local development)
load_dotenv()

# ─── Base Paths ───────────────────────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
LOGS_DIR: Path = BASE_DIR / "logs"

# Ensure critical directories exist at import time
LOGS_DIR.mkdir(exist_ok=True)

# ─── Ollama / LLM Configuration ───────────────────────────────────────────────
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3:8b")
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))  # Low temp for determinism

# ─── Data File Paths ──────────────────────────────────────────────────────────
SUPPLIERS_FILE: Path = DATA_DIR / os.getenv("SUPPLIERS_FILE", "suppliers.json")
BUDGETS_FILE: Path = DATA_DIR / os.getenv("BUDGETS_FILE", "budgets.json")

# ─── Logging Configuration ────────────────────────────────────────────────────
LOG_FILE: Path = LOGS_DIR / os.getenv("LOG_FILE", "execution.log")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = (
    "%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s"
)
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# ─── Procurement Business Rules ───────────────────────────────────────────────
# Default fallback department if not identified by the LLM
DEFAULT_DEPARTMENT: str = os.getenv("DEFAULT_DEPARTMENT", "General")

# Supplier scoring weights (must sum to 1.0)
SUPPLIER_WEIGHT_RATING: float = float(os.getenv("SUPPLIER_WEIGHT_RATING", "0.40"))
SUPPLIER_WEIGHT_PRICE: float = float(os.getenv("SUPPLIER_WEIGHT_PRICE", "0.35"))
SUPPLIER_WEIGHT_STOCK: float = float(os.getenv("SUPPLIER_WEIGHT_STOCK", "0.15"))
SUPPLIER_WEIGHT_LEAD_TIME: float = float(os.getenv("SUPPLIER_WEIGHT_LEAD_TIME", "0.10"))

# Maximum number of supplier candidates to pass to the LLM for final selection
MAX_SUPPLIER_CANDIDATES: int = int(os.getenv("MAX_SUPPLIER_CANDIDATES", "3"))

# PO number prefix
PO_PREFIX: str = os.getenv("PO_PREFIX", "PO")

# ─── Validation ───────────────────────────────────────────────────────────────
_weight_sum = round(
    SUPPLIER_WEIGHT_RATING
    + SUPPLIER_WEIGHT_PRICE
    + SUPPLIER_WEIGHT_STOCK
    + SUPPLIER_WEIGHT_LEAD_TIME,
    2,
)
assert _weight_sum == 1.0, (
    f"Supplier scoring weights must sum to 1.0, got {_weight_sum}"
)
