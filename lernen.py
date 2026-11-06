# -*- coding: utf-8 -*-
"""
Lernmodul: Etwa einmal im Monat spielt der Radar die letzten ~400 Handelstage mit vielen
Varianten seiner Einstellungen durch (Schwelle, Haltedauer, Stopp, Gewichtung der Signale).
Ist eine Variante klar besser als die aktuelle, übernimmt er sie – aber nur für die Zukunft.
Vergangene Empfehlungen im Journal werden nie nachträglich verändert.

Bewusst vorsichtig: kleine Auswahl an Varianten, Mindestzahl an Trades und eine Marge,
damit er nicht jedem Zufallstreffer hinterherläuft (Überanpassung).
"""
import itertools
import time
from types import SimpleNamespace

import numpy as np

import engine

GEWICHTE = {
    "ausgewogen": (0.30, 0.40, 0.40),
    "mehr Zahlen": (0.25, 0.50, 0.30),
    "mehr Insider": (0.25, 0.30, 0.50),
    "mehr Momentum": (0.40, 0.35, 0.35),
}
SCHWELLEN = (50, 55, 60, 65)
HALTEDAUERN = (20, 40, 60)
NACHZIEH = (2.5, 3.5)


def parameter(cfg, ueberschreibung=None):
    p = SimpleNamespace(**{k: getattr(cfg, k) for k in dir(cfg) if k.isupper()})
    for k, v in (ueberschreibung or {}).items():
        setattr(p, k, v)
    return p


def _ziel(eq):
    if len(eq) < 10:
        return 0.0
    return float(eq[-1] / eq[0] - 1 - 0.5 * abs((eq / np.maximum.accumulate(eq) - 1).min()))


def _bewerten(dep, teilung=2 / 3):
    """Lernteil = erste 2/3 des Fensters, Prüfteil = letztes 1/3 (liegt zeitlich danach)."""
    eq = np.array([k[1] for k in dep["kurve"]])
    if len(eq) < 30:
        return None
    k = int(len(eq) * teilung)
    gz = [t for t in dep["trades"] if t["status"] == "geschlossen"]
    grenze = dep["kurve"][k][0]
    return {"rendite": float(eq[-1] / eq[0] - 1), "maxdd": float((eq / np.maximum.accumulate(eq) - 1).min()),
            "trades": len(gz), "trades_lern": sum(1 for t in gz if t["signal_datum"] < grenze),
            "quote": float(np.mean([t["ergebnis"] > 0 for t in gz])) if gz else 0.0,
            "lern": _ziel(eq[:k + 1]), "pruef": _ziel(eq[k:]), "ziel": _ziel(eq)}


def _simulieren(s, par, start, ende, bench, score):
    dep = engine.neues_depot()
    for d in range(start, ende + 1):
        engine.tag_verarbeiten(dep, s, d, par, "Test", {}, bench, score=score)
    return dep


def lernen(dep, s, cfg, bench, erzwingen=False):
    """Prüft Varianten und passt dep['parameter'] an. Gibt einen Text für die Konsole zurück."""
    if not cfg.LERNEN_AKTIV:
        return "Lernmodul aus."
    idx = s["C"].index
    n = len(idx)
    letzte = dep.get("lernen", {}).get("datum")
    if letzte and not erzwingen:
        seit = int((idx > np.datetime64(letzte)).sum())
        if seit < cfg.LERN_INTERVALL:
            return f"Lernmodul: nächste Prüfung in {cfg.LERN_INTERVALL - seit} Handelstagen."
    start = max(300, n - 1 - cfg.LERN_FENSTER)
    ende = n - 1
    if ende - start < 120:
        return "Lernmodul: zu wenig Historie."

    t0 = time.time()
    aktuell = dict(dep.get("parameter") or {})
    akt_par = parameter(cfg, aktuell)
    zeilen = []
    scores = {name: engine.kombiniere(s, *w) for name, w in GEWICHTE.items()}
    for (gname, w), schw, halt, nz in itertools.product(GEWICHTE.items(), SCHWELLEN, HALTEDAUERN, NACHZIEH):
        ueb = {"GEWICHT_MOMENTUM": w[0], "GEWICHT_PEAD": w[1], "GEWICHT_INSIDER": w[2], "SCHWELLE": schw,
               "SCHWELLE_RISK_OFF": schw + 15, "HALTEDAUER": halt, "STOPP_ATR_NACHZIEH": nz}
        par = parameter(cfg, ueb)
        erg = _bewerten(_simulieren(s, par, start, ende, bench, scores[gname]))
        if erg:
            zeilen.append({**erg, "gewichte": gname, "parameter": ueb})

    def gleich(z):
        return all(abs(getattr(akt_par, k) - v) < 1e-9 for k, v in z["parameter"].items())

    ref = next((z for z in zeilen if gleich(z)), None)
    if ref is None:
        sc = engine.kombiniere(s, akt_par.GEWICHT_MOMENTUM, akt_par.GEWICHT_PEAD, akt_par.GEWICHT_INSIDER)
        ref = {**_bewerten(_simulieren(s, akt_par, start, ende, bench, sc)), "gewichte": "aktuell", "parameter": aktuell}
    geeignet = [z for z in zeilen if z["trades_lern"] >= cfg.LERN_MIN_TRADES * 2 / 3]
    bester = max(geeignet, key=lambda z: z["lern"]) if geeignet else ref
    marge = lambda x: x + max(0.02, cfg.LERN_MARGE * abs(x))
    # nur wechseln, wenn die Variante im Lernteil UND im danach liegenden Prüfteil klar besser ist
    wechsel = bester is not ref and bester["lern"] > marge(ref["lern"]) and bester["pruef"] > marge(ref["pruef"])

    eintrag = {"datum": idx[-1].date().isoformat(), "fenster": [idx[start].date().isoformat(), idx[ende].date().isoformat()],
               "varianten": len(zeilen), "aktuell": ref, "bester": bester, "gewechselt": wechsel,
               "top": sorted(geeignet, key=lambda z: z["lern"], reverse=True)[:8], "dauer_s": round(time.time() - t0, 1)}
    hist = dep.get("lernen", {}).get("historie", [])
    if wechsel:
        dep["parameter"] = bester["parameter"]
        hist.append({"datum": eintrag["datum"], "von": aktuell, "nach": bester["parameter"],
                     "grund": (f"Lernteil {bester['lern'] * 100:+.1f} % statt {ref['lern'] * 100:+.1f} %, Prüfteil "
                               f"{bester['pruef'] * 100:+.1f} % statt {ref['pruef'] * 100:+.1f} %").replace(".", ",")})
    eintrag["historie"] = hist[-20:]
    dep["lernen"] = eintrag
    return (f"Lernmodul: {len(zeilen)} Varianten geprüft ({eintrag['dauer_s']} s) – "
            + ("neue Einstellungen übernommen." if wechsel else "aktuelle Einstellungen bleiben."))
