# -*- coding: utf-8 -*-
"""
Markt-Scanner Finanzen (PAPIER-Test): dieselbe Frage an zwei Prognosebörsen. Polymarket und Kalshi handeln beide
die Fed-Zinsentscheidungen mit identischen Ausgängen. Liegen die Preise deutlich auseinander, ist eine der beiden
Börsen „falsch“ – der Scanner kauft auf Papier die bei Polymarket günstigere Seite und rechnet nach der Entscheidung ab.
Kalshi ist in den USA reguliert und hat bei Fed-Märkten meist mehr Volumen; sein Mittelkurs dient als Referenz.
"""
import json
import re
import time
from datetime import datetime

import requests

import einstellungen as E

GAMMA = "https://gamma-api.polymarket.com"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
_S = requests.Session()
_S.headers["User-Agent"] = "smart-money-radar (privat, Papier-Test, nur lesend)"
MONATE = {"january": "JAN", "february": "FEB", "march": "MAR", "april": "APR", "may": "MAY", "june": "JUN", "july": "JUL",
          "august": "AUG", "september": "SEP", "october": "OCT", "november": "NOV", "december": "DEC"}
ZUORDNUNG = {"50+ bps decrease": "C26", "25 bps decrease": "C25", "no change": "H0", "25 bps increase": "H25", "50+ bps increase": "H26"}
DEUTSCH = {"C26": "Senkung > 0,25 %", "C25": "Senkung 0,25 %", "H0": "keine Änderung", "H25": "Erhöhung 0,25 %", "H26": "Erhöhung > 0,25 %"}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def kalshi_fed():
    r = _S.get(KALSHI + "/events", params={"series_ticker": "KXFEDDECISION", "status": "open", "with_nested_markets": "true", "limit": 20}, timeout=40)
    r.raise_for_status()
    out = {}
    for e in r.json().get("events", []):
        m = re.match(r"KXFEDDECISION-(\d{2})([A-Z]{3})$", e["event_ticker"])
        if not m:
            continue
        key = f"20{m.group(1)}-{m.group(2)}"
        out[key] = {"titel": e.get("title"), "datum": e.get("sub_title"), "maerkte": {}}
        for mk in e.get("markets", []):
            code = mk["ticker"].rsplit("-", 1)[1]
            bid, ask = _f(mk.get("yes_bid_dollars")), _f(mk.get("yes_ask_dollars"))
            mitte = (bid + ask) / 2 if bid is not None and ask is not None and ask > 0 else _f(mk.get("last_price_dollars"))
            out[key]["maerkte"][code] = {"bid": bid, "ask": ask, "mitte": mitte, "vol": _f(mk.get("volume_fp") or mk.get("volume"))}
    return out


def polymarket_fed():
    r = _S.get(GAMMA + "/events", params={"tag_slug": "fed-rates", "closed": "false", "limit": 100}, timeout=40)
    r.raise_for_status()
    out = {}
    for e in r.json():
        m = re.match(r"^Fed [Dd]ecision in ([A-Za-z]+)\??$", e.get("title", "").strip())
        if not m or m.group(1).lower() not in MONATE:
            continue
        ende = datetime.fromisoformat(e["endDate"].replace("Z", "+00:00"))
        key = f"{ende.year}-{MONATE[m.group(1).lower()]}"
        maerkte = {}
        for mk in e.get("markets", []):
            code = ZUORDNUNG.get((mk.get("groupItemTitle") or "").strip().lower())
            if code and not mk.get("closed"):
                maerkte[code] = {"bid": _f(mk.get("bestBid")), "ask": _f(mk.get("bestAsk")), "id": mk["id"],
                                 "preis": _f((json.loads(mk.get("outcomePrices") or "[]") or [None])[0]), "liq": _f(mk.get("liquidityNum")) or 0}
        out[key] = {"slug": e["slug"], "titel": e["title"], "maerkte": maerkte}
    return out


def scannen(V):
    jetzt = time.time()
    k, p = kalshi_fed(), polymarket_fed()
    zeilen = []
    for key in sorted(set(k) & set(p)):
        for code, pm in p[key]["maerkte"].items():
            ka = k[key]["maerkte"].get(code)
            if not ka or ka["mitte"] is None:
                continue
            sig = None
            if pm["ask"] and pm["ask"] <= 0.97 and ka["mitte"] - pm["ask"] >= E.VG_MIN_ABSTAND:
                sig = ("JA", ka["mitte"] - pm["ask"], pm["ask"])
            elif pm["bid"] and pm["bid"] >= 0.03 and pm["bid"] - ka["mitte"] >= E.VG_MIN_ABSTAND:
                sig = ("NEIN", pm["bid"] - ka["mitte"], 1 - pm["bid"])
            z = {"termin": key, "datum": k[key]["datum"], "code": code, "ausgang": DEUTSCH.get(code, code), "pm_bid": pm["bid"], "pm_ask": pm["ask"],
                 "pm_preis": pm["preis"], "kalshi": round(ka["mitte"], 4), "kalshi_vol": ka["vol"], "liq": pm["liq"], "slug": p[key]["slug"],
                 "signal": {"seite": sig[0], "vorteil": round(sig[1], 3), "preis": sig[2]} if sig and pm["liq"] >= E.VG_MIN_LIQ else None}
            zeilen.append(z)
            if z["signal"]:
                schl = f"{p[key]['slug']}|{code}|{sig[0]}"
                if schl not in V["offen"] and schl not in V.get("erledigt", []):
                    V["offen"][schl] = {"slug": p[key]["slug"], "termin": key, "ausgang": z["ausgang"], "seite": sig[0], "market_id": pm["id"],
                                        "preis": round(min(0.99, sig[2] * (1 + E.VG_SLIPPAGE)), 4), "kalshi": z["kalshi"], "einsatz": E.VG_EINSATZ,
                                        "zeit": int(jetzt)}
    V["zeilen"] = zeilen
    V["letzter_scan"] = int(jetzt)
    abrechnen(V)
    return zeilen


def abrechnen(V):
    for slug in sorted({t["slug"] for t in V["offen"].values()}):
        try:
            ev = (_S.get(GAMMA + "/events", params={"slug": slug}, timeout=40).json() or [None])[0]
        except (requests.RequestException, ValueError):
            continue
        if not ev:
            continue
        erg = {}
        for m in ev.get("markets", []):
            op = json.loads(m.get("outcomePrices") or "[]")
            if m.get("closed") and op and op[0] in ("1", "0"):
                erg[m["id"]] = op[0] == "1"
        for schl in [s for s, t in V["offen"].items() if t["slug"] == slug]:
            t = V["offen"][schl]
            if t["market_id"] not in erg:
                continue
            V["offen"].pop(schl)
            gewonnen = erg[t["market_id"]] if t["seite"] == "JA" else not erg[t["market_id"]]
            e = (t["einsatz"] / t["preis"] if gewonnen else 0) - t["einsatz"]
            V["ergebnis"] += e
            V["n"] += 1
            V["gewonnen"] += gewonnen
            V["trades"].append({**t, "gewonnen": gewonnen, "erg": round(e, 2), "aufgeloest": int(time.time())})
            V["erledigt"] = (V.get("erledigt", []) + [schl])[-500:]


def lauf(S, protokoll):
    V = S.setdefault("vergleich", {"start": int(time.time()), "offen": {}, "trades": [], "ergebnis": 0.0, "n": 0, "gewonnen": 0, "verlauf": []})
    if time.time() - V.get("letzter_scan", 0) < E.WX_ALLE_MIN * 60:
        return V
    try:
        z = scannen(V)
        V["fehler"] = None
        print(f"Fed-Vergleich: {len(z)} Ausgänge, {sum(1 for x in z if x['signal'])} Signale, {len(V['offen'])} offen")
        for x in z:
            print(f"  {x['termin']} {x['ausgang']:<18} Polymarket {x['pm_bid']}/{x['pm_ask']}  Kalshi {x['kalshi']}")
    except Exception as ex:
        V["fehler"] = f"{type(ex).__name__}: {str(ex)[:120]}"
        protokoll.append(f"Fed-Vergleich: {V['fehler']}")
    jetzt = int(time.time() * 1000)
    if not V["verlauf"] or jetzt - V["verlauf"][-1][0] > 55 * 60_000:
        V["verlauf"].append([jetzt, round(E.VG_KAPITAL + V["ergebnis"], 2)])
        V["verlauf"] = V["verlauf"][-3000:]
    return V
