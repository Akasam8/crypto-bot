"""Turn research results into plain English reports, strategy cards, the playbook and survivors.json."""
from __future__ import annotations

import json
import math
from pathlib import Path

from .backtest import EXIT_PROFILES

PROFILE_TEXT = {
    "tight": "target about 1x expected move, stop about 1x",
    "runner": "target about 2x expected move, stop about 1x",
    "timed": "no target, stop about 2x expected move, otherwise sell at the max hold time",
}


def _pct(x, d=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "n/a"
    return f"{x:+.{d}f}%"


def _num(x, d=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    if isinstance(x, float) and math.isinf(x):
        return "inf"
    return f"{x:.{d}f}"


def _json_default(o):
    try:
        import numpy as np

        if isinstance(o, np.generic):
            return o.item()
    except ImportError:
        pass
    return str(o)


STAT_KEYS = ("n", "win_rate", "avg_net_pct", "profit_factor", "positive_month_share", "typical_stop_pct", "typical_target_pct", "worst_losing_streak")


def survivors_payload(research: dict, max_candidates: int = 3) -> list[dict]:
    """Setups the scanner may trade. 'validated' passed every check (live allowed);
    'candidate' only looked good on the past year (test mode only)."""
    out = []
    for f in research["families"]:
        if not f.get("survived"):
            continue
        ts = f["test_stats"]
        out.append({
            "status": "validated", "family": f["family"], "title": f["title"], "rule": f["rule"], "key": f["selected"],
            "params": f["config"]["params"], "hold": f["config"]["hold"], "profile": f["config"]["profile"],
            "test": {k: ts.get(k) for k in STAT_KEYS}, "random_p_value": f["random_baseline"].get("p_value"),
        })
    out.sort(key=lambda s: -(s["test"]["avg_net_pct"] or 0))
    cands = []
    for f in research["families"]:
        c = f.get("candidate")
        if f.get("survived") or not c:
            continue
        ys, rs = c["year_stats"], c["recent_stats"]
        cands.append({
            "status": "candidate", "family": f["family"], "title": f["title"], "rule": c["rule"], "key": c["key"],
            "params": c["config"]["params"], "hold": c["config"]["hold"], "profile": c["config"]["profile"],
            "test": {k: ys.get(k) for k in STAT_KEYS}, "recent": {k: rs.get(k) for k in ("n", "win_rate", "avg_net_pct")},
        })
    cands.sort(key=lambda s: -(s["test"]["avg_net_pct"] or 0))
    return out + cands[:max_candidates]


def verdict_text(research: dict) -> str:
    surv = [f for f in research["families"] if f.get("survived")]
    n_fam = len(research["families"])
    cands = [f for f in research["families"] if f.get("candidate") and not f.get("survived")]
    if not surv:
        tail = (f" Test mode will still trade the best {min(3, len(cands))} unproven setups with fake money, so you can watch how they do against real prices and fees. None of them can go live." if cands
                else " Nothing even looked good on the past year, so test mode has nothing to trade either.")
        return (
            f"**Nothing is proven.** None of the {n_fam} setup families made money after fees on data they "
            "weren't built on, in a way that clearly beat random entries. Live trading stays off." + tail
        )
    names = ", ".join(f["title"] for f in surv)
    return (
        f"**{len(surv)} of {n_fam} setup families survived:** {names}. They made money after fees on the unseen "
        "test period, beat random entries, and held up in the walk forward checks. Survival means it's worth paper "
        "trading, not that it's guaranteed. Live results usually come in worse than backtests."
    )


def backtest_report(research: dict, notes: dict, cfg: dict) -> str:
    L = []
    L.append("# Backtest report\n")
    L.append(verdict_text(research) + "\n")
    L.append(
        f"Data: {len(research['coins'])} coins, hourly candles from {research['data_from']} to {research['data_to']}. "
        f"Setups were picked on {research['train_window'][0]} to {research['train_window'][1]} and judged on "
        f"{research['test_window'][0]} to {research['test_window'][1]}, which they never saw. "
        f"{research['configs_tested']} setup variations were tried in total, so some will look good on training data by pure luck. "
        "That's why only the unseen year and the walk forward periods count.\n"
    )
    L.append(
        f"Every trade pays {cfg['fees']['taker_pct']}% Coinbase taker fee plus {cfg['fees']['slippage_pct']}% slippage on the way in "
        f"and again on the way out, so a round trip costs about {notes['round_trip_cost_pct']:.2f}%. A trade has to move that much just to break even.\n"
    )
    b = research["benchmarks"]
    L.append(f"For comparison, over the test period simply holding BTC returned {_pct(b['btc_hold_pct'])} and holding all the coins equally returned {_pct(b['equal_weight_hold_pct'])}.\n")

    L.append("## Results by setup\n")
    L.append("| Setup | Test trades | Win rate | Avg per trade after fees | Profit factor | Beat random? | Walk forward | Verdict |")
    L.append("|---|---|---|---|---|---|---|---|")
    for f in research["families"]:
        if not f.get("selected"):
            L.append(f"| {f['title']} | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |")
            continue
        ts, rb, wf = f["test_stats"], f["random_baseline"], f["walk_forward"]
        beat = "yes" if rb.get("trials") and ts.get("n") and ts["avg_net_pct"] > rb["random_cut_pct"] else "no"
        wfs = f"{sum(1 for w in wf if w['positive'])}/{len(wf)} positive"
        L.append(
            f"| {f['title']} | {ts.get('n', 0)} | {_num(ts.get('win_rate', float('nan')) * 100 if ts.get('n') else None, 0)}% | "
            f"{_pct(ts.get('avg_net_pct'))} | {_num(ts.get('profit_factor'))} | {beat} | {wfs} | {'**survived**' if f['survived'] else 'failed'} |"
        )
    L.append("")

    for f in research["families"]:
        L.append(f"## {f['title']}\n")
        if not f.get("selected"):
            L.append(f"Failed: {'; '.join(f['fail_reasons'])}.\n")
            continue
        tr, ts, rb = f["train_stats"], f["test_stats"], f["random_baseline"]
        L.append(f"Best version on training data: `{f['selected']}`. Rule: {f['rule']} Hold up to {f['config']['hold']}h, {PROFILE_TEXT[f['config']['profile']]}.\n")
        L.append(f"Training: {tr.get('n', 0)} trades, {_pct(tr.get('avg_net_pct'), 3)} per trade, win rate {_num((tr.get('win_rate') or 0) * 100, 0)}%.\n")
        if ts.get("n"):
            L.append(
                f"Unseen test period: {ts['n']} trades, {_pct(ts['avg_net_pct'], 3)} per trade after fees "
                f"({_pct(ts.get('avg_net_pct_maker_entry'), 3)} if entries filled as maker), win rate {ts['win_rate'] * 100:.0f}%, "
                f"average win {_pct(ts['avg_win_pct'])}, average loss {_pct(ts['avg_loss_pct'])}, profit factor {_num(ts['profit_factor'])}, "
                f"worst losing streak {ts['worst_losing_streak']}, {ts['positive_month_share'] * 100:.0f}% of months positive. "
                f"Exits: {', '.join(f'{k} {v * 100:.0f}%' for k, v in ts['exit_mix'].items())}.\n"
            )
            L.append(f"The same trades slid to random times averaged {_pct(rb['random_mean_pct'], 3)}. To pass, the setup had to beat {_pct(rb['random_cut_pct'], 3)}, which only {100 - cfg['backtest']['random_percentile']:g}% of random runs reach. Share of random runs that did at least as well as the setup: {rb['p_value'] * 100:.1f}%.\n")
            if ts.get("by_regime"):
                L.append("By market regime: " + "; ".join(f"{k}: {v['n']} trades, {_pct(v['avg_net_pct'], 3)}" for k, v in ts["by_regime"].items()) + ".\n")
        wf = f["walk_forward"]
        if wf:
            L.append("Walk forward inside the training period (picked on 4 months, tested on the next 2): " + "; ".join(
                f"{w.get('test_from', '?')} to {w.get('test_to', '?')}: " + (f"{w['n']} trades, {_pct(w['avg_net_pct'], 3)} per trade, {_pct(w.get('edge_vs_random_pct'), 3)} vs the 75th percentile of random timing" if w['avg_net_pct'] is not None else "nothing passed training") for w in wf) + ".\n")
        if f["fail_reasons"]:
            L.append(f"**Failed because:** {'; '.join(f['fail_reasons'])}.\n")
        else:
            L.append("**Survived every check.**\n")

    cands = [s_ for s_ in survivors_payload(research) if s_["status"] == "candidate"]
    if cands:
        L.append("## Test mode setups (unproven)\n")
        L.append("These looked best over the whole year, which is exactly the data they were picked on, so their numbers are flattering. Test mode trades them with fake money to find out if they hold up on new prices.\n")
        for c in cands:
            t, r = c["test"], c["recent"]
            L.append(f"**{c['title']}**: {c['rule']} Hold up to {c['hold']}h, {PROFILE_TEXT[c['profile']]}. Past year: {t['n']} trades, {t['win_rate'] * 100:.0f}% wins, {_pct(t['avg_net_pct'])} per trade after fees. Last {cfg['backtest']['test_months']} months alone: {r['n']} trades, {_pct(r['avg_net_pct'])} per trade.\n")
    L.append("## Caveats\n")
    L.append(
        "Trades on different coins often fire at the same time because crypto moves together, so the real number of independent bets is smaller than the trade count. "
        "The live bot also caps open positions, so it can't take every signal the backtest took. Spreads and fills on small coins can be worse than the slippage assumed here. "
        "Markets change, which is why the backtest reruns every month and drops setups that stop working.\n"
    )
    return "\n".join(L)


def strategy_cards(research: dict, cfg: dict) -> str:
    surv = [f for f in research["families"] if f.get("survived")]
    L = ["# Strategy cards\n"]
    if not surv:
        L.append("No setup is proven, so nothing can trade live. See the test mode setups in the backtest report for what's being paper traded.\n")
        return "\n".join(L)
    pos = cfg["risk"]["max_position_gbp"]
    for f in surv:
        ts = f["test_stats"]
        c = f["config"]
        L.append(f"## {f['title']}\n")
        L.append(f"Rule: {f['rule']}\n")
        L.append(f"Exit: hold up to {c['hold']} hours, {PROFILE_TEXT[c['profile']]}. Typical stop {_num(ts.get('typical_stop_pct'))}% below entry" + (f", typical target {_num(ts.get('typical_target_pct'))}% above." if ts.get("typical_target_pct") else "."))
        L.append("")
        L.append(f"Test year: {ts['n']} trades, win rate {ts['win_rate'] * 100:.0f}%, {_pct(ts['avg_net_pct'], 3)} per trade after fees, profit factor {_num(ts['profit_factor'])}.")
        per = ts['avg_net_pct'] / 100 * pos
        L.append(f"On a £{pos:.0f} position that's about {'+' if per >= 0 else '-'}£{abs(per):.2f} per trade on average, with plenty of losing trades along the way (worst losing streak {ts['worst_losing_streak']}).")
        if ts.get("by_regime"):
            L.append("Regimes: " + "; ".join(f"{k}: {v['n']} trades, {_pct(v['avg_net_pct'], 3)}" for k, v in ts["by_regime"].items()) + ".")
        top = list(f["coin_breakdown"].items())[:8]
        if top:
            L.append("Coins it traded most: " + ", ".join(f"{k} ({v['n']}, {_pct(v['avg_net_pct'])})" for k, v in top) + ".")
        L.append("")
    return "\n".join(L)


def playbook(research: dict, notes: dict, cfg: dict) -> str:
    L = ["# Playbook\n", "This is the bot's research on how these coins actually behave. Every number comes from the price history, nothing is a guess.\n"]
    L.append("## The fee hurdle\n")
    mv = notes["median_move_pct"]
    L.append(
        f"A round trip costs about {notes['round_trip_cost_pct']:.2f}% in fees and slippage. The typical move (median, ignoring direction) is "
        f"{mv['1h']:.2f}% over 1 hour, {mv['4h']:.2f}% over 4 hours and {mv['24h']:.2f}% over 24 hours. "
        + ("Short holds start in a hole, because the typical 1 to 2 hour move is about the same size as the fees.\n" if mv["2h"] < notes["round_trip_cost_pct"] * 1.5 else "\n")
    )
    hours = sorted(notes["by_uk_hour"], key=lambda r: -r["avg_abs_move_bp"])
    if hours:
        L.append("## Time of day (UK time)\n")
        L.append("Busiest hours: " + ", ".join(f"{r['group']:02d}:00 ({r['avg_abs_move_bp'] / 100:.2f}% avg move)" for r in hours[:3]) + ". Quietest: " + ", ".join(f"{r['group']:02d}:00 ({r['avg_abs_move_bp'] / 100:.2f}%)" for r in hours[-3:]) + ".")
        best = max(notes["by_uk_hour"], key=lambda r: r["avg_ret_bp"])
        worst = min(notes["by_uk_hour"], key=lambda r: r["avg_ret_bp"])
        L.append(f"Best average hour {best['group']:02d}:00 ({best['avg_ret_bp']:+.1f} basis points), worst {worst['group']:02d}:00 ({worst['avg_ret_bp']:+.1f}). These drifts are tiny next to the fees, which is why time of day alone rarely works.\n")
    if notes.get("weekend_vs_weekday_move_ratio"):
        r = notes["weekend_vs_weekday_move_ratio"]
        L.append(f"## Weekends\n\nWeekend hours move {r:.2f}x as much as weekday hours" + (", so weekends are quieter." if r < 1 else ".") + "\n")
    if notes["btc_correlation"]:
        cs = [v["corr"] for v in notes["btc_correlation"].values()]
        bs = [v["beta"] for v in notes["btc_correlation"].values()]
        L.append("## Alts and BTC\n")
        lag = notes["alt_follows_btc_lag_corr"]
        L.append(
            f"Alts move with BTC in the same hour (average correlation {sum(cs) / len(cs):.2f}, average beta {sum(bs) / len(bs):.2f}, so a 1% BTC move comes with about a {sum(bs) / len(bs):.1f}% alt move). "
            f"BTC's move one hour earlier barely predicts the next alt hour (correlation {_num(lag.get('1h'), 3)}), so the catch up mostly happens inside the same hour.\n"
        )
    if notes["after_big_btc_days"]:
        L.append("## After big BTC days\n")
        for k, v in notes["after_big_btc_days"].items():
            L.append(f"{k} ({v['days']} times): BTC's next day averaged {_pct(v['btc_next_day_avg_pct'])}, up {v['btc_next_day_up_share'] * 100:.0f}% of the time; alts averaged {_pct(v['alts_next_day_avg_pct'])}.")
        L.append("")
    if notes["regimes"]:
        L.append("## Market regimes\n")
        for k, v in notes["regimes"].items():
            L.append(f"{k}: average 24h move {_pct(v['avg_24h_move_pct'])}, up {v['up_share'] * 100:.0f}% of days, a random 24h long after fees {_pct(v['random_24h_long_after_fees_pct'])}.")
        L.append("")
    L.append("## Coins\n")
    L.append("| Coin | Yearly volatility | Return over the period | Daily volume (USD m) |")
    L.append("|---|---|---|---|")
    for k, v in sorted(notes["coins"].items(), key=lambda kv: -kv[1]["median_daily_usd_volume_m"]):
        L.append(f"| {k} | {v['annual_vol_pct']:.0f}% | {_pct(v['period_return_pct'], 0)} | {v['median_daily_usd_volume_m']:.1f} |")
    L.append("")
    L.append("## Verdict from the latest backtest\n")
    L.append(verdict_text(research) + "\n")
    L.append(strategy_cards(research, cfg).replace("# Strategy cards\n", ""))
    r = cfg["risk"]
    L.append("## Risk rules the bot enforces\n")
    L.append(
        f"1. Never risk more than {r['max_risk_per_trade_pct']}% of the pot on one trade. Position size comes from the stop distance, capped at £{r['max_position_gbp']:.0f}.\n"
        f"2. At most {r['max_open_positions']} positions open and {r['max_new_trades_per_day']} new trades a day.\n"
        f"3. Stop for the day after losing £{r['daily_loss_limit_gbp']:.0f}.\n"
        f"4. Halt completely if the pot falls to £{r['pot_floor_gbp']:.0f}, until you turn it back on.\n"
        "5. Spot only, long only. No leverage, margin, futures or perpetuals, ever.\n"
    )
    return "\n".join(L)


def write_all(research: dict, notes: dict, cfg: dict, out_dir: Path):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "research.json").write_text(json.dumps(research, indent=2, default=_json_default))
    (out_dir / "market_notes.json").write_text(json.dumps(notes, indent=2, default=_json_default))
    (out_dir / "survivors.json").write_text(json.dumps(survivors_payload(research), indent=2, default=_json_default))
    (out_dir / "backtest_report.md").write_text(backtest_report(research, notes, cfg))
    (out_dir / "strategy_cards.md").write_text(strategy_cards(research, cfg))
    (out_dir / "playbook.md").write_text(playbook(research, notes, cfg))
