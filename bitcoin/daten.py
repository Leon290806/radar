# -*- coding: utf-8 -*-
"""Datenquellen: CoinMetrics Community (Kurs, MVRV, Emission, Hashrate seit 2010), alternative.me (Fear & Greed),
bitcoin-data.com (Kostenbasis Kurz-/Langfrist-Halter, SOPR – nur die letzten Jahre, 10 Abrufe pro Stunde)."""
import time

import requests

import einstellungen as E

_S = requests.Session()
_S.headers["User-Agent"] = "bitcoin-radar (privat, nur lesend)"


def coinmetrics():
    zeilen, url, params = [], E.COINMETRICS, {"assets": "btc", "metrics": E.CM_METRIKEN, "frequency": "1d",
                                              "start_time": "2010-07-18", "page_size": 10000}
    while url:
        r = _S.get(url, params=params, timeout=90)
        r.raise_for_status()
        j = r.json()
        zeilen += j.get("data", [])
        url, params = j.get("next_page_url"), None
    return zeilen


def fear_greed():
    try:
        r = _S.get(E.FNG, timeout=60)
        r.raise_for_status()
        return r.json().get("data", [])
    except (requests.RequestException, ValueError):
        return []


def bgeo(cache, protokoll):
    """Ergänzt den Zwischenspeicher {endpunkt: {datum: wert}} – höchstens einmal pro 20 Std., Fehler sind nicht schlimm."""
    if time.time() - cache.get("_zeit", 0) < 20 * 3600:
        return cache
    ok = 0
    for ep, feld in E.BGEO_ENDPUNKTE.items():
        try:
            r = _S.get(E.BGEO + ep, timeout=60)
            if r.status_code == 429:
                protokoll.append(f"bitcoin-data.com: Abruflimit erreicht ({ep}) – nutze gespeicherte Werte")
                break
            r.raise_for_status()
            d = cache.setdefault(ep, {})
            for x in r.json():
                try:
                    d[x["d"]] = float(x[feld])
                except (KeyError, TypeError, ValueError):
                    pass
            ok += 1
        except (requests.RequestException, ValueError) as ex:
            protokoll.append(f"bitcoin-data.com {ep}: {type(ex).__name__}")
        time.sleep(1.5)
    if ok:
        cache["_zeit"] = time.time()
    return cache
