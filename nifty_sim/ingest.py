"""Fetch NIFTY 50 universe and daily OHLCV via yfinance."""
from __future__ import annotations

import logging
import time

import pandas as pd
import yfinance as yf

from config import EXCHANGE_SUFFIX, NIFTY50_CSV
from database import upsert_prices, upsert_stocks

log = logging.getLogger("ingest")


def load_universe() -> pd.DataFrame:
    """Read the official NSE NIFTY 50 CSV into a tidy frame."""
    df = pd.read_csv(NIFTY50_CSV)
    df = df.rename(
        columns={"Company Name": "name", "Industry": "industry", "Symbol": "symbol"}
    )
    df["yfin_symbol"] = df["symbol"].str.strip() + EXCHANGE_SUFFIX
    return df


def ingest_prices(universe: pd.DataFrame | None = None, period: str = "1y") -> pd.DataFrame:
    """Download daily history for all symbols and store in SQLite.

    Returns the combined DataFrame of newly/refreshed rows.
    Uses the yfinance batch downloader to keep request counts low.
    """
    if universe is None:
        universe = load_universe()

    symbols = universe["yfin_symbol"].tolist()
    log.info("Downloading %d symbols (period=%s) via yfinance...", len(symbols), period)

    data = yf.download(
        tickers=symbols,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )

    rows = []
    for _, u in universe.iterrows():
        sym = u["yfin_symbol"]
        try:
            if len(symbols) > 1:
                sub = data[sym]
            else:  # single ticker returns flat MultiIndex-less frame
                sub = data
        except KeyError:
            log.warning("No data for %s", sym)
            continue
        sub = sub.dropna(subset=["Close"])
        if sub.empty:
            log.warning("Empty history for %s", sym)
            continue
        out = sub[["Open", "High", "Low", "Close", "Volume"]].copy()
        out["date"] = out.index.strftime("%Y-%m-%d")
        out["symbol"] = u["symbol"]
        rows.append(out[["symbol", "date", "Open", "High", "Low", "Close", "Volume"]])

    combined = (
        pd.concat(rows)
        .rename(columns={"Open": "open", "High": "high", "Low": "low",
                         "Close": "close", "Volume": "volume"})
        if rows
        else pd.DataFrame()
    )
    n = upsert_prices(combined)
    log.info("Stored %d price rows.", n)
    return combined


def refresh_universe_csv(url: str = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv") -> pd.DataFrame:
    """Re-download the official NSE NIFTY 50 list and store in DB."""
    import requests

    r = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        timeout=30,
    )
    r.raise_for_status()
    NIFTY50_CSV.write_bytes(r.content)
    universe = load_universe()
    upsert_stocks(universe.to_dict("records"))
    log.info("Refreshed universe: %d stocks.", len(universe))
    return universe


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    import database

    database.init_db()
    universe = refresh_universe_csv()
    combined = ingest_prices(universe)
    if not combined.empty:
        print(f"Ingested {combined['symbol'].nunique()} symbols, "
              f"{combined['date'].min()} .. {combined['date'].max()}")
