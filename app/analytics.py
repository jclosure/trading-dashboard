from __future__ import annotations

import numpy as np
import pandas as pd


def to_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def build_positions_df(positions) -> pd.DataFrame:
    rows = []
    for p in positions:
        market_value = to_float(p.market_value)
        unrealized = to_float(p.unrealized_pl)
        unrealized_pct = to_float(p.unrealized_plpc) * 100
        side = str(p.side)
        signed_exposure = market_value if "long" in side.lower() else -market_value
        rows.append(
            {
                "symbol": p.symbol,
                "side": side,
                "qty": to_float(p.qty),
                "market_value": market_value,
                "cost_basis": to_float(p.cost_basis),
                "unrealized_pl": unrealized,
                "unrealized_pl_pct": unrealized_pct,
                "current_price": to_float(p.current_price),
                "avg_entry_price": to_float(p.avg_entry_price),
                "signed_exposure": signed_exposure,
            }
        )
    return pd.DataFrame(rows)


def aggregate_pl(positions_df: pd.DataFrame, account) -> dict:
    unrealized = positions_df["unrealized_pl"].sum() if not positions_df.empty else 0.0
    equity = to_float(account.equity)
    last_equity = to_float(account.last_equity)
    day_total = equity - last_equity
    realized_est = day_total - unrealized
    return {
        "day_total": day_total,
        "unrealized": unrealized,
        "realized_est": realized_est,
    }


def exposure_stats(positions_df: pd.DataFrame, account) -> dict:
    if positions_df.empty:
        return {"gross": 0.0, "net": 0.0, "gross_pct": 0.0, "net_pct": 0.0}
    gross = positions_df["market_value"].sum()
    net = positions_df["signed_exposure"].sum()
    equity = max(to_float(account.equity), 1.0)
    return {
        "gross": gross,
        "net": net,
        "gross_pct": gross / equity * 100,
        "net_pct": net / equity * 100,
    }


def performance_stats(recent_orders_df: pd.DataFrame) -> dict:
    if recent_orders_df.empty:
        return {"fills": 0, "win_rate": None, "avg_win": None, "avg_loss": None}

    filled = recent_orders_df[recent_orders_df["Status"].str.contains("filled", case=False, na=False)].copy()
    fills = len(filled)
    if fills == 0:
        return {"fills": 0, "win_rate": None, "avg_win": None, "avg_loss": None}

    if "Est P/L" not in filled.columns:
        return {"fills": fills, "win_rate": None, "avg_win": None, "avg_loss": None}

    pnl_samples = pd.to_numeric(filled["Est P/L"], errors="coerce").dropna()
    if pnl_samples.empty:
        return {"fills": fills, "win_rate": None, "avg_win": None, "avg_loss": None}

    wins = pnl_samples[pnl_samples > 0]
    losses = pnl_samples[pnl_samples < 0]
    win_rate = (len(wins) / len(pnl_samples)) * 100 if len(pnl_samples) else None

    return {
        "fills": fills,
        "win_rate": win_rate,
        "avg_win": wins.mean() if len(wins) else None,
        "avg_loss": losses.mean() if len(losses) else None,
    }


def build_blotter_df(orders_df: pd.DataFrame) -> pd.DataFrame:
    if orders_df.empty:
        return orders_df
    df = orders_df.copy()
    filled_mask = df["Status"].str.contains("filled", case=False, na=False)
    df = df[filled_mask].copy()
    if df.empty:
        return df
    qty = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
    px = pd.to_numeric(df["Filled Avg"], errors="coerce")
    signed = qty * px
    signed[df["Side"].str.contains("sell", case=False, na=False)] *= -1
    df["Signed Notional"] = signed
    df["Abs Notional"] = signed.abs()
    return df.sort_values("Created", ascending=False)


def symbol_attribution(positions_df: pd.DataFrame, blotter_df: pd.DataFrame, realized_total_est: float) -> pd.DataFrame:
    symbols = set()
    if not positions_df.empty:
        symbols.update(positions_df["symbol"].unique().tolist())
    if not blotter_df.empty:
        symbols.update(blotter_df["Symbol"].unique().tolist())

    rows = []
    total_notional = blotter_df["Abs Notional"].sum() if (not blotter_df.empty and "Abs Notional" in blotter_df.columns) else 0.0
    for s in sorted(symbols):
        unreal = 0.0
        if not positions_df.empty and s in positions_df["symbol"].values:
            unreal = float(positions_df.loc[positions_df["symbol"] == s, "unrealized_pl"].sum())

        sym_notional = 0.0
        if not blotter_df.empty and s in blotter_df["Symbol"].values and "Abs Notional" in blotter_df.columns:
            sym_notional = float(blotter_df.loc[blotter_df["Symbol"] == s, "Abs Notional"].sum())

        realized_est = (sym_notional / total_notional * realized_total_est) if total_notional > 0 else 0.0
        rows.append({"Symbol": s, "Unrealized P/L": unreal, "Realized P/L (est)": realized_est, "Turnover": sym_notional})

    out = pd.DataFrame(rows)
    if not out.empty:
        out["Total P/L (est)"] = out["Unrealized P/L"] + out["Realized P/L (est)"]
        out = out.sort_values("Total P/L (est)", ascending=False)
    return out


def drawdown_from_history(history) -> dict:
    if not history or not getattr(history, "equity", None):
        return {"max_drawdown": 0.0}
    eq = pd.Series([to_float(x) for x in history.equity])
    if eq.empty:
        return {"max_drawdown": 0.0}
    running_max = eq.cummax()
    dd = (eq - running_max) / running_max.replace(0, np.nan)
    return {"max_drawdown": float(dd.min() * 100) if not dd.empty else 0.0}


def alert_flags(pl_breakdown: dict, exposure: dict, drawdown: dict, equity: float) -> list[str]:
    alerts = []
    if abs(exposure.get("gross_pct", 0.0)) > 150:
        alerts.append("High gross exposure: above 150% of equity")
    if pl_breakdown.get("day_total", 0.0) < -(0.03 * equity):
        alerts.append("Day P/L below -3% of equity")
    if drawdown.get("max_drawdown", 0.0) < -5:
        alerts.append("Intraday max drawdown beyond -5%")
    return alerts
