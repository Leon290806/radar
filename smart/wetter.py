# -*- coding: utf-8 -*-
"""
Markt-Scanner Wetter (PAPIER-Test – es wird nichts gewettet; Polymarket ist von Deutschland aus nicht erlaubt).

Polymarket hat täglich ~100 Märkte „Höchst-/Tiefsttemperatur in <Stadt> am <Tag>“. Aufgelöst wird über die
METAR-Meldungen einer bestimmten Flughafen-Wetterstation. Der Scanner
  1. liest alle offenen Temperatur-Märkte (Gamma-API) und die Station aus der Beschreibung,
  2. holt die Ensemble-Vorhersage für genau diese Station (Open-Meteo: ECMWF 51 + GFS 31 Läufe),
  3. berücksichtigt bereits gemessene Werte des Tages (METAR, aviationweather.gov),
  4. rechnet für jede Temperatur-Spanne eine Wahrscheinlichkeit aus und vergleicht sie mit dem Marktpreis,
  5. „kauft“ auf Papier, wenn die Abweichung groß genug ist, und rechnet nach Auflösung ab.
Zusätzlich wird für alle aufgelösten Spannen gemessen, ob das Modell besser lag als der Markt (Brier-Score).
"""
import json
import math
import re
import time
from datetime import datetime, timezone

import requests

import einstellungen as E

GAMMA = "https://gamma-api.polymarket.com"
ENSEMBLE = "https://ensemble-api.open-meteo.com/v1/ensemble"
AWC = "https://aviationweather.gov/api/data"
_S = requests.Session()
_S.headers["User-Agent"] = "smart-money-radar (privat, Papier-Test, nur lesend)"


def _phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def spanne(titel):
    """'15°C' -> [14.5, 15.5) °C; '48-49°F' -> in °C; 'X or below/higher' offen. Rückgabe (lo, hi) in °C oder None."""
    t = (titel or "").replace("º", "°").strip()
    m = re.match(r"^(-?\d+)\s*°?([CF])\s*or\s*(below|lower|higher|above)$", t, re.I) or re.match(r"^(-?\d+)\s*°([CF])\s*or\s*(below|lower|higher|above)", t, re.I)
    f2c = lambda f: (f - 32) * 5 / 9  # noqa: E731
    if m:
        v, einheit, art = float(m.group(1)), m.group(2).upper(), m.group(3).lower()
        if art in ("below", "lower"):
            hi = v + 0.5
            return (-99.0, f2c(hi) if einheit == "F" else hi)
        lo = v - 0.5
        return (f2c(lo) if einheit == "F" else lo, 99.0)
    m = re.match(r"^(-?\d+)\s*[-–]\s*(-?\d+)\s*°([CF])$", t)
    if m:
        a, b, einheit = float(m.group(1)) - 0.5, float(m.group(2)) + 0.5, m.group(3).upper()
        return (f2c(a), f2c(b)) if einheit == "F" else (a, b)
    m = re.match(r"^(-?\d+)\s*°([CF])$", t)
    if m:
        v, einheit = float(m.group(1)), m.group(2).upper()
        return (f2c(v - 0.5), f2c(v + 0.5)) if einheit == "F" else (v - 0.5, v + 0.5)
    return None


def offene_maerkte():
    heute = datetime.now(timezone.utc).date().isoformat()
    alle, offset = [], 0
    while offset < 1500:
        r = _S.get(GAMMA + "/events", params={"tag_slug": "daily-temperature", "closed": "false", "end_date_min": heute + "T00:00:00Z",
                                              "limit": 100, "offset": offset}, timeout=60)
        r.raise_for_status()
        teil = r.json()
        alle += teil
        if len(teil) < 100:
            break
        offset += 100
    return alle


def _event_info(e):
    m = re.match(r"^(highest|lowest)-temperature-in-(.+)-on-([a-z]+)-(\d+)-(\d{4})$", e.get("slug", ""))
    icao = re.search(r"\(([A-Z]{4})\)", e.get("description") or "")
    if not m or not icao:
        return None
    try:
        d = datetime.strptime(f"{m.group(3)} {m.group(4)} {m.group(5)}", "%B %d %Y").date()
    except ValueError:
        return None
    return {"art": m.group(1), "stadt": m.group(2).replace("-", " ").title(), "datum": d.isoformat(), "icao": icao.group(1)}


def stationen(icaos, cache):
    fehlt = [i for i in icaos if i not in cache]
    for k in range(0, len(fehlt), 40):
        r = _S.get(AWC + "/stationinfo", params={"ids": ",".join(fehlt[k:k + 40]), "format": "json"}, timeout=40)
        if r.ok:
            for s in r.json():
                cache[s["icaoId"]] = {"lat": s["lat"], "lon": s["lon"], "name": s.get("site")}
    return cache


def beobachtet(icaos):
    """Gemessene Temperaturen der letzten 30 Std. je Station: [(obsTime UTC, °C)]."""
    out = {}
    for k in range(0, len(icaos), 40):
        r = _S.get(AWC + "/metar", params={"ids": ",".join(icaos[k:k + 40]), "format": "json", "hours": 30}, timeout=60)
        if not r.ok:
            continue
        for x in r.json():
            if x.get("metarType") == "SPECI" or x.get("temp") is None:
                continue
            raw = x.get("rawOb") or ""
            mt = re.search(r"\bT([01])(\d{3})[01]\d{3}\b", raw)
            temp = (-1 if mt.group(1) == "1" else 1) * int(mt.group(2)) / 10 if mt else float(x["temp"])
            out.setdefault(x["icaoId"], []).append((int(x["obsTime"]), temp))
    return out


def ensemble(lat, lon):
    r = _S.get(ENSEMBLE, params={"latitude": lat, "longitude": lon, "daily": "temperature_2m_max,temperature_2m_min",
                                 "models": "ecmwf_ifs025,gfs025", "forecast_days": 3, "timezone": "auto"}, timeout=60)
    r.raise_for_status()
    j = r.json()
    d = j["daily"]
    tage = d["time"]
    werte = {"max": {t: [] for t in tage}, "min": {t: [] for t in tage}}
    for k, v in d.items():
        art = "max" if k.startswith("temperature_2m_max") else "min" if k.startswith("temperature_2m_min") else None
        if not art:
            continue
        for t, x in zip(tage, v):    # Kontroll-Lauf + alle Ensemble-Mitglieder beider Modelle
            if x is not None:
                werte[art][t].append(float(x))
    return werte, int(j.get("utc_offset_seconds") or 0)


def wahrscheinlichkeiten(members, spannen, sigma):
    if not members:
        return None
    out = []
    for lo, hi in spannen:
        p = sum(_phi((hi - v) / sigma) - _phi((lo - v) / sigma) for v in members) / len(members)
        out.append(p)
    s = sum(out) or 1
    return [p / s for p in out]


def scannen(W, protokoll):
    """Ein Scan: Signale berechnen, Papier-Käufe tätigen, aufgelöste Märkte abrechnen."""
    jetzt = time.time()
    events = offene_maerkte()
    infos = [(e, _event_info(e)) for e in events]
    infos = [(e, i) for e, i in infos if i]
    icaos = sorted({i["icao"] for _, i in infos})
    W["stationen"] = stationen(icaos, W.get("stationen", {}))
    obs = beobachtet(icaos)
    ens_cache, signale = {}, []
    for e, info in infos:
        st = W["stationen"].get(info["icao"])
        if not st:
            continue
        if info["icao"] not in ens_cache:
            try:
                ens_cache[info["icao"]] = ensemble(st["lat"], st["lon"])
                time.sleep(0.2)
            except requests.RequestException:
                ens_cache[info["icao"]] = None
        ens = ens_cache[info["icao"]]
        if not ens:
            continue
        werte, offset = ens
        members = list(werte["max" if info["art"] == "highest" else "min"].get(info["datum"], []))
        if len(members) < 20:
            continue
        # bereits gemessene Werte des Tages (Ortszeit) einrechnen
        tag0 = datetime.fromisoformat(info["datum"]).replace(tzinfo=timezone.utc).timestamp() - offset
        heute_obs = [t for ts, t in obs.get(info["icao"], []) if tag0 <= ts < tag0 + 86400]
        stunden_rest = (tag0 + 86400 - jetzt) / 3600
        if heute_obs:
            if info["art"] == "highest":
                members = [max(v, max(heute_obs)) for v in members]
            else:
                members = [min(v, min(heute_obs)) for v in members]
        sigma = E.WX_SIGMA_HEUTE if stunden_rest < 24 else E.WX_SIGMA_MORGEN
        maerkte = [m for m in e.get("markets", []) if not m.get("closed")]
        sp = [spanne(m.get("groupItemTitle")) for m in maerkte]
        if not maerkte or any(s is None for s in sp):
            continue
        ps = wahrscheinlichkeiten(members, sp, sigma)
        zeilen = []
        for m, (lo, hi), p in zip(maerkte, sp, ps):
            ask, bid = _f(m.get("bestAsk")), _f(m.get("bestBid"))
            preis = _f((json.loads(m.get("outcomePrices") or "[]") or [None])[0])
            zeilen.append({"titel": m.get("groupItemTitle"), "p": round(p, 4), "ask": ask, "bid": bid, "preis": preis, "id": m.get("id"),
                           "liq": _f(m.get("liquidityNum")) or 0})
        best = None
        for z in zeilen:
            if z["liq"] < E.WX_MIN_LIQ:
                continue
            if z["ask"] and 0.02 <= z["ask"] <= 0.92 and z["p"] - z["ask"] >= E.WX_MIN_VORTEIL:
                kand = ("JA", z, z["p"] - z["ask"], z["ask"])
            elif z["bid"] and 0.08 <= z["bid"] <= 0.98 and z["bid"] - z["p"] >= E.WX_MIN_VORTEIL:
                kand = ("NEIN", z, z["bid"] - z["p"], 1 - z["bid"])
            else:
                continue
            if not best or kand[2] > best[2]:
                best = kand
        ev = {"slug": e["slug"], "stadt": info["stadt"], "art": info["art"], "datum": info["datum"], "icao": info["icao"],
              "station": st.get("name"), "beobachtet": (max(heute_obs) if info["art"] == "highest" else min(heute_obs)) if heute_obs else None,
              "ens_median": round(sorted(members)[len(members) // 2], 1), "stunden_rest": round(stunden_rest, 1), "zeilen": zeilen,
              "signal": {"seite": best[0], "titel": best[1]["titel"], "vorteil": round(best[2], 3), "preis": best[3], "p": best[1]["p"]} if best else None,
              "ende": e.get("endDate")}
        signale.append(ev)
        # Papier-Kauf (einmal pro Markt-Spanne)
        if best:
            key = f"{e['slug']}|{best[1]['titel']}|{best[0]}"
            if key not in W["offen"] and key not in W.get("erledigt_keys", []) and len(W["offen"]) < E.WX_MAX_OFFEN:
                preis = min(0.99, best[3] * (1 + E.WX_SLIPPAGE))
                W["offen"][key] = {"slug": e["slug"], "stadt": info["stadt"], "art": info["art"], "datum": info["datum"], "titel": best[1]["titel"],
                                   "seite": best[0], "preis": round(preis, 4), "p": best[1]["p"], "einsatz": E.WX_EINSATZ, "zeit": int(jetzt),
                                   "market_id": best[1]["id"]}
        # für die Treffsicherheits-Messung: letzte Schätzung je Spanne vor Marktende merken
        W["schaetzungen"][e["slug"]] = {"zeit": int(jetzt), "zeilen": [{"id": z["id"], "p": z["p"], "preis": z["preis"]} for z in zeilen]}
    W["signale"] = sorted(signale, key=lambda s: -(s["signal"]["vorteil"] if s["signal"] else 0))
    W["letzter_scan"] = int(jetzt)
    abrechnen(W)
    return len(signale)


def abrechnen(W):
    """Aufgelöste Märkte: Papier-Trades abrechnen und Modell gegen Markt bewerten."""
    slugs = sorted({t["slug"] for t in W["offen"].values()} | set(W["schaetzungen"]))
    heute = datetime.now(timezone.utc).date()
    for slug in slugs:
        datum = re.search(r"-on-([a-z]+-\d+-\d{4})$", slug)
        try:
            d = datetime.strptime(datum.group(1), "%B-%d-%Y").date() if datum else None
        except ValueError:
            d = None
        if d and d >= heute:
            continue  # frühestens am Folgetag aufgelöst
        try:
            r = _S.get(GAMMA + "/events", params={"slug": slug}, timeout=40)
            ev = (r.json() or [None])[0]
        except (requests.RequestException, ValueError):
            continue
        if not ev:
            continue
        ergebnis = {}
        for m in ev.get("markets", []):
            op = json.loads(m.get("outcomePrices") or "[]")
            if m.get("closed") and op and op[0] in ("1", "0"):
                ergebnis[m["id"]] = 1 if op[0] == "1" else 0
        if not ergebnis:
            if d and (heute - d).days > 3:
                W["schaetzungen"].pop(slug, None)
            continue
        sch = W["schaetzungen"].pop(slug, None)
        if sch:
            for z in sch["zeilen"]:
                if z["id"] in ergebnis and z["preis"] is not None:
                    o = ergebnis[z["id"]]
                    W["brier"]["n"] += 1
                    W["brier"]["modell"] += (z["p"] - o) ** 2
                    W["brier"]["markt"] += (z["preis"] - o) ** 2
        for key in [k for k, t in W["offen"].items() if t["slug"] == slug]:
            t = W["offen"].pop(key)
            o = ergebnis.get(t["market_id"])
            if o is None:
                continue
            gewonnen = (o == 1) if t["seite"] == "JA" else (o == 0)
            erg = (t["einsatz"] / t["preis"] if gewonnen else 0) - t["einsatz"] - t["einsatz"] * E.WX_GEBUEHR
            W["ergebnis"] += erg
            W["einsatz_summe"] += t["einsatz"]
            W["n"] += 1
            W["gewonnen"] += gewonnen
            W["trades"].append({**t, "gewonnen": gewonnen, "erg": round(erg, 2), "aufgeloest": int(time.time())})
            W["erledigt_keys"] = (W.get("erledigt_keys", []) + [key])[-2000:]
    W["trades"] = W["trades"][-400:]


def lauf(S, protokoll):
    W = S.setdefault("wetter", {"start": int(time.time()), "offen": {}, "trades": [], "ergebnis": 0.0, "einsatz_summe": 0.0, "n": 0,
                                "gewonnen": 0, "schaetzungen": {}, "brier": {"n": 0, "modell": 0.0, "markt": 0.0}, "verlauf": [], "stationen": {}})
    if time.time() - W.get("letzter_scan", 0) < E.WX_ALLE_MIN * 60:
        return W
    try:
        n = scannen(W, protokoll)
        W["fehler"] = None
        sig = sum(1 for s in W["signale"] if s["signal"])
        print(f"Wetter-Scanner: {n} Märkte, {sig} Signale, {len(W['offen'])} offene Papier-Trades, Ergebnis {W['ergebnis']:+.2f} $")
    except Exception as ex:
        W["fehler"] = f"{type(ex).__name__}: {str(ex)[:120]}"
        protokoll.append(f"Wetter-Scanner: {W['fehler']}")
    jetzt = int(time.time() * 1000)
    if not W["verlauf"] or jetzt - W["verlauf"][-1][0] > 55 * 60_000:
        W["verlauf"].append([jetzt, round(E.WX_KAPITAL + W["ergebnis"], 2)])
        W["verlauf"] = W["verlauf"][-3000:]
    return W
