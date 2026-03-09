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


def positions_table(positions) -> pd.DataFrame:
    rows = []
    for p in positions:
        mv = float(p.market_value)
        cost = float(p.cost_basis)
        upl = float(p.unrealized_pl)
        uplpc = float(p.unrealized_plpc) * 100
        rows.append(
            {
                "Symbol": p.symbol,
                "Side": str(p.side),
                "Qty": float(p.qty),
                "Avg Entry": float(p.avg_entry_price),
                "Market Value": mv,
                "Cost Basis": cost,
                "Unrealized P/L": upl,
                "Unrealized P/L %": uplpc,
                "Current Price": float(p.current_price),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by="Market Value", ascending=False)
    return df


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
    fig.update_layout(height=360, margin=dict(l=20, r=20, t=50, b=20))
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
