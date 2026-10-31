import copy

import numpy as np
import pandas as pd
import pytest

from bot.backtest import exit_levels, select_trades, simulate_all
from bot.config import costs, load_config
from bot.evaluate import prepare, run_research
from bot.features import btc_context, coin_features
from bot.strategies import FAMILIES, signal
from bot.synthetic import synthetic_universe


def bars(rows):
    a = np.array(rows, dtype=float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def test_target_hit():
    # entry at open of bar 1 = 100. sigma 0.01, hold 4 -> 2% levels with "tight" (1x, 1x)
    o, h, l, c = bars([[100, 100, 100, 100], [100, 101, 99.5, 100.5], [100.5, 102.5, 100, 102], [102, 102, 101, 101], [101, 101, 100, 100], [100, 100, 100, 100]])
    out = simulate_all(o, h, l, c, np.full(6, 0.01), 4, "tight")
    assert out.valid[0]
    assert out.reason[0] == 1
    assert out.exit_idx[0] == 2
    assert out.exit_px[0] == pytest.approx(102.0)


def test_stop_wins_when_both_in_same_bar():
    o, h, l, c = bars([[100, 100, 100, 100], [100, 103, 97, 100], [100, 100, 100, 100], [100, 100, 100, 100], [100, 100, 100, 100], [100, 100, 100, 100]])
    out = simulate_all(o, h, l, c, np.full(6, 0.01), 4, "tight")
    assert out.reason[0] == 2
    assert out.exit_px[0] == pytest.approx(98.0)


def test_gap_through_stop_fills_at_open():
    o, h, l, c = bars([[100, 100, 100, 100], [100, 100.5, 99.5, 100], [95, 96, 94, 95], [95, 95, 95, 95], [95, 95, 95, 95], [95, 95, 95, 95]])
    out = simulate_all(o, h, l, c, np.full(6, 0.01), 4, "tight")
    assert out.reason[0] == 2
    assert out.exit_px[0] == pytest.approx(95.0)


def test_time_exit_at_last_close_of_hold():
    o, h, l, c = bars([[100, 100, 100, 100]] + [[100, 100.2, 99.9, 100.1]] * 4 + [[100.1, 100.1, 100.1, 100.1]])
    out = simulate_all(o, h, l, c, np.full(6, 0.01), 4, "timed")
    assert out.reason[0] == 0
    assert out.exit_idx[0] == 4  # entry bar 1, hold 4 -> last bar 4
    assert out.exit_px[0] == pytest.approx(100.1)


def test_signals_without_full_hold_window_are_invalid():
    o = h = l = c = np.full(10, 100.0)
    out = simulate_all(o, h, l, c, np.full(10, 0.01), 4, "tight")
    assert out.valid[:6].all() and not out.valid[6:].any()


def test_no_overlapping_positions():
    o = h = l = c = np.full(20, 100.0)
    out = simulate_all(o, h, l, c, np.full(20, 0.01), 4, "timed")
    taken = select_trades(np.ones(20, bool), out)
    # each trade: signal i, exit at i+4, next signal allowed at i+4
    assert list(taken) == [0, 4, 8, 12]


def test_net_includes_fees_both_sides():
    o, h, l, c = bars([[100, 100, 100, 100]] + [[100, 100, 100, 100]] * 5)
    out = simulate_all(o, h, l, c, np.full(6, 0.01), 4, "timed")
    net = out.net(0.006, 0.006)[0]
    assert net == pytest.approx(0.994 / 1.006 - 1)


def test_exit_levels_clipped():
    tp, sl = exit_levels(np.array([1e-6, 1.0]), 4, 1.0, 1.0)
    assert sl[0] == pytest.approx(0.005) and sl[1] == pytest.approx(0.15)


def test_no_lookahead_in_features_and_signals():
    from bot.features import add_cross_sectional

    uni = synthetic_universe(n_coins=4, days=400, seed=3)

    def feats_of(u):
        ctx = btc_context(u["BTC-USD"])
        return add_cross_sectional({k: coin_features(v, ctx) for k, v in u.items()})

    full = feats_of(uni)
    cut = len(uni["BTC-USD"]) - 37
    tr = feats_of({k: v.iloc[:cut] for k, v in uni.items()})
    pid = "C1-USD"
    pd.testing.assert_frame_equal(full[pid].iloc[:cut], tr[pid], check_freq=False)
    for fam, spec in FAMILIES.items():
        for p in spec["grid"][:4]:
            a = signal(fam, p, full[pid])[:cut]
            b = signal(fam, p, tr[pid])
            assert (a == b).all(), (fam, p)


def test_live_window_gives_same_features_as_full_history():
    """The scan only fetches 800 hourly bars; long averages must match the backtest's values exactly."""
    from bot.features import add_cross_sectional

    uni = synthetic_universe(n_coins=3, days=200, seed=8)
    ctx_full = btc_context(uni["BTC-USD"])
    full = add_cross_sectional({k: coin_features(v, ctx_full) for k, v in uni.items()})
    short_uni = {k: v.iloc[-800:] for k, v in uni.items()}
    daily = uni["BTC-USD"]["close"].resample("1D").last()
    short = add_cross_sectional({k: coin_features(v, btc_context(short_uni["BTC-USD"], daily)) for k, v in short_uni.items()})
    cols = ["sma480", "sma240", "hi480", "ret_168", "mom_rank", "sigma", "rsi14", "btc_up50"]
    a = full["C1-USD"][cols].iloc[-24:]
    b = short["C1-USD"][cols].iloc[-24:]
    pd.testing.assert_frame_equal(a, b, check_freq=False, rtol=1e-9)


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_random_data_has_no_survivors_even_with_zero_fees(cfg):
    c = copy.deepcopy(cfg)
    c["fees"] = {"maker_pct": 0.0, "taker_pct": 0.0, "slippage_pct": 0.0}
    c["backtest"]["random_trials"] = 100
    u = prepare(synthetic_universe(n_coins=5, days=1095, seed=11), "BTC-USD")
    res = run_research(u, c, log=lambda *a: None)
    picked = [f for f in res["families"] if f.get("selected")]
    assert picked, "with zero fees some configs should look positive on training by luck"
    assert not [f["family"] for f in res["families"] if f["survived"]]


def test_planted_edge_is_found(cfg):
    uni = synthetic_universe(n_coins=5, days=1095, seed=5)
    rng = np.random.default_rng(1)
    for pid, df in uni.items():
        df = df.copy()
        r = np.log(df["close"]).diff().fillna(0).to_numpy().copy()
        vol = df["volume"].to_numpy().copy()
        events = rng.choice(np.arange(300, len(df) - 30), size=len(df) // 60, replace=False)
        for e in events:
            vol[e] *= 12
            r[e] = abs(r[e]) + 0.02
            r[e + 2 : e + 14] += 0.004  # drift up for 12 hours after the spike
        close = 100 * np.exp(np.cumsum(r))
        open_ = np.concatenate([[100.0], close[:-1]])
        df["close"], df["open"] = close, open_
        df["high"] = np.maximum(open_, close) * 1.001
        df["low"] = np.minimum(open_, close) * 0.999
        df["volume"] = vol
        uni[pid] = df
    c = copy.deepcopy(cfg)
    c["backtest"]["random_trials"] = 100
    c["backtest"]["hold_hours"] = [4, 24]  # the planted edge lasts 12 hours
    res = run_research(prepare(uni, "BTC-USD"), c, log=lambda *a: None)
    surv = {f["family"] for f in res["families"] if f["survived"]}
    assert surv & {"volume_spike", "breakout"}, [(f["family"], f["fail_reasons"]) for f in res["families"]]
