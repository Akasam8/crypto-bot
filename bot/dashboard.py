"""Dashboard data + local server.

The scan writes docs/data.js every hour; docs/index.html reads it. GitHub Pages serves the docs/
folder as the public website. To view it on your own PC instead:

    python -m bot.dashboard            # builds data.js and opens http://localhost:8000
"""
from __future__ import annotations

import csv
import json
import os
import sys
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .config import REPORTS_DIR, ROOT, STATE_DIR, costs, load_config
from .journal import Journal, load_state

DOCS_DIR = ROOT / "docs"
MAX_POINTS = 1500


def _load_json(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _equity(state_dir) -> list[dict]:
    p = state_dir / "equity.csv"
    if not p.exists():
        return []
    with open(p) as fh:
        rows = [{"t": r["time"], "b": round(float(r["balance_gbp"]), 2)} for r in csv.DictReader(fh)]
    if len(rows) > MAX_POINTS:
        step = len(rows) / MAX_POINTS
        rows = [rows[int(i * step)] for i in range(MAX_POINTS - 1)] + [rows[-1]]
    return rows


def build(cfg: dict, reports_dir=REPORTS_DIR, state_dir=STATE_DIR) -> dict:
    from .scan import settle  # local import: scan imports this module lazily too

    cost = costs(cfg)
    state = load_state(state_dir / "state.json")
    rows = Journal(state_dir / "trades.csv").rows()
    research = _load_json(reports_dir / "research.json", {})
    setups = _load_json(reports_dir / "survivors.json", [])
    decisions = _load_json(state_dir / "decisions.json", [])
    equity = _equity(state_dir)
    prices = state.get("last_prices", {})
    start = cfg["risk"]["pot_start_gbp"]

    closed = [r for r in rows if r["status"] == "closed"]
    active = [r for r in rows if r["status"] in ("open", "pending", "submitting")]
    open_list, open_pnl = [], 0.0
    for r in active:
        px = prices.get(r["coin"])
        pnl = settle(r, px, cost)["pnl_gbp"] if (px and r.get("entry_price") and r["status"] == "open") else 0.0
        open_pnl += pnl
        open_list.append({
            "coin": r["coin"].split("-")[0], "setup": r["setup"], "mode": r["mode"], "status": r["status"],
            "entry_time": r["entry_time"], "entry": r["entry_price"], "now": px, "size_gbp": r["size_gbp"],
            "pnl_gbp": round(pnl, 2), "pnl_pct": round(pnl / r["size_gbp"] * 100, 2) if r.get("size_gbp") else 0.0,
            "stop": r["sl_price"], "target": r["tp_price"], "exit_by": r["exit_by"],
            "unproven": "unproven" in (r.get("note") or ""),
        })
    realised = sum(r["pnl_gbp"] or 0 for r in closed)
    balance = equity[-1]["b"] if equity else start + realised + open_pnl
    trades = []
    for r in rows:
        if r["status"] == "cancelled":
            continue
        base = {"coin": r["coin"].split("-")[0], "setup": r["setup"], "mode": r["mode"], "size_gbp": r["size_gbp"]}
        trades.append({**base, "time": r["entry_time"], "side": "BUY", "price": r["entry_price"], "pnl_gbp": None, "reason": "signal"})
        if r["status"] == "closed":
            trades.append({**base, "time": r["exit_time"], "side": "SELL", "price": r["exit_price"],
                           "pnl_gbp": round(r["pnl_gbp"] or 0, 2), "pnl_pct": round(r["pnl_pct"] or 0, 2), "reason": r["exit_reason"]})
    trades.sort(key=lambda t: t["time"] or "", reverse=True)
    wins = sum(1 for r in closed if (r["pnl_gbp"] or 0) > 0)
    return {
        "generated": state.get("last_run") or "",
        "repo": os.environ.get("GITHUB_REPOSITORY", ""),
        "check_every_minutes": every if (every := int(os.environ.get("SCAN_EVERY_MINUTES") or 30)) in (15, 30, 60) else 30,
        "mode": cfg["mode"],
        "trading_enabled": bool(cfg.get("trading_enabled")),
        "halted": bool(state.get("halted")),
        "halt_reason": state.get("halt_reason", ""),
        "start_gbp": start,
        "balance_gbp": round(balance, 2),
        "realised_gbp": round(realised, 2),
        "open_pnl_gbp": round(open_pnl, 2),
        "closed_trades": len(closed),
        "wins": wins,
        "fees_paid_gbp": round(sum(r["fees_gbp"] or 0 for r in closed), 2),
        "round_trip_cost_pct": round((cost["a"][0] + cost["a"][1]) * 100, 2),
        "equity": equity,
        "open": open_list,
        "trades": trades[:200],
        "decisions": list(reversed(decisions[-100:])),
        "setups": setups,
        "research": {k: research.get(k) for k in ("data_from", "data_to", "configs_tested", "test_window")} | {"coins": len(research.get("coins") or [])},
        "risk": cfg["risk"],
    }


def write_data(cfg: dict, reports_dir=REPORTS_DIR, state_dir=STATE_DIR, docs_dir=None):
    docs_dir = docs_dir or DOCS_DIR
    docs_dir.mkdir(parents=True, exist_ok=True)
    data = build(cfg, reports_dir, state_dir)
    (docs_dir / "data.js").write_text("window.BOT_DATA = " + json.dumps(data, separators=(",", ":"), default=str) + ";\n")
    return data


def main():
    cfg = load_config()
    write_data(cfg)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = partial(SimpleHTTPRequestHandler, directory=str(DOCS_DIR))
    url = f"http://localhost:{port}/"
    print(f"Dashboard at {url}  (Ctrl+C to stop)")
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass
    ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


if __name__ == "__main__":
    main()
