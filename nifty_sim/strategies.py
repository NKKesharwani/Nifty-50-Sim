"""Strategy runner and backtester for multiple algorithms."""
from __future__ import annotations

import logging
import pandas as pd
import numpy as np
import sqlite3

from database import db, meta_get, set_cash, record_transaction, snapshot_portfolio

log = logging.getLogger("strategies")

def reset_book(initial_capital: float = 10_000_000.0):
    with db() as conn:
        conn.execute("DELETE FROM positions")
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM portfolio_daily")
    set_cash(initial_capital)
    from database import meta_set
    meta_set("initial_capital", f"{initial_capital:.6f}")

def load_pivot() -> pd.DataFrame:
    with db() as conn:
        rows = conn.execute("SELECT symbol, date, close FROM prices ORDER BY symbol, date").fetchall()
    df = pd.DataFrame(rows, columns=["symbol", "date", "close"])
    if df.empty:
        return df
    return df.pivot(index="date", columns="symbol", values="close")

# ------------------------------------------------------------------ #
# 1. Pct Threshold V1 (Current)
# ------------------------------------------------------------------ #
def run_pct_threshold(threshold=1.0, qty=5, initial_capital=10_000_000.0):
    reset_book(initial_capital)
    pivot = load_pivot()
    if pivot.empty: return 0
    pct = pivot.pct_change() * 100.0
    cash = initial_capital
    holdings = {}
    trades = 0

    for date, row in pivot.iterrows():
        close_map = row.dropna().to_dict()
        chg_row = pct.loc[date]
        for symbol, price in close_map.items():
            chg = chg_row.get(symbol)
            if chg is None or pd.isna(chg): continue
            if chg >= threshold:
                held = holdings.get(symbol, 0.0)
                if held >= qty:
                    record_transaction(date, symbol, "SELL", price, qty, f"up {chg:.2f}%")
                    cash += price * qty
                    holdings[symbol] = held - qty
                    trades += 1
            elif chg <= -threshold:
                cost = price * qty
                if cash >= cost:
                    record_transaction(date, symbol, "BUY", price, qty, f"down {chg:.2f}%")
                    cash -= cost
                    holdings[symbol] = holdings.get(symbol, 0.0) + qty
                    trades += 1
        set_cash(cash)
        snapshot_portfolio(date, close_map)
    return trades

# ------------------------------------------------------------------ #
# 2. Moving Average Crossover (SMA 20 vs SMA 50)
# ------------------------------------------------------------------ #
def run_ma_crossover(qty=10, initial_capital=10_000_000.0):
    reset_book(initial_capital)
    pivot = load_pivot()
    if pivot.empty: return 0
    sma20 = pivot.rolling(20).mean()
    sma50 = pivot.rolling(50).mean()
    
    cash = initial_capital
    holdings = {}
    trades = 0

    # start from day 50
    dates = pivot.index[50:]
    for date in dates:
        row = pivot.loc[date].dropna()
        close_map = row.to_dict()
        for symbol, price in close_map.items():
            s20 = sma20.loc[date, symbol]
            s50 = sma50.loc[date, symbol]
            prev_s20 = sma20.shift(1).loc[date, symbol]
            prev_s50 = sma50.shift(1).loc[date, symbol]
            if pd.isna(s20) or pd.isna(s50) or pd.isna(prev_s20) or pd.isna(prev_s50):
                continue
            
            held = holdings.get(symbol, 0.0)
            # Golden cross (Buy)
            if prev_s20 <= prev_s50 and s20 > s50:
                cost = price * qty
                if cash >= cost:
                    record_transaction(date, symbol, "BUY", price, qty, "SMA 20/50 Golden Cross")
                    cash -= cost
                    holdings[symbol] = held + qty
                    trades += 1
            # Death cross (Sell)
            elif prev_s20 >= prev_s50 and s20 < s50:
                if held >= qty:
                    record_transaction(date, symbol, "SELL", price, qty, "SMA 20/50 Death Cross")
                    cash += price * qty
                    holdings[symbol] = held - qty
                    trades += 1

        set_cash(cash)
        snapshot_portfolio(date, close_map)
    return trades

# ------------------------------------------------------------------ #
# 3. RSI Mean Reversion (Period 14, Oversold < 30, Overbought > 70)
# ------------------------------------------------------------------ #
def run_rsi(qty=10, initial_capital=10_000_000.0):
    reset_book(initial_capital)
    pivot = load_pivot()
    if pivot.empty: return 0

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

    dates = pivot.index[15:]
    for date in dates:
        row = pivot.loc[date].dropna()
        close_map = row.to_dict()
        for symbol, price in close_map.items():
            r = rsi.loc[date, symbol]
            if pd.isna(r): continue
            held = holdings.get(symbol, 0.0)
            if r < 30:  # Oversold -> BUY
                cost = price * qty
                if cash >= cost:
                    record_transaction(date, symbol, "BUY", price, qty, f"RSI {r:.1f} (<30)")
                    cash -= cost
                    holdings[symbol] = held + qty
                    trades += 1
            elif r > 70:  # Overbought -> SELL
                if held >= qty:
                    record_transaction(date, symbol, "SELL", price, qty, f"RSI {r:.1f} (>70)")
                    cash += price * qty
                    holdings[symbol] = held - qty
                    trades += 1

        set_cash(cash)
        snapshot_portfolio(date, close_map)
    return trades

# ------------------------------------------------------------------ #
# 4. Bollinger Bands Breakout (20 SMA, 2 StdDev)
# ------------------------------------------------------------------ #
def run_bollinger(qty=10, initial_capital=10_000_000.0):
    reset_book(initial_capital)
    pivot = load_pivot()
    if pivot.empty: return 0

    sma = pivot.rolling(20).mean()
    std = pivot.rolling(20).std()
    upper = sma + (std * 2)
    lower = sma - (std * 2)

    cash = initial_capital
    holdings = {}
    trades = 0

    dates = pivot.index[20:]
    for date in dates:
        row = pivot.loc[date].dropna()
        close_map = row.to_dict()
        for symbol, price in close_map.items():
            l_band = lower.loc[date, symbol]
            u_band = upper.loc[date, symbol]
            if pd.isna(l_band) or pd.isna(u_band): continue
            held = holdings.get(symbol, 0.0)
            if price <= l_band:  # Touch/break lower band -> BUY
                cost = price * qty
                if cash >= cost:
                    record_transaction(date, symbol, "BUY", price, qty, "Bollinger Lower Touch")
                    cash -= cost
                    holdings[symbol] = held + qty
                    trades += 1
            elif price >= u_band:  # Touch upper band -> SELL
                if held >= qty:
                    record_transaction(date, symbol, "SELL", price, qty, "Bollinger Upper Touch")
                    cash += price * qty
                    holdings[symbol] = held - qty
                    trades += 1

        set_cash(cash)
        snapshot_portfolio(date, close_map)
    return trades

# ------------------------------------------------------------------ #
# 5. Momentum / Rate of Change (20-day ROC)
# ------------------------------------------------------------------ #
def run_momentum(qty=10, initial_capital=10_000_000.0):
    reset_book(initial_capital)
    pivot = load_pivot()
    if pivot.empty: return 0

    roc = pivot.pct_change(20) * 100.0
    cash = initial_capital
    holdings = {}
    trades = 0

    dates = pivot.index[20:]
    for date in dates:
        row = pivot.loc[date].dropna()
        close_map = row.to_dict()
        r_row = roc.loc[date].dropna()
        if r_row.empty: continue
        
        # Top 3 momentum stocks -> BUY if not held
        top3 = r_row.nlargest(3).index.tolist()
        # Bottom 3 momentum stocks -> SELL if held
        bot3 = r_row.nsmallest(3).index.tolist()

        for symbol in top3:
            price = close_map.get(symbol)
            if not price: continue
            held = holdings.get(symbol, 0.0)
            cost = price * qty
            if cash >= cost and held == 0:
                record_transaction(date, symbol, "BUY", price, qty, f"Top Momentum ROC")
                cash -= cost
                holdings[symbol] = held + qty
                trades += 1

        for symbol in bot3:
            price = close_map.get(symbol)
            if not price: continue
            held = holdings.get(symbol, 0.0)
            if held >= qty:
                record_transaction(date, symbol, "SELL", price, qty, f"Bottom Momentum ROC")
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

    strategies = [
        ("Pct Threshold (1%)", lambda: run_pct_threshold()),
        ("MA Crossover (20/50)", lambda: run_ma_crossover()),
        ("RSI Mean Reversion (14)", lambda: run_rsi()),
        ("Bollinger Bands (20,2)", lambda: run_bollinger()),
        ("Momentum (20-day ROC)", lambda: run_momentum()),
    ]

    print(f"{'Strategy':<30} | {'Trades':<8} | {'Final Value (Rs)':<18} | {'P&L (%)':<10}")
    print("-" * 75)
    for name, fn in strategies:
        trades = fn()
        with db() as conn:
            last = conn.execute("SELECT total_value FROM portfolio_daily ORDER BY date DESC LIMIT 1").fetchone()
            val = last["total_value"] if last else 10_000_000.0
        pnl_pct = ((val / 10_000_000.0) - 1.0) * 100.0
        print(f"{name:<30} | {trades:<8} | {val:18,.2f} | {pnl_pct:+6.2f}%")
