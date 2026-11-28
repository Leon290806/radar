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


# Wirtschaftsdaten: Polymarket-Spannen gegen Kalshi-Schwellen („Above X%“)
WIRTSCHAFT = [
    # (Name, Polymarket-Slug-Muster, Kalshi-Serie)
    ("US-Inflation (Monat)", r"^(?P<m>[a-z]+)-inflation-us-monthly$", "KXCPI"),
    ("US-Inflation (Jahr)", r"^(?P<m>[a-z]+)-inflation-us-annual$", "KXCPIYOY"),
    ("US-Kerninflation (Monat)", r"^core-cpi-mom-(?P<m>[a-z]+)-(?P<y>\d{4})$", "KXCPICORE"),
    ("US-Kerninflation (Jahr)", r"^core-cpi-yoy-(?P<m>[a-z]+)-(?P<y>\d{4})$", "KXCPICOREYOY"),
    ("US-Wachstum (BIP Quartal)", r"^us-gdp-growth-in-q(?P<q>[1-4])-(?P<y>\d{4})$", "KXGDP"),
]


def _zahl(t):
    t = t.replace("−", "-").replace("–", "-").replace(",", ".").strip()
    return float(t)


def pm_spanne(titel):
    """'0.2%' -> (0.2, 0.2); '≤-0.3%' -> (-inf, -0.3); '≥0.4%' / '0.4%+' -> (0.4, inf); '2.0% to 2.5%' -> (2.0, 2.5); '<1.5%' -> (-inf, 1.4)."""
    t = (titel or "").replace("%", "").replace(" ", "").replace("−", "-").replace("–", "-")
    try:
        if t.startswith("≤"):
            return (-1e9, _zahl(t[1:]))
        if t.startswith("≥"):
            return (_zahl(t[1:]), 1e9)
        if t.endswith("+"):
            return (_zahl(t[:-1]), 1e9)
        if t.startswith("<"):
            return (-1e9, round(_zahl(t[1:]) - 0.1, 2))
        if t.startswith(">"):
            return (round(_zahl(t[1:]) + 0.1, 2), 1e9)
        m = re.match(r"^(-?\d+(?:\.\d+)?)(?:to|-)(-?\d+(?:\.\d+)?)$", t)
        if m:
            return (float(m.group(1)), float(m.group(2)))
        return (_zahl(t), _zahl(t))
    except ValueError:
        return None


def _p_ueber(schwellen, x):
    """P(Wert > x) aus Kalshi-Schwellen [(t, p)], linear interpoliert, an den Rändern gekappt."""
    if x <= -1e8:
        return 1.0
    if x >= 1e8:
        return 0.0
    if x <= schwellen[0][0]:
        return schwellen[0][1] if abs(x - schwellen[0][0]) < 1e-9 else max(schwellen[0][1], 1.0 if x < schwellen[0][0] - 0.05 else schwellen[0][1])
    if x >= schwellen[-1][0]:
        return schwellen[-1][1] if abs(x - schwellen[-1][0]) < 1e-9 else min(schwellen[-1][1], 0.0 if x > schwellen[-1][0] + 0.05 else schwellen[-1][1])
    for (a, pa), (b, pb) in zip(schwellen, schwellen[1:]):
        if a <= x <= b:
            return pa + (pb - pa) * (x - a) / (b - a)
    return 0.0


def kalshi_schwellen(serie):
    r = _S.get(KALSHI + "/events", params={"series_ticker": serie, "status": "open", "with_nested_markets": "true", "limit": 10}, timeout=40)
    r.raise_for_status()
    out = []
    for e in r.json().get("events", []):
        pts = []
        for mk in e.get("markets", []):
            m = re.match(r"^Above (-?[\d,.]+)%?$", (mk.get("yes_sub_title") or "").strip())
            bid, ask = _f(mk.get("yes_bid_dollars")), _f(mk.get("yes_ask_dollars"))
            if not m or bid is None or ask is None:
                continue
            pts.append((float(m.group(1).replace(",", "")), (bid + ask) / 2))
        if len(pts) >= 3:
            out.append({"ticker": e["event_ticker"], "titel": e.get("title"), "datum": e.get("sub_title"), "schwellen": sorted(pts)})
    return out


def wirtschaft(V, jetzt):
    zeilen = []
    pm_events = []
    for tag in ("inflation", "gdp"):
        try:
            pm_events += _S.get(GAMMA + "/events", params={"tag_slug": tag, "closed": "false", "limit": 100}, timeout=40).json()
        except (requests.RequestException, ValueError):
            pass
    if not V.get("bip_fix"):
        # BIP-Signale vom 28.11. beruhten auf falsch gerechneten Spannen -> verwerfen
        for k in [k for k, t in V.get("offen", {}).items() if "gdp" in t.get("slug", "")]:
            V["offen"].pop(k)
        V["bip_fix"] = 1
    gesehen = set()
    for name, muster, serie in WIRTSCHAFT:
        try:
            kal = kalshi_schwellen(serie)
        except requests.RequestException:
            continue
        for e in pm_events:
            m = re.match(muster, e.get("slug", ""))
            if not m or e["slug"] in gesehen:
                continue
            gesehen.add(e["slug"])
            ende = datetime.fromisoformat(e["endDate"].replace("Z", "+00:00"))
            d = m.groupdict()
            if "q" in d and d.get("q"):
                ziel = f"Q{d['q']} {d['y']}"
                ka = next((k for k in kal if ziel in (k["titel"] or "")), None)
            else:
                mon = MONATE.get(d["m"], "")
                jahr = int(d["y"]) if d.get("y") else ende.year
                if not d.get("y") and mon in ("NOV", "DEC") and ende.month <= 2:
                    jahr -= 1   # Novemberdaten werden erst im Dezember/Januar veröffentlicht
                ka = next((k for k in kal if k["ticker"].endswith(f"-{str(jahr)[2:]}{mon}")), None)
            if not ka:
                continue
            for mk in e.get("markets", []):
                if mk.get("closed"):
                    continue
                sp = pm_spanne(mk.get("groupItemTitle"))
                if not sp:
                    continue
                if serie == "KXGDP":
                    # Spannen wie "2.0% to 2.5%": durchgehende Intervalle, Summe bleibt 100 %
                    t = (mk.get("groupItemTitle") or "").replace(" ", "")
                    lo, hi = sp
                    if t.startswith("<"):
                        hi = round(hi + 0.1, 2)
                    pk = _p_ueber(ka["schwellen"], lo if lo > -1e8 else -1e9) - _p_ueber(ka["schwellen"], hi)
                else:
                    pk = _p_ueber(ka["schwellen"], round(sp[0] - 0.1, 2)) - _p_ueber(ka["schwellen"], sp[1])
                pk = max(0.0, min(1.0, pk))
                bid, ask, liq = _f(mk.get("bestBid")), _f(mk.get("bestAsk")), _f(mk.get("liquidityNum")) or 0
                sig = None
                if ask and ask <= 0.97 and pk - ask >= E.VG_MIN_ABSTAND:
                    sig = ("JA", pk - ask, ask)
                elif bid and bid >= 0.03 and bid - pk >= E.VG_MIN_ABSTAND:
                    sig = ("NEIN", bid - pk, 1 - bid)
                z = {"gruppe": name, "termin": e["title"], "datum": ka["datum"], "code": mk.get("groupItemTitle"), "ausgang": mk.get("groupItemTitle"),
                     "pm_bid": bid, "pm_ask": ask, "pm_preis": _f((json.loads(mk.get("outcomePrices") or "[]") or [None])[0]), "kalshi": round(pk, 4),
                     "liq": liq, "slug": e["slug"], "signal": {"seite": sig[0], "vorteil": round(sig[1], 3), "preis": sig[2]} if sig and liq >= E.VG_MIN_LIQ else None}
                zeilen.append(z)
                if z["signal"]:
                    schl = f"{e['slug']}|{z['code']}|{sig[0]}"
                    if schl not in V["offen"] and schl not in V.get("erledigt", []):
                        V["offen"][schl] = {"slug": e["slug"], "termin": e["title"], "ausgang": z["ausgang"], "seite": sig[0], "market_id": mk["id"],
                                            "preis": round(min(0.99, sig[2] * (1 + E.VG_SLIPPAGE)), 4), "kalshi": z["kalshi"], "einsatz": E.VG_EINSATZ,
                                            "zeit": int(jetzt)}
    return zeilen


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
            z = {"gruppe": "Fed-Zinsentscheidung", "termin": key, "datum": k[key]["datum"], "code": code, "ausgang": DEUTSCH.get(code, code), "pm_bid": pm["bid"], "pm_ask": pm["ask"],
                 "pm_preis": pm["preis"], "kalshi": round(ka["mitte"], 4), "kalshi_vol": ka["vol"], "liq": pm["liq"], "slug": p[key]["slug"],
                 "signal": {"seite": sig[0], "vorteil": round(sig[1], 3), "preis": sig[2]} if sig and pm["liq"] >= E.VG_MIN_LIQ else None}
            zeilen.append(z)
            if z["signal"]:
                schl = f"{p[key]['slug']}|{code}|{sig[0]}"
                if schl not in V["offen"] and schl not in V.get("erledigt", []):
                    V["offen"][schl] = {"slug": p[key]["slug"], "termin": key, "ausgang": z["ausgang"], "seite": sig[0], "market_id": pm["id"],
                                        "preis": round(min(0.99, sig[2] * (1 + E.VG_SLIPPAGE)), 4), "kalshi": z["kalshi"], "einsatz": E.VG_EINSATZ,
                                        "zeit": int(jetzt)}
    zeilen += wirtschaft(V, jetzt)
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
        print(f"Finanz-Vergleich: {len(z)} Ausgänge, {sum(1 for x in z if x['signal'])} Signale, {len(V['offen'])} offen")
        for x in z:
            if x["gruppe"] != "Fed-Zinsentscheidung":
                print(f"  {x['termin'][:34]:<34} {str(x['ausgang']):<14} Polymarket {x['pm_bid']}/{x['pm_ask']}  Kalshi {x['kalshi']}")
    except Exception as ex:
        V["fehler"] = f"{type(ex).__name__}: {str(ex)[:120]}"
        protokoll.append(f"Fed-Vergleich: {V['fehler']}")
    jetzt = int(time.time() * 1000)
    if not V["verlauf"] or jetzt - V["verlauf"][-1][0] > 55 * 60_000:
        V["verlauf"].append([jetzt, round(E.VG_KAPITAL + V["ergebnis"], 2)])
        V["verlauf"] = V["verlauf"][-3000:]
    return V
