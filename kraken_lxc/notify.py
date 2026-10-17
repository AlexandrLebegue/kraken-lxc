"""Compteur de notifications non lues, partagé entre `kl-notify` et le démon.

Fichier d'état : /run/kraken-lxc/notify.json (perdu au redémarrage, voulu).
"""
from __future__ import annotations

import fcntl
import json
import os
import time

STATE_DIR = "/run/kraken-lxc"
STATE = f"{STATE_DIR}/notify.json"


def _update(fn) -> dict:
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        try:
            data = json.load(f)
        except ValueError:
            data = {"count": 0}
        data = fn(data)
        data["updated"] = time.time()
        f.seek(0)
        f.truncate()
        json.dump(data, f)
        return data


def add(n: int = 1) -> int:
    return _update(lambda d: {**d, "count": d.get("count", 0) + n})["count"]


def clear() -> int:
    return _update(lambda d: {**d, "count": 0})["count"]


def count() -> int:
    try:
        with open(STATE) as f:
            return int(json.load(f).get("count", 0))
    except (OSError, ValueError):
        return 0
