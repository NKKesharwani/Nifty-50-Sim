"""Streamlit web dashboard for Nifty-Sim."""
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Nifty 50 Trading Simulator",
    page_icon="📈",
    layout="wide",
)

@st.cache_resource
def get_connection():
    return sqlite3.connect("data/trading.db", check_same_thread=False)

conn = get_connection()

st.title("📈 Nifty 50 Local Trading Simulator")
st.markdown("Monitor NIFTY 50 stocks, simulate different trading algorithms locally, and inspect performance & transactions.")

# Sidebar controls
st.sidebar.header("Simulation Control")
strategy = st.sidebar.selectbox(
    "Select Strategy",
    [
        "Percentage Threshold (±1%)",
        "RSI Mean Reversion (14)",
        "Bollinger Bands (20, 2)",
        "MA Crossover (20/50)",
        "Momentum (20-day ROC)",
    ]
)
initial_capital = st.sidebar.number_input("Initial Capital (₹)", value=10_000_000.0, step=100_000.0)
trade_qty = st.sidebar.number_input("Shares per Trade", value=5, step=1)

if st.sidebar.button("Run Simulation", type="primary"):
    with st.spinner("Running simulation..."):
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).resolve().parent))
        import strategies
        if "Percentage" in strategy:
            strategies.run_pct_threshold(qty=trade_qty, initial_capital=initial_capital)
        elif "RSI" in strategy:
            strategies.run_rsi(qty=trade_qty, initial_capital=initial_capital)
        elif "Bollinger" in strategy:
            strategies.run_bollinger(qty=trade_qty, initial_capital=initial_capital)
        elif "MA Crossover" in strategy:
            strategies.run_ma_crossover(qty=trade_qty, initial_capital=initial_capital)
        elif "Momentum" in strategy:
            strategies.run_momentum(qty=trade_qty, initial_capital=initial_capital)
    st.sidebar.success("Simulation complete!")
    st.rerun()

# Main metrics overview
try:
    portfolio_df = pd.read_sql("SELECT * FROM portfolio_daily ORDER BY date", conn)
    meta_df = dict(pd.read_sql("SELECT * FROM sim_meta", conn).values)
except Exception:
    portfolio_df = pd.DataFrame()
    meta_df = {}

if portfolio_df.empty:
    st.warning("No simulation data found. Click 'Run Simulation' in the sidebar to start.")
else:
    init_cap = float(meta_df.get("initial_capital", 10_000_000.0))
    latest = portfolio_df.iloc[-1]
    total_val = latest["total_value"]
    cash = latest["cash"]
    holdings_val = latest["holdings_value"]
    pnl = total_val - init_cap
    pnl_pct = (pnl / init_cap) * 100.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Portfolio Value", f"₹{total_val:,.2f}", f"{pnl_pct:+.2f}%")
    col2.metric("Total P&L", f"₹{pnl:+,.2f}")
    col3.metric("Available Cash", f"₹{cash:,.2f}")
    col4.metric("Holdings Market Value", f"₹{holdings_val:,.2f}")

    st.markdown("---")
    
    # Equity Curve
    st.subheader("📊 Portfolio Equity Curve")
    fig = px.line(portfolio_df, x="date", y="total_value", title="Portfolio Total Value Over Time")
    fig.update_layout(xaxis_title="Date", yaxis_title="Total Value (₹)")
    st.plotly_chart(fig, use_container_width=True)

    # Tabs for detailed views
    tab1, tab2, tab3 = st.tabs(["📦 Current Holdings", "📜 Transactions", "📉 Stock Prices & Universe"])

    with tab1:
        st.subheader("Active Holdings")
        pos_df = pd.read_sql("""
            SELECT p.symbol, p.quantity, ROUND(p.avg_cost, 2) as avg_cost, s.close as current_price,
                   ROUND(p.quantity * s.close, 2) as market_value
            FROM positions p
            JOIN (SELECT symbol, close FROM prices WHERE date = (SELECT MAX(date) FROM prices)) s ON p.symbol = s.symbol
            WHERE p.quantity > 0
            ORDER BY market_value DESC
        """, conn)
        if pos_df.empty:
            st.info("No active holdings.")
        else:
            st.dataframe(pos_df, use_container_width=True)

    with tab2:
        st.subheader("Transaction History")
        tx_df = pd.read_sql("SELECT * FROM transactions ORDER BY id DESC LIMIT 500", conn)
        if tx_df.empty:
            st.info("No transactions recorded.")
        else:
            st.dataframe(tx_df, use_container_width=True)

    with tab3:
        st.subheader("NIFTY 50 Universe & Latest Prices")
        uni_df = pd.read_sql("""
            st.subheader("NIFTY 50 Universe")
            SELECT s.symbol, s.name, s.industry, p.close as latest_close, p.date as price_date
            FROM stocks s
            LEFT JOIN (
                SELECT symbol, close, date FROM prices 
                WHERE date = (SELECT MAX(date) FROM prices)
            ) p ON s.symbol = p.symbol
        """, conn)
        # Fix query string inline
        uni_df = pd.read_sql("""
            SELECT s.symbol, s.name, s.industry, p.close as latest_close, p.date as price_date
            FROM stocks s
            LEFT JOIN (
                SELECT symbol, close, date FROM prices 
                WHERE date = (SELECT MAX(date) FROM prices)
            ) p ON s.symbol = p.symbol
        """, conn)
        st.dataframe(uni_df, use_container_width=True)
