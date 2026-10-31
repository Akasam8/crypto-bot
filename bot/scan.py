"""Hourly scan: manage open positions, look for validated setups on the candle that just closed,
apply the risk rules, open paper (or live) trades, and post to Discord.

    python -m bot.scan
"""
from __future__ import annotations

import json
import sys
import traceback
import uuid

import numpy as np
import pandas as pd

from .backtest import exit_levels
from .config import REPORTS_DIR, STATE_DIR, costs, load_config
from .data import DAY, HOUR, complete_only, fill_gaps, gbp_per_usd, make_api
from .features import add_cross_sectional, btc_context, coin_features
from .journal import Journal, load_state, save_state
from .notify import send
from .project import write_journal_summary
from .risk import gate, size_position
from .strategies import EXIT_PROFILES, signal

HOURLY_BARS = 800
DAILY_BARS = 420
H1 = pd.Timedelta(hours=1)
ACTIVE = ("open", "pending", "submitting")


def iso(t) -> str:
    return pd.Timestamp(t).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def ts(s: str) -> pd.Timestamp:
    t = pd.Timestamp(s)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def uk(t, cfg) -> pd.Timestamp:
    return pd.Timestamp(t).tz_convert(cfg["uk_timezone"])


def fmt_uk(t, cfg) -> str:
    return uk(t, cfg).strftime("%H:%M %a %d %b")


def sym(pid: str) -> str:
    return pid.split("-")[0]


def price(x: float) -> str:
    return f"${x:,.2f}" if x >= 1 else f"${x:.4g}"


def money(x: float) -> str:
    return f"{'+' if x >= 0 else '-'}£{abs(x):.2f}"


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def fetch_market(api, pids, btc_pid, now):
    """Closed hourly candles up to the hour that just ended (gaps filled flat), the open of the
    candle now forming (= the backtest's entry price), and BTC daily closes for the regime."""
    last_closed = now.floor("h") - H1
    frames, next_open = {}, {}
    for pid in pids:
        raw = api.candles(pid, now - pd.Timedelta(hours=HOURLY_BARS), now, HOUR)
        df = complete_only(raw, HOUR, now)
        if len(df) < 250:
            continue
        frames[pid] = fill_gaps(df, end=last_closed)
        forming = raw[raw.index == last_closed + H1]
        if len(forming):
            next_open[pid] = float(forming["open"].iloc[0])
    daily = complete_only(api.candles(btc_pid, now - pd.Timedelta(days=DAILY_BARS), now, DAY), DAY, now)
    return frames, daily["close"], next_open, last_closed


def paper_check(pos: dict, f: pd.DataFrame, now: pd.Timestamp):
    """Walk closed candles since the last check with exactly the backtest's exit rules."""
    entry_t = ts(pos["entry_time"])
    H = int(pos["hold_hours"])
    last = ts(pos["last_checked"]) if pos.get("last_checked") else entry_t - H1
    sl, tp = pos["sl_price"], pos["tp_price"]
    bars = f[(f.index > last) & (f.index >= entry_t) & (f.index < entry_t + H * H1)]
    for t, row in bars.iterrows():
        if row["low"] <= sl:
            return {"exit_price": float(min(row["open"], sl)), "exit_reason": "stop", "exit_time": iso(t + H1)}
        if tp and np.isfinite(tp) and row["high"] >= tp:
            return {"exit_price": float(tp), "exit_reason": "target", "exit_time": iso(t + H1)}
        if t >= entry_t + (H - 1) * H1:
            return {"exit_price": float(row["close"]), "exit_reason": "time", "exit_time": iso(t + H1)}
        last = t
    if now >= ts(pos["exit_by"]) + 3 * H1 and len(f):  # data gap safety net
        return {"exit_price": float(f["close"].iloc[-1]), "exit_reason": "time", "exit_time": iso(f.index[-1] + H1)}
    return {"last_checked": iso(last)}


def settle(pos: dict, exit_price: float, cost: dict) -> dict:
    c_in, c_out = cost["a"]
    size, entry = pos["size_gbp"], pos["entry_price"]
    net = exit_price * (1 - c_out) / (entry * (1 + c_in)) - 1
    fees = size * c_in / (1 + c_in) + size * (exit_price / entry) * c_out / (1 + c_in)
    return {"pnl_gbp": round(size * net, 4), "pnl_pct": round(net * 100, 4), "fees_gbp": round(fees, 4)}


def unrealised(pos: dict, price, cost: dict) -> float:
    if pos["status"] != "open" or not pos.get("entry_price") or not price:
        return 0.0
    return settle(pos, price, cost)["pnl_gbp"]


def run(cfg: dict, api, now: pd.Timestamp, notify=send, broker=None, can_open_live: bool = False,
        reports_dir=REPORTS_DIR, state_dir=STATE_DIR, docs_dir=None) -> dict:
    now = pd.Timestamp(now).tz_convert("UTC")
    mode = cfg["mode"]
    cost = costs(cfg)
    rt_cost = cost["a"][0] + cost["a"][1]
    state_path = state_dir / "state.json"
    state = load_state(state_path)
    journal = Journal(state_dir / "trades.csv")
    research = load_json(reports_dir / "research.json", {})
    survivors = load_json(reports_dir / "survivors.json", [])
    allow_candidates = mode == "PAPER" and cfg.get("paper_trades_candidates", True)
    setups = [s for s in survivors if s.get("status", "validated") == "validated" or (allow_candidates and s.get("status") == "candidate")]
    btc_pid = f"BTC-{cfg['data']['quote']}"
    pids = research.get("coins") or [btc_pid]
    live = bool(can_open_live and broker is not None and mode == "LIVE_AUTO")
    log = {"opened": [], "closed": [], "skipped": [], "messages": 0}

    def say(text):
        try:
            notify(text)
        except Exception as e:  # noqa: BLE001  (a Discord problem must never stop trade handling)
            print(f"[notify] failed: {e}")
        log["messages"] += 1

    frames, daily, next_open, last_closed = fetch_market(api, pids, btc_pid, now)
    if btc_pid not in frames:
        raise RuntimeError("couldn't load BTC candles from Coinbase")
    ctx = btc_context(frames[btc_pid], daily)
    feats = add_cross_sectional({pid: coin_features(df, ctx) for pid, df in frames.items()})
    gbp = gbp_per_usd(api, cfg["data"]["fallback_gbpusd"])

    # 1. manage open positions (live ones are always reconciled when a broker exists, even with trading off)
    for pos in journal.rows():
        if pos["status"] not in ACTIVE:
            continue
        try:
            if pos["mode"] == "LIVE_AUTO":
                if broker is None:
                    say(f"⚠️ Live position {sym(pos['coin'])} can't be checked: no Coinbase key available. Its stop and target still sit on Coinbase.")
                    continue
                upd = broker.reconcile(pos, now, gbp, cost)
            else:
                f = feats.get(pos["coin"])
                if f is None:
                    continue
                upd = paper_check(pos, f, now)
                if "exit_price" in upd:
                    upd.update(settle(pos, upd["exit_price"], cost))
                    upd["status"] = "closed"
        except Exception as e:  # noqa: BLE001
            say(f"⚠️ Couldn't update {sym(pos['coin'])} position: {type(e).__name__}: {str(e)[:200]}")
            continue
        if upd:
            journal.update(pos["id"], **upd)
            journal.save()
        if upd.get("status") == "closed":
            p = {**pos, **upd}
            held = (ts(p["exit_time"]) - ts(p["entry_time"])) / H1 if p.get("exit_time") else 0
            icon = "✅" if p["pnl_gbp"] > 0 else "🔻"
            say(f"{icon} {p['mode']} SOLD {sym(p['coin'])} ({p['exit_reason']}): {money(p['pnl_gbp'])} ({p['pnl_pct']:+.2f}%) after fees, held {held:.0f}h. Setup: {p['setup']}.")
            log["closed"].append(p["id"])

    # 2. pot and limits
    rows = journal.rows()
    closed = [r for r in rows if r["status"] == "closed"]
    active = [r for r in rows if r["status"] in ACTIVE]
    last_px = {pid: float(f["close"].iloc[-1]) for pid, f in feats.items()}
    open_pnl = sum(unrealised(r, last_px.get(r["coin"]), cost) for r in active)
    if live:
        pot = broker.portfolio_value_gbp(gbp)
    else:
        pot = cfg["risk"]["pot_start_gbp"] + sum(r["pnl_gbp"] or 0 for r in closed) + open_pnl
    free = pot - sum(r["size_gbp"] or 0 for r in active)
    today = uk(now, cfg).date()
    trades_today = sum(1 for r in rows if r["status"] != "cancelled" and r.get("entry_time") and uk(ts(r["entry_time"]), cfg).date() == today)
    realised_today = sum(r["pnl_gbp"] or 0 for r in closed if r.get("exit_time") and uk(ts(r["exit_time"]), cfg).date() == today)
    loss_today = realised_today + min(0.0, open_pnl)  # open losses count toward the daily limit too
    if pot <= cfg["risk"]["pot_floor_gbp"] and not state["halted"]:
        state.update(halted=True, halt_reason=f"pot fell to £{pot:.2f} (floor £{cfg['risk']['pot_floor_gbp']:.0f})")
        save_state(state_path, state)
        say(f"🛑 Bot halted: {state['halt_reason']}. No new trades until you run the Resume workflow. Review the journal first.")

    # 3. new signals on the candle that just closed
    candidates = []
    for s in setups:
        tp_mult, sl_mult = EXIT_PROFILES[s["profile"]]
        for pid, f in feats.items():
            if f.index[-1] != last_closed or f["volume"].iloc[-1] <= 0:
                continue  # stale or no trades in the last hour
            if not signal(s["family"], s["params"], f, is_btc=(pid == btc_pid))[-1]:
                continue
            sigma = float(f["sigma"].iloc[-1])
            if not np.isfinite(sigma):
                continue
            tp_pct, sl_pct = (float(x[0]) for x in exit_levels(np.array([sigma]), s["hold"], tp_mult, sl_mult))
            sig_t = last_closed + H1
            if journal.has(s["key"], pid, iso(sig_t)):
                continue
            candidates.append({"s": s, "pid": pid, "tp_pct": tp_pct, "sl_pct": sl_pct, "sig_t": sig_t})

    for c in candidates:
        s, pid = c["s"], c["pid"]
        try:
            active = [r for r in journal.rows() if r["status"] in ACTIVE]
            d = gate(state, pot, active, trades_today, loss_today, pid, cfg)
            if d.ok:
                d = size_position(pot, free, c["sl_pct"], rt_cost, cfg)
            product = broker.product_id(pid) if live else pid
            if d.ok:
                tk = (broker.best_bid_ask(product) if live else api.ticker(pid)) or {}
                bid, ask = float(tk.get("bid") or 0), float(tk.get("ask") or 0)
                if bid <= 0 or ask <= 0:
                    d.ok, d.reason = False, "no live price"
                elif (ask - bid) / ((ask + bid) / 2) * 100 > cfg["risk"]["max_spread_pct"]:
                    d.ok, d.reason = False, f"spread {(ask - bid) / ((ask + bid) / 2) * 100:.2f}% too wide"
            if not d.ok:
                log["skipped"].append(f"{sym(pid)} {s['title']}: {d.reason}")
                continue
            # paper uses the forming candle's open, exactly like the backtest; live uses the real fill
            entry = ask if live else next_open.get(pid, ask)
            sl_px = entry * (1 - c["sl_pct"])
            tp_px = entry * (1 + c["tp_pct"]) if np.isfinite(c["tp_pct"]) else None
            exit_by = c["sig_t"] + s["hold"] * H1
            rec = {
                "id": uuid.uuid4().hex[:10], "mode": "LIVE_AUTO" if live else ("LIVE_MANUAL" if mode == "LIVE_MANUAL" else "PAPER"),
                "coin": pid, "product": product, "setup": s["title"], "setup_key": s["key"], "signal_time": iso(c["sig_t"]),
                "entry_time": iso(c["sig_t"]), "entry_price": entry, "size_gbp": d.size_gbp,
                "units": d.size_gbp / gbp / (entry * (1 + cost["a"][0])), "risk_gbp": d.risk_gbp, "sl_price": sl_px,
                "tp_price": tp_px, "hold_hours": s["hold"], "exit_by": iso(exit_by), "status": "submitting" if live else "open",
                "note": ("unproven setup; " if s.get("status") == "candidate" else "") + ("" if live else f"ask at scan {ask:.6g}"),
            }
            journal.add(rec)
            journal.save()  # written before any order goes out, so nothing can be lost
            if live:
                order = broker.open_position(product, d.size_gbp / gbp, ask, sl_px, tp_px, client_order_id=f"{s['key']}|{pid}|{iso(c['sig_t'])}")
                if not order.get("ok"):
                    journal.update(rec["id"], status="cancelled", note=f"rejected: {order.get('error')}")
                    journal.save()
                    log["skipped"].append(f"{sym(pid)} {s['title']}: order rejected ({order.get('error')})")
                    continue
                journal.update(rec["id"], status="pending", order_id=order["order_id"], entry_price=order["limit_price"], units=order["base_size"])
                journal.save()
                rec["entry_price"] = order["limit_price"]
        except Exception as e:  # noqa: BLE001
            log["skipped"].append(f"{sym(pid)} {s['title']}: error {type(e).__name__}: {str(e)[:120]}")
            continue
        trades_today += 1
        free -= d.size_gbp
        log["opened"].append(rec["id"])
        t = s["test"]
        tag = {"PAPER": "TEST (fake money)", "LIVE_MANUAL": "SIGNAL (place it yourself)", "LIVE_AUTO": "LIVE ORDER"}[rec["mode"]]
        tp_txt = f"Target {price(tp_px)} (+{c['tp_pct'] * 100:.1f}%)" if tp_px else "No target"
        say(
            f"🟢 {tag}: BUY {sym(pid)} ({s['title']})\n"
            f"Entry {price(rec['entry_price'])} · £{d.size_gbp:.2f} position · £{d.risk_gbp:.2f} at risk\n"
            f"{tp_txt} · Stop {price(sl_px)} (-{c['sl_pct'] * 100:.1f}%) · Sell by {fmt_uk(exit_by, cfg)} UK\n"
            f"{'Unproven setup, past year' if s.get('status') == 'candidate' else 'Backtest test period'}: {t['win_rate'] * 100:.0f}% wins, {t['avg_net_pct']:+.2f}% avg after fees, {t['n']} trades\n"
            f"BTC above its 50 day average: {'yes' if f_up(feats[btc_pid]) else 'no'}"
        )
    if log["skipped"]:
        say("⏭️ Signals skipped this hour: " + "; ".join(log["skipped"]))

    # 4. summaries
    local = uk(now, cfg)
    if local.hour >= cfg["daily_summary_hour_uk"] and state["last_daily_summary"] != str(today):
        say(daily_summary(cfg, journal, setups, pot, last_px, cost, today, state, mode == "LIVE_AUTO" and not live))
        state["last_daily_summary"] = str(today)
        week = str((local - pd.Timedelta(days=local.weekday())).date())
        if local.weekday() == cfg["weekly_summary_weekday"] and state["last_weekly_summary"] != week:
            say(weekly_summary(journal, setups))
            state["last_weekly_summary"] = week

    # 5. decision log + balance history for the dashboard
    rows = journal.rows()
    closed = [r for r in rows if r["status"] == "closed"]
    active = [r for r in rows if r["status"] in ACTIVE]
    open_pnl = sum(unrealised(r, last_px.get(r["coin"]), cost) for r in active)
    realised = sum(r["pnl_gbp"] or 0 for r in closed)
    balance = broker.portfolio_value_gbp(gbp) if live else cfg["risk"]["pot_start_gbp"] + realised + open_pnl
    by_id = {r["id"]: r for r in rows}
    parts = [f"Sold {sym(by_id[i]['coin'])} ({by_id[i]['exit_reason']}, {money(by_id[i]['pnl_gbp'])})" for i in log["closed"] if i in by_id]
    parts += [f"Bought {sym(by_id[i]['coin'])} ({by_id[i]['setup']}) at {price(by_id[i]['entry_price'])}" for i in log["opened"] if i in by_id]
    if not parts:
        if state.get("halted"):
            parts.append(f"No trade: bot is halted ({state['halt_reason']})")
        elif not setups:
            parts.append("No trade: no setup is approved for this mode yet")
        elif log["skipped"]:
            reasons = sorted({x.split(": ", 1)[-1] for x in log["skipped"]})
            parts.append(f"No trade: {len(log['skipped'])} signal(s) skipped ({'; '.join(reasons)})")
        else:
            parts.append(f"No trade: none of the {len(setups)} setups fired on the {uk(last_closed, cfg).strftime('%H:%M')} candle")
    decision = {
        "time": iso(now), "candle": iso(last_closed), "mode": mode, "btc_trend": "up" if f_up(feats[btc_pid]) else "down",
        "coins_checked": len(feats), "setups": len(setups), "text": ". ".join(parts),
        "opened": log["opened"], "closed": log["closed"], "skipped": log["skipped"],
    }
    decisions = load_json(state_dir / "decisions.json", [])
    decisions = [d for d in decisions if d.get("candle") != decision["candle"]] + [decision]
    (state_dir / "decisions.json").write_text(json.dumps(decisions[-500:], indent=1))
    eq_path = state_dir / "equity.csv"
    if not eq_path.exists():
        eq_path.write_text("time,balance_gbp,realised_gbp,open_gbp\n")
    with open(eq_path, "a") as fh:
        fh.write(f"{iso(now)},{balance:.4f},{realised:.4f},{open_pnl:.4f}\n")
    state["last_prices"] = {k: round(v, 10) for k, v in last_px.items()}
    state["gbp_per_usd"] = round(gbp, 6)

    state["last_run"] = iso(now)
    state["consecutive_errors"] = 0
    journal.save()
    save_state(state_path, state)
    write_journal_summary(cfg)
    try:
        from .dashboard import write_data

        write_data(cfg, reports_dir=reports_dir, state_dir=state_dir, docs_dir=docs_dir)
    except Exception as e:  # noqa: BLE001
        print(f"[dashboard] couldn't update: {e}")
    log["pot_gbp"] = round(balance, 2)
    log["decision"] = decision["text"]
    return log


def f_up(f: pd.DataFrame) -> bool:
    return bool(f["btc_up50"].iloc[-1] == 1)


def daily_summary(cfg, journal, survivors, pot, last_px, cost, today, state, orders_off) -> str:
    rows = journal.rows()
    closed = [r for r in rows if r["status"] == "closed"]
    today_closed = [r for r in closed if r.get("exit_time") and uk(ts(r["exit_time"]), cfg).date() == today]
    active = [r for r in rows if r["status"] in ACTIVE]
    L = [f"📊 Daily summary {today.strftime('%a %d %b')} ({cfg['mode']}{', real orders OFF' if orders_off else ''})"]
    L.append(f"Pot £{pot:.2f} (started £{cfg['risk']['pot_start_gbp']:.0f}). Today: {money(sum(r['pnl_gbp'] for r in today_closed))} from {len(today_closed)} closed trade(s).")
    for r in active:
        u = unrealised(r, last_px.get(r["coin"]), cost)
        L.append(f"Open: {sym(r['coin'])} ({r['setup']}) since {fmt_uk(ts(r['entry_time']), cfg)}, now {money(u)}, sell by {fmt_uk(ts(r['exit_by']), cfg)}.")
    if closed:
        tot = sum(r["pnl_gbp"] for r in closed)
        L.append(f"All time: {len(closed)} trades, {sum(r['pnl_gbp'] > 0 for r in closed) / len(closed) * 100:.0f}% wins, {money(tot)}.")
    if state.get("halted"):
        L.append(f"🛑 HALTED: {state['halt_reason']}")
    if survivors:
        tags = [s["title"] + (" (unproven, test only)" if s.get("status") == "candidate" else "") for s in survivors]
        L.append("Setups being traded: " + ", ".join(tags) + ".")
    else:
        L.append("No setup is approved for this mode, so the bot is watching but not trading. It reruns the backtest on the 1st of each month.")
    return "\n".join(L)


def weekly_summary(journal, survivors) -> str:
    closed = journal.closed()
    L = ["🗓️ Weekly check: journal vs backtest"]
    if not closed:
        L.append("No closed trades yet.")
    by = {}
    for r in closed:
        by.setdefault(r["setup_key"], []).append(r)
    for s in survivors:
        rs = by.get(s["key"], [])
        bt = s["test"]
        if not rs:
            L.append(f"{s['title']}: no trades yet (backtest: {bt['win_rate'] * 100:.0f}% wins, {bt['avg_net_pct']:+.2f}% avg).")
            continue
        n = len(rs)
        wr = sum(r["pnl_pct"] > 0 for r in rs) / n
        avg = sum(r["pnl_pct"] for r in rs) / n
        flag = ""
        if n >= 30 and (avg < 0 or wr < bt["win_rate"] - 0.10):
            flag = " ⚠️ drifting well below the backtest, consider pausing it"
        L.append(f"{s['title']}: {n} trades, {wr * 100:.0f}% wins, {avg:+.2f}% avg (backtest {bt['win_rate'] * 100:.0f}%, {bt['avg_net_pct']:+.2f}%){flag}.")
    return "\n".join(L)


def main():
    cfg = load_config()
    state_path = STATE_DIR / "state.json"
    try:
        live_rows = any(r["mode"] == "LIVE_AUTO" and r["status"] in ACTIVE for r in Journal(STATE_DIR / "trades.csv").rows())
        want_live = cfg["mode"] == "LIVE_AUTO" and cfg.get("trading_enabled")
        broker, can_open = None, False
        if want_live or live_rows:
            from .broker import Broker, SafetyError

            broker = Broker(cfg)
            if want_live:
                try:
                    broker.check_permissions()
                    can_open = True
                except SafetyError as e:
                    state = load_state(state_path)
                    state.update(halted=True, halt_reason=f"API key check failed: {e}")
                    save_state(state_path, state)
                    send(f"🛑 Live trading blocked: {e}. Existing positions are still managed.")
        out = run(cfg, make_api(), pd.Timestamp.now(tz="UTC"), broker=broker, can_open_live=can_open)
        print(json.dumps(out))
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        state = load_state(state_path)
        state["consecutive_errors"] = int(state.get("consecutive_errors", 0)) + 1
        msg = f"⚠️ Scan failed ({state['consecutive_errors']} in a row): {type(e).__name__}: {str(e)[:300]}"
        if getattr(e, "halt", False) or (cfg["mode"] == "LIVE_AUTO" and state["consecutive_errors"] >= 3):
            state.update(halted=True, halt_reason=f"{type(e).__name__}: {str(e)[:200]}")
            msg += "\n🛑 Bot halted for safety."
        save_state(state_path, state)
        send(msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
