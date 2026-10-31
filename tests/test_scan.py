import copy
import json

import numpy as np
import pandas as pd
import pytest

from bot.backtest import simulate_all
from bot.broker import Broker, SafetyError
from bot.config import costs, load_config
from bot.journal import Journal, load_state, save_state
from bot.risk import gate, size_position
from bot.scan import run
from bot.synthetic import synthetic_universe

DAY_S = 86400


class FakeAPI:
    """Serves synthetic candles the way Coinbase does, including the candle still forming."""

    def __init__(self, uni, now):
        self.uni = uni
        self.now = now

    def candles(self, pid, start, end, granularity=3600):
        df = self.uni.get(pid if pid in self.uni else "BTC-USD")
        if granularity == DAY_S:
            df = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        return df[(df.index >= pd.Timestamp(start).floor("h")) & (df.index <= pd.Timestamp(end)) & (df.index <= self.now)]

    def ticker(self, pid):
        if pid == "BTC-GBP":
            return {"price": str(self.ticker("BTC-USD")["price"] * 0.8)}
        df = self.uni[pid]
        bar = df[df.index <= self.now].iloc[-1]  # forming candle: its open is the next-open the backtest uses
        p = float(bar["open"])
        return {"price": p, "bid": p, "ask": p}


@pytest.fixture()
def env(tmp_path):
    cfg = load_config()
    uni = synthetic_universe(n_coins=3, days=60, seed=2)
    rep = tmp_path / "reports"
    st = tmp_path / "state"
    rep.mkdir()
    st.mkdir()
    (rep / "research.json").write_text(json.dumps({"coins": list(uni)}))
    surv = [{
        "family": "session", "title": "Time of day entry", "rule": "x", "key": "session[hour=10]|4h|tight",
        "params": {"hour": 10}, "hold": 4, "profile": "tight",
        "test": {"n": 100, "win_rate": 0.55, "avg_net_pct": 0.3, "profit_factor": 1.3, "positive_month_share": 0.7, "typical_stop_pct": 2, "typical_target_pct": 2},
    }]
    (rep / "survivors.json").write_text(json.dumps(surv))
    msgs = []
    return cfg, uni, rep, st, msgs


def scan_at(env, when):
    cfg, uni, rep, st, msgs = env
    now = pd.Timestamp(when).tz_convert("UTC")
    return run(cfg, FakeAPI(uni, now), now, notify=msgs.append, reports_dir=rep, state_dir=st, docs_dir=st.parent / "docs")


def test_paper_trade_matches_backtest_exactly(env):
    cfg, uni, rep, st, msgs = env
    cfg["risk"]["max_open_positions"] = 3
    end = uni["BTC-USD"].index[-1]
    day = (end - pd.Timedelta(days=3)).floor("D")
    open_at = day + pd.Timedelta(hours=10, minutes=7)  # the 09:00 candle has just closed
    scan_at(env, open_at)
    j = Journal(st / "trades.csv").rows()
    assert len(j) == 3, msgs  # one per coin
    for h in range(1, 8):
        scan_at(env, open_at + pd.Timedelta(hours=h))
    rows = {r["coin"]: r for r in Journal(st / "trades.csv").rows()}
    cost = costs(cfg)
    for pid, df in uni.items():
        from bot.features import btc_context, coin_features

        f = coin_features(df, btc_context(uni["BTC-USD"]))
        i = f.index.get_loc(day + pd.Timedelta(hours=9))
        out = simulate_all(f["open"], f["high"], f["low"], f["close"], f["sigma"], 4, "tight")
        r = rows[pid]
        assert r["status"] == "closed"
        assert r["entry_price"] == pytest.approx(out.entry_px[i])
        assert r["exit_price"] == pytest.approx(out.exit_px[i], rel=1e-9)
        assert r["exit_reason"] == {0: "time", 1: "target", 2: "stop"}[int(out.reason[i])]
        assert r["pnl_pct"] / 100 == pytest.approx(out.net(*cost["a"])[i], abs=1e-6)


def test_rerun_same_hour_does_not_duplicate(env):
    cfg, uni, rep, st, msgs = env
    cfg["risk"]["max_open_positions"] = 3
    day = (uni["BTC-USD"].index[-1] - pd.Timedelta(days=3)).floor("D")
    t = day + pd.Timedelta(hours=10, minutes=7)
    scan_at(env, t)
    scan_at(env, t + pd.Timedelta(minutes=20))
    assert len(Journal(st / "trades.csv").rows()) == 3


def test_max_open_positions_respected(env):
    cfg, uni, rep, st, msgs = env
    cfg["risk"]["max_open_positions"] = 2
    day = (uni["BTC-USD"].index[-1] - pd.Timedelta(days=3)).floor("D")
    scan_at(env, day + pd.Timedelta(hours=10, minutes=7))
    assert len(Journal(st / "trades.csv").rows()) == 2
    assert any("already 2 open positions" in m for m in msgs)


def test_halted_bot_opens_nothing(env):
    cfg, uni, rep, st, msgs = env
    save_state(st / "state.json", {"halted": True, "halt_reason": "test"})
    day = (uni["BTC-USD"].index[-1] - pd.Timedelta(days=3)).floor("D")
    scan_at(env, day + pd.Timedelta(hours=10, minutes=7))
    assert len(Journal(st / "trades.csv").rows()) == 0


def test_daily_summary_sent_once(env):
    cfg, uni, rep, st, msgs = env
    day = (uni["BTC-USD"].index[-1] - pd.Timedelta(days=2)).floor("D")
    scan_at(env, day + pd.Timedelta(hours=14, minutes=7))  # 14:07 UTC is >= 14:00 UK in winter and summer
    scan_at(env, day + pd.Timedelta(hours=15, minutes=7))
    assert sum("Daily summary" in m for m in msgs) == 1
    assert load_state(st / "state.json")["last_daily_summary"]


def test_no_survivors_means_no_trades(env):
    cfg, uni, rep, st, msgs = env
    (rep / "survivors.json").write_text("[]")
    day = (uni["BTC-USD"].index[-1] - pd.Timedelta(days=2)).floor("D")
    scan_at(env, day + pd.Timedelta(hours=14, minutes=7))
    assert len(Journal(st / "trades.csv").rows()) == 0
    assert any("watching but not trading" in m for m in msgs)


def test_sizing_caps_risk():
    cfg = load_config()
    d = size_position(100, 100, 0.05, 0.012, cfg)  # 2% of 100 = £2 risk, loss per £ = 6.2%
    assert d.ok and d.size_gbp == pytest.approx(32.26, abs=0.01) and d.risk_gbp <= 2.0 + 1e-9
    d = size_position(100, 100, 0.01, 0.012, cfg)
    assert d.size_gbp == cfg["risk"]["max_position_gbp"]
    assert not size_position(100, 3, 0.05, 0.012, cfg).ok


def test_gates():
    cfg = load_config()
    st = {"halted": False}
    assert gate(st, 100, [], 0, 0, "SOL-USD", cfg).ok
    assert not gate(st, 79, [], 0, 0, "SOL-USD", cfg).ok
    assert not gate(st, 100, [], 3, 0, "SOL-USD", cfg).ok
    assert not gate(st, 100, [], 0, -5.0, "SOL-USD", cfg).ok
    assert not gate(st, 100, [{"coin": "SOL-USD"}], 0, 0, "SOL-USD", cfg).ok


class FakeClient:
    def __init__(self, perms):
        self.perms = perms

    def get(self, path, params=None):
        assert path.endswith("/key_permissions")
        return self.perms


def live_cfg(portfolio="p1"):
    cfg = copy.deepcopy(load_config())
    cfg["live"]["portfolio_uuid"] = portfolio
    return cfg


def test_broker_refuses_transfer_permission():
    b = Broker(live_cfg(), client=FakeClient({"can_view": True, "can_trade": True, "can_transfer": True, "portfolio_uuid": "p1"}))
    with pytest.raises(SafetyError, match="Transfer"):
        b.check_permissions()


def test_broker_refuses_wrong_portfolio():
    b = Broker(live_cfg(), client=FakeClient({"can_view": True, "can_trade": True, "can_transfer": False, "portfolio_uuid": "other"}))
    with pytest.raises(SafetyError, match="different portfolio"):
        b.check_permissions()


def test_broker_accepts_scoped_trade_key():
    b = Broker(live_cfg(), client=FakeClient({"can_view": True, "can_trade": True, "can_transfer": False, "portfolio_uuid": "p1"}))
    assert b.check_permissions()["can_trade"]


def test_live_regime_is_known_today():
    from bot.features import btc_context

    uni = synthetic_universe(n_coins=1, days=420, seed=4)
    btc = uni["BTC-USD"]
    now = btc.index[-1] - pd.Timedelta(hours=5) + pd.Timedelta(minutes=7)
    hourly = btc[btc.index < now.floor("h")]
    daily = btc.resample("1D").last()["close"]
    daily = daily[daily.index + pd.Timedelta(days=1) <= now]  # only finished days, like the live scan
    live = btc_context(hourly.iloc[-500:], daily)
    full = btc_context(hourly)
    assert np.isfinite(live["btc_up50"].iloc[-1])
    assert live["btc_up50"].iloc[-1] == full["btc_up50"].iloc[-1]


def test_stale_coin_data_is_not_traded(env):
    cfg, uni, rep, st, msgs = env
    cfg["risk"]["max_open_positions"] = 3
    day = (uni["BTC-USD"].index[-1] - pd.Timedelta(days=3)).floor("D")
    t = day + pd.Timedelta(hours=10, minutes=7)
    df = uni["C1-USD"]
    uni["C1-USD"] = df[df.index < day + pd.Timedelta(hours=8)]  # C1 stopped printing candles 2h ago
    scan_at(env, t)
    coins = {r["coin"] for r in Journal(st / "trades.csv").rows()}
    assert "C1-USD" not in coins and "BTC-USD" in coins


def test_candidates_trade_in_test_mode_only(env):
    cfg, uni, rep, st, msgs = env
    cfg["risk"]["max_open_positions"] = 3
    surv = json.loads((rep / "survivors.json").read_text())
    surv[0]["status"] = "candidate"
    (rep / "survivors.json").write_text(json.dumps(surv))
    day = (uni["BTC-USD"].index[-1] - pd.Timedelta(days=3)).floor("D")
    t = day + pd.Timedelta(hours=10, minutes=7)
    cfg["mode"] = "LIVE_MANUAL"
    scan_at(env, t)
    assert len(Journal(st / "trades.csv").rows()) == 0
    cfg["mode"] = "PAPER"
    scan_at(env, t + pd.Timedelta(minutes=5))
    rows = Journal(st / "trades.csv").rows()
    assert len(rows) == 3 and all("unproven" in r["note"] for r in rows)


def test_dashboard_data_and_decision_log(env):
    cfg, uni, rep, st, msgs = env
    cfg["risk"]["max_open_positions"] = 3
    day = (uni["BTC-USD"].index[-1] - pd.Timedelta(days=3)).floor("D")
    start = day + pd.Timedelta(hours=8, minutes=7)
    for h in range(0, 10):
        scan_at(env, start + pd.Timedelta(hours=h))
    js = (st.parent / "docs" / "data.js").read_text()
    assert js.startswith("window.BOT_DATA = ")
    d = json.loads(js[len("window.BOT_DATA = "):].rstrip().rstrip(";"))
    assert len(d["equity"]) == 10 and len(d["decisions"]) == 10
    assert d["decisions"][-1]["text"].startswith("No trade")  # oldest first scan: nothing fired at 07:00
    assert any(x["text"].startswith("Bought") for x in d["decisions"])
    assert any(x["text"].startswith("Sold") for x in d["decisions"])
    sides = {t["side"] for t in d["trades"]}
    assert sides == {"BUY", "SELL"}
    closed = [r for r in Journal(st / "trades.csv").rows() if r["status"] == "closed"]
    assert d["balance_gbp"] == pytest.approx(100 + sum(r["pnl_gbp"] for r in closed) + d["open_pnl_gbp"], abs=0.02)
