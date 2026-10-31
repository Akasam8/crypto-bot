"""Run the full research: fetch data, sweep setups, validate, write reports.

    python -m bot.run_backtest              # real Coinbase data (needs internet)
    python -m bot.run_backtest --synthetic  # fake no-edge data, for offline checks
"""
from __future__ import annotations

import argparse
import json
import time

from .config import DATA_DIR, REPORTS_DIR, load_config
from .evaluate import prepare, run_research
from .notes import market_notes
from .report import write_all


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true", help="use fake random walk data")
    ap.add_argument("--coins", type=int, default=None, help="override universe size")
    ap.add_argument("--out", default=None, help="report folder (default reports/)")
    ap.add_argument("--notify", action="store_true", help="post the verdict to Discord")
    args = ap.parse_args(argv)

    t0 = time.time()
    cfg = load_config()
    if args.coins:
        cfg["data"]["universe_size"] = args.coins
    if args.synthetic:
        from .synthetic import synthetic_universe

        universe = synthetic_universe(n_coins=args.coins or 6, days=cfg["data"]["history_days"])
    else:
        from .data import CandleStore, build_universe, make_api

        api = make_api()
        universe = build_universe(api, cfg, CandleStore(DATA_DIR / "hourly"))
    btc = f"BTC-{cfg['data']['quote']}"
    u = prepare(universe, btc)
    research = run_research(u, cfg)
    notes = market_notes(universe, btc, cfg)
    out = REPORTS_DIR if args.out is None else args.out
    write_all(research, notes, cfg, out)
    if args.out is None and not args.synthetic:
        from .project import write_project_pack

        write_project_pack(cfg)
    surv = [f["family"] for f in research["families"] if f["survived"]]
    if args.notify:
        from .notify import send

        lines = [f"🧪 Backtest finished on {len(u.pids)} coins ({research['data_from']} to {research['data_to']}), {research['configs_tested']} setup variations tried."]
        for f in research["families"]:
            ts = f.get("test_stats") or {}
            if f["survived"]:
                lines.append(f"✅ {f['title']}: {ts['n']} test trades, {ts['win_rate'] * 100:.0f}% wins, {ts['avg_net_pct']:+.2f}% avg after fees")
            else:
                lines.append(f"❌ {f['title']}: {(f['fail_reasons'] or ['failed'])[0]}")
        lines.append("Full report: reports/backtest_report.md in the repo.")
        send("\n".join(lines))
    print(json.dumps({"survivors": surv, "configs_tested": research["configs_tested"], "coins": len(u.pids), "seconds": round(time.time() - t0)}))


if __name__ == "__main__":
    main()
