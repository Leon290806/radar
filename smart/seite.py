# -*- coding: utf-8 -*-
"""Baut das Smart-Money-Dashboard als eine HTML-Datei (Radar-Design + Menü + Daten als JSON)."""
import json
import os

import einstellungen as E
import signale as SG

TRADER_FELDER = ("adresse", "name", "konto", "pnl_gesamt", "roi_gesamt", "pnl_monat", "roi_monat", "pnl_woche", "tage", "drawdown",
                 "monate", "monate_pos", "schliessungen", "trefferquote", "top_anteil", "haltedauer_std", "pnl_30t", "note")


def _lies(*teile):
    with open(os.path.join(*teile), encoding="utf-8") as f:
        return f.read()


def daten(S):
    P = S.get("portfolio") or {}
    preise = {c: {"px": px, "funding": 0} for c, px in (S.get("preise") or {}).items()}
    snap, konten = S.get("snap") or {}, S.get("konten") or {}
    einzel = SG.einzel_auswertung(S.get("einzel") or {}, preise)
    trader = []
    for t in S.get("trader", []):
        d = {k: t.get(k) for k in TRADER_FELDER}
        a = t["adresse"]
        d["konto_jetzt"] = konten.get(a)
        d["pos"] = [{"coin": c, **p} for c, p in sorted((snap.get(a) or {}).items(), key=lambda x: -x[1]["wert"])]
        d["kopie"] = einzel.get(a)
        trader.append(d)
    pos = []
    for coin, p in (P.get("pos") or {}).items():
        px = (S.get("preise") or {}).get(coin) or p.get("letzter_px") or p["einstieg"]
        erg = p["r"] * (px - p["einstieg"]) * p["menge"] - p.get("geb_ein", 0) + p.get("funding", 0)
        pos.append({"coin": coin, "r": p["r"], "ein": p["einstieg"], "px": px, "notional": round(p["notional"], 2), "zeit": p["zeit"],
                    "erg": round(erg, 2), "pct": round(erg / p["notional"], 4), "n": p.get("trader_n"), "anteil": p.get("anteil")})
    wert = P.get("cash", E.START_KAPITAL) + sum(x["notional"] + x["r"] * (x["px"] - x["ein"]) * (x["notional"] / x["ein"]) for x in pos)
    konsens = []
    for coin, c in (S.get("konsens") or {}).items():
        if c["n"] >= 2:
            konsens.append({"coin": coin, "long": c["long"], "short": c["short"], "n": c["n"], "richtung": c["richtung"], "anteil": c["anteil"],
                            "signal": c["signal"], "wert_long": c["wert_long"], "wert_short": c["wert_short"], "gehalten": coin in (P.get("pos") or {})})
    konsens.sort(key=lambda c: (-c["signal"], -c["n"], -c["anteil"]))
    alle_kopien = []
    for a, d in (S.get("einzel") or {}).items():
        for x in d.get("fertig", []):
            alle_kopien.append({**x, "a": a})
    alle_kopien.sort(key=lambda x: -x["zeit_aus"])
    return {
        "stand": S.get("stand"), "repo": E.REPO,
        "portfolio": {"start": P.get("start"), "wert": round(wert, 2), "start_kapital": E.START_KAPITAL, "cash": round(P.get("cash", 0), 2),
                      "gebuehren": round(P.get("gebuehren", 0), 2), "funding": round(P.get("funding", 0), 2), "pos": pos,
                      "trades": list(reversed(P.get("trades", [])))[:200], "verlauf": P.get("verlauf", []), "btc_start": P.get("btc_start")},
        "trader": trader, "konsens": konsens[:40], "bewegungen": (S.get("bewegungen") or [])[:150],
        "kopien": alle_kopien[:150], "abgelehnt": [{k: t.get(k) for k in TRADER_FELDER + ("gruende",)} for t in S.get("abgelehnt", [])[:25]],
        "auswahl": S.get("auswahl_info"), "protokoll": (S.get("protokoll") or [])[:40], "laeufe": (S.get("laeufe") or [])[-120:],
        "preise": S.get("preise") or {},
        "regeln": {k: getattr(E, k) for k in ("MIN_KONTO_USD", "MIN_TAGE_HISTORIE", "MIN_SCHLIESSUNGEN_30T", "MIN_HALTEDAUER_STD", "MAX_TOP_ANTEIL",
                                              "MAX_DRAWDOWN", "MIN_MONATE_POSITIV", "MAX_TRADER", "KONSENS_MIN_TRADER", "KONSENS_MIN_ANTEIL",
                                              "KONSENS_AUS_TRADER", "KONSENS_AUS_ANTEIL", "START_KAPITAL", "POS_ANTEIL", "MAX_POSITIONEN",
                                              "GEBUEHR", "SLIPPAGE", "EINZEL_NOTIONAL", "MAX_UMSCHLAG_MONAT", "MIN_POS_ANTEIL", "MIN_POS_USD")},
    }


def erstelle(S):
    D = json.dumps(daten(S), ensure_ascii=False, separators=(",", ":"), allow_nan=False, default=str).replace("</", "<\\/")
    css = _lies(E.REPO_WURZEL, "app.css") + "\n" + _lies(E.BASIS, "web", "smart.css")
    menue = _lies(E.REPO_WURZEL, "menue.js")
    js = _lies(E.BASIS, "web", "smart.js")
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex"><meta name="color-scheme" content="light dark">
<title>Smart-Money-Radar</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400..800&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body><main></main>
<script type="application/json" id="daten">{D}</script>
<script>{menue}</script>
<script>{js}</script>
</body></html>"""
