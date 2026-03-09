from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.alpaca_client import AlpacaGateway, load_config
from app.analytics import build_positions_df
from app.ui import orders_table


def run_review() -> str:
    cfg = load_config()
    gw = AlpacaGateway(cfg)

    account = gw.account()
    positions = gw.positions()
    orders = gw.recent_orders(limit=500)

    equity = float(account.equity)
    last_equity = float(account.last_equity)
    day_pl = equity - last_equity

    pos_df = build_positions_df(positions)
    ord_df = orders_table(orders)

    month = datetime.now().strftime("%Y-%m")
    path = Path("logs") / f"monthly-review-{month}.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    wins = 0
    losses = 0
    if not ord_df.empty and "Status" in ord_df.columns:
        filled = ord_df[ord_df["Status"].str.contains("filled", case=False, na=False)]
        wins = len(filled[filled["Side"].str.contains("sell", case=False, na=False)])
        losses = len(filled[filled["Side"].str.contains("buy", case=False, na=False)])

    text = f"""# Monthly Review {month}

## Snapshot
- Equity: ${equity:,.2f}
- Day P/L: ${day_pl:,.2f}
- Open positions: {0 if pos_df.empty else len(pos_df)}
- Recent orders sampled: {0 if ord_df.empty else len(ord_df)}

## Required Questions (draft)
1. Total return vs S&P 500: TODO (wire benchmark feed)
2. Outperformers: TODO
3. Underperformers and missed signals: TODO
4. Yield-vs-cost calibration updates: TODO
5. Macro/geopolitical surprises: TODO
6. Revised market context for next month: TODO

## Trade Outcome Proxy
- Filled sells (proxy wins realization events): {wins}
- Filled buys (entries): {losses}

"""
    path.write_text(text)
    return str(path)


if __name__ == "__main__":
    p = run_review()
    print("Monthly review written:", p)
