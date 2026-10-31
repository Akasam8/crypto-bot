"""Research pipeline: sweep every config on training data, pick one per family, then judge it on
data it has never seen (holdout year + rolling walk forward + random entry baseline)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .backtest import Outcomes, select_trades, simulate_all
from .config import costs
from .features import btc_context, coin_features
from .strategies import FAMILIES, all_configs, config_key, describe, signal

NS_HOUR = 3_600_000_000_000


def ns_index(idx: pd.DatetimeIndex) -> np.ndarray:
    return np.asarray(idx.as_unit("ns").asi8)


def ts_ns(t) -> int:
    return int(pd.Timestamp(t).as_unit("ns").value)


def ns_to_ts(x: int) -> pd.Timestamp:
    return pd.Timestamp(int(x), unit="ns", tz="UTC")


@dataclass
class Universe:
    pids: list[str]
    btc: str
    feats: dict[str, pd.DataFrame]
    t: dict[str, np.ndarray]
    start_ns: int
    end_ns: int
    _out: dict = field(default_factory=dict)
    _sig: dict = field(default_factory=dict)

    def outcomes(self, pid: str, hold: int, profile: str) -> Outcomes:
        k = (pid, hold, profile)
        if k not in self._out:
            f = self.feats[pid]
            self._out[k] = simulate_all(f["open"], f["high"], f["low"], f["close"], f["sigma"], hold, profile)
        return self._out[k]

    def signal(self, family: str, params: dict, pid: str) -> np.ndarray:
        k = (family, tuple(sorted(params.items())), pid)
        if k not in self._sig:
            self._sig[k] = signal(family, params, self.feats[pid], is_btc=(pid == self.btc))
        return self._sig[k]


def prepare(universe: dict[str, pd.DataFrame], btc_pid: str) -> Universe:
    ctx = btc_context(universe[btc_pid])
    feats, times = {}, {}
    for pid, df in universe.items():
        f = coin_features(df, ctx)
        feats[pid] = f
        times[pid] = ns_index(f.index)
    b = times[btc_pid]
    return Universe(list(universe), btc_pid, feats, times, int(b[0]), int(b[-1]) + NS_HOUR)


def trades_for(u: Universe, cfg: dict, cost: dict, detail: bool = False) -> dict:
    """All trades for one config across the universe. Times are the signal candle close (ns)."""
    parts = []
    for ci, pid in enumerate(u.pids):
        out = u.outcomes(pid, cfg["hold"], cfg["profile"])
        idx = select_trades(u.signal(cfg["family"], cfg["params"], pid), out)
        if not len(idx):
            continue
        p = {
            "t": u.t[pid][idx] + NS_HOUR,
            "net": out.net(*cost["a"])[idx],
        }
        if detail:
            f = u.feats[pid]
            p.update(
                coin=np.full(len(idx), ci),
                net_b=out.net(*cost["b"])[idx],
                reason=out.reason[idx],
                bars=out.exit_idx[idx] - idx,
                up50=f["btc_up50"].to_numpy()[idx],
                highvol=f["btc_highvol"].to_numpy()[idx],
                sl_pct=out.sl_pct[idx],
                tp_pct=out.tp_pct[idx],
            )
        parts.append(p)
    if not parts:
        keys = ["t", "net"] + (["coin", "net_b", "reason", "bars", "up50", "highvol", "sl_pct", "tp_pct"] if detail else [])
        return {k: np.array([]) for k in keys}
    ts = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    order = np.argsort(ts["t"], kind="stable")
    return {k: v[order] for k, v in ts.items()}


def window(ts: dict, a: int, b: int) -> dict:
    m = (ts["t"] >= a) & (ts["t"] < b)
    return {k: v[m] for k, v in ts.items()}


def quick_stats(net: np.ndarray) -> tuple[int, float, float]:
    n = len(net)
    if n < 2:
        return n, float(net.mean()) if n else 0.0, 0.0
    m, s = float(net.mean()), float(net.std(ddof=1))
    return n, m, (m / s * np.sqrt(n)) if s > 0 else 0.0


def full_stats(ts: dict) -> dict:
    net = ts["net"]
    n = len(net)
    if n == 0:
        return {"n": 0}
    wins, losses = net[net > 0], net[net <= 0]
    cum = np.cumsum(net)
    dd = float(np.max(np.maximum.accumulate(np.concatenate([[0], cum]))[1:] - cum)) if n else 0.0
    streak = best = 0
    for x in net:
        streak = streak + 1 if x <= 0 else 0
        best = max(best, streak)
    months = pd.Series(net, index=pd.to_datetime(ts["t"], unit="ns", utc=True)).groupby(lambda d: d.strftime("%Y-%m")).sum()
    years = pd.Series(net, index=pd.to_datetime(ts["t"], unit="ns", utc=True)).groupby(lambda d: d.year).agg(["count", "mean", "sum"])
    out = {
        "n": n,
        "win_rate": float((net > 0).mean()),
        "avg_net_pct": float(net.mean() * 100),
        "median_net_pct": float(np.median(net) * 100),
        "avg_win_pct": float(wins.mean() * 100) if len(wins) else 0.0,
        "avg_loss_pct": float(losses.mean() * 100) if len(losses) else 0.0,
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
        "t_stat": quick_stats(net)[2],
        "max_drawdown_pct_of_stake": dd * 100,
        "worst_losing_streak": int(best),
        "months_with_trades": int(len(months)),
        "positive_month_share": float((months > 0).mean()) if len(months) else 0.0,
        "monthly_net_pct": {k: round(float(v) * 100, 2) for k, v in months.items()},
        "by_year": {int(y): {"n": int(r["count"]), "avg_net_pct": round(float(r["mean"]) * 100, 3)} for y, r in years.iterrows()},
    }
    if "net_b" in ts:
        out["avg_net_pct_maker_entry"] = float(ts["net_b"].mean() * 100)
        out["avg_hold_hours"] = float(ts["bars"].mean() + 1)
        out["exit_mix"] = {name: float((ts["reason"] == code).mean()) for code, name in ((1, "target"), (2, "stop"), (0, "time"))}
        reg = {}
        for col, label in (("up50", "BTC above 50d avg"), ("highvol", "high volatility")):
            for val, txt in ((1.0, "yes"), (0.0, "no")):
                m = ts[col] == val
                if m.any():
                    reg[f"{label}: {txt}"] = {"n": int(m.sum()), "avg_net_pct": round(float(net[m].mean() * 100), 3), "win_rate": round(float((net[m] > 0).mean()), 3)}
        out["by_regime"] = reg
        out["typical_stop_pct"] = float(np.nanmedian(ts["sl_pct"]) * 100)
        tp = ts["tp_pct"][np.isfinite(ts["tp_pct"])]
        out["typical_target_pct"] = float(np.median(tp) * 100) if len(tp) else None
    return out


def shifted_means(u: Universe, cfg: dict, cost: dict, trades: dict, a: int, b: int, trials: int, seed: int = 7) -> np.ndarray:
    """Null model: slide every trade in the window by the same random time offset (wrapping round).

    Same coins, same number of trades, same exits, same clustering across coins, but entry timing
    that has nothing to do with the setup. Market drift is still captured, so beating this means the
    setup's timing adds something beyond just being long crypto."""
    if not len(trades["net"]):
        return np.array([])
    rng = np.random.default_rng(seed)
    span = b - a
    hours = max(int(span // NS_HOUR), 2)
    offsets = rng.integers(1, hours, size=trials) * NS_HOUR
    sums = np.zeros(trials)
    counts = np.zeros(trials)
    for ci in np.unique(trades["coin"].astype(int)):
        pid = u.pids[ci]
        out = u.outcomes(pid, cfg["hold"], cfg["profile"])
        net = out.net(*cost["a"])
        tbar = u.t[pid] + NS_HOUR
        tt = trades["t"][trades["coin"] == ci]
        shifted = a + ((tt[None, :] - a + offsets[:, None]) % span)
        idx = np.searchsorted(tbar, shifted)
        idx = np.clip(idx, 0, len(tbar) - 1)
        ok = (tbar[idx] == shifted) & out.valid[idx]
        vals = np.where(ok, net[idx], 0.0)
        sums += vals.sum(axis=1)
        counts += ok.sum(axis=1)
    return sums / np.maximum(counts, 1)


def random_baseline(u: Universe, cfg: dict, cost: dict, test: dict, a: int, b: int, trials: int, pct: float = 97.5, seed: int = 7) -> dict:
    if not len(test["net"]):
        return {"trials": 0}
    means = shifted_means(u, cfg, cost, test, a, b, trials, seed)
    actual = float(test["net"].mean())
    return {
        "trials": trials,
        "random_mean_pct": float(means.mean() * 100),
        "random_p90_pct": float(np.percentile(means, 90) * 100),
        "random_cut_pct": float(np.percentile(means, pct) * 100),
        "p_value": float((means >= actual).mean()),
    }


def month_add(t_ns: int, months: int) -> int:
    return ts_ns(ns_to_ts(t_ns) + pd.DateOffset(months=months))


def run_research(u: Universe, cfg: dict, log=print) -> dict:
    bc = cfg["backtest"]
    cost = costs(cfg)
    configs = all_configs(bc["hold_hours"])
    warm = month_add(u.start_ns, 0) + 200 * NS_HOUR  # indicators need ~200 bars
    end = u.end_ns
    test_a = month_add(end, -bc["test_months"])
    max_hold = max(bc["hold_hours"]) * NS_HOUR
    train = (warm, test_a - max_hold)  # training trades must be finished before the test year starts
    # walk forward folds live entirely before the holdout year, so they're independent evidence
    folds = []
    f0 = warm
    while True:
        tr_b = month_add(f0, bc["wf_train_months"])
        te_b = min(month_add(tr_b, bc["wf_test_months"]), test_a - max_hold)
        if te_b < month_add(tr_b, 3):  # need at least 3 months of unseen data per fold
            break
        folds.append(((f0, tr_b - max_hold), (tr_b, te_b)))
        f0 = month_add(f0, bc["wf_test_months"])
    log(f"[research] {len(configs)} configs, {len(u.pids)} coins, {len(folds)} walk forward folds")

    windows = [train] + [f[0] for f in folds]
    summary = []
    for i, c in enumerate(configs):
        ts = trades_for(u, c, cost)
        row = {"key": config_key(c), "cfg": c, "train": [quick_stats(window(ts, *w)["net"]) for w in windows]}
        summary.append(row)
        if (i + 1) % 100 == 0:
            log(f"[research] swept {i + 1}/{len(configs)}")

    def pick(family: str, wi: int):
        best = None
        for r in summary:
            if r["cfg"]["family"] != family:
                continue
            n, m, t = r["train"][wi]
            if n < bc["min_train_trades"] or m <= 0:
                continue
            if best is None or t > best["train"][wi][2]:
                best = r
        return best

    results = []
    for fam in FAMILIES:
        res = {"family": fam, "title": FAMILIES[fam]["title"], "configs_tested": sum(1 for r in summary if r["cfg"]["family"] == fam)}
        chosen = pick(fam, 0)
        if chosen is None:
            res.update(selected=None, survived=False, fail_reasons=["nothing was profitable after fees even on the training data"])
            results.append(res)
            continue
        c = chosen["cfg"]
        full = trades_for(u, c, cost, detail=True)
        tr, te = window(full, *train), window(full, test_a, end)
        test_stats = full_stats(te)
        rb = random_baseline(u, c, cost, te, test_a, end, bc["random_trials"], bc["random_percentile"])
        wf = []
        for wi, (ftr, fte) in enumerate(folds, start=1):
            fc = pick(fam, wi)
            if fc is None:
                wf.append({"fold": wi, "selected": None, "n": 0, "avg_net_pct": None, "positive": False})
                continue
            fts = window(trades_for(u, fc["cfg"], cost, detail=True), *fte)
            n, m, _ = quick_stats(fts["net"])
            null = shifted_means(u, fc["cfg"], cost, fts, *fte, trials=200, seed=wi)
            excess = m - float(np.percentile(null, bc["wf_random_percentile"])) if len(null) else float("nan")
            wf.append({
                "fold": wi, "selected": fc["key"], "test_from": str(ns_to_ts(fte[0]).date()), "test_to": str(ns_to_ts(fte[1]).date()),
                "n": n, "avg_net_pct": round(m * 100, 3), "edge_vs_random_pct": round(excess * 100, 3) if np.isfinite(excess) else None,
                "positive": bool(n >= 10 and m > 0 and np.isfinite(excess) and excess > 0),
            })

        reasons = []
        if test_stats.get("n", 0) < bc["min_test_trades"]:
            reasons.append(f"only {test_stats.get('n', 0)} trades in the test year (need {bc['min_test_trades']})")
        if test_stats.get("n", 0) and test_stats["avg_net_pct"] <= 0:
            reasons.append(f"lost money after fees in the test year ({test_stats['avg_net_pct']:.2f}% per trade)")
        if test_stats.get("n", 0) and test_stats["profit_factor"] < bc["min_profit_factor"]:
            reasons.append(f"profit factor {test_stats['profit_factor']:.2f} below {bc['min_profit_factor']}")
        if rb.get("trials") and test_stats.get("n", 0) and test_stats["avg_net_pct"] <= rb["random_cut_pct"]:
            reasons.append(f"didn't clearly beat random entries ({test_stats['avg_net_pct']:.2f}% vs {rb['random_cut_pct']:.2f}% for the top {100 - bc['random_percentile']}% of random runs)")
        if test_stats.get("n", 0) and test_stats["positive_month_share"] < bc["min_positive_month_share"]:
            reasons.append(f"only {test_stats['positive_month_share']:.0%} of test months were positive")
        pos_folds = sum(1 for w in wf if w["positive"])
        if not folds:
            reasons.append("not enough history for walk forward checks")
        elif pos_folds < min(bc["wf_min_positive_folds"], len(folds)):
            reasons.append(f"walk forward: only {pos_folds} of {len(folds)} unseen periods made money and beat random timing")

        res.update(
            selected=chosen["key"],
            config=c,
            rule=describe(fam, c["params"]),
            train_stats=full_stats(tr),
            test_stats=test_stats,
            random_baseline=rb,
            walk_forward=wf,
            coin_breakdown=_coin_breakdown(u, te),
            survived=not reasons,
            fail_reasons=reasons,
        )
        results.append(res)
        log(f"[research] {fam}: {'SURVIVED' if not reasons else 'failed'} {chosen['key']}")

    return {
        "configs_tested": len(configs),
        "coins": u.pids,
        "data_from": str(ns_to_ts(u.start_ns).date()),
        "data_to": str(ns_to_ts(end).date()),
        "train_window": [str(ns_to_ts(train[0]).date()), str(ns_to_ts(train[1]).date())],
        "test_window": [str(ns_to_ts(test_a).date()), str(ns_to_ts(end).date())],
        "folds": [{"train": [str(ns_to_ts(a).date()), str(ns_to_ts(b).date())], "test": [str(ns_to_ts(c).date()), str(ns_to_ts(d).date())]} for (a, b), (c, d) in folds],
        "benchmarks": _benchmarks(u, test_a, end),
        "families": results,
    }


def _coin_breakdown(u: Universe, te: dict) -> dict:
    out = {}
    if not len(te["net"]):
        return out
    for ci in np.unique(te["coin"].astype(int)):
        m = te["coin"] == ci
        out[u.pids[ci]] = {"n": int(m.sum()), "avg_net_pct": round(float(te["net"][m].mean() * 100), 3)}
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["n"]))


def _benchmarks(u: Universe, a: int, b: int) -> dict:
    rets = {}
    for pid in u.pids:
        f = u.feats[pid]
        t = u.t[pid]
        m = (t >= a) & (t < b)
        if m.sum() < 24:
            continue
        cl = f["close"].to_numpy()[m]
        rets[pid] = float(cl[-1] / cl[0] - 1)
    return {
        "btc_hold_pct": round(rets.get(u.btc, float("nan")) * 100, 2),
        "equal_weight_hold_pct": round(float(np.mean(list(rets.values()))) * 100, 2) if rets else None,
    }
