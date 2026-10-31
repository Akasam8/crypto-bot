"""Market notes: how these coins actually behaved over the history window."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import costs, round_trip_pct
from .features import btc_context

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _pooled(vals: np.ndarray, groups: np.ndarray, labels) -> list[dict]:
    rows = []
    for g in labels:
        v = vals[groups == g].ravel()
        v = v[np.isfinite(v) & (v != 0)]
        if not len(v):
            continue
        rows.append({"group": g, "n": int(len(v)), "avg_ret_bp": float(v.mean() * 1e4), "avg_abs_move_bp": float(np.abs(v).mean() * 1e4), "up_share": float((v > 0).mean())})
    return rows


def market_notes(universe: dict[str, pd.DataFrame], btc_pid: str, cfg: dict) -> dict:
    tz = cfg["uk_timezone"]
    closes = pd.DataFrame({pid: df["close"] for pid, df in universe.items()})
    rets = np.log(closes).diff()
    uk = rets.index.tz_convert(tz)
    vals = rets.to_numpy()

    by_hour = _pooled(vals, np.asarray(uk.hour), range(24))
    by_day = _pooled(vals, np.asarray(uk.dayofweek), range(7))
    for r in by_day:
        r["group"] = DAYS[r["group"]]
    wk = [r["avg_abs_move_bp"] for r in by_day if r["group"] in ("Sat", "Sun")]
    wd = [r["avg_abs_move_bp"] for r in by_day if r["group"] not in ("Sat", "Sun")]

    btc_r = rets[btc_pid]
    alts = [p for p in universe if p != btc_pid]
    corr = {}
    for p in alts:
        a = rets[p]
        m = a.notna() & btc_r.notna()
        if m.sum() < 500:
            continue
        cov = np.cov(a[m], btc_r[m])
        corr[p] = {"corr": float(np.corrcoef(a[m], btc_r[m])[0, 1]), "beta": float(cov[0, 1] / cov[1, 1])}
    lead = {}
    for k in (1, 2, 3):
        cs = [rets[p].corr(btc_r.shift(k)) for p in alts]
        cs = [c for c in cs if np.isfinite(c)]
        lead[f"{k}h"] = float(np.mean(cs)) if cs else None

    daily = closes.resample("1D").last()
    dret = daily.pct_change(fill_method=None)
    nxt = dret.shift(-1)
    big = {}
    for label, mask in (("BTC up 5%+ in a day", dret[btc_pid] >= 0.05), ("BTC down 5%+ in a day", dret[btc_pid] <= -0.05)):
        mask = mask.fillna(False)
        if mask.sum() == 0:
            continue
        bn = nxt[btc_pid][mask].dropna()
        an = nxt[alts][mask].mean(axis=1).dropna() if alts else pd.Series(dtype=float)
        big[label] = {"days": int(mask.sum()), "btc_next_day_avg_pct": float(bn.mean() * 100), "btc_next_day_up_share": float((bn > 0).mean()), "alts_next_day_avg_pct": float(an.mean() * 100) if len(an) else None}

    ctx = btc_context(universe[btc_pid])
    c_in, c_out = costs(cfg)["a"]
    rows = []
    for p, df in universe.items():
        fwd = np.log(df["close"].shift(-24) / df["close"])
        at = df.index.hour == 0
        r = pd.DataFrame({"fwd": fwd[at], "up50": ctx["btc_up50"].reindex(df.index)[at], "hv": ctx["btc_highvol"].reindex(df.index)[at]}).dropna()
        rows.append(r)
    reg = pd.concat(rows) if rows else pd.DataFrame(columns=["fwd", "up50", "hv"])
    reg["net"] = np.exp(reg["fwd"]) * (1 - c_out) / (1 + c_in) - 1
    regimes = {}
    for col, label in (("up50", "BTC above its 50 day average"), ("hv", "high volatility")):
        for v, txt in ((1.0, "yes"), (0.0, "no")):
            m = reg[col] == v
            if m.any():
                regimes[f"{label}: {txt}"] = {"n": int(m.sum()), "avg_24h_move_pct": float((np.exp(reg["fwd"][m]) - 1).mean() * 100), "up_share": float((reg["fwd"][m] > 0).mean()), "random_24h_long_after_fees_pct": float(reg["net"][m].mean() * 100)}

    moves = {}
    for h in (1, 2, 4, 12, 24):
        mv = np.log(closes).diff(h).abs().to_numpy().ravel()
        mv = mv[np.isfinite(mv) & (mv > 0)]
        moves[f"{h}h"] = float(np.median(mv) * 100)

    coins = {}
    for p, df in universe.items():
        r = np.log(df["close"]).diff()
        last30 = df[df.index >= df.index[-1] - pd.Timedelta(days=30)]
        dv = (last30["volume"] * last30["close"]).resample("1D").sum()
        coins[p] = {"annual_vol_pct": float(r.std() * np.sqrt(24 * 365) * 100), "period_return_pct": float((df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100), "median_daily_usd_volume_m": float(dv.median() / 1e6)}

    return {
        "round_trip_cost_pct": round_trip_pct(cfg),
        "median_move_pct": moves,
        "by_uk_hour": by_hour,
        "by_uk_weekday": by_day,
        "weekend_vs_weekday_move_ratio": float(np.mean(wk) / np.mean(wd)) if wk and wd else None,
        "btc_correlation": corr,
        "alt_follows_btc_lag_corr": lead,
        "after_big_btc_days": big,
        "regimes": regimes,
        "coins": coins,
    }
