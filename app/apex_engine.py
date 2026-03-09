from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from app.alpaca_client import AlpacaGateway
from app.analytics import build_positions_df


@dataclass
class PositionScore:
    symbol: str
    score: float
    position_yield: float
    momentum: float
    sharpe_like: float


class ApexEngine:
    def __init__(self, gw: AlpacaGateway, log_dir: str = "logs") -> None:
        self.gw = gw
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _momentum_score(self, symbol: str) -> float:
        bars = self.gw.recent_bars(symbol, limit=60)
        df = getattr(bars, "df", pd.DataFrame())
        if df.empty or "close" not in df.columns:
            return 0.0
        closes = pd.to_numeric(df["close"], errors="coerce").dropna().values
        if len(closes) < 50:
            return 0.0
        sma20 = closes[-20:].mean()
        sma50 = closes[-50:].mean()
        return float((sma20 - sma50) / sma50) if sma50 else 0.0

    def score_positions(self) -> list[PositionScore]:
        positions = self.gw.positions()
        df = build_positions_df(positions)
        if df.empty:
            return []

        out: list[PositionScore] = []
        for _, row in df.iterrows():
            symbol = row["symbol"]
            position_yield = float(row["unrealized_pl"] / row["cost_basis"]) if row["cost_basis"] else 0.0
            momentum = self._momentum_score(symbol)
            vol = abs(float(row["unrealized_pl_pct"])) / 100.0 + 1e-6
            sharpe_like = position_yield / vol
            score = (position_yield + momentum) / max(vol, 1e-6)
            out.append(PositionScore(symbol=symbol, score=score, position_yield=position_yield, momentum=momentum, sharpe_like=sharpe_like))
        return sorted(out, key=lambda x: x.score, reverse=True)

    def recommendations(self) -> dict:
        account = self.gw.account()
        equity = float(account.equity)
        scores = self.score_positions()
        n = len(scores)
        top = scores[: max(1, n // 4)] if n else []
        bottom = scores[-max(1, n // 4) :] if n else []

        recs = []
        for p in bottom:
            recs.append({"action": "TRIM", "symbol": p.symbol, "pct": 0.25, "reason": "Bottom quartile composite score"})
        for p in top:
            recs.append({"action": "ADD", "symbol": p.symbol, "pct": 0.10, "reason": "Top quartile composite score"})

        # Guardrails from strategy
        max_position = 0.15 * equity
        pos_df = build_positions_df(self.gw.positions())
        if not pos_df.empty:
            for _, r in pos_df.iterrows():
                if float(r["market_value"]) > max_position:
                    recs.append({"action": "TRIM", "symbol": r["symbol"], "pct": 0.20, "reason": "Position exceeds 15% max"})

        return {
            "timestamp": datetime.now().isoformat(),
            "equity": equity,
            "scores": [s.__dict__ for s in scores],
            "recommendations": recs,
        }

    def save_cycle(self, cycle: dict) -> Path:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.log_dir / f"apex-cycle-{ts}.json"
        pd.Series(cycle).to_json(path)
        return path

    def trade_log_template(self) -> Path:
        ts = datetime.now().strftime("%Y-%m")
        path = self.log_dir / f"decision-log-{ts}.md"
        if not path.exists():
            path.write_text(
                "# APEX Decision Log\n\n"
                "## Entry Template\n"
                "DATE:\nACTION:\nINSTRUMENT:\nSIZE:\nRATIONALE:\nEXPECTED OUTCOME:\nRISK SCENARIO:\nSTOP CONDITION:\n\n"
            )
        return path
