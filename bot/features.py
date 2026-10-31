"""Indicators and per coin feature frames. Every column only uses data up to that bar's close."""
from __future__ import annotations

import numpy as np
import pandas as pd

SIGMA_BARS = 168  # one week of hourly returns


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close).diff()


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0)
    dn = (-d).clip(lower=0)
    au = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    ad = dn.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    r = 100 - 100 / (1 + au / ad.replace(0, np.nan))
    return r.where(ad != 0, 100.0)


def prior_max(s: pd.Series, n: int) -> pd.Series:
    return s.shift(1).rolling(n, min_periods=n).max()


def prior_median(s: pd.Series, n: int) -> pd.Series:
    return s.shift(1).rolling(n, min_periods=n).median()


def btc_context(btc: pd.DataFrame, btc_daily_close: pd.Series | None = None) -> pd.DataFrame:
    """Market context from BTC, aligned to the hourly grid. Daily regime for day D uses closes up to D-1.

    The live scanner passes Coinbase daily candles (UTC days) because it only fetches a few hundred
    hourly bars; the backtest derives the same daily closes from the hourly history."""
    r = log_returns(btc["close"])
    ctx = pd.DataFrame(index=btc.index)
    ctx["btc_ret_1"] = r
    ctx["btc_ret_4"] = np.log(btc["close"]).diff(4)
    ctx["btc_sigma"] = r.rolling(SIGMA_BARS, min_periods=SIGMA_BARS // 2).std()

    daily = btc["close"].resample("1D").last() if btc_daily_close is None else btc_daily_close.sort_index()
    sma50 = daily.rolling(50).mean()
    sma200 = daily.rolling(200).mean()
    dvol = np.log(daily).diff().rolling(30).std()
    dvol_med = dvol.rolling(365, min_periods=120).median()
    reg = pd.DataFrame(index=daily.index)
    reg["btc_up50"] = np.where(sma50.notna(), (daily > sma50).astype(float), np.nan)
    reg["btc_up200"] = np.where(sma200.notna(), (daily > sma200).astype(float), np.nan)
    reg["btc_highvol"] = np.where(dvol_med.notna() & dvol.notna(), (dvol > dvol_med).astype(float), np.nan)
    reg.index = reg.index + pd.Timedelta(days=1)  # day D sees closes up to D-1, even if D-1 is the last row
    keys = ctx.index.floor("D")
    for c in reg.columns:
        ctx[c] = reg[c].reindex(keys).to_numpy()
    return ctx


def coin_features(df: pd.DataFrame, ctx: pd.DataFrame) -> pd.DataFrame:
    c = df["close"]
    lr = log_returns(c)
    f = df[["open", "high", "low", "close", "volume"]].copy()
    f["ret_1"] = lr
    f["ret_4"] = np.log(c).diff(4)
    f["sigma"] = lr.rolling(SIGMA_BARS, min_periods=SIGMA_BARS // 2).std()
    f["rsi14"] = rsi(c, 14)
    for span in (20, 50):
        f[f"ema{span}"] = ema(c, span)
    for n in (48, 120, 200, 240, 480):  # simple averages: identical whether you have 800 bars or 3 years
        f[f"sma{n}"] = c.rolling(n, min_periods=n).mean()
    for n in (24, 72, 240, 480):
        f[f"hi{n}"] = prior_max(df["high"], n)
    for n in (24, 72, 168):
        f[f"vmed{n}"] = prior_median(df["volume"], n)
    f["ret_168"] = np.log(c).diff(168)
    f = f.join(ctx, how="left")
    return f


def add_cross_sectional(feats: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Rank every coin by its 7 day return at each hour (1 = strongest). Uses only data up to that bar."""
    r = pd.DataFrame({pid: f["ret_168"] for pid, f in feats.items()})
    rank = r.rank(axis=1, ascending=False, method="first")
    for pid, f in feats.items():
        f["mom_rank"] = rank[pid].reindex(f.index)
    return feats
