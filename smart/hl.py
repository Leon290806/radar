# -*- coding: utf-8 -*-
"""Kleiner Client für die öffentliche Hyperliquid-API (nur lesen, kein Schlüssel nötig)."""
import time

import requests

import einstellungen as E

_S = requests.Session()
_S.headers["User-Agent"] = "smart-money-radar (privat, nur lesend)"


def _post(body, pause=0.2, versuche=4):
    for i in range(versuche):
        try:
            r = _S.post(E.API, json=body, timeout=40)
            if r.status_code == 429:
                time.sleep(5 * (i + 1))
                continue
            r.raise_for_status()
            time.sleep(pause)
            return r.json()
        except (requests.RequestException, ValueError):
            if i == versuche - 1:
                raise
            time.sleep(2 * (i + 1))


def leaderboard():
    r = _S.get(E.LEADERBOARD, timeout=120)
    r.raise_for_status()
    return r.json().get("leaderboardRows", [])


def positionen(adresse):
    return _post({"type": "clearinghouseState", "user": adresse}, pause=0.15)


def portfolio(adresse):
    return _post({"type": "portfolio", "user": adresse}, pause=1.0)


def fills(adresse, seit_ms):
    return _post({"type": "userFillsByTime", "user": adresse, "startTime": int(seit_ms), "aggregateByTime": True}, pause=1.5)


def preise():
    """Mittelkurse und stündliche Funding-Rate je Perp-Coin."""
    meta, ctxs = _post({"type": "metaAndAssetCtxs"}, pause=0.2)
    out = {}
    for a, c in zip(meta.get("universe", []), ctxs):
        try:
            px = float(c.get("midPx") or c.get("markPx") or 0)
        except (TypeError, ValueError):
            continue
        if px > 0:
            out[a["name"]] = {"px": px, "funding": float(c.get("funding") or 0)}
    return out
