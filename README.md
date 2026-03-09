# Trading Dashboard (Loop + Joel)

A realtime paper-trading dashboard for Alpaca that shows:
- Account KPIs (equity, day P/L, buying power, cash)
- Realized vs unrealized P/L breakdown (realized is estimated from day change)
- Open positions with unrealized P/L
- Pending/open orders
- Recent order activity
- Intraday equity chart + max drawdown
- Exposure view (gross/net + per-symbol chart)
- Performance snapshot (filled count, win-rate sample, avg win/loss sample)
- Watchlist live quotes (bid/ask/spread)
- Risk alerts (exposure, drawdown, day loss thresholds)

## Run

```bash
cd ~/projects/trading-dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional if env vars already exported
streamlit run app/main.py --server.address 0.0.0.0 --server.port 8501
```

## APEX automation

```bash
cd ~/projects/trading-dashboard
source .venv/bin/activate
PYTHONPATH=. python auto_rebalance.py
PYTHONPATH=. python monthly_review.py
```

Config file: `apex_config.yaml`
- `auto_execute: true` means paper orders are actually submitted.
- Keep `paper_trading` credentials only.

Open `http://<your-mac-lan-ip>:8501` from any device on your network.
(Example: `http://192.168.1.42:8501`)

## Always-on service (macOS)

The app is managed by LaunchAgent label `com.joel.trading-dashboard`.

Useful commands:
```bash
launchctl kickstart -k gui/$(id -u)/com.joel.trading-dashboard
launchctl print gui/$(id -u)/com.joel.trading-dashboard | grep -E "state =|pid =|last exit code"
```

Logs:
- `logs/launchd.out.log`
- `logs/launchd.err.log`

## Notes

- Uses Alpaca Paper account (`paper=True`).
- Reads credentials from environment or `.env`.
- Refresh interval is adjustable in sidebar.
