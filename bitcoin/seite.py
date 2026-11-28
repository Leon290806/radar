# -*- coding: utf-8 -*-
"""Bereitet die Analyse für das Dashboard auf (Zeitreihen ausgedünnt: wöchentlich, letzte 3 Jahre täglich)."""
import json
import math
import os

import numpy as np
import pandas as pd

import einstellungen as E
import analyse as AN


def _z(x, nk=4):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else round(x, nk)


def _ausduennen(idx):
    grenze = idx[-1] - pd.Timedelta(days=3 * 365)
    alt = [d for d in idx if d < grenze][::7]
    return alt + [d for d in idx if d >= grenze]


def zyklen(df):
    hv = pd.to_datetime(E.HALVINGS)
    out = []
    for i in range(len(hv) - 1):
        a, b = hv[i], hv[i + 1]
        teil = df["preis"].loc[a:b - pd.Timedelta(days=1)]
        if len(teil) < 30:
            continue
        p0 = teil.iloc[0]
        tage = (teil.index - a).days
        punkte = [[int(t), _z(v / p0, 4)] for t, v in zip(tage[::3], teil.values[::3])]
        bull = teil.loc[:a + pd.Timedelta(days=800)]       # Zyklus-Hoch: in den ersten ~2 Jahren nach dem Halving
        hoch_d = bull.idxmax()
        nach = teil.loc[hoch_d:]
        tief_d = nach.idxmin()
        out.append({"halving": str(a.date()), "start_preis": _z(p0, 2), "punkte": punkte, "fertig": bool(b <= df.index[-1]),
                    "hoch_tag": int((hoch_d - a).days), "hoch_preis": _z(bull.max(), 2), "hoch_faktor": _z(bull.max() / p0, 2),
                    "tief_tag": int((tief_d - a).days), "tief_preis": _z(nach.min(), 2), "rueckgang": _z(nach.min() / bull.max() - 1, 3)})
    return out


def daten(A, bg, stand, protokoll):
    df, P, score = A["df"], A["P"], A["score"]
    heute = df.index[-1]
    jahr = max(A["gewichte"])
    W = A["gewichte"][jahr]
    zeit = _ausduennen(df.index)
    sth = pd.Series(bg.get("sth-realized-price", {}), dtype=float)
    lth = pd.Series(bg.get("lth-realized-price", {}), dtype=float)
    sopr = pd.Series(bg.get("sopr", {}), dtype=float)
    sthm = pd.Series(bg.get("sth-mvrv", {}), dtype=float)
    for s in (sth, lth, sopr, sthm):
        s.index = pd.to_datetime(s.index)
    def reihe(s, nk=4):
        return [_z(s.get(d), nk) for d in zeit]
    S = {"t": [d.strftime("%Y-%m-%d") for d in zeit], "preis": reihe(df["preis"], 2), "pl_fair": reihe(df["pl_fair"], 2),
         "pl_unten": reihe(df["pl_unten"], 2), "pl_oben": reihe(df["pl_oben"], 2), "realized": reihe(df["realized"], 2),
         "ma200w": reihe(df["ma200w"], 2), "mvrv_z": reihe(df["mvrv_z"], 3), "nupl": reihe(df["nupl"], 3), "puell": reihe(df["puell"], 3),
         "mayer": reihe(df["mayer"], 3), "fng": reihe(df["fng"], 0), "score": reihe(score, 1), "hash_ribbon": reihe(df["hash_ribbon"], 4),
         "sth": reihe(sth, 2), "lth": reihe(lth, 2), "sopr": reihe(sopr.rolling(7, min_periods=1).mean(), 4), "sth_mvrv": reihe(sthm, 3),
         "pi": reihe(df["pi"], 3)}
    letzte = df.iloc[-1]
    indikatoren = []
    for k, (name, erkl, _) in AN.MERKMALE.items():
        p = P[k].iloc[-1]
        indikatoren.append({"k": k, "name": name, "erkl": erkl, "wert": _z(letzte[k], 4), "perzentil": _z(p, 3), "gewicht": W.get(k, 0),
                            "beitrag": _z(W.get(k, 0) * (0.5 - p), 4) if pd.notna(p) else None})
    sc = score.dropna()
    vor = {n: _z(sc.iloc[-1 - n], 1) if len(sc) > n else None for n in (7, 30, 90, 365)}
    bt, sp = A["backtest"], A["sparplan"]
    bt_t = bt["strategie"].index[::7]
    hv = pd.to_datetime(E.HALVINGS)
    naechstes = next((h for h in hv if h > heute), None)
    zonen_verlauf = []
    z = score.map(AN.zone)
    akt, seit = None, None
    for d, v in z.dropna().items():
        if v != akt:
            if akt:
                zonen_verlauf.append({"zone": akt, "von": str(seit.date()), "bis": str(d.date())})
            akt, seit = v, d
    if akt:
        zonen_verlauf.append({"zone": akt, "von": str(seit.date()), "bis": None})
    return {
        "stand": stand, "datum": str(heute.date()), "preis": _z(letzte["preis"], 2), "score": _z(score.iloc[-1], 1), "zone": AN.zone(score.iloc[-1]),
        "score_vor": vor, "zonen": A["zonen"], "zonen_def": E.ZONEN, "zonen_verlauf": zonen_verlauf,
        "indikatoren": indikatoren, "gewichte": {str(j): w for j, w in A["gewichte"].items()}, "merkmale": {k: v[0] for k, v in AN.MERKMALE.items()},
        "pl": {k: _z(v, 5) for k, v in A["pl"].items()} | {"fair": _z(letzte["pl_fair"], 2), "unten": _z(letzte["pl_unten"], 2), "oben": _z(letzte["pl_oben"], 2),
                                                          "fair_1j": _z(10 ** (A["pl"]["a"] + A["pl"]["b"] * np.log10((heute + pd.Timedelta(days=365) - pd.Timestamp(E.GENESIS)).days)), 2)},
        "kennzahlen": {k: _z(letzte[k], 4) for k in ("mvrv", "mvrv_z", "nupl", "puell", "mayer", "ma200w", "ma200w_ratio", "realized", "ath", "ath_ratio",
                                                     "pi", "hash_ribbon", "fng", "zyklus_tag", "ma200")}
        | {"sth": _z(sth.iloc[-1], 2) if len(sth) else None, "lth": _z(lth.iloc[-1], 2) if len(lth) else None,
           "sopr": _z(sopr.tail(7).mean(), 4) if len(sopr) else None, "sth_mvrv": _z(sthm.iloc[-1], 3) if len(sthm) else None,
           "bg_datum": str(sth.index[-1].date()) if len(sth) else None},
        "zyklus": {"tag": int(letzte["zyklus_tag"]), "halving": str(hv[int(letzte["zyklus_nr"])].date()), "naechstes": str(naechstes.date()) if naechstes is not None else None,
                   "tage_bis": int((naechstes - heute).days) if naechstes is not None else None, "zyklen": zyklen(df)},
        "serien": S,
        "backtest": {"t": [d.strftime("%Y-%m-%d") for d in bt_t], "strategie": [_z(bt["strategie"][d], 3) for d in bt_t], "halten": [_z(bt["halten"][d], 3) for d in bt_t],
                     "kz_strategie": bt["kz_strategie"], "kz_halten": bt["kz_halten"], "wechsel": bt["wechsel"], "start": bt["start"]},
        "sparplan": {"normal": {k: _z(v, 2) for k, v in sp["normal"].items()}, "smart": {k: _z(v, 2) for k, v in sp["smart"].items()}, "start": sp["start"],
                     "t": [v[0].strftime("%Y-%m-%d") for v in sp["verlauf"][::2]], "n_wert": [_z(v[1], 0) for v in sp["verlauf"][::2]],
                     "n_geld": [_z(v[2], 0) for v in sp["verlauf"][::2]], "s_wert": [_z(v[3], 0) for v in sp["verlauf"][::2]], "s_geld": [_z(v[4], 0) for v in sp["verlauf"][::2]]},
        "regeln": {"anteil": E.ANTEIL_JE_ZONE, "sparplan": E.SPARPLAN_FAKTOR, "max_gewicht": E.MAX_GEWICHT, "gebuehr": E.GEBUEHR, "lern_start": bt["start"], "horizont": E.HORIZONT},
        "protokoll": protokoll[:30],
    }


def erstelle(D):
    js = json.dumps(D, ensure_ascii=False, separators=(",", ":"), allow_nan=False, default=str).replace("</", "<\\/")
    lies = lambda *t: open(os.path.join(*t), encoding="utf-8").read()  # noqa: E731
    css = lies(E.REPO_WURZEL, "app.css") + "\n" + lies(E.BASIS, "web", "bitcoin.css")
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex"><meta name="color-scheme" content="light dark">
<title>Bitcoin-Radar</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400..800&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body><main></main>
<script type="application/json" id="daten">{js}</script>
<script>{lies(E.REPO_WURZEL, "menue.js")}</script>
<script>{lies(E.BASIS, "web", "bitcoin.js")}</script>
</body></html>"""
