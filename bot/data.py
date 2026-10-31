"""Coinbase public market data (no API keys): products, tickers, candles, local cache, universe."""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE_URL = "https://api.exchange.coinbase.com"
HOUR = 3600
DAY = 86400
MAX_CANDLES = 290  # Coinbase allows 300 per request, keep a margin

STABLE_OR_WRAPPED = {
    "USDT", "USDC", "DAI", "PYUSD", "EURC", "EUROC", "GUSD", "PAX", "PAXG", "XAUT", "USDS",
    "FDUSD", "TUSD", "BUSD", "UST", "LUSD", "GYEN", "RLUSD", "USD1", "USDE", "WBTC", "CBBTC",
    "CBETH", "WETH", "STETH", "WSTETH", "RETH", "MSOL", "JITOSOL", "LSETH", "CBDOGE", "CBXRP",
}

COLS = ["open", "high", "low", "close", "volume"]


def _iso(ts: pd.Timestamp) -> str:
    return pd.Timestamp(ts).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_frame() -> pd.DataFrame:
    df = pd.DataFrame(columns=COLS, dtype=float)
    df.index = pd.DatetimeIndex([], tz="UTC", name="time")
    return df


def rows_to_frame(rows) -> pd.DataFrame:
    """Coinbase rows are [time, low, high, open, close, volume], newest first."""
    if not rows:
        return empty_frame()
    a = np.asarray(rows, dtype=float)
    idx = pd.to_datetime(a[:, 0].astype("int64"), unit="s", utc=True)
    df = pd.DataFrame(
        {"open": a[:, 3], "high": a[:, 2], "low": a[:, 1], "close": a[:, 4], "volume": a[:, 5]},
        index=idx,
    )
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index.name = "time"
    return df


def complete_only(df: pd.DataFrame, granularity_s: int = HOUR, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Drop the candle that is still forming. Only closed candles are ever used for signals."""
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    return df[df.index + pd.Timedelta(seconds=granularity_s) <= now]


def fill_gaps(df: pd.DataFrame, freq: str = "1h", end: pd.Timestamp | None = None) -> pd.DataFrame:
    """Coinbase skips candles with no trades. Fill them flat at the previous close with zero volume."""
    if df.empty:
        return df
    last = max(df.index[-1], end) if end is not None else df.index[-1]
    idx = pd.date_range(df.index[0], last, freq=freq, tz="UTC", name="time")
    out = df.reindex(idx)
    close = out["close"].ffill()
    missing = out["open"].isna()
    for c in ("open", "high", "low"):
        out[c] = out[c].where(~missing, close)
    out["close"] = close
    out["volume"] = out["volume"].fillna(0.0)
    return out


class CoinbasePublic:
    def __init__(self, base_url: str = BASE_URL, rate_per_sec: float = 7.0, timeout: int = 20, session=None):
        self.base_url = base_url
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "crypto-bot/1.0", "Accept": "application/json"})
        self._min_gap = 1.0 / rate_per_sec
        self._last = 0.0
        self.requests_made = 0

    def _throttle(self):
        gap = self._min_gap - (time.monotonic() - self._last)
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()

    def get(self, path: str, params: dict | None = None, tries: int = 6):
        err = None
        for attempt in range(tries):
            self._throttle()
            try:
                r = self.session.get(self.base_url + path, params=params, timeout=self.timeout)
                self.requests_made += 1
            except requests.RequestException as e:
                err = e
                time.sleep(min(30, 2 ** attempt))
                continue
            if r.status_code == 404:
                return None
            if r.status_code == 403:
                raise RuntimeError(f"HTTP 403 from {self.base_url}")
            if r.status_code == 429 or r.status_code >= 500:
                err = RuntimeError(f"HTTP {r.status_code}")
                time.sleep(min(30, 2 ** attempt))
                continue
            if r.status_code == 400:
                raise RuntimeError(f"HTTP 400 for {path} {params}: {r.text[:200]}")
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"GET {path} failed after {tries} tries: {err}")

    def products(self) -> list[dict]:
        return self.get("/products") or []

    def ticker(self, product_id: str) -> dict | None:
        return self.get(f"/products/{product_id}/ticker")

    def candles(self, product_id: str, start: pd.Timestamp, end: pd.Timestamp, granularity: int = HOUR) -> pd.DataFrame:
        span = pd.Timedelta(seconds=granularity * MAX_CANDLES)
        rows: list = []
        t = pd.Timestamp(start)
        end = pd.Timestamp(end)
        while t < end:
            t2 = min(t + span, end)
            data = self.get(
                f"/products/{product_id}/candles",
                {"granularity": granularity, "start": _iso(t), "end": _iso(t2)},
            )
            if data:
                rows.extend(data)
            t = t2
        return rows_to_frame(rows)

    def recent_candles(self, product_id: str, bars: int, granularity: int = HOUR) -> pd.DataFrame:
        end = pd.Timestamp.now(tz="UTC")
        start = end - pd.Timedelta(seconds=granularity * bars)
        return self.candles(product_id, start, end, granularity)


class CoinbaseAdvancedPublic(CoinbasePublic):
    """Same interface, using Coinbase Advanced Trade's public market endpoints. Used as a fallback
    if the Exchange API refuses the runner's IP."""

    GRAN = {HOUR: "ONE_HOUR", DAY: "ONE_DAY"}
    MAX = 340

    def __init__(self, **kw):
        super().__init__(base_url="https://api.coinbase.com/api/v3/brokerage/market", **kw)

    def products(self) -> list[dict]:
        r = self.get("/products", {"product_type": "SPOT", "limit": 1000}) or {}
        out = []
        for p in r.get("products", []):
            out.append({
                "id": p.get("product_id"),
                "base_currency": p.get("base_currency_id") or p.get("base_display_symbol"),
                "quote_currency": p.get("quote_currency_id") or p.get("quote_display_symbol"),
                "status": str(p.get("status", "")).lower(),
                "trading_disabled": bool(p.get("trading_disabled") or p.get("is_disabled")),
                "fx_stablecoin": False,
            })
        return out

    def ticker(self, product_id: str) -> dict | None:
        r = self.get(f"/products/{product_id}/ticker", {"limit": 1})
        if not r:
            return None
        price = (r.get("trades") or [{}])[0].get("price") or r.get("best_bid")
        return {"bid": r.get("best_bid"), "ask": r.get("best_ask"), "price": price}

    def candles(self, product_id: str, start: pd.Timestamp, end: pd.Timestamp, granularity: int = HOUR) -> pd.DataFrame:
        span = pd.Timedelta(seconds=granularity * self.MAX)
        rows = []
        t = pd.Timestamp(start)
        end = pd.Timestamp(end)
        while t < end:
            t2 = min(t + span, end)
            r = self.get(f"/products/{product_id}/candles", {"start": int(t.timestamp()), "end": int(t2.timestamp()), "granularity": self.GRAN[granularity]})
            for c in (r or {}).get("candles", []):
                rows.append([int(c["start"]), float(c["low"]), float(c["high"]), float(c["open"]), float(c["close"]), float(c["volume"])])
            t = t2
        return rows_to_frame(rows)


def make_api(log=print) -> CoinbasePublic:
    """Exchange API first; switch to the Advanced Trade public API if it's blocked or broken."""
    api = CoinbasePublic()
    try:
        t = api.get("/products/BTC-USD/ticker", tries=2)
        if t and t.get("price"):
            return api
    except Exception as e:  # noqa: BLE001
        log(f"[data] Exchange API unavailable ({e}), trying Advanced Trade public API")
    adv = CoinbaseAdvancedPublic()
    t = adv.ticker("BTC-USD")
    if not t or not t.get("price"):
        raise RuntimeError("neither Coinbase public API answered")
    log("[data] using Coinbase Advanced Trade public API")
    return adv


class CandleStore:
    """Parquet cache of hourly candles per product, so later runs only fetch new candles."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, pid: str) -> Path:
        return self.root / f"{pid}.parquet"

    def load(self, pid: str) -> pd.DataFrame | None:
        p = self.path(pid)
        if not p.exists():
            return None
        df = pd.read_parquet(p)
        df.index = pd.DatetimeIndex(df.index, tz="UTC", name="time") if df.index.tz is None else df.index
        return df

    def save(self, pid: str, df: pd.DataFrame):
        df.to_parquet(self.path(pid))

    def update(self, api: CoinbasePublic, pid: str, history_days: int, now: pd.Timestamp | None = None) -> pd.DataFrame:
        now = (now or pd.Timestamp.now(tz="UTC")).floor("h")
        start_needed = now - pd.Timedelta(days=history_days)
        cached = self.load(pid)
        if cached is None or cached.empty:
            df = api.candles(pid, start_needed, now, HOUR)
        else:
            fresh = api.candles(pid, cached.index[-1] + pd.Timedelta(hours=1), now, HOUR)
            df = pd.concat([cached, fresh])
            df = df[~df.index.duplicated(keep="last")].sort_index()
        df = complete_only(df, HOUR, now)
        df = df[df.index >= start_needed]
        if not df.empty:
            self.save(pid, df)
        return df


def list_products(api: CoinbasePublic, quote: str = "USD", exclude=()) -> list[str]:
    ex = {e.upper() for e in exclude} | STABLE_OR_WRAPPED
    out = set()
    for p in api.products():
        if p.get("quote_currency") != quote:
            continue
        if p.get("status") != "online" or p.get("trading_disabled") or p.get("fx_stablecoin"):
            continue
        base = str(p.get("base_currency", "")).upper()
        if not base or base in ex:
            continue
        out.add(p["id"])
    return sorted(out)


def rank_by_volume(api: CoinbasePublic, product_ids: list[str], days: int = 30) -> list[tuple[str, float]]:
    end = pd.Timestamp.now(tz="UTC").floor("D")
    start = end - pd.Timedelta(days=days)
    ranked = []
    for pid in product_ids:
        d = api.candles(pid, start, end, DAY)
        if len(d) < days * 0.66:
            continue
        ranked.append((pid, float((d["volume"] * d["close"]).median())))
    ranked.sort(key=lambda x: -x[1])
    return ranked


def build_universe(api: CoinbasePublic, cfg: dict, store: CandleStore, log=print) -> dict[str, pd.DataFrame]:
    dc = cfg["data"]
    products = list_products(api, dc["quote"], dc.get("exclude", []))
    log(f"[data] {len(products)} tradable {dc['quote']} products, ranking by 30 day volume")
    ranked = rank_by_volume(api, products)
    pool = [pid for pid, _ in ranked[: dc["candidate_pool"]]]
    btc = f"BTC-{dc['quote']}"
    if btc not in pool:
        pool.insert(0, btc)
    universe: dict[str, pd.DataFrame] = {}
    for pid in pool:
        df = store.update(api, pid, dc["history_days"])
        days = (df.index[-1] - df.index[0]).days if len(df) else 0
        if pid != btc and days < dc["min_history_days"]:
            log(f"[data] skip {pid}: only {days} days of history")
            continue
        universe[pid] = fill_gaps(df)
        log(f"[data] {pid}: {len(df)} candles, {days} days")
        if len(universe) >= dc["universe_size"] and btc in universe:
            break
    log(f"[data] universe: {len(universe)} coins, {api.requests_made} requests")
    return universe


def gbp_per_usd(api: CoinbasePublic, fallback_gbpusd: float) -> float:
    """GBP value of 1 USD, from BTC-USD vs BTC-GBP."""
    try:
        a = api.ticker("BTC-USD")
        b = api.ticker("BTC-GBP")
        return float(b["price"]) / float(a["price"])
    except Exception as e:  # noqa: BLE001
        print(f"[data] GBP rate fallback used: {e}")
        return 1.0 / fallback_gbpusd
