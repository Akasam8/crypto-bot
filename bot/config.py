"""Config loading. Tunables live in config.toml, secrets only in environment variables."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
STATE_DIR = ROOT / "state"
PROJECT_DIR = ROOT / "claude_project"

MODES = ("PAPER", "LIVE_MANUAL", "LIVE_AUTO")


def _env_bool(name: str):
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return None
    return v.strip().lower() in ("1", "true", "yes", "on")


def load_dotenv(path: Path = ROOT / ".env"):
    """For running on your own PC: KEY=VALUE lines in .env become env vars (real env vars win)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_config(path: str | os.PathLike | None = None) -> dict:
    load_dotenv()
    p = Path(path) if path else ROOT / "config.toml"
    with open(p, "rb") as f:
        cfg = tomllib.load(f)
    mode = os.environ.get("BOT_MODE", "").strip().upper() or cfg.get("mode", "PAPER").upper()
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}, expected one of {MODES}")
    cfg["mode"] = mode
    te = _env_bool("TRADING_ENABLED")
    if te is not None:
        cfg["trading_enabled"] = te
    portfolio = os.environ.get("COINBASE_PORTFOLIO_UUID", "").strip()
    if portfolio:
        cfg["live"]["portfolio_uuid"] = portfolio
    return cfg


def costs(cfg: dict) -> dict:
    """Per side costs as fractions. 'a' = taker both sides (main), 'b' = maker entry, taker exit."""
    f = cfg["fees"]
    taker = (f["taker_pct"] + f["slippage_pct"]) / 100.0
    maker = f["maker_pct"] / 100.0
    return {"a": (taker, taker), "b": (maker, taker)}


def round_trip_pct(cfg: dict) -> float:
    c_in, c_out = costs(cfg)["a"]
    return (c_in + c_out) * 100.0
