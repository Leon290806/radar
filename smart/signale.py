# -*- coding: utf-8 -*-
"""
Positionen der ausgewählten Trader beobachten, Konsens-Signale bilden und zwei Papier-Tests führen:
  1. Konsens-Portfolio: kauft/verkauft (simuliert), wenn mehrere Top-Trader dieselbe Richtung halten.
  2. Einzel-Kopie: kopiert jede NEUE Position jedes Traders mit fester Größe – zeigt, ob man einzelne Trader
     mit Verzögerung gewinnbringend kopieren kann und wie viel schlechter der eigene Einstiegspreis ist.
Alle Preise mit Slippage und Gebühr, Funding wird stündlich verrechnet. Keine echten Orders.
"""
import time

import einstellungen as E
import hl


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def jetzt_ms():
    return int(time.time() * 1000)


def schnappschuss(trader, protokoll):
    """Aktuelle relevante Positionen je Trader: {adresse: {coin: {r, wert, einstieg, hebel, upnl}}}."""
    snap, konten = {}, {}
    for t in trader:
        a = t["adresse"]
        try:
            st = hl.positionen(a)
        except Exception as ex:
            protokoll.append(f"Positionen {a[:10]}: {type(ex).__name__}")
            continue
        av = _f((st.get("marginSummary") or {}).get("accountValue"))
        konten[a] = av
        pos = {}
        for ap in st.get("assetPositions", []):
            p = ap.get("position") or {}
            szi, wert = _f(p.get("szi")), abs(_f(p.get("positionValue")))
            if not szi or wert < max(E.MIN_POS_USD, E.MIN_POS_ANTEIL * av):
                continue
            pos[p["coin"]] = {"r": 1 if szi > 0 else -1, "wert": round(wert), "einstieg": _f(p.get("entryPx")),
                              "hebel": (p.get("leverage") or {}).get("value"), "upnl": round(_f(p.get("unrealizedPnl")))}
        snap[a] = pos
    return snap, konten


def konsens(snap):
    je_coin = {}
    for a, pos in snap.items():
        for coin, p in pos.items():
            c = je_coin.setdefault(coin, {"long": 0, "short": 0, "wert_long": 0, "wert_short": 0, "trader": []})
            c["long" if p["r"] > 0 else "short"] += 1
            c["wert_long" if p["r"] > 0 else "wert_short"] += p["wert"]
            c["trader"].append([a, p["r"]])
    for coin, c in je_coin.items():
        n = c["long"] + c["short"]
        r = 1 if c["long"] >= c["short"] else -1
        c["n"], c["richtung"] = n, r
        c["anteil"] = round(max(c["long"], c["short"]) / n, 2)
        c["signal"] = n >= E.KONSENS_MIN_TRADER and c["anteil"] >= E.KONSENS_MIN_ANTEIL
    return je_coin


# ---------------- Papier-Portfolio (Konsens) ----------------
def neues_portfolio(preise):
    return {"start": jetzt_ms(), "cash": E.START_KAPITAL, "pos": {}, "trades": [], "verlauf": [],
            "btc_start": (preise.get("BTC") or {}).get("px"), "gebuehren": 0.0, "funding": 0.0, "zuletzt": jetzt_ms()}


def _wert_pos(p, px):
    return p["notional"] + p["r"] * (px - p["einstieg"]) * p["menge"]


def portfolio_wert(P, preise):
    w = P["cash"]
    for coin, p in P["pos"].items():
        px = (preise.get(coin) or {}).get("px") or p.get("letzter_px") or p["einstieg"]
        w += _wert_pos(p, px)
    return w


def funding_verbuchen(P, preise):
    jetzt = jetzt_ms()
    std = max(0.0, (jetzt - P.get("zuletzt", jetzt)) / 3_600_000)
    for coin, p in P["pos"].items():
        q = preise.get(coin)
        if not q:
            continue
        betrag = q["funding"] * std * p["menge"] * q["px"] * p["r"]  # Longs zahlen bei positiver Rate
        P["cash"] -= betrag
        P["funding"] -= betrag
        p["funding"] = p.get("funding", 0.0) - betrag
        p["letzter_px"] = q["px"]
    P["zuletzt"] = jetzt


def konsens_handeln(P, K, preise):
    """Schließt Positionen ohne Konsens, eröffnet neue Konsens-Signale. Gibt Ereignisse für Push zurück."""
    ereignisse = []
    for coin in list(P["pos"]):
        p, c, q = P["pos"][coin], K.get(coin), preise.get(coin)
        if not q:
            continue
        gleich = c and c["richtung"] == p["r"]
        n_gleich = (c["long"] if p["r"] > 0 else c["short"]) if c else 0
        ant = (n_gleich / c["n"]) if c and c["n"] else 0
        if not gleich or n_gleich < E.KONSENS_AUS_TRADER or ant < E.KONSENS_AUS_ANTEIL:
            aus = q["px"] * (1 - p["r"] * E.SLIPPAGE)
            brutto = p["r"] * (aus - p["einstieg"]) * p["menge"]
            geb = abs(aus * p["menge"]) * E.GEBUEHR
            P["cash"] += p["notional"] + brutto - geb
            P["gebuehren"] += geb
            ergebnis = brutto - geb - p.get("geb_ein", 0) + p.get("funding", 0)
            t = {"coin": coin, "r": p["r"], "ein": p["einstieg"], "aus": round(aus, 6), "zeit_ein": p["zeit"], "zeit_aus": jetzt_ms(),
                 "notional": round(p["notional"], 2), "ergebnis": round(ergebnis, 2), "pct": round(ergebnis / p["notional"], 4),
                 "trader_ein": p.get("trader_n"), "grund": "Konsens weg" if c else "keiner hält mehr"}
            P["trades"].append(t)
            del P["pos"][coin]
            ereignisse.append(("zu", t))
    wert = portfolio_wert(P, preise)
    kandidaten = sorted((k for k, c in K.items() if c["signal"] and k not in P["pos"] and k in preise),
                        key=lambda k: (-K[k]["n"], -K[k]["anteil"]))
    for coin in kandidaten:
        if len(P["pos"]) >= E.MAX_POSITIONEN:
            break
        c, q = K[coin], preise[coin]
        notional = min(wert * E.POS_ANTEIL, P["cash"])
        if notional < 50:
            break
        ein = q["px"] * (1 + c["richtung"] * E.SLIPPAGE)
        geb = notional * E.GEBUEHR
        P["cash"] -= notional + geb
        P["gebuehren"] += geb
        P["pos"][coin] = {"r": c["richtung"], "einstieg": round(ein, 6), "menge": notional / ein, "notional": notional,
                          "zeit": jetzt_ms(), "geb_ein": geb, "trader_n": c["n"], "anteil": c["anteil"], "letzter_px": q["px"]}
        ereignisse.append(("auf", {"coin": coin, "r": c["richtung"], "ein": ein, "n": c["n"],
                                   "gleich": c["long"] if c["richtung"] > 0 else c["short"], "notional": notional}))
    return ereignisse


# ---------------- Einzel-Kopie-Test ----------------
def einzel_kopie(EK, alt, neu, preise, erster_lauf):
    """EK: {adresse: {"offen": {coin: {...}}, "fertig": [...]}}. Kopiert nur Positionen, die NEU auftauchen."""
    jetzt = jetzt_ms()
    for a, pos in neu.items():
        d = EK.setdefault(a, {"offen": {}, "fertig": []})
        vorher = alt.get(a)
        # Kopien schließen, wenn der Trader schließt oder dreht
        for coin in list(d["offen"]):
            k = d["offen"][coin]
            p = pos.get(coin)
            if p and p["r"] == k["r"]:
                continue
            q = preise.get(coin)
            if not q:
                continue
            aus = q["px"] * (1 - k["r"] * E.SLIPPAGE)
            erg = k["r"] * (aus - k["ein"]) * k["menge"] - (aus * k["menge"] + E.EINZEL_NOTIONAL) * E.GEBUEHR
            d["fertig"].append({"coin": coin, "r": k["r"], "ein": k["ein"], "aus": round(aus, 6), "zeit_ein": k["zeit"], "zeit_aus": jetzt,
                                "ergebnis": round(erg, 2), "verz": k.get("verz")})
            d["fertig"] = d["fertig"][-60:]
            del d["offen"][coin]
        if erster_lauf or vorher is None:
            continue  # bestehende Positionen nicht kopieren: Einstiegszeitpunkt unbekannt
        for coin, p in pos.items():
            if coin in d["offen"]:
                continue
            war = vorher.get(coin)
            if war and war["r"] == p["r"]:
                continue
            q = preise.get(coin)
            if not q:
                continue
            ein = q["px"] * (1 + p["r"] * E.SLIPPAGE)
            # Verzögerungskosten: wie viel schlechter als der Trader selbst eingestiegen sind
            verz = p["r"] * (ein - p["einstieg"]) / p["einstieg"] if p["einstieg"] else None
            d["offen"][coin] = {"r": p["r"], "ein": round(ein, 6), "menge": E.EINZEL_NOTIONAL / ein, "zeit": jetzt,
                                "trader_ein": p["einstieg"], "verz": round(verz, 5) if verz is not None else None}
    # Trader, die nicht mehr ausgewählt sind: offene Kopien zum aktuellen Preis schließen
    for a in list(EK):
        if a in neu:
            continue
        d = EK[a]
        for coin, k in list(d["offen"].items()):
            q = preise.get(coin)
            if not q:
                continue
            aus = q["px"] * (1 - k["r"] * E.SLIPPAGE)
            erg = k["r"] * (aus - k["ein"]) * k["menge"] - (aus * k["menge"] + E.EINZEL_NOTIONAL) * E.GEBUEHR
            d["fertig"].append({"coin": coin, "r": k["r"], "ein": k["ein"], "aus": round(aus, 6), "zeit_ein": k["zeit"], "zeit_aus": jetzt,
                                "ergebnis": round(erg, 2), "verz": k.get("verz"), "grund": "abgewählt"})
            del d["offen"][coin]


def einzel_auswertung(EK, preise):
    out = {}
    for a, d in EK.items():
        fertig = d["fertig"]
        offen_erg = 0.0
        for coin, k in d["offen"].items():
            q = preise.get(coin)
            if q:
                offen_erg += k["r"] * (q["px"] - k["ein"]) * k["menge"]
        verz = [x["verz"] for x in fertig + list(d["offen"].values()) if x.get("verz") is not None]
        out[a] = {"anzahl": len(fertig), "offen": len(d["offen"]), "ergebnis": round(sum(x["ergebnis"] for x in fertig), 2),
                  "offen_erg": round(offen_erg, 2), "treffer": round(sum(x["ergebnis"] > 0 for x in fertig) / len(fertig), 2) if fertig else None,
                  "verz": round(sum(verz) / len(verz), 5) if verz else None}
    return out
