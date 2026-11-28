# -*- coding: utf-8 -*-
"""Baut das Smart-Money-Dashboard als eine HTML-Datei (Radar-Design + Menü + Daten als JSON)."""
import json
import os

import einstellungen as E
import signale as SG
import spiegel as SP

TRADER_FELDER = ("adresse", "name", "konto", "pnl_gesamt", "roi_gesamt", "pnl_monat", "roi_monat", "pnl_woche", "tage", "drawdown",
                 "monate", "monate_pos", "schliessungen", "trefferquote", "top_anteil", "haltedauer_std", "pnl_30t", "note")


def _lies(*teile):
    with open(os.path.join(*teile), encoding="utf-8") as f:
        return f.read()


def vg_daten(S):
    V = S.get("vergleich")
    if not V:
        return None
    return {k: V.get(k) for k in ("start", "letzter_scan", "fehler", "ergebnis", "n", "gewonnen", "verlauf", "zeilen")} | {
        "offen": sorted(V.get("offen", {}).values(), key=lambda t: -t["zeit"]), "trades": sorted(V.get("trades", []), key=lambda t: -t["aufgeloest"])[:100],
        "kapital": E.VG_KAPITAL, "regeln": {"abstand": E.VG_MIN_ABSTAND, "einsatz": E.VG_EINSATZ, "liq": E.VG_MIN_LIQ}}


def wx_daten(S):
    W = S.get("wetter")
    if not W:
        return None
    b = W.get("brier") or {}
    return {"start": W.get("start"), "letzter_scan": W.get("letzter_scan"), "fehler": W.get("fehler"), "ergebnis": round(W.get("ergebnis", 0), 2),
            "einsatz_summe": W.get("einsatz_summe", 0), "n": W.get("n", 0), "gewonnen": W.get("gewonnen", 0), "kapital": E.WX_KAPITAL,
            "brier": {"n": b.get("n", 0), "modell": b["modell"] / b["n"] if b.get("n") else None, "markt": b["markt"] / b["n"] if b.get("n") else None},
            "offen": sorted(W.get("offen", {}).values(), key=lambda t: -t["zeit"]), "trades": sorted(W.get("trades", []), key=lambda t: -t["aufgeloest"])[:150],
            "signale": (W.get("signale") or [])[:80], "verlauf": W.get("verlauf", []),
            "regeln": {"vorteil": E.WX_MIN_VORTEIL, "einsatz": E.WX_EINSATZ, "liq": E.WX_MIN_LIQ, "sigma_heute": E.WX_SIGMA_HEUTE,
                       "sigma_morgen": E.WX_SIGMA_MORGEN, "slippage": E.WX_SLIPPAGE, "alle": E.WX_ALLE_MIN}}


def pm_daten(S):
    out = []
    for w, T in (S.get("polymarket") or {}).items():
        out.append({k: T.get(k) for k in ("name", "wallet", "start", "ideal", "real", "er", "ideal_einsatz", "real_einsatz", "er_einsatz", "n",
                                           "verpasst", "gewonnen_ideal", "gewonnen_real", "fehler", "verlauf")}
                   | {"offen": len(T.get("offen", [])), "trades": sorted(T.get("trades", []), key=lambda x: -x["ts"])[:150], "kapital": E.PM_KAPITAL,
                      "regeln": {"basis": E.PM_BASIS_EINSATZ, "min": E.PM_MIN_EINSATZ, "max": E.PM_MAX_EINSATZ, "verzug": E.PM_KOPIE_VERZUG_S,
                                 "slippage": E.PM_SLIPPAGE, "gebuehr": E.PM_GEBUEHR}})
    return out


def daten(S):
    P = S.get("portfolio") or {}
    preise = {c: {"px": px, "funding": 0} for c, px in (S.get("preise") or {}).items()}
    snap, konten = S.get("snap") or {}, S.get("konten") or {}
    einzel = SG.einzel_auswertung(S.get("einzel") or {}, preise)
    SPG = S.get("spiegel") or {}
    sp_je = SP.auswertung(SPG, preise) if SPG else {}
    trader = []
    for t in S.get("trader", []):
        d = {k: t.get(k) for k in TRADER_FELDER}
        a = t["adresse"]
        d["konto_jetzt"] = konten.get(a)
        d["pos"] = [{"coin": c, **p} for c, p in sorted((snap.get(a) or {}).items(), key=lambda x: -x[1]["wert"])]
        d["kopie"] = einzel.get(a)
        d["spiegel"] = sp_je.get(a)
        trader.append(d)
    pos = []
    for coin, p in (P.get("pos") or {}).items():
        px = (S.get("preise") or {}).get(coin) or p.get("letzter_px") or p["einstieg"]
        erg = p["r"] * (px - p["einstieg"]) * p["menge"] - p.get("geb_ein", 0) + p.get("funding", 0)
        pos.append({"coin": coin, "r": p["r"], "ein": p["einstieg"], "px": px, "notional": round(p["notional"], 2), "zeit": p["zeit"],
                    "erg": round(erg, 2), "pct": round(erg / p["notional"], 4), "n": p.get("trader_n"), "anteil": p.get("anteil")})
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
    sp_pos = []
    for p in (SPG.get("pos") or {}).values():
        px = (S.get("preise") or {}).get(p["coin"]) or p.get("letzter_px") or p["einstieg"]
        einsatz = p["menge"] * p["einstieg"]
        erg = p["r"] * (px - p["einstieg"]) * p["menge"] + p.get("funding", 0)
        sp_pos.append({"a": p["a"], "coin": p["coin"], "r": p["r"], "ein": p["einstieg"], "px": px, "notional": round(einsatz, 2), "zeit": p["zeit"],
                       "erg": round(erg, 2), "pct": round(erg / einsatz, 4) if einsatz else None})
    sp_pos.sort(key=lambda x: -x["notional"])
    netto = {}
    for x in sp_pos:
        n = netto.setdefault(x["coin"], {"coin": x["coin"], "long": 0.0, "short": 0.0, "trader": 0})
        n["long" if x["r"] > 0 else "short"] += x["notional"]
        n["trader"] += 1
    sp_wert = SP.wert(SPG, preise) if SPG else None
    spiegel = {"start": SPG.get("start"), "kapital": SPG.get("kapital", E.SPIEGEL_KAPITAL), "wert": round(sp_wert, 2) if sp_wert else None,
               "cash": round(SPG.get("cash", 0), 2), "gebuehren": round(SPG.get("gebuehren", 0), 2), "funding": round(SPG.get("funding", 0), 2),
               "pos": sp_pos, "netto": sorted(netto.values(), key=lambda n: -(n["long"] + n["short"])),
               "trades": list(reversed(SPG.get("trades", [])))[:200], "verlauf": SPG.get("verlauf", []),
               "je_trader": {a: v for a, v in sp_je.items() if v.get("gewicht") or v.get("positionen") or v.get("realisiert")}}
    return {
        "stand": S.get("stand"), "repo": E.REPO,
        "portfolio": {"start": P.get("start"), "wert": round(SG.portfolio_wert(P, preise), 2) if P else E.START_KAPITAL, "start_kapital": E.START_KAPITAL, "cash": round(P.get("cash", 0), 2),
                      "gebuehren": round(P.get("gebuehren", 0), 2), "funding": round(P.get("funding", 0), 2), "pos": pos,
                      "trades": list(reversed(P.get("trades", [])))[:200], "verlauf": P.get("verlauf", []), "btc_start": P.get("btc_start")},
        "spiegel": spiegel, "polymarket": pm_daten(S), "wetter": wx_daten(S), "vergleich": vg_daten(S), "trader": trader, "konsens": konsens[:40], "bewegungen": (S.get("bewegungen") or [])[:150],
        "kopien": alle_kopien[:150], "abgelehnt": [{k: t.get(k) for k in TRADER_FELDER + ("gruende",)} for t in S.get("abgelehnt", [])[:25]],
        "auswahl": S.get("auswahl_info"), "protokoll": (S.get("protokoll") or [])[:40], "laeufe": (S.get("laeufe") or [])[-120:],
        "preise": S.get("preise") or {},
        "regeln": {k: getattr(E, k) for k in ("MIN_KONTO_USD", "MIN_TAGE_HISTORIE", "MIN_SCHLIESSUNGEN_30T", "MIN_HALTEDAUER_STD", "MAX_TOP_ANTEIL",
                                              "MAX_DRAWDOWN", "MIN_MONATE_POSITIV", "MAX_TRADER", "KONSENS_MIN_TRADER", "KONSENS_MIN_ANTEIL",
                                              "KONSENS_AUS_TRADER", "KONSENS_AUS_ANTEIL", "START_KAPITAL", "POS_ANTEIL", "MAX_POSITIONEN",
                                              "GEBUEHR", "SLIPPAGE", "EINZEL_NOTIONAL", "MAX_UMSCHLAG_MONAT", "MIN_POS_ANTEIL", "MIN_POS_USD",
                                              "SPIEGEL_KAPITAL", "MIN_POS_SPIEGEL_ANTEIL", "SPIEGEL_MIN_POS", "SPIEGEL_ANPASSEN_AB", "SPIEGEL_PUSH_AB",
                                              "TAGES_PUSH_STUNDE")},
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
