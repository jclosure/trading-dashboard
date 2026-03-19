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
    c1.metric(
        "Equity",
        f"${equity:,.2f}",
        f"{pct:+.2f}%",
        help="Your total account value right now. If all positions were closed, this is about what the account is worth.",
    )
    c2.metric(
        "Buying Power",
        f"${float(account.buying_power):,.2f}",
        help="How much money you can use for new trades at this moment.",
    )
    c3.metric(
        "Cash",
        f"${float(account.cash):,.2f}",
        help="Money sitting in the account that is not currently invested in positions.",
    )
    c4.metric(
        "P/L Today (net)",
        f"${delta:,.2f}",
        help="How much your account is up or down today compared with yesterday's close.",
    )


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


def important_highlights_panel(pl: dict, exposure: dict, drawdown: dict, perf: dict, open_orders_count: int):
    st.subheader("Important Highlights")

    notes: list[tuple[str, str]] = []

    day_total = float(pl.get("day_total", 0.0))
    gross_pct = float(exposure.get("gross_pct", 0.0))
    dd = float(drawdown.get("max_drawdown", 0.0))
    fills = int(perf.get("fills") or 0)
    win_rate = perf.get("win_rate")

    if day_total <= 0:
        notes.append(("bad", f"Day P/L is negative (${day_total:,.2f}). Keep risk tight until momentum improves."))
    else:
        notes.append(("good", f"Day P/L is positive (${day_total:,.2f}). Protect gains, avoid overtrading."))

    if gross_pct > 120:
        notes.append(("bad", f"Gross exposure is elevated at {gross_pct:.1f}% of equity."))
    elif gross_pct < 60:
        notes.append(("good", f"Gross exposure is moderate at {gross_pct:.1f}% of equity."))

    if dd < -3:
        notes.append(("bad", f"Intraday drawdown reached {dd:.2f}%. This is a caution zone."))
    elif dd > -1:
        notes.append(("good", f"Intraday drawdown is contained ({dd:.2f}%)."))

    if fills >= 20 and win_rate is not None:
        if win_rate >= 55:
            notes.append(("good", f"Sample win rate is {win_rate:.1f}% across {fills} filled orders."))
        elif win_rate < 45:
            notes.append(("bad", f"Sample win rate is {win_rate:.1f}% across {fills} filled orders."))

    if open_orders_count > 0:
        notes.append(("neutral", f"{open_orders_count} open order(s) waiting for fills."))

    if not notes:
        st.info("No major temporary signal yet. Market state is neutral.")
        return

    for level, msg in notes[:4]:
        if level == "good":
            st.success(msg)
        elif level == "bad":
            st.warning(msg)
        else:
            st.info(msg)


def docs_reference_panel():
    st.subheader("Quick Reference")
    st.caption("Simple definitions for common dashboard fields. Docs: [Alpaca Orders](https://docs.alpaca.markets/docs/trading/orders), [Order Lifecycle](https://docs.alpaca.markets/docs/trading/orders/#order-lifecycle)")

    st.markdown("""
**Account KPIs**
- **Equity**: total account value right now.
- **Buying Power**: how much you can deploy for new trades.
- **Cash**: uninvested cash balance.
- **Day P/L**: change vs previous day close.

**Positions**
- **Market Value**: current dollar value of a position.
- **Cost Basis**: total cost paid for current shares.
- **Unrealized P/L**: profit or loss if closed now.
- **Unrealized P/L %**: unrealized P/L as a percentage.
- **Avg Entry**: average entry price.
- **Current Price**: latest market price.

**Orders / Blotter**
- **Created**: when the order was submitted.
- **Symbol**: ticker (AAPL, TSLA, etc.).
- **Side**: buy or sell.
- **Type**: market, limit, stop, etc.
- **Status**: new, partially filled, filled, canceled, rejected.
- **Qty**: number of shares.
- **Notional**: target dollar amount instead of share qty.
- **Limit**: max buy price or min sell price for a limit order.
- **Filled Avg**: average execution price of fills.
- **Signed Notional**: trade value with sign (+ buy, - sell).
- **Turnover**: total traded notional over the sample.

**Risk / Exposure**
- **Gross Exposure**: total absolute capital deployed.
- **Net Exposure**: long exposure minus short exposure.
- **Max Drawdown (intraday)**: worst peak-to-trough drop during the day.

**Performance sample**
- **Filled Orders**: count of filled orders in sample window.
- **Win Rate**: percent of positive estimated outcomes in sample.
- **Avg Win / Avg Loss**: mean gain/loss for sample trades.
""")
