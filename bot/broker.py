"""Live trading on Coinbase Advanced. Only used when mode = LIVE_AUTO and trading_enabled = true.

Safety rules baked in here:
  * refuses to start if the API key can transfer funds, can't trade, or isn't scoped to the
    configured "bot" portfolio
  * spot, long only: it only ever sends BUY limit orders with an attached take profit / stop loss,
    and SELL orders to close what it bought. No leverage or margin fields are ever set.
  * client order IDs are derived from the signal, so a rerun can't double buy

Needs env vars COINBASE_API_KEY (the key name, organizations/.../apiKeys/...) and
COINBASE_API_SECRET (the EC private key, ECDSA type). Treat the first live runs as supervised:
this module was written against Coinbase's docs and can't be exercised without a real account.
"""
from __future__ import annotations

import os
import uuid
from decimal import ROUND_DOWN, Decimal

import pandas as pd

API = "/api/v3/brokerage"


class SafetyError(RuntimeError):
    halt = True


def _floor_to(x: float, inc: str) -> str:
    """Round down to Coinbase's increment exactly (Decimal, so 0.3 at step 0.1 stays 0.3)."""
    step = Decimal(str(inc))
    v = (Decimal(repr(float(x))) / step).to_integral_value(rounding=ROUND_DOWN) * step
    return format(v.quantize(step), "f")


class Broker:
    def __init__(self, cfg: dict, client=None):
        if client is None:
            from coinbase.rest import RESTClient

            key = os.environ.get("COINBASE_API_KEY", "").strip()
            secret = os.environ.get("COINBASE_API_SECRET", "").strip().replace("\\n", "\n")
            if not key or not secret:
                raise SafetyError("COINBASE_API_KEY / COINBASE_API_SECRET secrets are missing")
            client = RESTClient(api_key=key, api_secret=secret)
        self.c = client
        self.cfg = cfg
        self.quote = cfg["live"]["quote_currency"]
        self.portfolio = cfg["live"].get("portfolio_uuid", "")
        self.buffer = cfg["live"]["entry_limit_buffer_pct"] / 100.0
        self._products = {}

    def _get(self, path, params=None) -> dict:
        r = self.c.get(API + path, params=params)
        return r if isinstance(r, dict) else r.to_dict()

    def _post(self, path, data) -> dict:
        r = self.c.post(API + path, data=data)
        return r if isinstance(r, dict) else r.to_dict()

    def check_permissions(self):
        p = self._get("/key_permissions")
        if p.get("can_transfer"):
            raise SafetyError("the Coinbase API key has Transfer permission. Make a new key with View and Trade only.")
        if not p.get("can_trade"):
            raise SafetyError("the Coinbase API key can't trade. Give it View and Trade.")
        if not self.portfolio:
            raise SafetyError("COINBASE_PORTFOLIO_UUID isn't set, so the bot can't confirm it's using the bot portfolio")
        if p.get("portfolio_uuid") != self.portfolio:
            raise SafetyError("the API key is scoped to a different portfolio than COINBASE_PORTFOLIO_UUID")
        return p

    def product_id(self, pid_usd: str) -> str:
        return f"{pid_usd.split('-')[0]}-{self.quote}"

    def product(self, product_id: str) -> dict:
        if product_id not in self._products:
            self._products[product_id] = self._get(f"/products/{product_id}")
        return self._products[product_id]

    def best_bid_ask(self, product_id: str) -> dict | None:
        r = self._get("/best_bid_ask", {"product_ids": product_id})
        books = r.get("pricebooks") or []
        if not books or not books[0].get("bids") or not books[0].get("asks"):
            return None
        return {"bid": books[0]["bids"][0]["price"], "ask": books[0]["asks"][0]["price"]}

    def balances(self) -> dict[str, float]:
        r = self._get("/accounts", {"limit": 250})
        out = {}
        for a in r.get("accounts", []):
            avail = float(a.get("available_balance", {}).get("value", 0) or 0)
            hold = float(a.get("hold", {}).get("value", 0) or 0)
            out[a["currency"]] = out.get(a["currency"], 0.0) + avail + hold
        return out

    def portfolio_value_gbp(self, gbp_per_usd: float) -> float:
        total_usd = 0.0
        for cur, amt in self.balances().items():
            if amt <= 0:
                continue
            if cur in ("USD", "USDC"):
                total_usd += amt
            elif cur == "GBP":
                total_usd += amt / gbp_per_usd
            else:
                bba = self.best_bid_ask(f"{cur}-{self.quote}")
                if bba:
                    total_usd += amt * float(bba["bid"])
        return total_usd * gbp_per_usd

    def open_position(self, product_id: str, quote_amount: float, ask: float, sl_px: float, tp_px: float | None, client_order_id: str) -> dict:
        p = self.product(product_id)
        if p.get("trading_disabled") or p.get("is_disabled"):
            return {"ok": False, "error": "product disabled"}
        price_inc = p.get("price_increment") or p.get("quote_increment")
        limit = float(_floor_to(ask * (1 + self.buffer), price_inc))
        base = _floor_to(quote_amount / limit, p["base_increment"])
        if float(base) < float(p.get("base_min_size") or 0) or float(base) * limit < float(p.get("quote_min_size") or 0):
            return {"ok": False, "error": "below Coinbase minimum order size"}
        tp = tp_px if tp_px else ask * 1.5  # timed setups: far away target, the stop and the time exit do the work
        body = {
            "client_order_id": str(uuid.uuid5(uuid.NAMESPACE_URL, client_order_id)),
            "product_id": product_id,
            "side": "BUY",
            "order_configuration": {"limit_limit_gtc": {"base_size": base, "limit_price": _floor_to(limit, price_inc), "post_only": False}},
            "attached_order_configuration": {"trigger_bracket_gtc": {"limit_price": _floor_to(tp, price_inc), "stop_trigger_price": _floor_to(sl_px, price_inc)}},
        }
        r = self._post("/orders", body)
        if not r.get("success"):
            err = r.get("error_response") or r
            return {"ok": False, "error": str(err)[:200]}
        return {"ok": True, "order_id": r["success_response"]["order_id"], "limit_price": limit, "base_size": float(base)}

    def order(self, order_id: str) -> dict:
        return self._get(f"/orders/historical/{order_id}").get("order", {})

    def open_orders(self, product_id: str) -> list[dict]:
        return self._get("/orders/historical/batch", {"product_ids": product_id, "order_status": "OPEN"}).get("orders", [])

    def sell_fills_since(self, product_id: str, since: str) -> list[dict]:
        fills = self._get("/orders/historical/fills", {"product_ids": product_id, "start_sequence_timestamp": since, "limit": 100}).get("fills", [])
        return [f for f in fills if f.get("side") == "SELL"]

    def _dust(self, product: str, held: float, units: float) -> bool:
        min_size = float(self.product(product).get("base_min_size") or 0)
        return held < max(units * 0.01, min_size)

    def _market_sell(self, pos: dict, product: str, held: float, why: str) -> dict:
        ids = [o["order_id"] for o in self.open_orders(product) if o.get("side") == "SELL"]
        if ids:
            self._post("/orders/batch_cancel", {"order_ids": ids})
        size = _floor_to(held, self.product(product)["base_increment"])
        if Decimal(size) <= 0:
            return {"note": "nothing left to sell"}
        attempt = pd.Timestamp.now(tz="UTC").strftime("%Y%m%d%H%M")
        r = self._post("/orders", {
            "client_order_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"exit|{pos['id']}|{attempt}")),
            "product_id": product, "side": "SELL",
            "order_configuration": {"market_market_ioc": {"base_size": size}},
        })
        if not r.get("success"):
            raise RuntimeError(f"{why} exit sell failed for {product}: {str(r.get('error_response') or r)[:200]}")
        return {"note": f"{why} exit sent"}

    def reconcile(self, pos: dict, now: pd.Timestamp, gbp_per_usd: float, cost: dict) -> dict:
        product = pos["product"]
        base_cur = product.split("-")[0]
        if pos["status"] == "submitting":
            # the run died between journaling and the order call: look for the order by its client ID
            return {"status": "cancelled", "note": "order call didn't complete; check Coinbase if unsure"}
        if pos["status"] == "pending":
            o = self.order(pos["order_id"])
            st = o.get("status")
            if st not in ("FILLED", "CANCELLED", "EXPIRED", "FAILED") and now - pd.Timestamp(pos["entry_time"]) > pd.Timedelta(minutes=50):
                self._post("/orders/batch_cancel", {"order_ids": [pos["order_id"]]})
                o = self.order(pos["order_id"])  # read again: it may have filled, fully or partly, meanwhile
                st = o.get("status")
            filled = float(o.get("filled_size") or 0)
            if filled > 0 and st != "OPEN":
                return {
                    "status": "open", "entry_price": float(o["average_filled_price"]), "units": filled,
                    "fees_gbp": float(o.get("total_fees") or 0) * gbp_per_usd,
                    "last_checked": o.get("last_fill_time") or pos["entry_time"], "note": "filled" if st == "FILLED" else "partly filled",
                }
            if st in ("CANCELLED", "EXPIRED", "FAILED"):
                return {"status": "cancelled", "note": f"entry {st.lower()}"}
            return {}
        held = self.balances().get(base_cur, 0.0)
        units = float(pos["units"] or 0)
        if self._dust(product, held, units):  # target, stop or our exit has sold it
            return self._closed_from_fills(pos, product, gbp_per_usd)
        bba = self.best_bid_ask(product)
        bid = float(bba["bid"]) if bba else 0.0
        if bid and pos.get("sl_price") and bid <= pos["sl_price"]:
            return self._market_sell(pos, product, min(held, units), "stop")  # software stop backs up the exchange stop
        if now >= pd.Timestamp(pos["exit_by"]):
            return self._market_sell(pos, product, min(held, units), "time")
        return {}

    def _closed_from_fills(self, pos: dict, product: str, gbp_per_usd: float) -> dict:
        since = pos.get("last_checked") or pos["entry_time"]  # the entry fill time, so older trades' sells aren't counted
        fills = self.sell_fills_since(product, since)
        fills.sort(key=lambda f: f.get("trade_time", ""))
        need, used, px_sum, fees_q, last_t = float(pos["units"]), 0.0, 0.0, 0.0, ""
        for f in fills:
            if used >= need * 0.999:
                break
            take = min(float(f["size"]), need - used)
            used += take
            px_sum += float(f["price"]) * take
            fees_q += float(f.get("commission") or 0) * take / float(f["size"])
            last_t = f.get("trade_time", last_t)
        if used <= 0:
            return {"note": "position gone but no sell fills found yet"}
        px = px_sum / used
        cost_q = pos["entry_price"] * used
        entry_fees_gbp = float(pos.get("fees_gbp") or 0)
        pnl_gbp = (px * used - fees_q - cost_q) * gbp_per_usd - entry_fees_gbp
        if "time exit" in (pos.get("note") or ""):
            reason = "time"
        elif pos.get("tp_price") and px >= 0.995 * pos["tp_price"]:
            reason = "target"
        else:
            reason = "stop"
        return {
            "status": "closed", "exit_price": px, "exit_reason": reason, "exit_time": last_t,
            "fees_gbp": round(entry_fees_gbp + fees_q * gbp_per_usd, 4), "pnl_gbp": round(pnl_gbp, 4),
            "pnl_pct": round(pnl_gbp / pos["size_gbp"] * 100, 4) if pos.get("size_gbp") else 0.0,
        }
