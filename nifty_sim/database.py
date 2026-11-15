"""SQLite storage layer for Nifty-Sim.

Schema:
  stocks           - NIFTY 50 universe
  prices           - daily OHLCV per stock
  positions        - current simulated holdings (cash-equivalent book)
  transactions     - full audit log of every buy/sell
  portfolio_daily  - equity curve (cash + holdings value) per day
  sim_meta         - key/value: initial capital, last processed date, etc.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS stocks (
    symbol   TEXT PRIMARY KEY,
    name     TEXT,
    industry TEXT
);

CREATE TABLE IF NOT EXISTS prices (
    symbol  TEXT NOT NULL,
    date    TEXT NOT NULL,   -- ISO date YYYY-MM-DD
    open    REAL,
    high    REAL,
    low     REAL,
    close   REAL,
    volume  REAL,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);

CREATE TABLE IF NOT EXISTS positions (
    symbol    TEXT PRIMARY KEY,
    quantity  REAL NOT NULL DEFAULT 0,
    avg_cost  REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS transactions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,      -- when the sim recorded it
    date      TEXT NOT NULL,      -- market date of the fill
    symbol    TEXT NOT NULL,
    side      TEXT NOT NULL,      -- BUY | SELL
    price     REAL NOT NULL,
    quantity  REAL NOT NULL,
    reason    TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);

CREATE TABLE IF NOT EXISTS portfolio_daily (
    date           TEXT PRIMARY KEY,
    cash           REAL NOT NULL,
    holdings_value REAL NOT NULL,
    total_value    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sim_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)


def upsert_stocks(rows: Iterable[dict[str, Any]]) -> int:
    n = 0
    with db() as conn:
        for r in rows:
            conn.execute(
                "INSERT INTO stocks(symbol, name, industry) VALUES(?,?,?) "
                "ON CONFLICT(symbol) DO UPDATE SET name=excluded.name, "
                "industry=excluded.industry",
                (r["symbol"], r.get("name"), r.get("industry")),
            )
            n += 1
    return n


def upsert_prices(df: pd.DataFrame) -> int:
    """df must have columns: symbol, date, open, high, low, close, volume."""
    if df.empty:
        return 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = df.assign(**{"_n": now})
    with db() as conn:
        conn.executemany(
            "INSERT INTO prices(symbol,date,open,high,low,close,volume) "
            "VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(symbol,date) DO UPDATE SET "
            "open=excluded.open, high=excluded.high, low=excluded.low, "
            "close=excluded.close, volume=excluded.volume",
            [
                (r.symbol, r.date, r.open, r.high, r.low, r.close, r.volume)
                for r in rows.itertuples()
            ],
        )
        return len(rows)


def meta_get(key: str, default: str | None = None) -> str | None:
    with db() as conn:
        row = conn.execute("SELECT value FROM sim_meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def meta_set(key: str, value: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO sim_meta(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )


def last_processed_date() -> str | None:
    return meta_get("last_processed_date")


def record_transaction(
    date: str, symbol: str, side: str, price: float, quantity: float, reason: str
) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as conn:
        conn.execute(
            "INSERT INTO transactions(ts,date,symbol,side,price,quantity,reason) "
            "VALUES(?,?,?,?,?,?,?)",
            (ts, date, symbol, side, price, quantity, reason),
        )
        # update position
        row = conn.execute(
            "SELECT quantity, avg_cost FROM positions WHERE symbol=?", (symbol,)
        ).fetchone()
        qty = row["quantity"] if row else 0.0
        avg = row["avg_cost"] if row else 0.0
        if side == "BUY":
            new_qty = qty + quantity
            avg = (avg * qty + price * quantity) / new_qty if new_qty else 0.0
        else:  # SELL
            new_qty = qty - quantity
            avg = avg  # avg cost unchanged on sell
        conn.execute(
            "INSERT INTO positions(symbol,quantity,avg_cost) VALUES(?,?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET quantity=excluded.quantity, "
            "avg_cost=excluded.avg_cost",
            (symbol, new_qty, avg),
        )


def snapshot_portfolio(date: str, prices: dict[str, float]) -> float:
    """Record cash + holdings value for a date; returns total value."""
    with db() as conn:
        cash = float(meta_get("cash", "0"))
        pos = conn.execute("SELECT symbol, quantity FROM positions WHERE quantity > 0").fetchall()
        holdings = 0.0
        for p in pos:
            holdings += p["quantity"] * prices.get(p["symbol"], 0.0)
        total = cash + holdings
        conn.execute(
            "INSERT INTO portfolio_daily(date,cash,holdings_value,total_value) "
            "VALUES(?,?,?,?) ON CONFLICT(date) DO UPDATE SET "
            "cash=excluded.cash, holdings_value=excluded.holdings_value, "
            "total_value=excluded.total_value",
            (date, cash, holdings, total),
        )
    return total


def set_cash(cash: float) -> None:
    meta_set("cash", f"{cash:.6f}")
