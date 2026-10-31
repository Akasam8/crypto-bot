"""Risk rules. These are enforced in code before any trade, paper or live."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Decision:
    ok: bool
    reason: str = ""
    size_gbp: float = 0.0
    risk_gbp: float = 0.0


def size_position(pot_gbp: float, free_gbp: float, sl_pct: float, round_trip_cost: float, cfg: dict) -> Decision:
    """Size so that a stop out (stop distance plus fees) loses at most max_risk_per_trade_pct of the pot."""
    r = cfg["risk"]
    loss_per_gbp = sl_pct + round_trip_cost
    if loss_per_gbp <= 0:
        return Decision(False, "invalid stop")
    budget = pot_gbp * r["max_risk_per_trade_pct"] / 100.0
    size = min(budget / loss_per_gbp, r["max_position_gbp"], free_gbp)
    if size < r["min_position_gbp"]:
        return Decision(False, f"position would be £{size:.2f}, below the £{r['min_position_gbp']:.0f} minimum")
    return Decision(True, size_gbp=round(size, 2), risk_gbp=round(size * loss_per_gbp, 2))


def gate(state: dict, pot_gbp: float, open_positions: list[dict], trades_today: int, realised_today_gbp: float, coin: str, cfg: dict) -> Decision:
    r = cfg["risk"]
    if state.get("halted"):
        return Decision(False, f"bot is halted: {state.get('halt_reason', '')}")
    if pot_gbp <= r["pot_floor_gbp"]:
        return Decision(False, f"pot £{pot_gbp:.2f} is at or below the £{r['pot_floor_gbp']:.0f} floor")
    if len(open_positions) >= r["max_open_positions"]:
        return Decision(False, f"already {len(open_positions)} open positions")
    if trades_today >= r["max_new_trades_per_day"]:
        return Decision(False, f"already {trades_today} trades today")
    if realised_today_gbp <= -r["daily_loss_limit_gbp"]:
        return Decision(False, f"daily loss limit hit (£{realised_today_gbp:.2f} today)")
    if any(p["coin"] == coin for p in open_positions):
        return Decision(False, f"already holding {coin}")
    return Decision(True)
