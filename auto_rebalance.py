from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from app.alpaca_client import AlpacaGateway, load_config
from app.analytics import build_positions_df
from app.apex_engine import ApexEngine


@dataclass
class ExecConfig:
    auto_execute: bool
    max_position_pct: float
    cash_floor_pct: float
    trim_bottom_quartile_pct: float
    add_top_quartile_pct: float
    min_order_notional_usd: float
    allowlist: list[str]
    blocklist: list[str]


def load_exec_config(path: str | Path = "apex_config.yaml") -> ExecConfig:
    raw = yaml.safe_load(Path(path).read_text()) if Path(path).exists() else {}
    a = (raw or {}).get("apex", {})
    return ExecConfig(
        auto_execute=bool(a.get("auto_execute", False)),
        max_position_pct=float(a.get("max_position_pct", 0.15)),
        cash_floor_pct=float(a.get("cash_floor_pct", 0.08)),
        trim_bottom_quartile_pct=float(a.get("trim_bottom_quartile_pct", 0.25)),
        add_top_quartile_pct=float(a.get("add_top_quartile_pct", 0.10)),
        min_order_notional_usd=float(a.get("min_order_notional_usd", 50)),
        allowlist=[s.upper() for s in a.get("symbols_allowlist", [])],
        blocklist=[s.upper() for s in a.get("symbols_blocklist", [])],
    )


def symbol_allowed(symbol: str, cfg: ExecConfig) -> bool:
    s = symbol.upper()
    if cfg.allowlist and s not in cfg.allowlist:
        return False
    if s in cfg.blocklist:
        return False
    return True


def load_regime_overrides(path: str | Path = "apex_overrides.yaml") -> dict[str, Any]:
    if not Path(path).exists():
        return {}
    raw = yaml.safe_load(Path(path).read_text()) or {}
    return raw.get("regime", {})


def run_once() -> dict[str, Any]:
    env = load_config()
    gw = AlpacaGateway(env)
    cfg = load_exec_config("apex_config.yaml")
    regime = load_regime_overrides("apex_overrides.yaml")
    engine = ApexEngine(gw, log_dir="logs")

    cycle = engine.recommendations()
    account = gw.account()
    equity = float(account.equity)
    cash = float(account.cash)
    min_cash = equity * cfg.cash_floor_pct

    positions_df = build_positions_df(gw.positions())
    mv_by_symbol = {
        str(r["symbol"]).upper(): float(r["market_value"]) for _, r in positions_df.iterrows()
    } if not positions_df.empty else {}

    actions = []
    for rec in cycle.get("recommendations", []):
        sym = rec["symbol"].upper()
        if not symbol_allowed(sym, cfg):
            continue

        if rec["action"] == "TRIM":
            notional = max(0.0, mv_by_symbol.get(sym, 0.0) * cfg.trim_bottom_quartile_pct)
            if notional < cfg.min_order_notional_usd:
                continue
            if cfg.auto_execute:
                order = gw.trading.submit_order(
                    order_data=MarketOrderRequest(
                        symbol=sym,
                        notional=round(notional, 2),
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY,
                    )
                )
                actions.append({"action": "SELL", "symbol": sym, "notional": notional, "order_id": str(order.id)})

        if rec["action"] == "ADD":
            room = max(0.0, cash - min_cash)
            if room < cfg.min_order_notional_usd:
                continue
            current_mv = mv_by_symbol.get(sym, 0.0)
            max_for_symbol = equity * cfg.max_position_pct
            cap_room = max(0.0, max_for_symbol - current_mv)
            target = min(room, equity * cfg.add_top_quartile_pct, cap_room)
            if target < cfg.min_order_notional_usd:
                continue
            if cfg.auto_execute:
                order = gw.trading.submit_order(
                    order_data=MarketOrderRequest(
                        symbol=sym,
                        notional=round(target, 2),
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY,
                    )
                )
                actions.append({"action": "BUY", "symbol": sym, "notional": target, "order_id": str(order.id)})

    # Regime overlays (e.g., oil shock)
    if regime.get("active"):
        # Optional funding trims first
        trim_syms = [s.upper() for s in regime.get("funding", {}).get("trim_symbols", [])]
        trim_pct_each = float(regime.get("funding", {}).get("trim_pct_each", 0.0))
        for sym in trim_syms:
            current_mv = mv_by_symbol.get(sym, 0.0)
            notional = current_mv * trim_pct_each
            if notional >= cfg.min_order_notional_usd and cfg.auto_execute and symbol_allowed(sym, cfg):
                order = gw.trading.submit_order(
                    order_data=MarketOrderRequest(
                        symbol=sym,
                        notional=round(notional, 2),
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY,
                    )
                )
                actions.append({"action": "SELL", "symbol": sym, "notional": notional, "order_id": str(order.id), "tag": "regime_funding"})
                cash += notional

        overlays = regime.get("tactical_overlays", [])
        for ov in overlays:
            sym = str(ov.get("symbol", "")).upper()
            if not sym or not symbol_allowed(sym, cfg):
                continue
            target_pct = float(ov.get("target_portfolio_pct", 0.0))
            desired = equity * target_pct
            current_mv = mv_by_symbol.get(sym, 0.0)
            add_need = max(0.0, desired - current_mv)
            room = max(0.0, cash - min_cash)
            cap_room = max(0.0, equity * cfg.max_position_pct - current_mv)
            notional = min(add_need, room, cap_room)
            if notional < cfg.min_order_notional_usd:
                continue
            if cfg.auto_execute:
                order = gw.trading.submit_order(
                    order_data=MarketOrderRequest(
                        symbol=sym,
                        notional=round(notional, 2),
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY,
                    )
                )
                actions.append({"action": "BUY", "symbol": sym, "notional": notional, "order_id": str(order.id), "tag": "regime_overlay"})
                cash -= notional

    cycle["regime"] = regime
    cycle["executed_actions"] = actions
    cycle_path = engine.save_cycle(cycle)
    return {"cycle_path": str(cycle_path), "actions": actions}


if __name__ == "__main__":
    result = run_once()
    print("Auto rebalance complete")
    print(result)
