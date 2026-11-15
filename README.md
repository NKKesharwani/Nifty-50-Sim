# Nifty-Sim

Local NIFTY 50 stock market simulator with a Streamlit dashboard.

## Features

- **Data ingestion** — official NSE NIFTY 50 list + daily OHLCV via `yfinance` (1-year history)
- **SQLite storage** — stocks, prices, positions, transactions, portfolio equity curve
- **Multiple strategies** — percentage threshold, MA crossover, RSI mean reversion, Bollinger Bands, momentum
- **Streamlit web dashboard** — interactive backtest runner with equity curve, holdings, and transaction history

## Project Structure

```
nifty_sim/
├── config.py          # Configuration constants
├── database.py        # SQLite schema & helpers
├── ingest.py          # Fetch universe + prices from yfinance
├── sim.py             # Original percentage-threshold simulator
├── strategies.py      # 5 strategies + backtest runner
├── setup.py           # One-time database setup
├── web/
│   └── app.py         # Streamlit dashboard
└── data/
    ├── nifty50.csv    # Official NSE NIFTY 50 list
    └── trading.db     # SQLite database (gitignored)
```

## Quick Start (Linux / macOS / WSL)

```bash
# 1. Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install yfinance streamlit pandas plotly

# 2. One-time setup: create DB and ingest NIFTY 50 data
python nifty_sim/setup.py

# 3. Start the dashboard
streamlit run nifty_sim/web/app.py
```

## Quick Start (Windows)

```powershell
# 1. Install dependencies
python -m venv .venv
.venv\Scripts\activate
pip install yfinance streamlit pandas plotly

# 2. One-time setup: create DB and ingest NIFTY 50 data
python nifty_sim\setup.py

# 3. Start the dashboard
streamlit run nifty_sim\web\app.py
```

## Dashboard URLs

- Local: `http://localhost:8501`
- Network: `http://<your-local-ip>:8501`

## Environment

- Python 3.12
- yfinance, streamlit, pandas, plotly