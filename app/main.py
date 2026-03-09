from __future__ import annotations

import streamlit as st

from app.alpaca_client import AlpacaGateway, load_config
from app.ui import kpi_row, orders_table, portfolio_chart, positions_table, watchlist_quotes

st.set_page_config(page_title="Loop + Joel Trading Dashboard", page_icon="📈", layout="wide")

st.title("📈 Loop + Joel Trading Dashboard")
st.caption("Paper trading realtime monitor via Alpaca")

refresh = st.sidebar.slider("Refresh interval (seconds)", min_value=2, max_value=60, value=5)
st.sidebar.write("Auto-refresh is enabled")
st.sidebar.caption("This page updates itself on interval.")

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0

try:
    cfg = load_config()
    gw = AlpacaGateway(cfg)
except Exception as e:
    st.error(f"Config error: {e}")
    st.stop()

account = gw.account()
positions = gw.positions()
open_orders = gw.open_orders()
recent_orders = gw.recent_orders(limit=100)
history = gw.portfolio_history()
tracked = sorted(set(cfg.watchlist + [p.symbol for p in positions]))
quotes = gw.latest_quotes(tracked)

kpi_row(account)

col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("Portfolio")
    portfolio_chart(history)
with col2:
    st.subheader("Open Orders")
    oo = orders_table(open_orders)
    st.dataframe(oo, use_container_width=True, hide_index=True)

st.subheader("Positions")
pos_df = positions_table(positions)
if pos_df.empty:
    st.info("No open positions.")
else:
    st.dataframe(
        pos_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Market Value": st.column_config.NumberColumn(format="$%.2f"),
            "Cost Basis": st.column_config.NumberColumn(format="$%.2f"),
            "Unrealized P/L": st.column_config.NumberColumn(format="$%.2f"),
            "Unrealized P/L %": st.column_config.NumberColumn(format="%.2f%%"),
            "Avg Entry": st.column_config.NumberColumn(format="$%.2f"),
            "Current Price": st.column_config.NumberColumn(format="$%.2f"),
        },
    )

st.subheader("Watchlist Quotes")
watchlist_quotes(quotes)

st.subheader("Recent Orders")
ro = orders_table(recent_orders)
st.dataframe(ro, use_container_width=True, hide_index=True)

st.markdown(
    f"""
    <script>
        setTimeout(function() {{ window.location.reload(); }}, {refresh * 1000});
    </script>
    """,
    unsafe_allow_html=True,
)
