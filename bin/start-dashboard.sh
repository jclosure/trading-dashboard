#!/bin/zsh
set -euo pipefail
cd /Users/loop/projects/trading-dashboard
source .venv/bin/activate
exec streamlit run app/main.py --server.address 0.0.0.0 --server.port 8501
