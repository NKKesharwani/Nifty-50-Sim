"""Backtest/simulation engine.

V1 strategy (user-specified):
  For each stock, on each trading day (vs previous close):
    - daily change >= +1%  -> SELL 5 shares (if held)
    - daily change <= -1%  -> BUY  5 shares (if cash allows)
  Fills at the day's close price.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
import sqlite3

from config import DEFAULT_INITIAL_CAPITAL, THRESHOLD_PCT, TRADE_QUANTITY
from database import db, meta_get, record_transaction, set_cash, snapshot_portfolio

log = logging.getLogger("sim")


@dataclass
class SimConfig:
    threshold_pct: float = THRESHOLD_PCT
    quantity: int = TRADE_QUANTITY
    initial_capital: float = DEFAULT_INITIAL_CAPITAL


class Simulator:
    def __init__(self, cfg: SimConfig | None = None):
        self.cfg = cfg or SimConfig()

    # ------------------------------------------------------------------ #
    def _load_prices(self) -> pd.DataFrame:
        with db() as conn:
            rows = conn.execute(
                "SELECT symbol, date, close FROM prices ORDER BY symbol, date"
            ).fetchall()
        return pd.DataFrame(rows, columns=["symbol", "date", "close"])

    def _holdings(self) -> dict[str, float]:
        with db() as conn:
            rows = conn.execute("SELECT symbol, quantity FROM positions WHERE quantity > 0").fetchall()
        return {r["symbol"]: r["quantity"] for r in rows}

    def _cash(self) -> float:
        return float(meta_get("cash", "0") or 0)

    # ------------------------------------------------------------------ #
    def start(self, initial_capital: float | None = None) -> None:
        """Reset the simulation book with fresh capital."""
        capital = float(initial_capital or self.cfg.initial_capital)
        with db() as conn:
            conn.execute("DELETE FROM positions")
            conn.execute("DELETE FROM transactions")
            conn.execute("DELETE FROM portfolio_daily")
        set_cash(capital)
        from database import meta_set
        meta_set("initial_capital", f"{capital:.6f}")
        log.info("Simulation started with initial capital %.2f", capital)

    def run(self) -> dict:
        """Process all stored prices chronologically, one day at a time."""
        prices = self._load_prices()
        if prices.empty:
            log.warning("No prices in DB - run ingest first.")
            return {"days": 0, "trades": 0}

        cash = self._cash()
        if cash <= 0 and not meta_get("initial_capital"):
            raise RuntimeError("Run Simulator.start() before simulating.")

        holdings = self._holdings()
        trades = 0

        # pivot: index=date, cols=symbol
        pivot = prices.pivot(index="date", columns="symbol", values="close")
        pct = pivot.pct_change() * 100.0

        for date, row in pivot.iterrows():
            close_map = row.dropna().to_dict()
            chg_row = pct.loc[date]
            for symbol in close_map:
                chg = chg_row.get(symbol)
                if chg is None or pd.isna(chg):
                    continue
                price = close_map[symbol]
                if chg >= self.cfg.threshold_pct:
                    held = holdings.get(symbol, 0.0)
                    if held >= self.cfg.quantity:
                        record_transaction(date, symbol, "SELL", price, self.cfg.quantity,
                                            f"up {chg:.2f}%")
                        cash += price * self.cfg.quantity
                        holdings[symbol] = held - self.cfg.quantity
                        trades += 1
                elif chg <= -self.cfg.threshold_pct:
                    cost = price * self.cfg.quantity
                    if cash >= cost:
                        record_transaction(date, symbol, "BUY", price, self.cfg.quantity,
                                            f"down {chg:.2f}%")
                        cash -= cost
                        holdings[symbol] = holdings.get(symbol, 0.0) + self.cfg.quantity
                        trades += 1

            # commit cash after day completes (transactions are committed per-row)
            set_cash(cash)
            snapshot_portfolio(date, close_map)

        log.info("Simulated %d days, %d trades.", len(pivot), trades)
        return {"days": len(pivot), "trades": trades}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    import database

    database.init_db()
    sim = Simulator()
    sim.start()
    print(sim.run())
