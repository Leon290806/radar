# -*- coding: utf-8 -*-
"""Professionelle Kennzahlen (ähnlich TradingView-Strategietester) für Radar und Vergleichsindizes."""
import numpy as np
import pandas as pd

JAHR = 252


def _f(x):
    x = float(x)
    return x if np.isfinite(x) else None


def reihe_kennzahlen(eq, rf=0.02):
    """Kennzahlen einer Wertreihe (pd.Series mit Datumsindex)."""
    eq = eq.dropna()
    if len(eq) < 20:
        return {}
    r = eq.pct_change().dropna()
    jahre = len(r) / JAHR
    gesamt = eq.iloc[-1] / eq.iloc[0] - 1
    cagr = (1 + gesamt) ** (1 / jahre) - 1 if jahre > 0 else np.nan
    vola = r.std() * np.sqrt(JAHR)
    rf_d = (1 + rf) ** (1 / JAHR) - 1
    ex = r - rf_d
    sharpe = ex.mean() / r.std() * np.sqrt(JAHR) if r.std() > 0 else np.nan
    unten = r[r < 0]
    dd_std = np.sqrt((np.minimum(r, 0) ** 2).mean()) * np.sqrt(JAHR)
    sortino = (r.mean() * JAHR - rf) / dd_std if dd_std > 0 else np.nan
    dd = eq / eq.cummax() - 1
    maxdd = dd.min()
    # längste Phase unter Höchststand (Handelstage)
    unter, laengste = 0, 0
    for v in dd.values:
        unter = unter + 1 if v < -1e-9 else 0
        laengste = max(laengste, unter)
    gew, verl = r[r > 0].sum(), -r[r < 0].sum()
    omega = gew / verl if verl > 0 else np.nan
    calmar = cagr / abs(maxdd) if maxdd < 0 else np.nan
    ulcer = np.sqrt((dd ** 2).mean())
    m = (1 + r).groupby([r.index.year, r.index.month]).prod() - 1
    return {
        "gesamt": _f(gesamt), "cagr": _f(cagr), "vola": _f(vola), "sharpe": _f(sharpe), "sortino": _f(sortino),
        "calmar": _f(calmar), "omega": _f(omega), "maxdd": _f(maxdd), "dd_dauer": int(laengste), "ulcer": _f(ulcer),
        "bester_tag": _f(r.max()), "schlechtester_tag": _f(r.min()), "pos_tage": _f((r > 0).mean()),
        "pos_monate": _f((m > 0).mean()) if len(m) else None, "bester_monat": _f(m.max()) if len(m) else None,
        "schlechtester_monat": _f(m.min()) if len(m) else None, "schiefe": _f(r.skew()), "tage": int(len(r)),
    }


def relativ(eq, bench):
    """Alpha, Beta usw. gegenüber einem Vergleichsindex."""
    df = pd.concat([eq.pct_change(), bench.pct_change()], axis=1).dropna()
    if len(df) < 30:
        return {}
    a, b = df.iloc[:, 0], df.iloc[:, 1]
    beta = a.cov(b) / b.var() if b.var() > 0 else np.nan
    alpha = (a.mean() - beta * b.mean()) * JAHR
    te = (a - b).std() * np.sqrt(JAHR)
    ir = (a - b).mean() * JAHR / te if te > 0 else np.nan
    hoch, runter = b > 0, b < 0
    up = a[hoch].mean() / b[hoch].mean() if hoch.any() and b[hoch].mean() != 0 else np.nan
    down = a[runter].mean() / b[runter].mean() if runter.any() and b[runter].mean() != 0 else np.nan
    return {"alpha": _f(alpha), "beta": _f(beta), "korrelation": _f(a.corr(b)), "tracking_error": _f(te),
            "info_ratio": _f(ir), "up_capture": _f(up), "down_capture": _f(down)}


def trade_kennzahlen(trades, kosten=0.001):
    gz = [t for t in trades if t["status"] == "geschlossen"]
    if not gz:
        return {"anzahl": 0}
    erg = np.array([t["ergebnis"] for t in gz])
    pnl = np.array([t["stueck"] * (t["ausstieg_kurs"] * (1 - kosten) - t["einstieg_kurs"] * (1 + kosten)) for t in gz])
    tage = np.array([np.busday_count(t["einstieg_datum"], t["ausstieg_datum"]) for t in gz])
    gew, verl = pnl[pnl > 0], pnl[pnl <= 0]
    folge_g = folge_v = best_g = best_v = 0
    for x in sorted(gz, key=lambda t: t["ausstieg_datum"]):
        if x["ergebnis"] > 0:
            folge_g, folge_v = folge_g + 1, 0
        else:
            folge_v, folge_g = folge_v + 1, 0
        best_g, best_v = max(best_g, folge_g), max(best_v, folge_v)
    ueber = [t["ueber_markt"] for t in gz if t.get("ueber_markt") is not None]
    return {
        "anzahl": len(gz), "gewinner": int((erg > 0).sum()), "verlierer": int((erg <= 0).sum()),
        "trefferquote": _f((erg > 0).mean()), "profit_factor": _f(gew.sum() / -verl.sum()) if verl.sum() < 0 else None,
        "netto_pnl": _f(pnl.sum()), "brutto_gewinn": _f(gew.sum()), "brutto_verlust": _f(verl.sum()),
        "erwartung": _f(erg.mean()), "erwartung_pnl": _f(pnl.mean()),
        "avg_gewinn": _f(erg[erg > 0].mean()) if (erg > 0).any() else None,
        "avg_verlust": _f(erg[erg <= 0].mean()) if (erg <= 0).any() else None,
        "payoff": _f(erg[erg > 0].mean() / -erg[erg <= 0].mean()) if (erg > 0).any() and (erg <= 0).any() and erg[erg <= 0].mean() < 0 else None,
        "groesster_gewinn": _f(erg.max()), "groesster_verlust": _f(erg.min()),
        "serie_gewinn": best_g, "serie_verlust": best_v, "haltedauer": _f(tage.mean()),
        "haltedauer_gewinner": _f(tage[erg > 0].mean()) if (erg > 0).any() else None,
        "haltedauer_verlierer": _f(tage[erg <= 0].mean()) if (erg <= 0).any() else None,
        "ueber_markt": _f(np.mean(ueber)) if ueber else None,
        "schlag_markt": _f(np.mean([u > 0 for u in ueber])) if ueber else None,
        "verteilung": [round(float(x), 4) for x in erg],
        "ausstiege": pd.Series([t["ausstieg_grund"].split(" (")[0] for t in gz]).value_counts().to_dict(),
    }


def monatstabelle(eq):
    r = eq.pct_change().dropna()
    if r.empty:
        return []
    m = (1 + r).groupby([r.index.year, r.index.month]).prod() - 1
    j = (1 + r).groupby(r.index.year).prod() - 1
    out = []
    for jahr in sorted(set(r.index.year)):
        out.append({"jahr": int(jahr), "monate": [_f(m.get((jahr, k))) if (jahr, k) in m.index else None for k in range(1, 13)],
                    "jahr_r": _f(j.get(jahr))})
    return out
