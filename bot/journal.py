"""Trade journal (state/trades.csv) and bot state (state/state.json). Both are committed to the repo."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

COLUMNS = [
    "id", "mode", "coin", "product", "setup", "setup_key", "signal_time", "entry_time", "entry_price",
    "size_gbp", "units", "risk_gbp", "sl_price", "tp_price", "hold_hours", "exit_by", "last_checked",
    "exit_time", "exit_price", "exit_reason", "fees_gbp", "pnl_gbp", "pnl_pct", "status", "order_id", "note",
]
NUMERIC = ["entry_price", "size_gbp", "units", "risk_gbp", "sl_price", "tp_price", "hold_hours", "exit_price", "fees_gbp", "pnl_gbp", "pnl_pct"]

DEFAULT_STATE = {
    "halted": False,
    "halt_reason": "",
    "last_daily_summary": "",
    "last_weekly_summary": "",
    "last_run": "",
    "consecutive_errors": 0,
}


class Journal:
    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.exists() and self.path.stat().st_size > 0:
            df = pd.read_csv(self.path, dtype=str, keep_default_na=False)
            for c in COLUMNS:
                if c not in df.columns:
                    df[c] = ""
            self.df = df[COLUMNS]
        else:
            self.df = pd.DataFrame(columns=COLUMNS, dtype=str)

    def rows(self, status: str | None = None) -> list[dict]:
        df = self.df if status is None else self.df[self.df["status"] == status]
        out = []
        for _, r in df.iterrows():
            d = dict(r)
            for c in NUMERIC:
                d[c] = float(d[c]) if d.get(c) not in (None, "") else None
            out.append(d)
        return out

    def open_positions(self) -> list[dict]:
        return self.rows("open")

    def closed(self) -> list[dict]:
        return self.rows("closed")

    def has(self, setup_key: str, coin: str, signal_time: str) -> bool:
        m = (self.df["setup_key"] == setup_key) & (self.df["coin"] == coin) & (self.df["signal_time"] == signal_time)
        return bool(m.any())

    def add(self, rec: dict):
        row = {c: "" if rec.get(c) is None else str(rec.get(c)) for c in COLUMNS}
        self.df = pd.concat([self.df, pd.DataFrame([row], columns=COLUMNS)], ignore_index=True)

    def update(self, trade_id: str, **fields):
        m = self.df["id"] == trade_id
        for k, v in fields.items():
            self.df.loc[m, k] = "" if v is None else str(v)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(self.path, index=False)


def load_state(path: Path) -> dict:
    s = dict(DEFAULT_STATE)
    if Path(path).exists():
        s.update(json.loads(Path(path).read_text() or "{}"))
    return s


def save_state(path: Path, state: dict):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(state, indent=2) + "\n")
