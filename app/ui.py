from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st


def kpi_row(account) -> None:
    equity = float(account.equity)
    last_equity = float(account.last_equity)
    delta = equity - last_equity
    pct = (delta / last_equity * 100) if last_equity else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equity", f"${equity:,.2f}", f"{pct:+.2f}%")
    c2.metric("Buying Power", f"${float(account.buying_power):,.2f}")
    c3.metric("Cash", f"${float(account.cash):,.2f}")
    c4.metric("Day P/L", f"${delta:,.2f}")


def positions_table(positions_df: pd.DataFrame) -> pd.DataFrame:
    if positions_df.empty:
        return pd.DataFrame()
    df = positions_df.rename(
        columns={
            "symbol": "Symbol",
            "side": "Side",
            "qty": "Qty",
            "avg_entry_price": "Avg Entry",
            "market_value": "Market Value",
            "cost_basis": "Cost Basis",
            "unrealized_pl": "Unrealized P/L",
            "unrealized_pl_pct": "Unrealized P/L %",
            "current_price": "Current Price",
        }
    )
    return df.sort_values(by="Market Value", ascending=False)


def orders_table(orders) -> pd.DataFrame:
    rows = []
    for o in orders:
        rows.append(
            {
                "Created": str(o.created_at),
                "Symbol": o.symbol,
                "Side": str(o.side),
                "Type": str(o.order_type),
                "Status": str(o.status),
                "Qty": float(o.qty) if o.qty is not None else None,
                "Notional": float(o.notional) if o.notional is not None else None,
                "Limit": float(o.limit_price) if o.limit_price is not None else None,
                "Filled Avg": float(o.filled_avg_price) if o.filled_avg_price is not None else None,
            }
        )
    return pd.DataFrame(rows)


def portfolio_chart(history):
    if not history or not getattr(history, "timestamp", None):
        st.info("No portfolio history available yet.")
        return
    ts = pd.to_datetime(history.timestamp, unit="s", utc=True).tz_convert("America/Chicago")
    df = pd.DataFrame({"time": ts, "equity": history.equity, "profit_loss": history.profit_loss})
    fig = px.line(df, x="time", y="equity", title="Intraday Equity")
    fig.update_layout(height=340, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)


def exposure_chart(positions_df: pd.DataFrame):
    if positions_df.empty:
        st.info("No exposures to chart.")
        return
    chart_df = positions_df[["symbol", "signed_exposure", "unrealized_pl"]].copy()
    chart_df["Direction"] = chart_df["signed_exposure"].apply(lambda x: "Long" if x >= 0 else "Short")
    fig = px.bar(
        chart_df,
        x="symbol",
        y="signed_exposure",
        color="unrealized_pl",
        title="Exposure by Symbol (signed)",
        labels={"symbol": "Symbol", "signed_exposure": "Exposure ($)", "unrealized_pl": "U P/L"},
    )
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)


def watchlist_quotes(quotes: dict):
    rows = []
    for sym, q in quotes.items():
        bid = float(q.bid_price) if q.bid_price else None
        ask = float(q.ask_price) if q.ask_price else None
        spread = (ask - bid) if (ask and bid) else None
        mid = (ask + bid) / 2 if (ask and bid) else None
        rows.append(
            {
                "Symbol": sym,
                "Bid": bid,
                "Ask": ask,
                "Spread": spread,
                "Mid": mid,
                "Timestamp": str(q.timestamp),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        st.dataframe(df.sort_values("Symbol"), use_container_width=True, hide_index=True)
    else:
        st.info("No quotes available.")


def alerts_panel(alerts: list[str]):
    st.subheader("Risk Alerts")
    if not alerts:
        st.success("No active risk alerts.")
        return
    for a in alerts:
        st.warning(a)
