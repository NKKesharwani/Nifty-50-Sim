# Nifty 50 Stock Monitor & Simulation Project

## Objective
Build a system to monitor NIFTY 50 stocks, simulate trading algorithms locally, track transactions in a local database, and incorporate news sentiment (global/local/domain-specific) for analysis.

## Roadmap
1.  **Project Setup & Data Ingestion:**
    *   Initialize project structure.
    *   Implement stock price fetching (e.g., Yahoo Finance API or similar).
    *   Setup database (SQLite) for tracking stocks, transactions, and simulation state.
2.  **Core Simulation Engine:**
    *   Implement basic buy/sell logic.
    *   Develop a runner for different algorithms.
    *   Track historical portfolio performance.
3.  **Sentiment/News Integration:**
    *   Incorporate news fetching for NIFTY 50 companies.
    *   Implement basic sentiment analysis (e.g., using a pre-trained model or lightweight NLP).
4.  **Web Dashboard:**
    *   Build a simple UI (using a lightweight framework like Streamlit or Flask/React) to visualize performance and transactions.

---
## Memory & Decisions
<!-- project: path:/home/openclaw/.openclaw/workspace -->
<!-- observed: 2026-11-14 | status: active -->
- Project Nifty-Sim initialized to track NIFTY 50, simulate trades, and integrate news sentiment.
- NIFTY 50 list fetched from official NSE archive CSV (ind_nifty50list.csv), stored as nifty_sim/data/nifty50.csv.
- yfinance uses `.NS` suffix for NSE tickers.
- News/sentiment part is DEPRIORITIZED by user on 2026-11-14: "leave the news part as of now, we'll only use algorithm as of now".
- V1 strategy (user-specified): daily close change >= +1% -> SELL 5 shares of that stock; change <= -1% -> BUY 5 shares. Fill at day close (sim assumption).
- User wants questions/clarifications posted to Discord #general (conversationRef conv_27b96ff91f054dffe73fb8401c9fa37d, channel 1558758662099570742) instead of in webchat when needed.
- Environment: project venv at nifty_sim/.venv (system pip is PEP 668 locked; never pip install without the venv).
