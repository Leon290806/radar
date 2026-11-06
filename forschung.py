# -*- coding: utf-8 -*-
"""
Forschungslabor – welche Effekte wirken mit echten Daten wirklich?

Einmal pro Woche über die gesamte Kurshistorie (~8 Jahre):

1. Ereignisstudie: Für jedes Signal (Kurssprung, Insider-Anomalie, 52W-Hoch, Momentum, ...)
   werden ALLE Ereignisse der Vergangenheit ausgewertet – oft tausende statt der ~100 Trades
   des Musterdepots. Gemessen wird die Rendite ab der nächsten Eröffnung nach 5, 20 und 60
   Handelstagen, jeweils abzüglich des Durchschnitts aller Aktien am selben Tag. Das ist die
   echte Mehrrendite des Signals – unabhängig davon, wie der Gesamtmarkt lief, und weitgehend
   frei vom Fehler „nur heutige Indexmitglieder“, weil der Vergleich dieselben Aktien nutzt.
   Zusätzlich wird gegen den S&P 500 gerechnet, denn den will der Radar schlagen.

2. Ehrliche Trennung: Gelernt wird nur auf dem älteren Teil (vor dem Rückblick des Musterdepots).
   Der Rückblick (~3 Jahre) ist damit ein echter Test mit Daten, die bei der Wahl unbekannt waren.

3. Übernahme: Ein Auslöser bleibt nur aktiv, wenn er im Lernteil statistisch belegt ist
   (t-Wert ≥ 2) und im Testteil nicht ins Minus kippt. Gibt es keinen belegten Auslöser,
   bleibt das Geld im ETF – lieber Index als Zufall.

4. Portfolio-Aufbau: Wie viele Aktien, wie groß, wie eng der Stopp? 12 Varianten werden über
   die ganze Historie simuliert; gewählt wird nach dem Lernteil.
"""
import itertools
import math
import time

import numpy as np
import pandas as pd

import engine

HORIZONTE = (5, 20, 60)


def _pz(x, n=1):
    """Prozent mit Vorzeichen, deutsches Komma."""
    return f"{x * 100:+.{n}f} %".replace(".", ",").replace("-", "−")
GROESSEN = {0: "klein", 1: "mittel", 2: "groß"}

# Welche Auslöser zusammen? (wird im Portfolio getestet – einzeln belegt heißt nicht, dass die Mischung besser ist)
AUSLOESER = {"M": "MOMENTUM_TRIGGER", "U": "UMKEHR_TRIGGER", "N": "NEG_KAUF_TRIGGER", "H": "HOCH_TRIGGER"}
AUSLOESER_NAME = {"M": "Momentum", "U": "Umkehr", "N": "Kursrutsch", "H": "52W-Hoch"}
# Ausstieg: Trend laufen lassen – oder schnell kleine Gewinne mitnehmen und Verluste früh begrenzen
AUSSTIEG = [
    ("Trend · Nachzieh-Stopp, 40 Tage", {"GEWINNZIEL_ATR": 0, "STOPP_ATR_START": 2.5, "STOPP_ATR_NACHZIEH": 3.0, "HALTEDAUER": 40}),
    ("Kurz · Ziel 1× ATR, Stopp 1,5× ATR, 5 Tage", {"GEWINNZIEL_ATR": 1.0, "STOPP_ATR_START": 1.5, "STOPP_ATR_NACHZIEH": 99, "HALTEDAUER": 5}),
    ("Schnell · Ziel 1,5× ATR, Stopp 2× ATR, 10 Tage", {"GEWINNZIEL_ATR": 1.5, "STOPP_ATR_START": 2.0, "STOPP_ATR_NACHZIEH": 99, "HALTEDAUER": 10}),
    ("Mittel · Ziel 2,5× ATR, Stopp 2× ATR, 20 Tage", {"GEWINNZIEL_ATR": 2.5, "STOPP_ATR_START": 2.0, "STOPP_ATR_NACHZIEH": 99, "HALTEDAUER": 20}),
]
AUFBAU = [
    ("8 Aktien · 8–20 %", {"MAX_POSITIONEN": 8, "GEWICHT_MIN": 0.08, "GEWICHT_MAX": 0.20, "MAX_VERLUST_PRO_TRADE": 0.02, "MAX_NEU_PRO_TAG": 2}),
    ("12 Aktien · 5–12 %", {"MAX_POSITIONEN": 12, "GEWICHT_MIN": 0.05, "GEWICHT_MAX": 0.12, "MAX_VERLUST_PRO_TRADE": 0.015, "MAX_NEU_PRO_TAG": 3}),
    ("20 Aktien · 3–8 %", {"MAX_POSITIONEN": 20, "GEWICHT_MIN": 0.03, "GEWICHT_MAX": 0.08, "MAX_VERLUST_PRO_TRADE": 0.01, "MAX_NEU_PRO_TAG": 4}),
]


# ---------------------------------------------------------------------------
# Ereignisse
# ---------------------------------------------------------------------------
def _beginn(maske):
    """Nur der erste Tag einer Phase zählt als Ereignis (sonst würde dasselbe Signal mehrfach gezählt)."""
    m = maske.fillna(False).astype(bool)
    return m & ~m.shift(1, fill_value=False)


def _ereignisse(s, ins, cfg):
    C = s["C"]
    elig = s["elig"].fillna(False)
    g = s["groesse"]
    ev = s["ev"].fillna(False) & elig
    E = {}
    E["Kurssprung nach Zahlen (alle)"] = ("zahlen", ev)
    for k, name in GROESSEN.items():
        E[f"Kurssprung · {name}e Aktien"] = ("zahlen_" + str(k), ev & (g == k))
    E["Kurssprung · starker Tagesschluss"] = ("zahlen_stark", ev & s["stark"].fillna(False))
    E["Kurssprung ≥ 10 %"] = ("zahlen_gross", ev & (s["plus"] >= 0.10))
    E["Negativer Kurssprung (Warnsignal)"] = ("neg", s["neg_ev"].fillna(False) & elig)
    E["Kauf nach Kursrutsch (Überreaktion)"] = ("neg_kauf", s["neg_ev"].fillna(False) & elig)
    E["52-Wochen-Hoch mit Volumen"] = ("hoch", s["h_ev"].fillna(False) & elig)
    monatsende = pd.Series(C.index.to_period("M"), index=C.index)
    monatsende = monatsende != monatsende.shift(-1)
    E["Momentum: stärkste 10 % (monatlich)"] = ("momentum", ((s["M"] >= 0.9) & elig).to_numpy() & monatsende.to_numpy()[:, None])
    r5 = C / C.shift(5) - 1
    rang5 = r5.where(elig & (g == 2)).rank(axis=1, pct=True)
    freitag = (C.index.dayofweek == 4)[:, None]
    E["Kurzfrist-Verlierer, große Aktien (Umkehr)"] = ("umkehr", (rang5 <= 0.05).to_numpy() & freitag)
    Ip = s["Ipkt"]
    E["Insider-Anomalie ≥ 50"] = ("insider50", _beginn(Ip >= 50) & elig)
    E["Insider-Anomalie ≥ 70"] = ("insider70", _beginn(Ip >= 70) & elig)
    E["Insider-Anomalie ≥ 50 · kleine/mittlere Aktien"] = ("insider50_km", _beginn(Ip >= 50) & elig & (g <= 1))
    E["Kurssprung + Insider gleichzeitig"] = ("kombi", _beginn((s["P"] > 0) & (Ip >= 50)) & elig)
    # Vergleich: jeder Insider-Kauf ab 25 Tsd. (ohne Bewertung) – zeigt, ob die Anomalie-Bewertung etwas bringt
    if ins is not None and not ins.empty:
        k = ins[(ins["typ"] == "Kauf") & ~ins["plan"].astype(bool) & (ins["wert"] >= cfg.INSIDER_MIN_KAUF) & ins["ticker"].isin(C.columns)]
        pos = C.index.searchsorted(pd.to_datetime(k["datum"]).values, side="right")
        jede = np.zeros(C.shape, dtype=bool)
        ok = pos < len(C.index)
        jede[pos[ok], [C.columns.get_loc(t) for t in k["ticker"][ok]]] = True
        E["Jeder Insider-Kauf (ohne Bewertung)"] = ("insider_alle", pd.DataFrame(jede, index=C.index, columns=C.columns) & elig)
    return E


def _renditen(s, bench):
    """Rendite von der nächsten Eröffnung bis zum Schluss nach h Tagen – gegen alle Aktien und gegen den S&P 500."""
    O, C, elig = s["O"], s["C"], s["elig"].fillna(False)
    E = O.shift(-1)
    out = {}
    for h in HORIZONTE:
        r = (C.shift(-h) / E - 1).where(elig).clip(-0.95, 3.0)
        uni = r.sub(r.mean(axis=1), axis=0)
        b = (bench.shift(-h) / bench.shift(-1) - 1) if bench is not None else r.mean(axis=1)
        spy = r.sub(b, axis=0)
        out[h] = (uni.to_numpy(), spy.to_numpy())
    return out


def _stat(werte, daten):
    """Mittelwert, Trefferquote und t-Wert über Monatsmittel (Ereignisse am selben Tag/Monat sind nicht unabhängig)."""
    if len(werte) < 8:
        return {"n": int(len(werte)), "avg": None, "t": None, "quote": None}
    m = pd.Series(werte).groupby(pd.PeriodIndex(daten, freq="M")).mean()
    t = float(m.mean() / (m.std(ddof=1) / math.sqrt(len(m)))) if len(m) > 2 and m.std(ddof=1) > 0 else None
    return {"n": int(len(werte)), "avg": float(np.mean(werte)), "t": t, "quote": float(np.mean(werte > 0))}


def ereignisstudie(s, ins, cfg, bench, grenze):
    idx = s["C"].index
    R = _renditen(s, bench)
    ergebnis = []
    for name, (key, maske) in _ereignisse(s, ins, cfg).items():
        m = np.asarray(maske, dtype=bool)
        zeilen, spalten = np.nonzero(m)
        if not len(zeilen):
            continue
        d = idx[zeilen]
        lern = d < grenze
        e = {"name": name, "key": key, "n": int(len(zeilen))}
        for h in HORIZONTE:
            uni, spy = R[h]
            v, w = uni[zeilen, spalten], spy[zeilen, spalten]
            ok = np.isfinite(v)
            e[f"h{h}"] = {"lern": _stat(v[ok & lern], d[ok & lern]), "test": _stat(v[ok & ~lern], d[ok & ~lern]),
                          "spy_lern": _stat(w[ok & lern & np.isfinite(w)], d[ok & lern & np.isfinite(w)]),
                          "spy_test": _stat(w[ok & ~lern & np.isfinite(w)], d[ok & ~lern & np.isfinite(w)])}
        uni, _ = R[20]
        v = uni[zeilen, spalten]
        ok = np.isfinite(v)
        e["jahre"] = {str(j): round(float(x), 4) for j, x in pd.Series(v[ok]).groupby(d[ok].year).mean().items()}
        e["urteil"] = _urteil(e)
        ergebnis.append(e)
    return ergebnis


def _urteil(e):
    """Belegt = im Lernteil t ≥ 2 (20 oder 60 Tage) und im Testteil nicht negativ."""
    best = None
    for h in (20, 60):
        l, t = e[f"h{h}"]["lern"], e[f"h{h}"]["test"]
        if l["avg"] is None or l["t"] is None:
            continue
        if best is None or (l["t"] or 0) > (best[1]["t"] or 0):
            best = (h, l, t)
    if best is None:
        return {"stufe": "zu wenig Daten", "h": None}
    h, l, t = best
    neg = e["key"] == "neg"
    if neg:
        return {"stufe": "Warnsignal belegt" if l["avg"] < 0 and (l["t"] or 0) <= -2 else "kein klares Warnsignal", "h": h}
    test_ok = t["avg"] is None or t["avg"] > 0
    if l["avg"] > 0 and l["t"] >= 2 and test_ok:
        stufe = "belegt"
    elif l["avg"] > 0 and l["t"] >= 1.5 and test_ok:
        stufe = "schwach"
    else:
        stufe = "kein Vorteil"
    return {"stufe": stufe, "h": h, "t": l["t"], "avg": l["avg"], "test": t["avg"]}


# ---------------------------------------------------------------------------
# Signal-Regeln aus der Ereignisstudie ableiten
# ---------------------------------------------------------------------------
def signal_regeln(studie):
    E = {e["key"]: e for e in studie}
    stufe = lambda k: E.get(k, {}).get("urteil", {}).get("stufe")
    t_l = lambda k, h=20: (E.get(k, {}).get(f"h{h}", {}).get("lern", {}).get("t") or 0)
    avg_l = lambda k, h=20: (E.get(k, {}).get(f"h{h}", {}).get("lern", {}).get("avg") or 0)
    p, gedanken = {}, []

    # Zahlen-Baustein
    groessen = [k for k in (0, 1, 2) if stufe(f"zahlen_{k}") in ("belegt", "schwach")]
    if stufe("zahlen") == "belegt" or any(stufe(f"zahlen_{k}") == "belegt" for k in (0, 1, 2)):
        p["PEAD_AKTIV"] = True
        p["PEAD_GROESSEN"] = groessen or [0, 1, 2]
        gedanken.append("Kurssprung nach Zahlen: belegt für " + ", ".join(GROESSEN[k] + "e" for k in p["PEAD_GROESSEN"]) + " Aktien.")
        ausgeschl = [GROESSEN[k] + "e" for k in (0, 1, 2) if k not in p["PEAD_GROESSEN"]]
        if ausgeschl:
            gedanken.append(f"Bei {', '.join(ausgeschl)} Aktien wirkt der Kurssprung nicht – dort wird er ignoriert.")
        if stufe("zahlen_stark") == "belegt" and avg_l("zahlen_stark") > avg_l("zahlen") + 0.003:
            p["PEAD_STARKER_SCHLUSS"] = True
            gedanken.append("Nur Kurssprünge mit starkem Tagesschluss zählen – sie liefen klar besser.")
        else:
            p["PEAD_STARKER_SCHLUSS"] = False
    else:
        p["PEAD_AKTIV"] = False
        gedanken.append("Kurssprung nach Zahlen: in den echten Daten kein belegter Vorteil – als Auslöser abgeschaltet.")

    # Insider-Baustein
    kand = [(k, thr) for k, thr in (("insider50", 50), ("insider70", 70)) if stufe(k) in ("belegt",)]
    if kand:
        k, thr = max(kand, key=lambda x: t_l(x[0]))
        p["INSIDER_TRIGGER"] = True
        p["INSIDER_MIN_AUFFAELLIG"] = thr
        gedanken.append(f"Insider-Anomalie: belegt, Schwelle {thr} Punkte (höchster t-Wert).")
    elif stufe("insider50") == "schwach" or stufe("insider70") == "schwach":
        p["INSIDER_TRIGGER"] = True
        p["INSIDER_MIN_AUFFAELLIG"] = 70
        gedanken.append("Insider-Anomalie: nur schwach belegt – nur die stärksten Fälle (ab 70 Punkten) zählen.")
    else:
        p["INSIDER_TRIGGER"] = False
        gedanken.append("Insider-Anomalie: in den echten Daten kein belegter Vorteil – als Auslöser abgeschaltet.")
    if "insider_alle" in E and "insider50" in E:
        a, b = avg_l("insider_alle"), avg_l("insider50")
        gedanken.append(f"Bewertung der Insider-Käufe: Anomalien ab 50 brachten {_pz(b, 2)} in 20 Tagen (gegenüber allen Aktien), "
                        f"alle Käufe ohne Bewertung {_pz(a, 2)}.")
    # Faktor-Auslöser: bekannte Marktanomalien, die ohne Ereignis wirken
    for key, par, name in (("momentum", "MOMENTUM_TRIGGER", "Momentum (stärkste 10 %)"),
                           ("hoch", "HOCH_TRIGGER", "52-Wochen-Hoch mit Volumen"),
                           ("umkehr", "UMKEHR_TRIGGER", "Kurzfrist-Umkehr (große Aktien nach 5 schwachen Tagen)"),
                           ("neg_kauf", "NEG_KAUF_TRIGGER", "Kauf nach Kursrutsch (Überreaktion)")):
        p[par] = stufe(key) == "belegt"
        gedanken.append(f"{name}: " + ("belegt – darf jetzt allein eine Empfehlung auslösen." if p[par]
                                       else "nicht belegt – löst nichts aus."))
    # Warnsignal: Verkauf/Sperre nach Kursrutsch nur, wenn danach wirklich weiter Verluste folgten
    warn = stufe("neg") == "Warnsignal belegt"
    p["EXIT_NEG_SPRUNG"] = p["NEG_SPERRE_AKTIV"] = warn
    if not warn:
        gedanken.append("Negativer Kurssprung: Danach ging es im Schnitt NICHT weiter abwärts – "
                        "Notverkauf und Kaufsperre nach Kursrutschen sind deshalb abgeschaltet.")
    # Priorität: belegte Mehrrendite in 20 Tagen (Lernteil) entscheidet, welcher Auslöser zuerst zum Zug kommt
    prio = {"M": avg_l("momentum"), "H": avg_l("hoch"), "U": avg_l("umkehr"), "N": avg_l("neg_kauf")}
    ereignis = [avg_l("zahlen")] if p["PEAD_AKTIV"] else []
    if p["INSIDER_TRIGGER"]:
        ereignis.append(avg_l(f"insider{p['INSIDER_MIN_AUFFAELLIG']}"))
    prio["E"] = max(ereignis) if ereignis else 0.0
    p["TRIGGER_PRIO"] = {k: round(float(v), 5) for k, v in prio.items()}
    if not any(p.get(k) for k in ("PEAD_AKTIV", "INSIDER_TRIGGER", "MOMENTUM_TRIGGER", "HOCH_TRIGGER", "UMKEHR_TRIGGER", "NEG_KAUF_TRIGGER")):
        gedanken.append("Kein Auslöser ist belegt. Der Radar kauft deshalb keine Einzelaktien und bleibt im ETF, "
                        "bis sich das ändert – lieber Index als Zufall.")
    return p, gedanken


# ---------------------------------------------------------------------------
# Portfolio-Aufbau
# ---------------------------------------------------------------------------
def _kennz(eq, tage):
    if len(eq) < 30:
        return None
    eq = np.asarray(eq, dtype=float)
    r = np.diff(eq) / eq[:-1]
    jahre = len(eq) / 252
    cagr = (eq[-1] / eq[0]) ** (1 / jahre) - 1 if eq[0] > 0 and eq[-1] > 0 else -1.0
    dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    sharpe = float((r.mean() * 252 - 0.02) / (r.std() * math.sqrt(252))) if r.std() > 0 else 0.0
    return {"cagr": float(cagr), "maxdd": dd, "sharpe": sharpe, "ziel": float(cagr - 0.25 * abs(dd))}


def _kombis(regeln):
    """Alle Mischungen der belegten Faktor-Auslöser (Ereignis-Auslöser laufen immer mit, wenn belegt)."""
    belegt = [k for k, f in AUSLOESER.items() if regeln.get(f)]
    out = []
    for n in range(1, len(belegt) + 1):
        out += [set(c) for c in itertools.combinations(belegt, n)]
    if regeln.get("PEAD_AKTIV") or regeln.get("INSIDER_TRIGGER"):
        out.append(set())                                 # nur Ereignis-Auslöser
    return out or [set()]


def portfolio_aufbau(s, cfg, bench, grenze, basis, start):
    import lernen
    idx = s["C"].index
    g = int(idx.searchsorted(grenze))
    k = g - start
    erg = []
    score = None
    for kombi in _kombis(basis):
        flags = {f: (key in kombi) for key, f in AUSLOESER.items()}
        kname = " + ".join(AUSLOESER_NAME[x] for x in sorted(kombi)) or "nur Ereignisse"
        for (xn, xp), (an, ap) in itertools.product(AUSSTIEG, AUFBAU):
            par = lernen.parameter(cfg, {**basis, **flags, **xp, **ap})
            if score is None:
                score = engine.kombiniere(s, par)
            dep = engine.neues_depot()
            for d in range(start, len(idx)):
                engine.tag_verarbeiten(dep, s, d, par, "Test", {}, bench, score=score)
            eq = [z[1] for z in dep["kurve"]]
            gz = [t for t in dep["trades"] if t["status"] == "geschlossen"]
            lern_t = [t["ergebnis"] for t in gz if t["signal_datum"] < grenze.date().isoformat()]
            test_t = [t["ergebnis"] for t in gz if t["signal_datum"] >= grenze.date().isoformat()]
            q = lambda x: float(np.mean([v > 0 for v in x])) if x else None
            gv = lambda x: (float(np.mean([v for v in x if v > 0])) if any(v > 0 for v in x) else None,
                            float(np.mean([v for v in x if v <= 0])) if any(v <= 0 for v in x) else None)
            erg.append({"name": f"{kname} · {xn} · {an}", "auslöser": kname, "ausstieg": xn, "aufbau": an,
                        "parameter": {**flags, **xp, **ap}, "lern": _kennz(eq[:k + 1], k), "test": _kennz(eq[k:], len(eq) - k),
                        "trades": len(gz), "quote": q([t["ergebnis"] for t in gz]), "quote_lern": q(lern_t), "quote_test": q(test_t),
                        "gv_lern": gv(lern_t), "gv_test": gv(test_t)})
    b = bench.iloc[start:].to_numpy() if bench is not None else None
    ref = {"lern": _kennz(b[:k + 1], 0), "test": _kennz(b[k:], 0)} if b is not None else None
    return erg, ref


def waehle(varianten, cfg, ref):
    """Auswahl NUR nach dem Lernteil. Profil „ruhig“: Trefferquote ≥ Mindestwert und Rückgang kleiner als beim Index,
    dann die höchste Rendite. Sonst: Rendite minus ¼ des größten Rückgangs."""
    gueltig = [v for v in varianten if v["lern"] and v["quote_lern"] is not None]
    if not gueltig:
        return None, "keine gültige Variante"
    if getattr(cfg, "PROFIL", "") == "ruhig":
        dd_index = ref["lern"]["maxdd"] if ref and ref.get("lern") else -1
        passend = [v for v in gueltig if v["quote_lern"] >= getattr(cfg, "PROFIL_MIN_TREFFER", 0.55)
                   and v["lern"]["maxdd"] > dd_index]
        if passend:
            return max(passend, key=lambda v: v["lern"]["cagr"] - 0.25 * abs(v["lern"]["maxdd"])), \
                f"Profil „ruhig“: {len(passend)} Varianten mit mind. {getattr(cfg, 'PROFIL_MIN_TREFFER', 0.55) * 100:.0f} % Treffern und kleinerem Rückgang als der Index"
        passend = [v for v in gueltig if v["quote_lern"] >= getattr(cfg, "PROFIL_MIN_TREFFER", 0.55)]
        if passend:
            return max(passend, key=lambda v: v["lern"]["cagr"] - 0.5 * abs(v["lern"]["maxdd"])), \
                "Profil „ruhig“: Keine Variante hatte einen kleineren Rückgang als der Index – gewählt nach Treffern und Rückgang"
    return max(gueltig, key=lambda v: v["lern"]["ziel"]), "nach Rendite und Rückgang"


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------
def faellig(dep, idx, tage=5):
    f = dep.get("forschung") or {}
    if f.get("version") != engine.VERSION or not f.get("datum"):
        return True
    return int((idx > pd.Timestamp(f["datum"])).sum()) >= tage


def forschen(dep, s, ins, cfg, bench, grenze):
    """Führt Ereignisstudie und Portfolio-Test aus und schreibt das Ergebnis nach dep['forschung']."""
    t0 = time.time()
    idx = s["C"].index
    grenze = pd.Timestamp(grenze)
    start = 300
    if idx.searchsorted(grenze) - start < 250:
        dep["forschung"] = {"version": engine.VERSION, "datum": idx[-1].date().isoformat(), "fehler": "Zu wenig Historie für die Forschung.",
                            "parameter": {}}
        return "Forschung: zu wenig Historie."
    print("  Ereignisstudie ...")
    studie = ereignisstudie(s, ins, cfg, bench, grenze)
    regeln, gedanken = signal_regeln(studie)
    print("  Portfolio-Varianten ...")
    varianten, ref = portfolio_aufbau(s, cfg, bench, grenze, regeln, start)
    aktiv = any(regeln.get(k) for k in ("PEAD_AKTIV", "INSIDER_TRIGGER", "MOMENTUM_TRIGGER", "HOCH_TRIGGER", "UMKEHR_TRIGGER", "NEG_KAUF_TRIGGER"))
    bester, wie = waehle(varianten, cfg, ref) if aktiv else (None, "")
    parameter = dict(regeln)
    if bester:
        parameter.update(bester["parameter"])
        gl = bester["gv_lern"]
        gedanken.append(f"Gewählt ({wie}): „{bester['name']}“ – im Lernteil {_pz(bester['lern']['cagr'])} pro Jahr, "
                        f"größter Rückgang {_pz(bester['lern']['maxdd'], 0)}, {bester['quote_lern'] * 100:.0f} % Gewinner-Trades"
                        + (f", Ø Gewinn {_pz(gl[0])} / Ø Verlust {_pz(gl[1])}" if gl[0] is not None and gl[1] is not None else "") + ".")
        if bester["test"] and ref and ref["test"]:
            besser = bester["test"]["cagr"] > ref["test"]["cagr"]
            gedanken.append(f"Im Testteil (Daten, die bei der Wahl unbekannt waren): {_pz(bester['test']['cagr'])} pro Jahr, "
                            f"größter Rückgang {_pz(bester['test']['maxdd'], 0)} – S&P 500: {_pz(ref['test']['cagr'])} pro Jahr, "
                            f"größter Rückgang {_pz(ref['test']['maxdd'], 0)}. "
                            + ("Der Radar war besser." if besser else "Der Radar war NICHT besser. Ehrliches Ergebnis: Ein Vorteil ist nicht nachgewiesen."))
    dep["forschung"] = {
        "version": engine.VERSION, "datum": idx[-1].date().isoformat(), "grenze": grenze.date().isoformat(),
        "von": idx[start].date().isoformat(), "bis": idx[-1].date().isoformat(), "studie": studie,
        "varianten": varianten, "bench": ref, "bester": bester["name"] if bester else None,
        "parameter": parameter, "gedanken": gedanken, "dauer_s": round(time.time() - t0, 1),
    }
    return f"Forschung: {len(studie)} Signale und {len(varianten)} Portfolio-Varianten geprüft ({dep['forschung']['dauer_s']} s)."


def bericht(f, s=None, bench=None):
    """Kurzer Text-Bericht fürs Protokoll (nur Statistik über Signale – keine Positionen, keine Empfehlungen)."""
    z = []
    if f.get("fehler"):
        return f["fehler"]
    z.append(f"FORSCHUNG {f['von']} – {f['bis']} · Lernteil bis {f['grenze']}")
    fm = lambda st: "      –      " if not st or st.get("avg") is None else f"{st['avg'] * 100:+6.2f}% t{(st['t'] or 0):+5.1f} n{st['n']:<5d}"
    z.append(f"{'Signal':48s} | {'20T Lern':22s} | {'20T Test':22s} | {'60T Lern':22s} | {'60T Test':22s} | {'vsSPY20 Test':22s} | Urteil")
    for e in f["studie"]:
        z.append(f"{e['name'][:48]:48s} | {fm(e['h20']['lern'])} | {fm(e['h20']['test'])} | {fm(e['h60']['lern'])} | "
                 f"{fm(e['h60']['test'])} | {fm(e['h20']['spy_test'])} | {e['urteil']['stufe']}")
        z.append(" " * 50 + "Jahre 20T: " + " ".join(f"{j}:{v * 100:+.1f}" for j, v in e["jahre"].items()))
    z.append("PORTFOLIO (CAGR / maxDD / Sharpe)")
    k = lambda v: "–" if not v else f"{v['cagr'] * 100:+6.1f}% {v['maxdd'] * 100:6.1f}% {v['sharpe']:+.2f}"
    if f.get("bench"):
        z.append(f"{'S&P 500':60s} Lern {k(f['bench']['lern'])} | Test {k(f['bench']['test'])}")
    pz = lambda x: "  – " if x is None else f"{x * 100:+.1f}"
    for v in sorted(f["varianten"], key=lambda v: -(v["lern"] or {}).get("ziel", -9)):
        gl, gt = v.get("gv_lern") or (None, None), v.get("gv_test") or (None, None)
        z.append(f"{v['name'][:78]:78s} Lern {k(v['lern'])} T{(v.get('quote_lern') or 0) * 100:3.0f}% G{pz(gl[0])}/V{pz(gl[1])} | "
                 f"Test {k(v['test'])} T{(v.get('quote_test') or 0) * 100:3.0f}% G{pz(gt[0])}/V{pz(gt[1])} | n{v['trades']}"
                 + ("  <== gewählt" if v["name"] == f.get("bester") else ""))
    if s is not None:
        C, elig = s["C"], s["elig"].fillna(False)
        r = (C / C.shift(1) - 1).where(elig & elig.shift(1, fill_value=False)).clip(-0.5, 1.0)
        gl = (1 + r.mean(axis=1).fillna(0)).cumprod()
        g = pd.Timestamp(f["grenze"])
        for name, a, b in (("Lernteil", pd.Timestamp(f["von"]), g), ("Testteil", g, C.index[-1])):
            x = gl[(gl.index >= a) & (gl.index <= b)]
            y = bench[(bench.index >= a) & (bench.index <= b)] if bench is not None else None
            jahre = len(x) / 252
            z.append(f"Alle Aktien gleichgewichtet {name}: {((x.iloc[-1] / x.iloc[0]) ** (1 / jahre) - 1) * 100:+.1f}% p.a."
                     + (f" · S&P 500 {((y.iloc[-1] / y.iloc[0]) ** (1 / jahre) - 1) * 100:+.1f}% p.a." if y is not None and len(y) else ""))
    z.append("PARAMETER " + ", ".join(f"{a}={b}" for a, b in f["parameter"].items()))
    z += ["- " + g for g in f["gedanken"]]
    return "\n".join(z)
