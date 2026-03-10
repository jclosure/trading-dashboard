from __future__ import annotations

import streamlit as st

from alpaca_client import AlpacaGateway, load_config
import pandas as pd
import plotly.express as px

from analytics import (
    aggregate_pl,
    alert_flags,
    build_blotter_df,
    build_positions_df,
    drawdown_from_history,
    exposure_stats,
    performance_stats,
    symbol_attribution,
)
from ui import (
    alerts_panel,
    docs_reference_panel,
    exposure_chart,
    important_highlights_panel,
    kpi_row,
    orders_table,
    portfolio_chart,
    positions_table,
    watchlist_quotes,
)

st.set_page_config(page_title="Loop + Joel Trading Dashboard", page_icon="📈", layout="wide")

st.title("📈 Loop + Joel Trading Dashboard")
st.caption("Paper trading realtime monitor via Alpaca")

refresh = st.sidebar.slider("Refresh interval (seconds)", min_value=2, max_value=60, value=5)
st.sidebar.write("Auto-refresh is enabled")
st.sidebar.caption("LAN-ready via 0.0.0.0 bind")

try:
    cfg = load_config()
    gw = AlpacaGateway(cfg)
except Exception as e:
    st.error(f"Config error: {e}")
    st.stop()

account = gw.account()
positions = gw.positions()
open_orders = gw.open_orders()
recent_orders = gw.recent_orders(limit=200)
history = gw.portfolio_history()
tracked = sorted(set(cfg.watchlist + [p.symbol for p in positions]))
quotes = gw.latest_quotes(tracked)

positions_df = build_positions_df(positions)
recent_orders_df = orders_table(recent_orders)
pl = aggregate_pl(positions_df, account)
exposure = exposure_stats(positions_df, account)
dd = drawdown_from_history(history)
perf = performance_stats(recent_orders_df)
alerts = alert_flags(pl, exposure, dd, float(account.equity))

kpi_row(account)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Realized P/L (est)", f"${pl['realized_est']:,.2f}")
m2.metric("Unrealized P/L", f"${pl['unrealized']:,.2f}")
m3.metric("Gross Exposure", f"${exposure['gross']:,.2f}", f"{exposure['gross_pct']:.1f}% of eq")
m4.metric("Net Exposure", f"${exposure['net']:,.2f}", f"{exposure['net_pct']:.1f}% of eq")

n1, n2, n3, n4 = st.columns(4)
wr = "n/a" if perf["win_rate"] is None else f"{perf['win_rate']:.1f}%"
aw = "n/a" if perf["avg_win"] is None else f"${perf['avg_win']:,.2f}"
al = "n/a" if perf["avg_loss"] is None else f"${perf['avg_loss']:,.2f}"
n1.metric("Filled Orders (sample)", f"{perf['fills']}")
n2.metric("Win Rate (sample)", wr)
n3.metric("Avg Win (sample)", aw)
n4.metric("Avg Loss (sample)", al)

st.metric("Max Drawdown (intraday)", f"{dd['max_drawdown']:.2f}%")

c1, c2 = st.columns([2, 1])
with c1:
    st.subheader("Portfolio")
    portfolio_chart(history)
with c2:
    important_highlights_panel(pl, exposure, dd, perf, len(open_orders))
    alerts_panel(alerts)

st.subheader("Positions")
pos_df = positions_table(positions_df)
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

st.subheader("Exposure Heat")
exposure_chart(positions_df)

left, right = st.columns([1, 1])
with left:
    st.subheader("Open Orders")
    oo = orders_table(open_orders)
    st.dataframe(oo, use_container_width=True, hide_index=True)
with right:
    st.subheader("Watchlist Quotes")
    watchlist_quotes(quotes)

tabs = st.tabs(["Overview", "Trade Blotter", "Symbol Drilldown", "Reference"])

with tabs[0]:
    st.subheader("Recent Orders")
    st.dataframe(recent_orders_df, use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("Trade Blotter")
    blotter_df = build_blotter_df(recent_orders_df)
    if blotter_df.empty:
        st.info("No filled orders yet for blotter stats.")
    else:
        st.dataframe(
            blotter_df[["Created", "Symbol", "Side", "Type", "Qty", "Filled Avg", "Signed Notional", "Status"]],
            use_container_width=True,
            hide_index=True,
        )
        b1, b2 = st.columns(2)
        b1.metric("Filled Trades", f"{len(blotter_df)}")
        b2.metric("Turnover", f"${blotter_df['Abs Notional'].sum():,.2f}")

with tabs[2]:
    st.subheader("Symbol Drilldown")
    blotter_df = build_blotter_df(recent_orders_df)
    attrib_df = symbol_attribution(positions_df, blotter_df, pl["realized_est"])

    if attrib_df.empty:
        st.info("No symbol attribution data yet.")
    else:
        st.dataframe(
            attrib_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Unrealized P/L": st.column_config.NumberColumn(format="$%.2f"),
                "Realized P/L (est)": st.column_config.NumberColumn(format="$%.2f"),
                "Total P/L (est)": st.column_config.NumberColumn(format="$%.2f"),
                "Turnover": st.column_config.NumberColumn(format="$%.2f"),
            },
        )

        fig_attr = px.bar(
            attrib_df,
            x="Symbol",
            y="Total P/L (est)",
            color="Total P/L (est)",
            title="Estimated P/L by Symbol",
        )
        st.plotly_chart(fig_attr, use_container_width=True)

        symbols = attrib_df["Symbol"].tolist()
        selected = st.selectbox("Select symbol", symbols, index=0)
        bars = gw.recent_bars(selected, limit=180)
        bars_df = getattr(bars, "df", pd.DataFrame())
        if not bars_df.empty:
            if isinstance(bars_df.index, pd.MultiIndex):
                bars_df = bars_df.reset_index()
            else:
                bars_df = bars_df.reset_index().rename(columns={bars_df.index.name or "index": "timestamp"})
            if "symbol" in bars_df.columns:
                bars_df = bars_df[bars_df["symbol"] == selected]
            if "timestamp" in bars_df.columns:
                bars_df["timestamp"] = pd.to_datetime(bars_df["timestamp"], utc=True).dt.tz_convert("America/Chicago")
            if "close" in bars_df.columns and "timestamp" in bars_df.columns:
                fig_px = px.line(bars_df, x="timestamp", y="close", title=f"{selected} recent minute bars")
                st.plotly_chart(fig_px, use_container_width=True)
        else:
            st.info("No recent bars available for this symbol.")

with tabs[3]:
    docs_reference_panel()

st.markdown(
    f"""
    <script>
        setTimeout(function() {{ window.location.reload(); }}, {refresh * 1000});
    </script>
    """,
    unsafe_allow_html=True,
)
