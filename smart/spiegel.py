# -*- coding: utf-8 -*-
"""
Spiegel-Portfolio: Startkapital wird nach der Note auf alle ausgewählten Trader verteilt. Jede Position eines Traders
wird anteilig gespiegelt: hält er 20 % seines Kontos in ETH long, hält sein Teil-Portfolio ebenfalls 20 % in ETH long.
Ohne Hebel: nutzt ein Trader mehr als 100 % seines Kontos, werden seine Positionen proportional heruntergerechnet.
Gewichte und Budgets passen sich bei jedem Lauf an (neue Trader bekommen Kapital, ausgeschiedene werden geschlossen).
Gebühren, Slippage und Funding wie im Konsens-Test. Keine echten Orders.
"""
import einstellungen as E
import signale as SG


def neues(preise):
    return {"start": SG.jetzt_ms(), "kapital": E.SPIEGEL_KAPITAL, "cash": E.SPIEGEL_KAPITAL, "pos": {}, "trades": [], "verlauf": [],
            "btc_start": (preise.get("BTC") or {}).get("px"), "gebuehren": 0.0, "funding": 0.0, "zuletzt": SG.jetzt_ms(), "je_trader": {}}


def _px(p, preise):
    return (preise.get(p["coin"]) or {}).get("px") or p.get("letzter_px") or p["einstieg"]


def wert(S, preise):
    return S["cash"] + sum(p["menge"] * p["einstieg"] + p["r"] * (_px(p, preise) - p["einstieg"]) * p["menge"] for p in S["pos"].values())


def funding(S, preise):
    jetzt = SG.jetzt_ms()
    std = max(0.0, (jetzt - S.get("zuletzt", jetzt)) / 3_600_000)
    for p in S["pos"].values():
        q = preise.get(p["coin"])
        if not q:
            continue
        betrag = q["funding"] * std * p["menge"] * q["px"] * p["r"]
        S["cash"] -= betrag
        S["funding"] -= betrag
        p["funding"] = p.get("funding", 0.0) - betrag
        p["letzter_px"] = q["px"]
        jt = S["je_trader"].setdefault(p["a"], {"realisiert": 0.0})
        jt["realisiert"] = jt.get("realisiert", 0.0) - betrag
    S["zuletzt"] = jetzt


def gewichte(trader):
    noten = {t["adresse"]: max(t.get("note") or 0, 1) for t in trader}
    summe = sum(noten.values()) or 1
    return {a: n / summe for a, n in noten.items()}


def _kaufen(S, a, coin, r, notional, px, grund):
    ein = px * (1 + r * E.SLIPPAGE)
    menge = notional / ein
    geb = notional * E.GEBUEHR
    key = f"{a}|{coin}"
    p = S["pos"].get(key)
    if p:  # aufstocken: Durchschnittspreis
        ges = p["menge"] + menge
        p["einstieg"] = (p["einstieg"] * p["menge"] + ein * menge) / ges
        p["menge"] = ges
    else:
        S["pos"][key] = {"a": a, "coin": coin, "r": r, "menge": menge, "einstieg": ein, "zeit": SG.jetzt_ms(), "funding": 0.0, "letzter_px": px}
    S["cash"] -= notional + geb
    S["gebuehren"] += geb
    jt = S["je_trader"].setdefault(a, {"realisiert": 0.0})
    jt["realisiert"] = jt.get("realisiert", 0.0) - geb
    return {"art": "auf" if not p else "mehr", "a": a, "coin": coin, "r": r, "notional": round(notional, 2), "px": ein, "grund": grund}


def _verkaufen(S, key, anteil, px, grund):
    p = S["pos"][key]
    menge = p["menge"] * anteil
    aus = px * (1 - p["r"] * E.SLIPPAGE)
    brutto = p["r"] * (aus - p["einstieg"]) * menge
    geb = aus * menge * E.GEBUEHR
    S["cash"] += p["einstieg"] * menge + brutto - geb
    S["gebuehren"] += geb
    jt = S["je_trader"].setdefault(p["a"], {"realisiert": 0.0})
    jt["realisiert"] = jt.get("realisiert", 0.0) + brutto - geb
    t = {"a": p["a"], "coin": p["coin"], "r": p["r"], "ein": round(p["einstieg"], 6), "aus": round(aus, 6), "zeit_ein": p["zeit"],
         "zeit_aus": SG.jetzt_ms(), "notional": round(p["einstieg"] * menge, 2), "ergebnis": round(brutto - geb, 2), "teil": anteil < 0.999, "grund": grund}
    if anteil >= 0.999:
        del S["pos"][key]
    else:
        p["menge"] -= menge
    S["trades"].append(t)
    S["trades"] = S["trades"][-600:]
    return {"art": "zu" if anteil >= 0.999 else "weniger", **t}


def handeln(S, trader, snap, konten, preise):
    """Zielgrößen aus den Positionen der Trader berechnen und das Spiegel-Portfolio darauf ausrichten."""
    ereignisse = []
    gesamt = wert(S, preise)
    gew = gewichte(trader)
    ausgewaehlt = {t["adresse"] for t in trader}
    ziele = {}
    for a, g in gew.items():
        if a not in snap or not konten.get(a):
            continue
        av = konten[a]
        ws = {coin: p["r"] * p["wert"] / av for coin, p in snap[a].items() if p.get("wert")}
        summe = sum(abs(w) for w in ws.values())
        faktor = 1 / summe if summe > 1 else 1.0  # kein Hebel
        budget = gesamt * g
        for coin, w in ws.items():
            ziele[f"{a}|{coin}"] = (1 if w > 0 else -1, abs(w) * faktor * budget, a, coin)
    for a in gew:
        jt = S["je_trader"].setdefault(a, {"realisiert": 0.0})
        jt["gewicht"] = round(gew[a], 4)
        jt["budget"] = round(gesamt * gew[a], 2)
    for a, jt in S["je_trader"].items():
        if a not in gew:
            jt["gewicht"], jt["budget"] = 0.0, 0.0
    # schließen: Trader hat geschlossen, gedreht oder ist ausgeschieden (bei Abruffehler nichts anfassen)
    for key in list(S["pos"]):
        p = S["pos"][key]
        if p["a"] in ausgewaehlt and p["a"] not in snap:
            continue
        z = ziele.get(key)
        if z and z[0] == p["r"] and z[1] >= E.SPIEGEL_MIN_POS:
            continue
        q = preise.get(p["coin"])
        if not q:
            continue
        grund = "ausgeschieden" if p["a"] not in ausgewaehlt else ("gedreht" if z else "Trader hat geschlossen")
        ereignisse.append(_verkaufen(S, key, 1.0, q["px"], grund))
    # eröffnen oder anpassen
    for key, (r, ziel, a, coin) in sorted(ziele.items(), key=lambda x: -x[1][1]):
        q = preise.get(coin)
        if not q or ziel < E.SPIEGEL_MIN_POS:
            continue
        p = S["pos"].get(key)
        if not p:
            betrag = min(ziel, S["cash"] * 0.995)
            if betrag >= E.SPIEGEL_MIN_POS:
                ereignisse.append(_kaufen(S, a, coin, r, betrag, q["px"], "Trader hat eröffnet" if S.get("verlauf") else "Start"))
            continue
        jetzt = p["menge"] * q["px"]
        diff = ziel - jetzt
        if abs(diff) < max(E.SPIEGEL_ANPASSEN_AB * ziel, E.SPIEGEL_MIN_POS):
            continue
        if diff > 0:
            betrag = min(diff, S["cash"] * 0.995)
            if betrag >= E.SPIEGEL_MIN_POS:
                ereignisse.append(_kaufen(S, a, coin, r, betrag, q["px"], "aufgestockt"))
        else:
            ereignisse.append(_verkaufen(S, key, min(1.0, -diff / jetzt), q["px"], "verkleinert"))
    return ereignisse


def auswertung(S, preise):
    je = {}
    for a, jt in S.get("je_trader", {}).items():
        offen = [p for p in S["pos"].values() if p["a"] == a]
        uerg = sum(p["r"] * (_px(p, preise) - p["einstieg"]) * p["menge"] for p in offen)
        je[a] = {"gewicht": jt.get("gewicht"), "budget": jt.get("budget"), "realisiert": round(jt.get("realisiert", 0.0), 2),
                 "offen_erg": round(uerg, 2), "positionen": len(offen), "einsatz": round(sum(p["menge"] * p["einstieg"] for p in offen), 2)}
    return je
