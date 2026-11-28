# -*- coding: utf-8 -*-
"""
Tracking eines Polymarket-Traders als PAPIER-Test (es wird nichts gewettet – in Deutschland wäre die Teilnahme
an Polymarket ohnehin nicht erlaubt; hier werden nur öffentliche Daten gelesen).

Jeder Kauf des Traders wird zweimal simuliert, sobald der Markt aufgelöst ist:
  • ideal:        zum selben Preis wie er (in der Praxis unmöglich – zeigt die Obergrenze)
  • realistisch:  zum Marktpreis ~KOPIE_VERZUG_S Sekunden später (+ Slippage). Schließt der Markt vorher, ist der
                  Trade verpasst.
Einsatz: Basisbetrag × (sein Einsatz / sein typischer Einsatz) – seine Gewichtung bleibt, die Größe passt zum
Papierkapital. Gewinn oder Verlust ergibt sich aus dem Endpreis des Markts (1 = gewonnen, 0 = verloren).
"""
import re
import statistics
import time

import requests

import einstellungen as E

API = "https://data-api.polymarket.com/v2"
_S = requests.Session()
_S.headers["User-Agent"] = "smart-money-radar (privat, Papier-Test, nur lesend)"


def _get(pfad, params, versuche=3):
    for i in range(versuche):
        r = _S.get(API + pfad, params=params, timeout=40)
        if r.status_code == 429:
            time.sleep(float(r.headers.get("Retry-After") or 5))
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def _ende(slug):
    """btc-updown-15m-1795877100 -> Ende = Start + 15 Min. (Start steht im Slug)."""
    m = re.search(r"-(\d+)m-(\d{9,11})$", slug or "")
    if not m:
        return None
    return int(m.group(2)) + int(m.group(1)) * 60


def neu(trader):
    jetzt = int(time.time())
    return {"name": trader["name"], "wallet": trader["wallet"], "start": jetzt, "letzte_ts": jetzt, "offen": [], "einsaetze": [],
            "ideal": 0.0, "real": 0.0, "er": 0.0, "ideal_einsatz": 0.0, "real_einsatz": 0.0, "er_einsatz": 0.0,
            "n": 0, "verpasst": 0, "gewonnen_ideal": 0, "gewonnen_real": 0, "trades": [], "verlauf": [], "fehler": None}


def aktivitaet_holen(T):
    """Neue Trades seit dem letzten Lauf (absteigend geblättert, bis der letzte bekannte Zeitpunkt erreicht ist)."""
    neue, cursor = [], None
    for _ in range(20):
        params = {"user": T["wallet"], "limit": 500, "start": T["letzte_ts"] + 1}
        if cursor:
            params["cursor"] = cursor
        j = _get("/activity", params)
        daten = j.get("data", [])
        neue += [x for x in daten if x.get("type") == "TRADE" and int(x["timestamp"]) > T["letzte_ts"]]
        cursor = (j.get("pagination") or {}).get("next_cursor")
        if not cursor or not daten:
            break
    if neue:
        T["letzte_ts"] = max(int(x["timestamp"]) for x in neue)
    for x in neue:
        T["offen"].append({"ts": int(x["timestamp"]), "token": x["token_id"], "slug": x.get("slug"), "titel": x.get("title"),
                           "outcome": x.get("outcome"), "seite": x.get("side"), "preis": float(x.get("price") or 0),
                           "anteile": float(x.get("size") or 0), "usdc": float(x.get("usdc_size") or 0), "ende": _ende(x.get("slug"))})
        if x.get("side") == "BUY":
            T["einsaetze"] = (T["einsaetze"] + [float(x.get("usdc_size") or 0)])[-500:]
    return len(neue)


def _verlauf_preise(token, von, bis):
    j = _get("/prices-history", {"token_id": token, "start": von, "end": bis, "bucket_seconds": 60})
    return [(int(p["timestamp"]), float(p["price"])) for p in j.get("data", [])]


def auswerten(T, max_maerkte=300):
    """Trades abrechnen, deren Markt geschlossen ist. Ein Kursabruf pro Markt-Token."""
    jetzt = int(time.time())
    typisch = statistics.median(T["einsaetze"]) if T["einsaetze"] else 1.0
    fertig_token = {}
    for t in T["offen"]:
        if t["ende"] and jetzt > t["ende"] + 120:
            fertig_token.setdefault(t["token"], []).append(t)
    bleiben = [t for t in T["offen"] if t["token"] not in fertig_token and (not t["ende"] or jetzt - t["ende"] < 6 * 3600)]
    erledigt = 0
    for token, liste in list(fertig_token.items())[:max_maerkte]:
        ende = liste[0]["ende"]
        try:
            pv = _verlauf_preise(token, min(x["ts"] for x in liste) - 60, ende + 180)
        except requests.RequestException:
            bleiben += liste
            continue
        nach = [p for ts, p in pv if ts >= ende]
        endpreis = nach[-1] if nach else (pv[-1][1] if pv else None)
        if endpreis is None or 0.05 < endpreis < 0.95:
            if jetzt - ende < 3600:
                bleiben += liste   # noch nicht aufgelöst – später erneut
            continue
        gewonnen = endpreis >= 0.95
        for t in sorted(liste, key=lambda x: x["ts"]):
            if t["seite"] != "BUY" or t["preis"] <= 0:
                continue  # Verkäufe vor Marktende sind selten; sie würden hier nur das Ergebnis verwässern
            einsatz = max(E.PM_MIN_EINSATZ, min(E.PM_MAX_EINSATZ, E.PM_BASIS_EINSATZ * t["usdc"] / max(typisch, 0.01)))
            auszahlung = 1.0 if gewonnen else 0.0
            # ideal: sein Preis
            anteile_i = einsatz / t["preis"]
            erg_i = anteile_i * auszahlung - einsatz - einsatz * E.PM_GEBUEHR
            # realistisch: Preis nach der Verzögerung
            spaeter = [p for ts, p in pv if ts >= t["ts"] + E.PM_KOPIE_VERZUG_S]
            ts_spaeter = next((ts for ts, p in pv if ts >= t["ts"] + E.PM_KOPIE_VERZUG_S), None)
            verpasst = not spaeter or ts_spaeter is None or ts_spaeter >= ende or spaeter[0] >= 0.99 or spaeter[0] <= 0.01
            if verpasst:
                erg_r, preis_r = 0.0, None
                T["verpasst"] += 1
            else:
                preis_r = min(0.99, spaeter[0] * (1 + E.PM_SLIPPAGE))
                erg_r = einsatz / preis_r * auszahlung - einsatz - einsatz * E.PM_GEBUEHR
                T["real"] += erg_r
                T["real_einsatz"] += einsatz
                T["gewonnen_real"] += gewonnen
            er = t["anteile"] * auszahlung - t["usdc"]
            T["ideal"] += erg_i
            T["ideal_einsatz"] += einsatz
            T["er"] += er
            T["er_einsatz"] += t["usdc"]
            T["n"] += 1
            T["gewonnen_ideal"] += gewonnen
            T["trades"].append({"ts": t["ts"], "titel": t["titel"], "outcome": t["outcome"], "preis": round(t["preis"], 4),
                                "preis_r": round(preis_r, 4) if preis_r else None, "einsatz": round(einsatz, 2), "gewonnen": gewonnen,
                                "erg_i": round(erg_i, 2), "erg_r": round(erg_r, 2), "verpasst": verpasst, "sekunden_vor_ende": ende - t["ts"],
                                "er_usdc": round(t["usdc"], 2), "er_erg": round(er, 2)})
            erledigt += 1
    T["trades"] = T["trades"][-400:]
    T["offen"] = bleiben
    return erledigt


def lauf(S, protokoll):
    """Ein Durchgang je Trader. Fehler stoppen den Smart-Money-Radar nicht."""
    PM = S.setdefault("polymarket", {})
    for trader in E.PM_TRADER:
        T = PM.get(trader["wallet"]) or neu(trader)
        try:
            n_neu = aktivitaet_holen(T)
            n_fertig = auswerten(T)
            T["fehler"] = None
            print(f"Polymarket {T['name']}: {n_neu} neue Trades, {n_fertig} abgerechnet, {len(T['offen'])} offen, "
                  f"realistisch {T['real']:+.2f} $, ideal {T['ideal']:+.2f} $")
        except Exception as ex:
            T["fehler"] = f"{type(ex).__name__}: {str(ex)[:120]}"
            protokoll.append(f"Polymarket-Tracking {T['name']}: {T['fehler']}")
        jetzt = int(time.time() * 1000)
        if not T["verlauf"] or jetzt - T["verlauf"][-1][0] > 55 * 60_000:
            T["verlauf"].append([jetzt, round(E.PM_KAPITAL + T["real"], 2), round(E.PM_KAPITAL + T["ideal"], 2), round(T["er"], 2)])
            T["verlauf"] = T["verlauf"][-3000:]
        PM[trader["wallet"]] = T
    return PM
