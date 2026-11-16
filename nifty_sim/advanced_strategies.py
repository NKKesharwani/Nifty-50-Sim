"""Advanced and Combined Trading Algorithms for Nifty-Sim.

This module implements hybrid/combined strategies:
1. RSI + Bollinger Mean Reversion (Combines RSI oversold/overbought with Bollinger band touch confirmation)
2. MACD + EMA Trend Following (Combines MACD histogram direction with fast/slow EMA trend filter)
3. Volatility-Adjusted Momentum (Combines 20-day ROC momentum with ATR volatility filter to avoid choppy stocks)
"""
from __future__ import annotations

import logging
import pandas as pd
import numpy as np

from database import db, record_transaction, set_cash, snapshot_portfolio
from strategies import reset_book, load_pivot

log = logging.getLogger("advanced_strategies")


# ------------------------------------------------------------------ #
# 1. RSI + Bollinger Bands Mean Reversion (Hybrid)
# ------------------------------------------------------------------ #
def run_rsi_bollinger_hybrid(qty=10, initial_capital=10_000_000.0):
    """BUY when price touches lower Bollinger Band AND RSI < 35 (strong oversold).
    SELL when price touches upper Bollinger Band AND RSI > 65 (strong overbought).
    """
    reset_book(initial_capital)
    pivot = load_pivot()
    if pivot.empty: return 0

    # Indicators
    sma = pivot.rolling(20).mean()
    std = pivot.rolling(20).std()
    upper = sma + (std * 2)
    lower = sma - (std * 2)

    delta = pivot.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    cash = initial_capital
    holdings = {}
    trades = 0

    dates = pivot.index[25:]
    for date in dates:
        row = pivot.loc[date].dropna()
        close_map = row.to_dict()
        for symbol, price in close_map.items():
            l_band = lower.loc[date, symbol]
            u_band = upper.loc[date, symbol]
            r_val = rsi.loc[date, symbol]
            if pd.isna(l_band) or pd.isna(u_band) or pd.isna(r_val):
                continue

            held = holdings.get(symbol, 0.0)
            # Buy signal: Price at or below lower band AND RSI < 35
            if price <= l_band and r_val < 35:
                cost = price * qty
                if cash >= cost:
                    record_transaction(date, symbol, "BUY", price, qty, f"RSI({r_val:.1f})+BB Lower")
                    cash -= cost
                    holdings[symbol] = held + qty
                    trades += 1
            # Sell signal: Price at or above upper band AND RSI > 65
            elif price >= u_band and r_val > 65:
                if held >= qty:
                    record_transaction(date, symbol, "SELL", price, qty, f"RSI({r_val:.1f})+BB Upper")
                    cash += price * qty
                    holdings[symbol] = held - qty
                    trades += 1

        set_cash(cash)
        snapshot_portfolio(date, close_map)
    return trades


# ------------------------------------------------------------------ #
# 2. MACD + EMA Trend Following (Hybrid)
# ------------------------------------------------------------------ #
def run_macd_ema_trend(qty=10, initial_capital=10_000_000.0):
    """BUY when MACD line crosses above Signal line AND price > 50 EMA (bullish trend).
    SELL when MACD crosses below Signal line OR price < 50 EMA.
    """
    reset_book(initial_capital)
    pivot = load_pivot()
    if pivot.empty: return 0

    ema12 = pivot.ewm(span=12, adjust=False).mean()
    ema26 = pivot.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    ema50 = pivot.ewm(span=50, adjust=False).mean()

    cash = initial_capital
    holdings = {}
    trades = 0

    dates = pivot.index[50:]
    for i in range(1, len(dates)):
        date = dates[i]
        prev_date = dates[i-1]
        row = pivot.loc[date].dropna()
        close_map = row.to_dict()

        for symbol, price in close_map.items():
            m_curr = macd_line.loc[date, symbol]
            s_curr = signal_line.loc[date, symbol]
            m_prev = macd_line.loc[prev_date, symbol]
            s_prev = signal_line.loc[prev_date, symbol]
            e50 = ema50.loc[date, symbol]

            if pd.isna(m_curr) or pd.isna(s_curr) or pd.isna(m_prev) or pd.isna(s_prev) or pd.isna(e50):
                continue

            held = holdings.get(symbol, 0.0)
            # Bullish crossover + above 50 EMA
            if m_prev <= s_prev and m_curr > s_curr and price > e50:
                cost = price * qty
                if cash >= cost:
                    record_transaction(date, symbol, "BUY", price, qty, "MACD Bullish Cross + EMA50")
                    cash -= cost
                    holdings[symbol] = held + qty
                    trades += 1
            # Bearish crossover or price drops below 50 EMA
            elif (m_prev >= s_prev and m_curr < s_curr) or price < e50:
                if held >= qty:
                    record_transaction(date, symbol, "SELL", price, qty, "MACD Bearish Cross / EMA50 breach")
                    cash += price * qty
                    holdings[symbol] = held - qty
                    trades += 1

        set_cash(cash)
        snapshot_portfolio(date, close_map)
    return trades


# ------------------------------------------------------------------ #
# 3. Volatility-Filtered Momentum (ROC + ATR Filter)
# ------------------------------------------------------------------ #
def run_volatility_momentum(qty=10, initial_capital=10_000_000.0):
    """Rank Nifty 50 stocks by 20-day Rate of Change (ROC), but filter out
    stocks with excessively high volatility (ATR / Price ratio) to avoid whipsaws.
    """
    reset_book(initial_capital)
    pivot = load_pivot()
    if pivot.empty: return 0

    roc = pivot.pct_change(20) * 100.0
    # Approximate ATR via rolling std of returns over 14 days
    volatility = pivot.pct_change().rolling(14).std() * 100.0

    cash = initial_capital
    holdings = {}
    trades = 0

    dates = pivot.index[30:]
    for date in dates:
        row = pivot.loc[date].dropna()
        close_map = row.to_dict()
        r_row = roc.loc[date].dropna()
        v_row = volatility.loc[date].dropna()
        if r_row.empty: continue

        # Filter out top 20% most volatile stocks (noise filter)
        valid_stocks = [s for s in r_row.index if s in v_row and v_row[s] < v_row.quantile(0.8)]
        if not valid_stocks: continue

        filtered_roc = r_row.loc[valid_stocks]
        top3 = filtered_roc.nlargest(3).index.tolist()
        bot3 = filtered_roc.nsmallest(3).index.tolist()

        for symbol in top3:
            price = close_map.get(symbol)
            if not price: continue
            held = holdings.get(symbol, 0.0)
            cost = price * qty
            if cash >= cost and held == 0:
                record_transaction(date, symbol, "BUY", price, qty, "Vol-Filtered Top Momentum")
                cash -= cost
                holdings[symbol] = held + qty
                trades += 1

        for symbol in bot3:
            price = close_map.get(symbol)
            if not price: continue
            held = holdings.get(symbol, 0.0)
            if held >= qty:
                record_transaction(date, symbol, "SELL", price, qty, "Vol-Filtered Bottom Momentum")
                cash += price * qty
                holdings[symbol] = held - qty
                trades += 1

        set_cash(cash)
        snapshot_portfolio(date, close_map)
    return trades


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    import database
    database.init_db()

    advanced_strategies = [
        ("RSI + Bollinger Hybrid", run_rsi_bollinger_hybrid),
        ("MACD + EMA Trend", run_macd_ema_trend),
        ("Volatility Momentum", run_volatility_momentum),
    ]

    print(f"{'Strategy':<30} | {'Trades':<8} | {'Final Value (Rs)':<18} | {'P&L (%)':<10}")
    print("-" * 75)
    for name, fn in advanced_strategies:
        trades = fn()
        with db() as conn:
            last = conn.execute("SELECT total_value FROM portfolio_daily ORDER BY date DESC LIMIT 1").fetchone()
            val = last["total_value"] if last else 10_000_000.0
        pnl_pct = ((val / 10_000_000.0) - 1.0) * 100.0
        print(f"{name:<30} | {trades:<8} | {val:18,.2f} | {pnl_pct:+6.2f}%")
