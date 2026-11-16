"""Nifty-Sim configuration."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "trading.db"
NIFTY50_CSV = DATA_DIR / "nifty50.csv"

# Simulation defaults (overridable in UI before first run)
DEFAULT_INITIAL_CAPITAL = 10_000_000.0  # 1 crore INR
STRATEGY = "pct_threshold_1"
THRESHOLD_PCT = 1.0        # trigger level in %
TRADE_QUANTITY = 5         # shares per signal
LOOKBACK_PERIOD = "5y"     # history to pull on first ingest
CURRENCY = "INR"
EXCHANGE_SUFFIX = ".NS"    # yfinance suffix for NSE
