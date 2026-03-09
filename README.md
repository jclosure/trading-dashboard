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

Open `http://<your-mac-lan-ip>:8501` from any device on your network.
(Example: `http://192.168.1.42:8501`)

## Notes

- Uses Alpaca Paper account (`paper=True`).
- Reads credentials from environment or `.env`.
- Refresh interval is adjustable in sidebar.
