# -*- coding: utf-8 -*-
"""
Lernmodul – der Radar überprüft sich selbst.

Etwa einmal im Monat:
 1. Fehleranalyse: Welche Merkmale hatten die Verlierer gemeinsam (z. B. sehr hohe Schwankung,
    riesiger Kurssprung, Kauf bei schwachem Markt)? Daraus entstehen Filter-Ideen.
 2. Gittersuche: ~180 Kombinationen aus Gewichtung, Kauf-Schwelle, Haltedauer und Stopp werden
    über die letzten ~400 Handelstage simuliert.
 3. Robustheit: Eine Variante zählt nur, wenn auch ihre "Nachbarn" (leicht andere Einstellungen)
    gut sind – sonst ist es ein Zufallstreffer.
 4. Filter-Test: Die besten Varianten werden mit jeder Filter-Idee erneut simuliert.
 5. Prüfung: Gewählt wird auf den ersten 2/3 des Zeitraums (Lernteil). Übernommen wird nur, was
    auch im späteren Drittel (Prüfteil) klar besser ist.
Neue Regeln gelten nur für künftige Empfehlungen. Alles wird im Reiter "Lernen" protokolliert.
"""
import itertools
import time
from types import SimpleNamespace

import numpy as np
import pandas as pd

import engine

GEWICHTE = {
    "ausgewogen": (0.30, 0.40, 0.40, 0.15),
    "mehr Zahlen": (0.25, 0.50, 0.30, 0.15),
    "mehr Insider": (0.25, 0.30, 0.50, 0.15),
    "mehr Momentum": (0.40, 0.35, 0.35, 0.15),
    "mehr 52W-Hoch": (0.25, 0.35, 0.35, 0.30),
}
SCHWELLEN = (50, 55, 60, 65)
HALTEDAUERN = (20, 40, 60)
NACHZIEH = (2.5, 3.0, 3.5)
STANDARD_FILTER = [
    {"merkmal": "vola", "op": "<=", "wert": 0.60, "text": "Schwankung höchstens 60 % p.a."},
    {"merkmal": "dist200", "op": "<=", "wert": 0.40, "text": "höchstens 40 % über der 200-Tage-Linie"},
    {"merkmal": "sprung", "op": "<=", "wert": 0.15, "text": "Kurssprung höchstens +15 %"},
    {"merkmal": "m1", "op": "<=", "wert": 0.25, "text": "Kursplus im letzten Monat höchstens 25 %"},
    {"merkmal": "regime", "op": ">=", "wert": 1, "text": "nur kaufen, wenn der Markt über seiner 200-Tage-Linie liegt"},
]


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


def _pct(x):
    return f"{x * 100:+.1f} %".replace(".", ",")


# ---------------------------------------------------------------------------
# Fehleranalyse
# ---------------------------------------------------------------------------
def fehleranalyse(trades):
    """Vergleicht Gewinner und Verlierer nach Merkmalen und schlägt Filter vor."""
    gz = [t for t in trades if t["status"] == "geschlossen" and t.get("merkmale")]
    if len(gz) < 12:
        return {"muster": [], "filter_ideen": [], "n": len(gz)}
    df = pd.DataFrame([{**t["merkmale"], "erg": t["ergebnis"]} for t in gz])
    gesamt = df["erg"].mean()
    muster, ideen = [], []
    for m, name in engine.MERKMALE.items():
        if m not in df or df[m].nunique() < 3:
            continue
        if m == "regime":
            for wert, label in ((0, "Markt unter 200-Tage-Linie"), (1, "Markt über 200-Tage-Linie")):
                g = df[df[m] == wert]
                if len(g) >= 4:
                    muster.append({"merkmal": name, "bereich": label, "n": int(len(g)), "avg": float(g["erg"].mean()),
                                   "quote": float((g["erg"] > 0).mean())})
            continue
        q1, q2 = df[m].quantile([1 / 3, 2 / 3])
        for label, maske, op, grenze in (("unteres Drittel", df[m] <= q1, ">=", q1),
                                         ("mittleres Drittel", (df[m] > q1) & (df[m] <= q2), None, None),
                                         ("oberes Drittel", df[m] > q2, "<=", q2)):
            g = df[maske]
            if len(g) < 4:
                continue
            fmt = (lambda v: f"{v:.0f}") if m == "score" else (lambda v: f"{v * 100:.0f} %")
            bereich = {"unteres Drittel": f"≤ {fmt(q1)}", "mittleres Drittel": f"{fmt(q1)} – {fmt(q2)}",
                       "oberes Drittel": f"> {fmt(q2)}"}[label]
            eintrag = {"merkmal": name, "bereich": bereich, "n": int(len(g)), "avg": float(g["erg"].mean()),
                       "quote": float((g["erg"] > 0).mean())}
            muster.append(eintrag)
            if op and len(g) >= 5 and g["erg"].mean() < gesamt - 0.02 and g["erg"].mean() < 0:
                ideen.append({"merkmal": m, "op": op, "wert": round(float(grenze), 3),
                              "text": f"{name} {'mindestens' if op == '>=' else 'höchstens'} {fmt(grenze)}",
                              "grund": f"{len(g)} Trades mit {name} {bereich} brachten im Schnitt {_pct(g['erg'].mean())} "
                                       f"(alle Trades: {_pct(gesamt)})"})
    muster.sort(key=lambda x: x["avg"])
    return {"muster": muster, "filter_ideen": ideen, "n": len(gz), "gesamt": float(gesamt)}


def verlust_diagnose(trades, n=6):
    gz = sorted([t for t in trades if t["status"] == "geschlossen"], key=lambda t: t["ergebnis"])[:n]
    out = []
    for t in gz:
        if t["ergebnis"] >= 0:
            break
        mk = t.get("merkmale", {})
        ursachen = []
        if t.get("markt") is not None and t["markt"] < -0.03:
            ursachen.append(f"der Gesamtmarkt fiel in der Zeit um {_pct(t['markt'])} – Marktrisiko, kein Einzelfehler")
        if mk.get("vola", 0) > 0.55:
            ursachen.append(f"sehr schwankungsreiche Aktie ({mk['vola'] * 100:.0f} % p.a.) – Stopp wurde leicht erreicht")
        if mk.get("sprung", 0) > 0.15:
            ursachen.append(f"riesiger Kurssprung (+{mk['sprung'] * 100:.0f} %) – vieles war schon eingepreist")
        if mk.get("dist200", 0) > 0.35:
            ursachen.append(f"Aktie lag schon {mk['dist200'] * 100:.0f} % über ihrer 200-Tage-Linie – überdehnt")
        if mk.get("regime", 1) == 0:
            ursachen.append("Kauf bei schwachem Gesamtmarkt")
        if "Negativer" in t.get("ausstieg_grund", ""):
            ursachen.append("negative Nachricht/Kursrutsch während der Haltezeit – Notausstieg hat größeren Schaden verhindert")
        if not ursachen:
            ursachen.append("kein auffälliges Merkmal – normale Streuung, die zu jeder Strategie gehört")
        try:
            tage = int(np.busday_count(t["einstieg_datum"], t["ausstieg_datum"]))
        except Exception:
            tage = None
        out.append({"ticker": t["ticker"], "datum": t["signal_datum"], "ergebnis": t["ergebnis"], "tage": tage,
                    "grund": t["ausstieg_grund"], "typen": t.get("typen", []), "ursachen": ursachen, "id": t["id"]})
    return out


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------
def lernen(dep, s, cfg, bench, erzwingen=False):
    """Prüft Varianten und passt dep['parameter'] an. Gibt einen Text für die Konsole zurück."""
    if not cfg.LERNEN_AKTIV:
        return "Lernmodul aus."
    idx = s["C"].index
    n = len(idx)
    letzte = dep.get("lernen", {}).get("datum")
    if letzte and not erzwingen:
        seit = int((idx > pd.Timestamp(letzte)).sum())
        if seit < cfg.LERN_INTERVALL:
            return f"Lernmodul: nächste Prüfung in {cfg.LERN_INTERVALL - seit} Handelstagen."
    start = max(300, n - 1 - cfg.LERN_FENSTER)
    ende = n - 1
    if ende - start < 120:
        return "Lernmodul: zu wenig Historie."

    t0 = time.time()
    aktuell = dict(dep.get("parameter") or {})
    akt_par = parameter(cfg, aktuell)
    gedanken = []

    # 1) Referenz: aktuelle Einstellungen
    ref_dep = _simulieren(s, akt_par, start, ende, bench, engine.kombiniere(s, akt_par))
    ref = {**_bewerten(ref_dep), "name": "aktuell", "parameter": aktuell}
    ref["robust"] = ref["lern"]
    analyse = fehleranalyse(dep["trades"] + [t for t in ref_dep["trades"] if t["signal_datum"] < (dep.get("start") or "9")])
    gedanken.append(f"Mit den aktuellen Einstellungen: {_pct(ref['rendite'])} Rendite, max. Rückgang {_pct(ref['maxdd'])}, "
                    f"{ref['trades']} Trades, Trefferquote {ref['quote'] * 100:.0f} %.")
    if analyse["filter_ideen"]:
        for f in analyse["filter_ideen"][:3]:
            gedanken.append(f"Auffällig bei den Verlierern: {f['grund']}. Idee: „{f['text']}“ testen.")
    else:
        gedanken.append("Die Verlierer haben kein gemeinsames Merkmal, das deutlich heraussticht.")

    # 2) Gittersuche
    scores = {name: engine.kombiniere(s, parameter(cfg, dict(zip(("GEWICHT_MOMENTUM", "GEWICHT_PEAD", "GEWICHT_INSIDER", "GEWICHT_HOCH"), w))))
              for name, w in GEWICHTE.items()}
    zeilen = {}
    for (gname, w), schw, halt, nz in itertools.product(GEWICHTE.items(), SCHWELLEN, HALTEDAUERN, NACHZIEH):
        ueb = {"GEWICHT_MOMENTUM": w[0], "GEWICHT_PEAD": w[1], "GEWICHT_INSIDER": w[2], "GEWICHT_HOCH": w[3],
               "SCHWELLE": schw, "SCHWELLE_RISK_OFF": schw + 15, "HALTEDAUER": halt, "STOPP_ATR_NACHZIEH": nz,
               "FILTER": list(akt_par.FILTER)}
        erg = _bewerten(_simulieren(s, parameter(cfg, ueb), start, ende, bench, scores[gname]))
        if erg:
            zeilen[(gname, schw, halt, nz)] = {**erg, "name": f"{gname} · {schw} · {halt} T · {nz:.1f}×".replace(".", ","),
                                               "gewichte": gname, "parameter": ueb}

    # 3) Robustheit: Mittel aus Variante und Nachbarn
    def nachbarn(k):
        g, sc, h, z = k
        for ds in (-1, 0, 1):
            for dh in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    i, j, l = SCHWELLEN.index(sc) + ds, HALTEDAUERN.index(h) + dh, NACHZIEH.index(z) + dz
                    if 0 <= i < len(SCHWELLEN) and 0 <= j < len(HALTEDAUERN) and 0 <= l < len(NACHZIEH):
                        kk = (g, SCHWELLEN[i], HALTEDAUERN[j], NACHZIEH[l])
                        if kk in zeilen:
                            yield zeilen[kk]
    for k, z in zeilen.items():
        nb = list(nachbarn(k))
        z["robust"] = float(np.mean([x["lern"] for x in nb])) if nb else z["lern"]
    geeignet = [z for z in zeilen.values() if z["trades_lern"] >= cfg.LERN_MIN_TRADES * 2 / 3]
    top = sorted(geeignet, key=lambda z: z["robust"], reverse=True)

    # 4) Filter-Test auf den 3 robustesten Varianten (und den aktuellen Einstellungen)
    ideen = analyse["filter_ideen"] + [f for f in STANDARD_FILTER
                                       if not any(i["merkmal"] == f["merkmal"] for i in analyse["filter_ideen"])]
    vorh = {(f["merkmal"], f["op"]) for f in akt_par.FILTER}
    ideen = [f for f in ideen if (f["merkmal"], f["op"]) not in vorh]
    filter_tests = []
    basen = top[:3] + [ref]
    for basis in basen:
        for f in ideen:
            ueb = dict(basis["parameter"] or {})
            ueb["FILTER"] = list(parameter(cfg, ueb).FILTER) + [{k: f[k] for k in ("merkmal", "op", "wert", "text")}]
            p = parameter(cfg, ueb)
            erg = _bewerten(_simulieren(s, p, start, ende, bench, engine.kombiniere(s, p)))
            if erg:
                # Robustheit vom Basis-Nachbarschaftswert übernehmen und nur die Verbesserung addieren (faire Vergleichbarkeit)
                filter_tests.append({**erg, "name": f"{basis['name']} + Filter: {f['text']}", "basis": basis["name"],
                                     "filter": f["text"], "parameter": ueb,
                                     "robust": basis.get("robust", basis["lern"]) + (erg["lern"] - basis["lern"]),
                                     "verbesserung_lern": erg["lern"] - basis["lern"], "verbesserung_pruef": erg["pruef"] - basis["pruef"]})

    # 5) Entscheidung: bester Kandidat nach Lernteil (robust), Bestätigung im Prüfteil
    kandidaten = [z for z in top[:10]] + [f for f in filter_tests if f["trades_lern"] >= cfg.LERN_MIN_TRADES * 2 / 3
                                          and f["verbesserung_lern"] > 0.005 and f["verbesserung_pruef"] >= 0]
    marge = lambda x: x + max(0.02, cfg.LERN_MARGE * abs(x))
    bestaetigt = [z for z in kandidaten if z["robust"] > marge(ref["lern"]) and z["pruef"] > marge(ref["pruef"])]
    bester = max(bestaetigt, key=lambda z: z["robust"]) if bestaetigt else (max(kandidaten, key=lambda z: z["robust"]) if kandidaten else ref)
    wechsel = bool(bestaetigt)

    if top:
        b = top[0]
        gedanken.append(f"{len(zeilen)} Grundvarianten getestet. Robustester Kandidat: {b['name']} "
                        f"(Lernteil {_pct(b['lern'])}, Nachbarn im Schnitt {_pct(b['robust'])}, Prüfteil {_pct(b['pruef'])}).")
    gute_filter = [f for f in filter_tests if f["verbesserung_lern"] > 0.02 and f["verbesserung_pruef"] > 0]
    if gute_filter:
        f = max(gute_filter, key=lambda x: x["verbesserung_lern"] + x["verbesserung_pruef"])
        gedanken.append(f"Bester Filter: „{f['filter']}“ – verbessert {f['basis']} um {_pct(f['verbesserung_lern'])} (Lernteil) "
                        f"und {_pct(f['verbesserung_pruef'])} (Prüfteil).")
    elif filter_tests:
        gedanken.append(f"{len(filter_tests)} Filter-Tests: Keiner war in beiden Zeiträumen besser – Filter hätten auch gute Trades aussortiert.")
    if wechsel:
        gedanken.append(f"Entscheidung: Wechsel zu „{bester['name']}“. Sie ist im Lernteil ({_pct(bester['lern'])} statt "
                        f"{_pct(ref['lern'])}), auch bei leicht veränderten Einstellungen (Ø {_pct(bester['robust'])}), "
                        f"UND im späteren Prüfteil ({_pct(bester['pruef'])} statt {_pct(ref['pruef'])}) klar besser.")
    else:
        gedanken.append("Entscheidung: Keine Änderung. Keine Variante war in beiden Zeiträumen klar besser. "
                        "Ein Wechsel wäre wahrscheinlich nur Anpassung an Zufall.")

    eintrag = {"datum": idx[-1].date().isoformat(), "fenster": [idx[start].date().isoformat(), idx[ende].date().isoformat()],
               "varianten": len(zeilen) + len(filter_tests), "grund_varianten": len(zeilen), "filter_varianten": len(filter_tests),
               "aktuell": ref, "bester": bester, "gewechselt": wechsel, "gedanken": gedanken,
               "top": [{k: v for k, v in z.items() if k != "parameter"} for z in top[:10]],
               "filter_tests": sorted([{k: v for k, v in z.items() if k != "parameter"} for z in filter_tests],
                                      key=lambda z: z["lern"] + z["pruef"], reverse=True)[:10],
               "analyse": analyse, "verluste": verlust_diagnose(dep["trades"]), "dauer_s": round(time.time() - t0, 1),
               "punkte": [{"lern": round(z["lern"], 4), "pruef": round(z["pruef"], 4), "name": z["name"]} for z in zeilen.values()]}
    hist = dep.get("lernen", {}).get("historie", [])
    if wechsel:
        dep["parameter"] = bester["parameter"]
        hist.append({"datum": eintrag["datum"], "nach": bester["name"],
                     "grund": f"Lernteil {_pct(bester['lern'])} statt {_pct(ref['lern'])}, "
                              f"Prüfteil {_pct(bester['pruef'])} statt {_pct(ref['pruef'])}"})
    else:
        hist.append({"datum": eintrag["datum"], "nach": None, "grund": "Geprüft – keine Änderung nötig"})
    eintrag["historie"] = hist[-24:]
    dep["lernen"] = eintrag
    return (f"Lernmodul: {eintrag['varianten']} Varianten geprüft ({eintrag['dauer_s']} s) – "
            + ("neue Einstellungen übernommen." if wechsel else "aktuelle Einstellungen bleiben."))
