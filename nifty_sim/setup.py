#!/usr/bin/env python3
"""
Initialize Nifty-Sim database and ingest NIFTY 50 data.
Run this once after cloning the repository.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

print("🔧 Initializing Nifty-Sim...")
print(f"   Project root: {PROJECT_ROOT}")

# 1. Initialize database
print("   Creating database schema...")
from nifty_sim.database import init_db
init_db()

# 2. Ingest NIFTY 50 universe
print("   Fetching NIFTY 50 list and prices (1 year)...")
from nifty_sim.ingest import refresh_universe_csv, ingest_prices
universe = refresh_universe_csv()
prices = ingest_prices(universe)

print(f"✅ Done! Ingested {prices['symbol'].nunique()} symbols, {len(prices)} price rows.")
print(f"   Date range: {prices['date'].min()} → {prices['date'].max()}")
print()
print("🚀 Now start the dashboard:")
print(f"   streamlit run nifty_sim/web/app.py")