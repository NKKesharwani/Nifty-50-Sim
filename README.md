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
├── strategies.py      # All 5 strategies + backtest runner
├── web/
│   └── app.py         # Streamlit dashboard
└── data/
    ├── nifty50.csv    # Official NSE NIFTY 50 list
    └── trading.db     # SQLite database (gitignored)
```

## Quick Start

```bash
# 1. Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install yfinance streamlit pandas plotly

# 2. Ingest NIFTY 50 data
python nifty_sim/ingest.py

# 3. Run a backtest
python nifty_sim/strategies.py

# 4. Start the dashboard
streamlit run nifty_sim/web/app.py
```

## Dashboard URLs

- Local: `http://localhost:8501`
- Network: `http://192.168.219.7:8501`

## Environment

- Python 3.12
- yfinance, streamlit, pandas, plotly