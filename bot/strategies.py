"""Strategy families. Each returns a boolean signal on closed candles; the trade enters at the next open."""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

# Exit profiles in multiples of expected volatility over the hold (hourly sigma * sqrt(hold hours)).
# (take_profit_mult, stop_loss_mult); None take profit means exit on the stop or at max hold time.
EXIT_PROFILES = {
    "tight": (1.0, 1.0),
    "runner": (2.0, 1.0),
    "timed": (None, 2.0),
}

FAMILIES = {
    "breakout": {
        "title": "Breakout with volume",
        "desc": "Price closes above its highest high of the last {lookback} hours on volume at least {vol_mult}x the usual.",
        "grid": [{"lookback": lb, "vol_mult": vm} for lb in (24, 72) for vm in (1.5, 2.5)],
    },
    "oversold_bounce": {
        "title": "Oversold bounce in a BTC uptrend",
        "desc": "RSI(14) {mode_text} {threshold} while BTC is above its 50 day average.",
        "grid": [
            {"threshold": 25, "mode": "below"},
            {"threshold": 30, "mode": "below"},
            {"threshold": 30, "mode": "cross_up"},
        ],
    },
    "volume_spike": {
        "title": "Volume spike continuation",
        "desc": "A one hour move up of more than {k}x normal volatility on at least 3x the usual volume.",
        "grid": [{"k": 1.5}, {"k": 2.5}],
    },
    "btc_catchup": {
        "title": "Alt catching up to BTC",
        "desc": "BTC jumps strongly over the last {lookback}h while this coin has moved less than half as much.",
        "grid": [{"lookback": 1}, {"lookback": 4}],
    },
    "trend_pullback": {
        "title": "Trend pullback",
        "desc": "In an uptrend (above a rising 200 hour average), price dips to the {fast}h average and closes back above it.",
        "grid": [{"fast": 20}, {"fast": 50}],
    },
    "trend_breakout": {
        "title": "Trend breakout",
        "desc": "Price breaks above its highest point of the last {days} days while above its 20 day average{btc_text}.",
        "grid": [{"days": d, "btc_filter": b} for d in (10, 20) for b in (True, False)],
    },
    "ma_cross": {
        "title": "Moving average cross",
        "desc": "The {fast_d:g} day average crosses above the {slow_d:g} day average.",
        "grid": [{"fast": 120, "slow": 480}, {"fast": 48, "slow": 240}],
    },
    "momentum_leader": {
        "title": "Momentum leader",
        "desc": "Once a day, buy a coin that's in the top {top} for 7 day gains, up on the week, while BTC is above its 50 day average.",
        "grid": [{"top": 3}, {"top": 5}],
    },
    "session": {
        "research": False,
        "title": "Time of day entry",
        "desc": "Enter at {hour:02d}:00 UTC every day. The hour is picked on training data only.",
        "grid": [{"hour": h} for h in range(24)],
    },
}


def describe(family: str, params: dict) -> str:
    p = dict(params)
    if family == "oversold_bounce":
        p["mode_text"] = "drops below" if p["mode"] == "below" else "climbs back above"
    if family == "trend_breakout":
        p["btc_text"] = ", with BTC above its 50 day average" if p["btc_filter"] else ""
    if family == "ma_cross":
        p["fast_d"], p["slow_d"] = p["fast"] / 24, p["slow"] / 24
    return FAMILIES[family]["desc"].format(**p)


def signal(family: str, params: dict, f: pd.DataFrame, is_btc: bool = False) -> np.ndarray:
    if family == "breakout":
        lb, vm = params["lookback"], params["vol_mult"]
        s = (f["close"] > f[f"hi{lb}"]) & (f["volume"] > vm * f[f"vmed{lb}"])
    elif family == "oversold_bounce":
        th = params["threshold"]
        trend_ok = f["btc_up50"] == 1
        if params["mode"] == "below":
            s = (f["rsi14"] < th) & trend_ok
        else:
            s = (f["rsi14"].shift(1) < th) & (f["rsi14"] >= th) & trend_ok
    elif family == "volume_spike":
        s = (f["ret_1"] > params["k"] * f["sigma"]) & (f["volume"] > 3 * f["vmed168"])
    elif family == "btc_catchup":
        if is_btc:
            return np.zeros(len(f), dtype=bool)
        L = params["lookback"]
        b = f["btc_ret_1"] if L == 1 else f["btc_ret_4"]
        a = f["ret_1"] if L == 1 else f["ret_4"]
        s = (b > 1.5 * f["btc_sigma"] * np.sqrt(L)) & (a < 0.5 * b)
    elif family == "trend_pullback":
        e = f[f"ema{params['fast']}"]
        up = (f["close"] > f["sma200"]) & (f["sma200"] > f["sma200"].shift(24))
        s = up & (f["low"] <= e) & (f["close"] > e)
    elif family == "trend_breakout":
        s = (f["close"] > f[f"hi{params['days'] * 24}"]) & (f["close"] > f["sma480"])
        if params["btc_filter"]:
            s = s & (f["btc_up50"] == 1)
    elif family == "ma_cross":
        fa, sl = f[f"sma{params['fast']}"], f[f"sma{params['slow']}"]
        s = (fa.shift(1) <= sl.shift(1)) & (fa > sl)
    elif family == "momentum_leader":
        s = (f.index.hour == 23) & (f["mom_rank"] <= params["top"]) & (f["ret_168"] > 0) & (f["btc_up50"] == 1)
        s = pd.Series(s, index=f.index)
    elif family == "session":
        # signal bar closes at the top of the entry hour
        s = pd.Series((f.index.hour + 1) % 24 == params["hour"], index=f.index)
    else:
        raise KeyError(family)
    return s.fillna(False).to_numpy(dtype=bool)


def all_configs(hold_hours) -> list[dict]:
    out = []
    for fam, spec in FAMILIES.items():
        if not spec.get("research", True):
            continue
        for params, hold, prof in itertools.product(spec["grid"], hold_hours, EXIT_PROFILES):
            out.append({"family": fam, "params": params, "hold": int(hold), "profile": prof})
    return out


def config_key(c: dict) -> str:
    p = ",".join(f"{k}={v}" for k, v in sorted(c["params"].items()))
    return f"{c['family']}[{p}]|{c['hold']}h|{c['profile']}"
