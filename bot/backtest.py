"""Trade simulation. Enter at the next candle's open, exit on take profit, stop loss or max hold time.

Rules (shared with the live scanner so paper results match the backtest):
  * signal uses only closed candles, entry = open of the following candle
  * stop and target are checked candle by candle; if both fall in the same candle the stop wins
  * a stop that gaps fills at the worse open price; targets fill exactly at the target
  * no stop or target hit within the hold: exit at the close of the last candle of the hold
  * one position per coin per setup at a time
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from .strategies import EXIT_PROFILES

MIN_SL, MAX_SL = 0.005, 0.15
MIN_TP, MAX_TP = 0.005, 0.50
REASONS = {0: "time", 1: "target", 2: "stop"}


def exit_levels(sigma, hold: int, tp_mult, sl_mult):
    s = np.asarray(sigma, dtype=float) * np.sqrt(hold)
    sl = np.clip(sl_mult * s, MIN_SL, MAX_SL)
    tp = np.clip(tp_mult * s, MIN_TP, MAX_TP) if tp_mult else np.full_like(s, np.nan)
    return tp, sl


@dataclass
class Outcomes:
    """Outcome of a hypothetical trade signalled at every bar i (entry at bar i+1)."""
    valid: np.ndarray
    exit_idx: np.ndarray
    entry_px: np.ndarray
    exit_px: np.ndarray
    reason: np.ndarray
    tp_pct: np.ndarray
    sl_pct: np.ndarray

    def net(self, c_in: float, c_out: float) -> np.ndarray:
        with np.errstate(invalid="ignore", divide="ignore"):
            return (self.exit_px * (1 - c_out)) / (self.entry_px * (1 + c_in)) - 1


def simulate_all(o, h, l, c, sigma, hold: int, profile: str) -> Outcomes:
    o, h, l, c, sigma = (np.asarray(x, dtype=float) for x in (o, h, l, c, sigma))
    n = len(o)
    H = int(hold)
    tp_mult, sl_mult = EXIT_PROFILES[profile]
    valid = np.zeros(n, bool)
    exit_idx = np.full(n, -1, dtype=np.int64)
    entry_px = np.full(n, np.nan)
    exit_px = np.full(n, np.nan)
    reason = np.zeros(n, dtype=np.int8)
    tp_all = np.full(n, np.nan)
    sl_all = np.full(n, np.nan)
    m = n - H  # signals at i < m have a full hold window inside the data
    if m <= 0:
        return Outcomes(valid, exit_idx, entry_px, exit_px, reason, tp_all, sl_all)

    i = np.arange(m)
    e = i + 1
    ep = o[e]
    tp_pct, sl_pct = exit_levels(sigma[i], H, tp_mult, sl_mult)
    ok = np.isfinite(ep) & (ep > 0) & np.isfinite(sl_pct)
    sl_px = ep * (1 - sl_pct)
    tp_px = ep * (1 + tp_pct)

    W_l = sliding_window_view(l, H)[1 : m + 1]
    W_h = sliding_window_view(h, H)[1 : m + 1]
    W_o = sliding_window_view(o, H)[1 : m + 1]
    stop_hit = W_l <= sl_px[:, None]
    with np.errstate(invalid="ignore"):
        tp_hit = W_h >= tp_px[:, None]
    any_hit = stop_hit | tp_hit
    hit = any_hit.any(axis=1)
    first = np.where(hit, any_hit.argmax(axis=1), H - 1)
    rows = np.arange(m)
    is_stop = hit & stop_hit[rows, first]
    is_tp = hit & ~is_stop
    stop_fill = np.minimum(W_o[rows, first], sl_px)
    xp = np.where(is_stop, stop_fill, np.where(is_tp, tp_px, c[e + H - 1]))

    valid[:m] = ok & np.isfinite(xp)
    exit_idx[:m] = e + first
    entry_px[:m] = ep
    exit_px[:m] = xp
    reason[:m] = np.where(is_stop, 2, np.where(is_tp, 1, 0))
    tp_all[:m] = tp_pct
    sl_all[:m] = sl_pct
    return Outcomes(valid, exit_idx, entry_px, exit_px, reason, tp_all, sl_all)


def select_trades(signal_mask: np.ndarray, out: Outcomes) -> np.ndarray:
    """Indices of signal bars actually traded, skipping signals while a position is open."""
    idxs = np.flatnonzero(signal_mask & out.valid)
    taken = []
    next_free = -1
    ex = out.exit_idx
    for i in idxs.tolist():
        if i >= next_free:
            taken.append(i)
            next_free = int(ex[i])
    return np.asarray(taken, dtype=np.int64)
