from __future__ import annotations

from alpaca_client import AlpacaGateway, load_config
from apex_engine import ApexEngine


def main():
    cfg = load_config()
    gw = AlpacaGateway(cfg)
    engine = ApexEngine(gw, log_dir="logs")

    cycle = engine.recommendations()
    cycle_path = engine.save_cycle(cycle)
    log_path = engine.trade_log_template()

    print("APEX cycle complete")
    print("Cycle:", cycle_path)
    print("Decision log:", log_path)
    print("Recommendations:")
    for r in cycle.get("recommendations", []):
        print("-", r)


if __name__ == "__main__":
    main()
