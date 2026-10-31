"""Discord webhook messages. Without DISCORD_WEBHOOK_URL set, messages just print to the log."""
from __future__ import annotations

import os
import time

import requests

LIMIT = 1900


def _chunks(text: str):
    buf = ""
    for line in text.splitlines(keepends=True):
        if len(buf) + len(line) > LIMIT:
            if buf:
                yield buf
            buf = line[:LIMIT]
        else:
            buf += line
    if buf:
        yield buf


def send(text: str, url: str | None = None) -> bool:
    url = url or os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    print("[notify]\n" + text)
    if not url:
        return False
    ok = True
    for part in _chunks(text):
        for attempt in range(3):
            try:
                r = requests.post(url, json={"content": part, "allowed_mentions": {"parse": []}}, timeout=15)
            except requests.RequestException as e:
                print(f"[notify] error {e}")
                time.sleep(2)
                continue
            if r.status_code == 429:
                time.sleep(float(r.json().get("retry_after", 2)))
                continue
            if r.status_code >= 300:
                print(f"[notify] Discord answered {r.status_code}: {r.text[:200]}")
                ok = False
            break
    return ok


if __name__ == "__main__":
    import sys

    send(" ".join(sys.argv[1:]) or "test message from crypto-bot")
