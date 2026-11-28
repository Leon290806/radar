# -*- coding: utf-8 -*-
"""
Auswahl der „Smart Money“-Trader – bewusst NICHT die Rangliste nach Gewinn, sondern nach Beständigkeit:
lange Historie, Gewinn in den meisten Monaten, kein einzelner Glückstreffer, begrenzter Rückgang,
Haltedauer lang genug zum Kopieren, kein Hochfrequenz-Handel.
"""
import math
import time
from collections import defaultdict

import einstellungen as E
import hl

TAG_MS = 86_400_000


def _fenster(row):
    return {k: v for k, v in row.get("windowPerformances", [])}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def vorauswahl(rows):
    """Billiger Filter auf der Rangliste (alle ~47.000 Konten) -> ~80 Kandidaten für die genaue Prüfung."""
    gut = []
    for r in rows:
        av = _f(r.get("accountValue"))
        if av < E.MIN_KONTO_USD:
            continue
        w = _fenster(r)
        at, mo = w.get("allTime") or {}, w.get("month") or {}
        pnl_at, pnl_mo, vlm_mo, roi_at = _f(at.get("pnl")), _f(mo.get("pnl")), _f(mo.get("vlm")), _f(at.get("roi"))
        if pnl_at <= 0 or pnl_mo <= 0:
            continue
        if vlm_mo < av * E.MIN_AKTIVITAET or vlm_mo > av * E.MAX_UMSCHLAG_MONAT:
            continue
        gut.append({"adresse": r["ethAddress"], "name": r.get("displayName"), "konto": av, "pnl_gesamt": pnl_at,
                    "roi_gesamt": roi_at, "pnl_monat": pnl_mo, "roi_monat": _f(mo.get("roi")), "umsatz_monat": vlm_mo,
                    "pnl_woche": _f((w.get("week") or {}).get("pnl"))})
    nach_pnl = sorted(gut, key=lambda k: -k["pnl_gesamt"])[:E.KANDIDATEN_PNL]
    nach_roi = sorted((k for k in gut if k["konto"] >= 200_000 and k["roi_gesamt"] < 50), key=lambda k: -k["roi_gesamt"])[:E.KANDIDATEN_ROI]
    seen, out = set(), []
    for k in nach_pnl + nach_roi:
        if k["adresse"] not in seen:
            seen.add(k["adresse"])
            out.append(k)
    return out, len(gut)


def _kurve(portfolio):
    d = {name: werte for name, werte in portfolio}
    p = d.get("perpAllTime") or d.get("allTime") or {}
    pnl = [(int(t), _f(v)) for t, v in p.get("pnlHistory", [])]
    av = [(int(t), _f(v)) for t, v in p.get("accountValueHistory", [])]
    return pnl, av


def kurven_kennzahlen(pnl, av):
    """Rückgang und Monats-Beständigkeit aus zeitgewichteten Renditen (Ein- und Auszahlungen verfälschen so nichts):
    Rendite je Intervall = Gewinnänderung / Kontowert zu Beginn des Intervalls."""
    if len(pnl) < 3:
        return None
    tage = (pnl[-1][0] - pnl[0][0]) / TAG_MS
    av_map = dict(av)
    index, punkte, letzter_av = 1.0, [(pnl[0][0], 1.0)], av_map.get(pnl[0][0], 0.0)
    for (t0, p0), (t1, p1) in zip(pnl, pnl[1:]):
        basis = letzter_av if letzter_av and letzter_av > 1000 else None
        if basis:
            r = max(-0.95, min((p1 - p0) / basis, 5.0))
            index *= 1 + r
        punkte.append((t1, index))
        letzter_av = av_map.get(t1, letzter_av)
    hoch, dd = punkte[0][1], 0.0
    for _, x in punkte:
        hoch = max(hoch, x)
        dd = max(dd, 1 - x / hoch if hoch > 0 else 0)
    start, ende = punkte[0][0], punkte[-1][0]
    bloecke, pos, t0 = 0, 0, start
    while t0 + 30 * TAG_MS <= ende + TAG_MS:
        t1 = t0 + 30 * TAG_MS
        a = [x for t, x in punkte if t <= t0]
        b = [x for t, x in punkte if t <= t1]
        if a and b:
            bloecke += 1
            pos += b[-1] > a[-1]
        t0 = t1
    return {"tage": round(tage), "drawdown": round(dd, 3), "monate": bloecke, "monate_pos": round(pos / bloecke, 2) if bloecke else None,
            "index": round(index, 3)}


def trade_kennzahlen(fl):
    """Aus den Fills der letzten 30 Tage: Anzahl Schließungen, Trefferquote, Glückstreffer-Anteil, Haltedauer."""
    if not fl:
        return {"fills": 0, "schliessungen": 0}
    fl = sorted(fl, key=lambda f: f["time"])
    je_order = defaultdict(float)
    pos, offen_seit, halte = defaultdict(float), {}, []
    for f in fl:
        coin, sz = f["coin"], _f(f["sz"])
        start = _f(f.get("startPosition"))
        signiert = sz if f.get("side") == "B" else -sz
        neu = start + signiert
        if abs(start) < 1e-12 and abs(neu) > 1e-12:
            offen_seit[coin] = f["time"]
        if abs(start) > 1e-12 and (abs(neu) < 1e-9 * max(1, abs(start)) or start * neu < 0):
            if coin in offen_seit:
                halte.append((f["time"] - offen_seit.pop(coin)) / 3_600_000)
            if start * neu < 0:
                offen_seit[coin] = f["time"]
        pos[coin] = neu
        cp = _f(f.get("closedPnl"))
        if cp:
            je_order[(coin, f.get("oid"))] += cp
    werte = list(je_order.values())
    gewinne = [w for w in werte if w > 0]
    return {"fills": len(fl), "schliessungen": len(werte),
            "trefferquote": round(len(gewinne) / len(werte), 2) if werte else None,
            "top_anteil": round(max(gewinne) / sum(gewinne), 2) if gewinne else None,
            "pnl_30t": round(sum(werte), 2),
            "haltedauer_std": round(sorted(halte)[len(halte) // 2], 1) if halte else None,
            "runden": len(halte)}


def bewerten(k):
    """Gesamtnote 0–100 aus Beständigkeit, Rendite und Rückgang (nur für Trader, die alle Filter bestehen)."""
    mp = k.get("monate_pos") or 0
    roi = max(0.0, min(k.get("roi_gesamt") or 0, 5.0))
    dd = k.get("drawdown") or 0
    tq = k.get("trefferquote") or 0.5
    roh = mp * (0.5 + 0.5 * roi / 5) * (1 - dd) * (0.6 + 0.4 * tq) * math.log10(max(k.get("pnl_gesamt", 1), 10))
    return roh


def pruefen(k):
    gruende = []
    if (k.get("tage") or 0) < E.MIN_TAGE_HISTORIE:
        gruende.append(f"Historie nur {k.get('tage')} Tage")
    if (k.get("monate_pos") or 0) < E.MIN_MONATE_POSITIV:
        gruende.append("zu wenige Gewinnmonate")
    if (k.get("drawdown") or 0) > E.MAX_DRAWDOWN:
        gruende.append(f"Rückgang {round((k.get('drawdown') or 0) * 100)} %")
    if (k.get("schliessungen") or 0) < E.MIN_SCHLIESSUNGEN_30T:
        gruende.append("zu wenige Trades")
    if k.get("haltedauer_std") is not None and k["haltedauer_std"] < E.MIN_HALTEDAUER_STD:
        gruende.append("Scalping (Haltedauer zu kurz)")
    if (k.get("fills") or 0) >= 2000 and (k.get("haltedauer_std") is None or k["haltedauer_std"] < E.MIN_HALTEDAUER_STD):
        gruende.append("Hochfrequenz")
    if k.get("top_anteil") is not None and k["top_anteil"] > E.MAX_TOP_ANTEIL:
        gruende.append("Gewinn hängt an einem Trade")
    return gruende


def auswaehlen(protokoll):
    t0 = time.time()
    rows = hl.leaderboard()
    kand, n_gut = vorauswahl(rows)
    seit = int((time.time() - 30 * 86400) * 1000)
    geprueft = []
    for k in kand:
        try:
            pnl, av = _kurve(hl.portfolio(k["adresse"]))
            kz = kurven_kennzahlen(pnl, av) or {}
            tk = trade_kennzahlen(hl.fills(k["adresse"], seit))
        except Exception as ex:  # einzelner Fehler darf die Auswahl nicht stoppen
            protokoll.append(f"Auswahl: {k['adresse'][:10]} übersprungen ({type(ex).__name__})")
            continue
        k.update(kz)
        k.update(tk)
        k["gruende"] = pruefen(k)
        k["note_roh"] = bewerten(k) if not k["gruende"] else 0
        geprueft.append(k)
    from collections import Counter
    print("Ablehnungsgründe:", dict(Counter(g.split(" ")[0] if g.startswith(("Historie", "Rückgang")) else g for k in geprueft for g in k["gruende"])))
    for k in geprueft[:25]:
        print(f"  {k['adresse'][:8]} tage={k.get('tage')} mon={k.get('monate')}/{k.get('monate_pos')} dd={k.get('drawdown')} "
              f"schl={k.get('schliessungen')} fills={k.get('fills')} halt={k.get('haltedauer_std')} top={k.get('top_anteil')} -> {k['gruende']}")
    gut = sorted((k for k in geprueft if not k["gruende"]), key=lambda k: -k["note_roh"])
    top = max((k["note_roh"] for k in gut), default=1) or 1
    for k in geprueft:
        k["note"] = round(100 * k["note_roh"] / top) if k["note_roh"] else 0
    auswahl = gut[:E.MAX_TRADER]
    info = {"zeit": int(time.time() * 1000), "konten": len(rows), "vorfilter": n_gut, "geprueft": len(geprueft),
            "bestanden": len(gut), "ausgewaehlt": len(auswahl), "dauer_s": round(time.time() - t0)}
    abgelehnt = sorted((k for k in geprueft if k["gruende"]), key=lambda k: -k["pnl_gesamt"])[:40]
    return auswahl, abgelehnt, info
