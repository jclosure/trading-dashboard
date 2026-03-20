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
history = gw.portfolio_history(period="1D", timeframe="5Min", extended_hours=True)
daily_history = gw.portfolio_history(period="1M", timeframe="1D", extended_hours=True)
tracked = sorted(set(cfg.watchlist + [p.symbol for p in positions]))
quotes = gw.latest_quotes(tracked)

positions_df = build_positions_df(positions)
recent_orders_df = orders_table(recent_orders)
pl = aggregate_pl(positions_df, account)
exposure = exposure_stats(positions_df, account)
dd = drawdown_from_history(history)
perf = performance_stats(recent_orders_df)
alerts = alert_flags(pl, exposure, dd, float(account.equity))

last_equity = float(account.last_equity)
day_pl_pct = (pl["day_total"] / last_equity * 100) if last_equity else 0.0

wr = "n/a" if perf["win_rate"] is None else f"{perf['win_rate']:.1f}%"
aw = "n/a" if perf["avg_win"] is None else f"${perf['avg_win']:,.2f}"
al = "n/a" if perf["avg_loss"] is None else f"${perf['avg_loss']:,.2f}"

mode = st.sidebar.radio(
    "Dashboard mode",
    options=["Basic", "Pro"],
    index=0,
    help="Basic keeps only the essentials. Pro shows full analytics and execution detail.",
)

if mode == "Basic":
    st.subheader("Simple dashboard")
    st.metric(
        "Simple answer: Net P/L today",
        f"${pl['day_total']:,.2f}",
        f"{day_pl_pct:+.2f}% vs previous close",
        help="Your total account change since yesterday's close.",
    )

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Equity", f"${float(account.equity):,.2f}", help="Total account value right now.")
    b2.metric("Cash", f"${float(account.cash):,.2f}", help="Uninvested money currently in the account.")
    b3.metric("Open positions", f"{len(positions)}", help="How many symbols you currently hold.")
    b4.metric("Open orders", f"{len(open_orders)}", help="Orders submitted but not fully filled yet.")

    if daily_history and getattr(daily_history, "timestamp", None) and getattr(daily_history, "equity", None):
        basic_df = pd.DataFrame({"timestamp": daily_history.timestamp, "equity": daily_history.equity})
        basic_df = basic_df[pd.to_numeric(basic_df["equity"], errors="coerce") > 0].copy()
        if len(basic_df) >= 2:
            basic_df["time"] = pd.to_datetime(basic_df["timestamp"], unit="s", utc=True).dt.tz_convert("America/Chicago")
            basic_df = basic_df.sort_values("time").tail(10)

            start_eq = float(basic_df["equity"].iloc[0])
            end_eq = float(basic_df["equity"].iloc[-1])
            change_10d = end_eq - start_eq
            change_10d_pct = (change_10d / start_eq * 100) if start_eq else 0.0

            c1, c2 = st.columns([1, 2])
            c1.metric(
                "P/L (last 10 trading days)",
                f"${change_10d:,.2f}",
                f"{change_10d_pct:+.2f}%",
                help="How much the account changed over the last 10 trading days shown.",
            )
            with c2:
                fig_basic = px.line(basic_df, x="time", y="equity", title="Equity, last 10 trading days")
                fig_basic.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig_basic, use_container_width=True)

    st.subheader("Risk alerts")
    alerts_panel(alerts)
    st.caption("Switch to Pro mode in the sidebar for positions, execution details, and drilldowns.")
    st.stop()

views = st.tabs(["Home", "Positions & Risk", "Execution", "Insights", "Reference"])

with views[0]:
    st.subheader("Today at a glance")
    st.metric(
        "Simple answer: Net P/L today",
        f"${pl['day_total']:,.2f}",
        f"{day_pl_pct:+.2f}% vs previous close",
        help="The one-number answer. This is your full account change since yesterday's close. Positive means you made money. Negative means you lost money.",
    )

    kpi_row(account)

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Realized P/L (est)", f"${pl['realized_est']:,.2f}", help="Estimated profit or loss from trades that were effectively closed today.")
    h2.metric("Unrealized P/L", f"${pl['unrealized']:,.2f}", help="Profit or loss on open positions if you sold them right now.")
    h3.metric("Filled Orders (sample)", f"{perf['fills']}", help="How many orders in this sample window were actually executed.")
    h4.metric("Win Rate (sample)", wr, help="Percent of sampled outcomes that were positive. Higher is generally better.")

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Intraday Equity")
        portfolio_chart(history)
    with c2:
        important_highlights_panel(pl, exposure, dd, perf, len(open_orders))
        alerts_panel(alerts)

with views[1]:
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

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Gross Exposure", f"${exposure['gross']:,.2f}", f"{exposure['gross_pct']:.1f}% of eq", help="Total dollars currently in positions, ignoring direction.")
    r2.metric("Net Exposure", f"${exposure['net']:,.2f}", f"{exposure['net_pct']:.1f}% of eq", help="Long exposure minus short exposure.")
    r3.metric("Max Drawdown (intraday)", f"{dd['max_drawdown']:.2f}%", help="Worst drop from a high point to a low point in your equity during today.")
    r4.metric("Avg Loss (sample)", al, help="Average dollar loss for losing sampled trades.")

    st.subheader("Exposure Heat")
    exposure_chart(positions_df)

with views[2]:
    st.subheader("Orders & Realized Activity")

    left, right = st.columns([1, 1])
    with left:
        st.markdown("**Open Orders**")
        oo = orders_table(open_orders)
        st.dataframe(oo, use_container_width=True, hide_index=True)
    with right:
        st.markdown("**Recent Orders**")
        st.dataframe(recent_orders_df, use_container_width=True, hide_index=True)

    st.markdown("**Trade Blotter (filled orders)**")
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
        b1.metric("Filled Trades", f"{len(blotter_df)}", help="Number of completed trades in this blotter view.")
        b2.metric("Turnover", f"${blotter_df['Abs Notional'].sum():,.2f}", help="Total dollars traded in the sample period. Activity, not profit.")

    st.divider()
    st.markdown("**Realized gains activity**")
    days = st.slider(
        "Lookback window (days)",
        min_value=3,
        max_value=60,
        value=14,
        step=1,
        help="Choose how far back to analyze sells and account profit.",
    )

    filled_df = recent_orders_df.copy()
    if not filled_df.empty:
        filled_df = filled_df[
            filled_df["Status"].astype(str).str.contains("filled", case=False, na=False)
            & filled_df["Side"].astype(str).str.contains("sell", case=False, na=False)
        ].copy()

    sell_count = 0
    sell_notional = 0.0
    avg_sell_size = 0.0

    if not filled_df.empty:
        filled_df["CreatedDT"] = pd.to_datetime(filled_df["Created"], errors="coerce", utc=True)
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
        recent_sells = filled_df[filled_df["CreatedDT"] >= cutoff].copy()

        if not recent_sells.empty:
            recent_sells["QtyNum"] = pd.to_numeric(recent_sells["Qty"], errors="coerce").fillna(0)
            recent_sells["PriceNum"] = pd.to_numeric(recent_sells["Filled Avg"], errors="coerce").fillna(0)
            recent_sells["Sell Notional"] = recent_sells["QtyNum"] * recent_sells["PriceNum"]
            sell_count = int(len(recent_sells))
            sell_notional = float(recent_sells["Sell Notional"].sum())
            avg_sell_size = float(recent_sells["Sell Notional"].mean()) if sell_count else 0.0

    window_profit = 0.0
    window_profit_pct = 0.0
    if daily_history and getattr(daily_history, "timestamp", None) and getattr(daily_history, "equity", None):
        hist_df = pd.DataFrame({"timestamp": daily_history.timestamp, "equity": daily_history.equity})
        hist_df = hist_df[pd.to_numeric(hist_df["equity"], errors="coerce") > 0].copy()
        if not hist_df.empty:
            hist_df["time"] = pd.to_datetime(hist_df["timestamp"], unit="s", utc=True)
            cutoff_hist = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
            hist_df = hist_df[hist_df["time"] >= cutoff_hist].sort_values("time")
            if len(hist_df) >= 2:
                start_eq = float(hist_df["equity"].iloc[0])
                end_eq = float(hist_df["equity"].iloc[-1])
                window_profit = end_eq - start_eq
                window_profit_pct = (window_profit / start_eq * 100) if start_eq else 0.0

    x1, x2, x3, x4 = st.columns(4)
    x1.metric(
        f"Net account profit ({days}d)",
        f"${window_profit:,.2f}",
        f"{window_profit_pct:+.2f}%",
        help="How much total account value changed over the selected days.",
    )
    x2.metric(f"Profit-taking sells ({days}d)", f"{sell_count}", help="Number of completed sell orders in this window.")
    x3.metric(f"Sell notional ({days}d)", f"${sell_notional:,.2f}", help="Total dollars sold in this window.")
    x4.metric(f"Avg sell size ({days}d)", f"${avg_sell_size:,.2f}", help="Average size per completed sell order.")

with views[3]:
    st.subheader("Longer view")
    if daily_history and getattr(daily_history, "timestamp", None) and getattr(daily_history, "equity", None):
        daily_df = pd.DataFrame({"timestamp": daily_history.timestamp, "equity": daily_history.equity})
        daily_df = daily_df[pd.to_numeric(daily_df["equity"], errors="coerce") > 0].copy()

        if len(daily_df) >= 2:
            daily_df["time"] = pd.to_datetime(daily_df["timestamp"], unit="s", utc=True).dt.tz_convert("America/Chicago")
            daily_df = daily_df.sort_values("time").tail(10)

            start_eq = float(daily_df["equity"].iloc[0])
            end_eq = float(daily_df["equity"].iloc[-1])
            change_10d = end_eq - start_eq
            change_10d_pct = (change_10d / start_eq * 100) if start_eq else 0.0

            t1, t2 = st.columns([1, 2])
            t1.metric(
                "P/L (last 10 trading days)",
                f"${change_10d:,.2f}",
                f"{change_10d_pct:+.2f}%",
                help="How much your account changed from the first to the most recent day in this 10-day view.",
            )

            with t2:
                fig_10d = px.line(daily_df, x="time", y="equity", title="Equity, last 10 trading days")
                fig_10d.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig_10d, use_container_width=True)
        else:
            st.info("Not enough daily history yet to show a 10-day P/L trend.")
    else:
        st.info("No daily portfolio history available yet.")

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

    st.subheader("Watchlist Quotes")
    watchlist_quotes(quotes)

with views[4]:
    docs_reference_panel()

st.markdown(
    f"""
    <script>
        setTimeout(function() {{ window.location.reload(); }}, {refresh * 1000});
    </script>
    """,
    unsafe_allow_html=True,
)
