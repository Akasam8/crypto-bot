"""Fake market with no edge in it, used for tests and offline dry runs.

Prices are random walks with fat tails and BTC correlation. Any setup that 'survives' on this
data survived by luck, so the pipeline should find nothing here."""
from __future__ import annotations

import numpy as np
import pandas as pd


def synthetic_universe(n_coins: int = 6, days: int = 1095, seed: int = 0, end: pd.Timestamp | None = None) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    hours = days * 24
    end = (end or pd.Timestamp.now(tz="UTC")).floor("h")
    idx = pd.date_range(end=end - pd.Timedelta(hours=1), periods=hours, freq="1h", tz="UTC", name="time")
    t_scale = np.sqrt(4 / 2)  # unit variance for t(4)
    btc_r = 0.006 * rng.standard_t(4, hours) / t_scale
    out = {}
    names = ["BTC-USD"] + [f"C{i}-USD" for i in range(1, n_coins)]
    for k, pid in enumerate(names):
        if k == 0:
            r = btc_r
        else:
            beta = rng.uniform(0.8, 1.5)
            r = beta * btc_r + 0.008 * rng.standard_t(4, hours) / t_scale
        close = 100.0 * np.exp(np.cumsum(r))
        open_ = np.concatenate([[100.0], close[:-1]])
        wig = np.abs(rng.normal(0, 0.003, (2, hours)))
        high = np.maximum(open_, close) * np.exp(wig[0])
        low = np.minimum(open_, close) * np.exp(-wig[1])
        vol = rng.lognormal(10, 0.6, hours) * (1 + 40 * np.abs(r))
        out[pid] = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx)
    return out
