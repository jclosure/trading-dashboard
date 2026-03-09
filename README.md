# Trading Dashboard (Loop + Joel)

A realtime paper-trading dashboard for Alpaca that shows:
- Account KPIs (equity, day P/L, buying power, cash)
- Open positions with unrealized P/L
- Pending/open orders
- Recent order activity
- Intraday equity chart
- Watchlist live quotes (bid/ask/spread)

## Run

```bash
cd ~/projects/trading-dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional if env vars already exported
streamlit run app/main.py
```

Open the local URL Streamlit prints (usually http://localhost:8501).

## Notes

- Uses Alpaca Paper account (`paper=True`).
- Reads credentials from environment or `.env`.
- Refresh interval is adjustable in sidebar.
