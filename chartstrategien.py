# -*- coding: utf-8 -*-
"""
Chart-Strategien für Krypto – nachgebaut nach den Regel-Beschreibungen (PDFs) und den Indikator-Einstellungen,
denn LSOB und GUSS sind auf TradingView „Protected Source“ (Code nicht einsehbar). Eigene Umsetzung, nur zum Prüfen.

  LSOB      Liquidity Sweep Orderblock: Hoch über einem früheren Pivot-Hoch (Sweep), danach 2 Gegenkerzen →
            Orderblock = Sweep-Kerze. Short, wenn der Preis zurückkommt und die Zone ablehnt (Docht rein,
            Schluss nicht zu tief drin). Ungültig bei neuem Sweep, zu tiefem Schluss oder nach 150 Kerzen. Long gespiegelt.
  Delfin    Rücklauf an die EMA21 von unten mit Docht-Berührung und Schluss darunter, nachdem vorher über der EMA
            geschlossen wurde; EMAs dürfen sich nicht gerade kreuzen; Ziel = letztes Tief, mind. 1,5 R. Long gespiegelt.
  GUSS      Neues Hoch weit über der EMA21 (Überdehnung), danach Korrektur OHNE Gegenkerze bis zur EMA50 →
            Long an der EMA50 (optional Fibonacci 0,5–0,786). Ziel EMA21 bzw. Stopp auf Einstand. Short gespiegelt.
  Ausbruch  „Old Money Stacks“: Kerzenkörper schließt überwiegend über Widerstand, Docht max. 30 % des Körpers,
            Kerze nicht riesig, Stopp unter dem Docht, Ziel 2 R. Short gespiegelt.

Daten: Binance-Archiv (Spot, 15 min ab ~2 Jahren, 1 h/4 h ab 2021) für den Backtest, Hyperliquid für die letzten Wochen.
Kosten: 0,05 % Gebühr + 0,02 % Schlupf je Seite. Risiko 1 % des Kontos je Trade (max. 5-facher Hebel).
Liquidation-Heatmaps gibt es nicht als freie Historie – dieser Teil lässt sich nicht testen.
"""
import datetime as dt
import itertools
import json
import math
import os
import time

import numpy as np
import pandas as pd
import requests

import krypto

COINS = ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "LINK", "AVAX", "ADA", "SUI"]
TIMEFRAMES = {"15m": {"quelle": "15m", "monate": 24, "ms": 900_000},
              "1h": {"quelle": "1h", "monate": 70, "ms": 3_600_000},
              "4h": {"quelle": "1h", "monate": 70, "ms": 14_400_000, "resample": "4h"}}
KOSTEN = 0.0007              # Gebühr + Schlupf je Seite
RISIKO = 0.01                # 1 % des Kontos je Trade
MAX_HEBEL = 5.0
MAX_KERZEN = 300             # Trade wird spätestens nach so vielen Kerzen geschlossen

STRATEGIEN = {
    "lsob": {"name": "LSOB · Liquidity Sweep Orderblock", "kurz": "LSOB"},
    "delfin": {"name": "Delfin · EMA21-Rücklauf", "kurz": "Delfin"},
    "guss": {"name": "GUSS · Sniper an der EMA50", "kurz": "GUSS"},
    "ausbruch": {"name": "Ausbruch · Old Money Stacks", "kurz": "Ausbruch"},
}
GRID = {
    "lsob": {"TP": [1.5, 2.0, 3.0], "TREND": [False, True]},
    "delfin": {"TP": ["swing", 2.0], "TREND": [False, True]},
    "guss": {"K": [1.5, 3.0], "EXIT": ["ema21", "be3"], "FIB": [False, True]},
    "ausbruch": {"TP": [1.5, 2.0, 3.0], "TREND": [False, True]},
}


# ---------------------------------------------------------------------------
# Daten
# ---------------------------------------------------------------------------
def _klines_monat(sym, iv, m):
    df = krypto._bv_monat(f"{krypto.BV}/spot/monthly/klines/{sym}/{iv}/{sym}-{iv}-{m}.zip", f"kl_{sym}_{iv}_{m}.pkl")
    if df is None or df.empty:
        return None
    t = pd.to_numeric(df.iloc[:, 0], errors="coerce").to_numpy()
    t = np.where(t > 1e14, t / 1000, t)
    out = pd.DataFrame({"o": pd.to_numeric(df.iloc[:, 1]), "h": pd.to_numeric(df.iloc[:, 2]),
                        "l": pd.to_numeric(df.iloc[:, 3]), "c": pd.to_numeric(df.iloc[:, 4]),
                        "v": pd.to_numeric(df.iloc[:, 5])})
    out.index = pd.to_datetime(t, unit="ms")
    return out


def lade_archiv(coin, tf):
    T = TIMEFRAMES[tf]
    jetzt = pd.Timestamp.utcnow().tz_localize(None)
    monate = pd.period_range(jetzt - pd.DateOffset(months=T["monate"]), jetzt - pd.offsets.MonthBegin(1), freq="M")
    teile = [x for x in (_klines_monat(f"{coin}USDT", T["quelle"], m) for m in monate) if x is not None]
    if not teile:
        return None
    df = pd.concat(teile).sort_index()
    df = df[~df.index.duplicated()]
    if T.get("resample"):
        df = df.resample(T["resample"]).agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna()
    return df


def lade_hl(coin, tf, n=4000):
    T = TIMEFRAMES[tf]
    ende = int(time.time() * 1000)
    roh = krypto._hl({"type": "candleSnapshot", "req": {"coin": coin, "interval": tf, "startTime": ende - n * T["ms"], "endTime": ende}}) or []
    roh = [k for k in roh if int(k["T"]) < ende]                          # nur abgeschlossene Kerzen
    if not roh:
        return None
    df = pd.DataFrame({"o": [float(k["o"]) for k in roh], "h": [float(k["h"]) for k in roh], "l": [float(k["l"]) for k in roh],
                       "c": [float(k["c"]) for k in roh], "v": [float(k["v"]) for k in roh]},
                      index=pd.to_datetime([int(k["t"]) for k in roh], unit="ms"))
    return df


# ---------------------------------------------------------------------------
# Indikatoren
# ---------------------------------------------------------------------------
def _ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def _ind(df):
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in "ohlc")
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    return {"o": o, "h": h, "l": l, "c": c, "atr": pd.Series(tr).rolling(14, min_periods=5).mean().to_numpy(),
            "e21": _ema(c, 21), "e50": _ema(c, 50), "e200": _ema(c, 200), "n": len(c), "t": df.index}


def _pivots(x, L, hoch=True):
    """Bestätigte Pivots: Rückgabe Array „bestätigt am Index i“ -> (Pivot-Index, Wert) als zwei Arrays mit NaN sonst."""
    n = len(x)
    wert = np.full(n, np.nan)
    idx = np.full(n, -1)
    roll = pd.Series(x).rolling(2 * L + 1, center=True)
    ext = (roll.max() if hoch else roll.min()).to_numpy()
    for i in range(L, n - L):
        if x[i] == ext[i]:
            wert[i + L], idx[i + L] = x[i], i
    return wert, idx


# ---------------------------------------------------------------------------
# Setups erkennen. Rückgabe: Liste von dict(i=Einstiegs-Kerze, seite=+1/-1, entry, stopp, ziel(optional), art)
# ---------------------------------------------------------------------------
def setups_lsob(D, p, L=5, inval=0.20, retest=0.10, docht=0.50, ablauf=150):
    o, h, l, c, atr, e200, n = D["o"], D["h"], D["l"], D["c"], D["atr"], D["e200"], D["n"]
    ph, _ = _pivots(h, L, True)
    pl, _ = _pivots(l, L, False)
    out = []
    letzt_h = letzt_l = np.nan
    zonen = []                                   # [seite, unten, oben, bestätigt_ab, verlassen]
    for i in range(n):
        if not np.isnan(ph[i]):
            letzt_h = ph[i]
        if not np.isnan(pl[i]):
            letzt_l = pl[i]
        a = atr[i] if np.isfinite(atr[i]) else 0
        # neue Zone: Sweep-Kerze s = i-2, danach zwei Gegenkerzen (i-1, i)
        s = i - 2
        if s > 0 and a > 0:
            if np.isfinite(letzt_h) and h[s] > letzt_h + 0.1 * a and h[s] == max(h[s - 1:i + 1]) and c[i - 1] < o[i - 1] and c[i] < o[i]:
                zonen.append([-1, l[s], h[s], i, False, s])
                letzt_h = np.nan
            if np.isfinite(letzt_l) and l[s] < letzt_l - 0.1 * a and l[s] == min(l[s - 1:i + 1]) and c[i - 1] > o[i - 1] and c[i] > o[i]:
                zonen.append([1, l[s], h[s], i, False, s])
                letzt_l = np.nan
        neu = []
        for z in zonen:
            seite, un, ob, ab, verlassen, s0 = z
            hoehe = max(ob - un, 1e-12)
            if i <= ab:
                neu.append(z)
                continue
            if i - ab > ablauf:
                continue
            if seite < 0:
                if h[i] > ob:                                 # neuer Sweep über die Zone -> ungültig
                    continue
                if c[i] > un + inval * hoehe:                 # schließt zu weit rein
                    continue
                if not verlassen:
                    z[4] = c[i] < un
                    neu.append(z)
                    continue
                if h[i] >= un - retest * hoehe:               # Retest
                    if h[i] <= un + docht * hoehe and c[i] < un and (not p.get("TREND") or c[i] < e200[i]):
                        stopp = ob + 0.1 * a
                        out.append({"i": i, "seite": -1, "entry": c[i], "stopp": stopp, "art": "LSOB Short", "zone": [un, ob], "s": s0})
                        continue
                neu.append(z)
            else:
                if l[i] < un:
                    continue
                if c[i] < ob - inval * hoehe:
                    continue
                if not verlassen:
                    z[4] = c[i] > ob
                    neu.append(z)
                    continue
                if l[i] <= ob + retest * hoehe:
                    if l[i] >= ob - docht * hoehe and c[i] > ob and (not p.get("TREND") or c[i] > e200[i]):
                        stopp = un - 0.1 * a
                        out.append({"i": i, "seite": 1, "entry": c[i], "stopp": stopp, "art": "LSOB Long", "zone": [un, ob], "s": s0})
                        continue
                neu.append(z)
        zonen = neu[-20:]
    return out


def setups_delfin(D, p, rueck=30):
    o, h, l, c, atr, e21, e50, e200, n = D["o"], D["h"], D["l"], D["c"], D["atr"], D["e21"], D["e50"], D["e200"], D["n"]
    ueber = c > e21
    kreuz = np.r_[False, np.sign(e21[1:] - e50[1:]) != np.sign(e21[:-1] - e50[:-1])]
    kreuz10 = pd.Series(kreuz).rolling(10, min_periods=1).max().to_numpy() > 0
    out = []
    for i in range(rueck, n - 1):
        a = atr[i]
        if not np.isfinite(a) or a <= 0 or kreuz10[i]:
            continue
        rng = h[i] - l[i]
        if rng <= 0:
            continue
        fenster = slice(i - rueck, i)
        # Short: vorher Schluss über EMA21, jetzt Docht-Berührung von unten, Schluss darunter, oberer Docht vorhanden
        if ueber[fenster].any() and h[i] >= e21[i] and c[i] < e21[i] and o[i] < e21[i] and (h[i] - max(o[i], c[i])) >= 0.25 * rng:
            if not p.get("TREND") or e21[i] < e50[i]:
                tief = l[i - rueck:i].min()
                stopp = h[i] + 0.1 * a
                ziel = tief if p.get("TP") == "swing" else None
                if ziel is None or (c[i] - ziel) >= 1.5 * (stopp - c[i]):
                    out.append({"i": i, "seite": -1, "entry": c[i], "stopp": stopp, "ziel": ziel, "art": "Delfin Short"})
        unter = c < e21
        if unter[fenster].any() and l[i] <= e21[i] and c[i] > e21[i] and o[i] > e21[i] and (min(o[i], c[i]) - l[i]) >= 0.25 * rng:
            if not p.get("TREND") or e21[i] > e50[i]:
                hoch = h[i - rueck:i].max()
                stopp = l[i] - 0.1 * a
                ziel = hoch if p.get("TP") == "swing" else None
                if ziel is None or (ziel - c[i]) >= 1.5 * (c[i] - stopp):
                    out.append({"i": i, "seite": 1, "entry": c[i], "stopp": stopp, "ziel": ziel, "art": "Delfin Long"})
    return out


def setups_guss(D, p, L=5, max_korrektur=25, swing=60):
    o, h, l, c, atr, e21, e50, e200, n = D["o"], D["h"], D["l"], D["c"], D["atr"], D["e21"], D["e50"], D["e200"], D["n"]
    ph, _ = _pivots(h, L, True)
    pl, _ = _pivots(l, L, False)
    out = []
    letzt_h = letzt_l = np.nan
    i = 0
    while i < n - 1:
        if not np.isnan(ph[i]):
            letzt_h = ph[i]
        if not np.isnan(pl[i]):
            letzt_l = pl[i]
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            i += 1
            continue
        # LONG: neues höheres Hoch, weit über EMA21, Trend über EMA200
        if np.isfinite(letzt_h) and h[i] > letzt_h and (h[i] - e21[i]) >= p["K"] * a and e50[i] > e200[i]:
            spitze, j = i, i + 1
            treffer = None
            while j < n and j - spitze <= max_korrektur:
                if h[j] > h[spitze] and c[j] >= o[j]:
                    spitze = j                                 # Hoch läuft weiter
                elif c[j] > o[j] and l[j] > e50[j]:
                    break                                      # bullishe Gegenkerze vor der EMA50 -> ungültig
                if l[j] <= e50[j] and j > spitze:
                    treffer = j
                    break
                j += 1
            if treffer is not None:
                j = treffer
                entry = min(o[j], e50[j]) if o[j] > e50[j] else o[j]
                tief = l[max(0, spitze - swing):spitze].min()
                fib_ok = True
                if p.get("FIB"):
                    r = (h[spitze] - entry) / max(h[spitze] - tief, 1e-12)
                    fib_ok = 0.5 <= r <= 0.786
                stopp = min(tief, entry - 1.0 * atr[j]) if np.isfinite(atr[j]) else tief
                if fib_ok and entry > stopp:
                    out.append({"i": j, "seite": 1, "entry": entry, "stopp": stopp, "art": "GUSS Long", "intrabar": True})
                letzt_h = np.nan
                i = j + 1
                continue
            letzt_h = np.nan
        # SHORT gespiegelt
        if np.isfinite(letzt_l) and l[i] < letzt_l and (e21[i] - l[i]) >= p["K"] * a and e50[i] < e200[i]:
            spitze, j = i, i + 1
            treffer = None
            while j < n and j - spitze <= max_korrektur:
                if l[j] < l[spitze] and c[j] <= o[j]:
                    spitze = j
                elif c[j] < o[j] and h[j] < e50[j]:
                    break
                if h[j] >= e50[j] and j > spitze:
                    treffer = j
                    break
                j += 1
            if treffer is not None:
                j = treffer
                entry = max(o[j], e50[j]) if o[j] < e50[j] else o[j]
                hoch = h[max(0, spitze - swing):spitze].max()
                fib_ok = True
                if p.get("FIB"):
                    r = (entry - l[spitze]) / max(hoch - l[spitze], 1e-12)
                    fib_ok = 0.5 <= r <= 0.786
                stopp = max(hoch, entry + 1.0 * atr[j]) if np.isfinite(atr[j]) else hoch
                if fib_ok and stopp > entry:
                    out.append({"i": j, "seite": -1, "entry": entry, "stopp": stopp, "art": "GUSS Short", "intrabar": True})
                letzt_l = np.nan
                i = j + 1
                continue
            letzt_l = np.nan
        i += 1
    return out


def setups_ausbruch(D, p, L=5, anzahl=3):
    o, h, l, c, atr, e200, n = D["o"], D["h"], D["l"], D["c"], D["atr"], D["e200"], D["n"]
    koerper_oben, koerper_unten = np.maximum(o, c), np.minimum(o, c)
    rh, _ = _pivots(koerper_oben, L, True)
    rl, _ = _pivots(koerper_unten, L, False)
    wid, unt = [], []
    out = []
    for i in range(n):
        if not np.isnan(rh[i]):
            wid = (wid + [rh[i]])[-anzahl:]
        if not np.isnan(rl[i]):
            unt = (unt + [rl[i]])[-anzahl:]
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        koerper = abs(c[i] - o[i])
        if koerper <= 0 or koerper > 2.5 * a:
            continue
        if c[i] > o[i]:
            for r in wid:
                if o[i] < r < c[i] and (c[i] - r) > 0.5 * koerper and (h[i] - c[i]) <= 0.3 * koerper:
                    if not p.get("TREND") or c[i] > e200[i]:
                        stopp = l[i] - 0.05 * a
                        hoeher = [x for x in wid if x > c[i]]
                        if not hoeher or min(hoeher) - c[i] >= 2 * (c[i] - stopp):
                            out.append({"i": i, "seite": 1, "entry": c[i], "stopp": stopp, "art": "Ausbruch Long"})
                            wid = [x for x in wid if x != r]
                    break
        elif c[i] < o[i]:
            for s in unt:
                if c[i] < s < o[i] and (s - c[i]) > 0.5 * koerper and (c[i] - l[i]) <= 0.3 * koerper:
                    if not p.get("TREND") or c[i] < e200[i]:
                        stopp = h[i] + 0.05 * a
                        tiefer = [x for x in unt if x < c[i]]
                        if not tiefer or c[i] - max(tiefer) >= 2 * (stopp - c[i]):
                            out.append({"i": i, "seite": -1, "entry": c[i], "stopp": stopp, "art": "Ausbruch Short"})
                            unt = [x for x in unt if x != s]
                    break
    return out


ERKENNER = {"lsob": setups_lsob, "delfin": setups_delfin, "guss": setups_guss, "ausbruch": setups_ausbruch}


# ---------------------------------------------------------------------------
# Trades simulieren
# ---------------------------------------------------------------------------
def simuliere(D, setups, p, offen=None):
    """Ein Trade gleichzeitig je Coin. Rückgabe: Liste Trades mit R und Konto-Rendite (1 % Risiko).
    offen (Liste) bekommt den noch laufenden Trade am Datenende."""
    h, l, c, e21, n, t = D["h"], D["l"], D["c"], D["e21"], D["n"], D["t"]
    trades, frei_ab = [], -1
    for s in setups:
        i = s["i"]
        if i <= frei_ab or i >= n - 1:
            continue
        seite, entry, stopp = s["seite"], float(s["entry"]), float(s["stopp"])
        risiko = (entry - stopp) * seite
        if risiko <= 0 or risiko / entry < 0.001:
            continue
        tp_art = p.get("TP", 2.0)
        exit_art = p.get("EXIT")
        if s.get("ziel") is not None:
            ziel = float(s["ziel"])
        elif exit_art == "be3":
            ziel = entry + seite * 3 * risiko
        elif exit_art == "ema21":
            ziel = None
        else:
            ziel = entry + seite * float(tp_art) * risiko
        sl = stopp
        start = i if s.get("intrabar") else i + 1
        aus, aus_px, grund = None, None, None
        for j in range(start, min(n, start + MAX_KERZEN)):
            if j > i or not s.get("intrabar"):
                if (seite > 0 and l[j] <= sl) or (seite < 0 and h[j] >= sl):
                    aus, aus_px, grund = j, sl, ("Einstand" if sl == entry else "Stopp")
                    break
            if exit_art == "ema21" and j > i:
                if (seite > 0 and h[j] >= e21[j]) or (seite < 0 and l[j] <= e21[j]):
                    aus, aus_px, grund = j, e21[j], "Ziel EMA21"
                    break
            if exit_art == "be3" and j > i and sl != entry:
                if (seite > 0 and h[j] >= e21[j]) or (seite < 0 and l[j] <= e21[j]):
                    sl = entry                                         # EMA21 erreicht -> Stopp auf Einstand
            if ziel is not None and j > i and ((seite > 0 and h[j] >= ziel) or (seite < 0 and l[j] <= ziel)):
                aus, aus_px, grund = j, ziel, "Ziel"
                break
        if aus is None:
            aus = min(n - 1, start + MAX_KERZEN - 1)
            if aus == n - 1 and start + MAX_KERZEN - 1 > n - 1:
                if offen is not None:                                  # noch offen – nicht werten, aber anzeigen
                    offen.append({"zeit": t[i].isoformat(), "seite": seite, "art": s["art"], "entry": entry, "stopp": float(sl),
                                  "ziel": float(ziel) if ziel is not None else None, "kurs": float(c[-1])})
                break
            aus_px, grund = c[aus], "Zeit"
        bewegung = (aus_px - entry) / entry * seite
        hebel = min(RISIKO / (risiko / entry), MAX_HEBEL)
        konto = hebel * (bewegung - 2 * KOSTEN)
        trades.append({"ein": t[i if s.get("intrabar") else i].isoformat(), "aus": t[aus].isoformat(), "seite": seite,
                       "art": s["art"], "entry": entry, "stopp": stopp, "exit": float(aus_px), "grund": grund,
                       "R": float(bewegung * entry / risiko - 2 * KOSTEN * entry / risiko), "konto": float(konto),
                       "kerzen": int(aus - i)})
        frei_ab = aus
    return trades


def statistik(trades):
    if not trades:
        return {"n": 0}
    R = np.array([x["R"] for x in trades])
    k = np.array([x["konto"] for x in trades])
    gew, ver = R[R > 0], R[R <= 0]
    eq = np.cumprod(1 + k)
    dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    se = R.std(ddof=1) / math.sqrt(len(R)) if len(R) > 2 else None
    return {"n": int(len(R)), "treffer": float((R > 0).mean()), "avgR": float(R.mean()),
            "pf": float(gew.sum() / -ver.sum()) if len(ver) and ver.sum() < 0 else None,
            "rendite": float(eq[-1] - 1), "maxdd": dd, "t": float(R.mean() / se) if se else None,
            "gewinnR": float(gew.mean()) if len(gew) else None, "verlustR": float(ver.mean()) if len(ver) else None}


def _kurve(trades, punkte=400):
    if not trades:
        return []
    tr = sorted(trades, key=lambda x: x["aus"])
    eq, out = 1.0, []
    for x in tr:
        eq *= 1 + x["konto"]
        out.append([x["aus"][:10], round(eq - 1, 4)])
    schritt = max(1, len(out) // punkte)
    return out[::schritt] + ([out[-1]] if len(out) % schritt else [])


# ---------------------------------------------------------------------------
# Forschung: alle Strategien × Timeframes × Coins
# ---------------------------------------------------------------------------
def forschen(log=print):
    t0 = time.time()
    daten = {}
    for tf in TIMEFRAMES:
        for coin in COINS:
            try:
                df = lade_archiv(coin, tf)
            except Exception as e:
                log(f"  {coin} {tf}: {str(e)[:80]}")
                df = None
            if df is not None and len(df) > 500:
                daten[(coin, tf)] = _ind(df)
    log(f"  Chart-Daten: {len(daten)} Reihen ({time.time() - t0:.0f} s)")
    ergebnis = {}
    for sid, erk in ERKENNER.items():
        ergebnis[sid] = {}
        for tf in TIMEFRAMES:
            reihen = {coin: D for (coin, t), D in daten.items() if t == tf}
            if not reihen:
                continue
            varianten = []
            for werte in itertools.product(*GRID[sid].values()):
                p = dict(zip(GRID[sid].keys(), werte))
                alle = {}
                for coin, D in reihen.items():
                    grenze = D["t"][int(D["n"] * 2 / 3)]
                    tr = simuliere(D, erk(D, p), p)
                    for x in tr:
                        x["coin"] = coin
                        x["teil"] = "lern" if pd.Timestamp(x["ein"]) < grenze else "test"
                    alle[coin] = tr
                flach = [x for tr in alle.values() for x in tr]
                lern = [x for x in flach if x["teil"] == "lern"]
                test = [x for x in flach if x["teil"] == "test"]
                varianten.append({"par": p, "lern": statistik(lern), "test": statistik(test), "alle": alle})
            gueltig = [v for v in varianten if v["lern"]["n"] >= 30]
            bester = max(gueltig, key=lambda v: v["lern"]["avgR"]) if gueltig else (varianten[0] if varianten else None)
            if not bester:
                continue
            coins = {}
            for coin, tr in bester["alle"].items():
                coins[coin] = {"lern": statistik([x for x in tr if x["teil"] == "lern"]),
                               "test": statistik([x for x in tr if x["teil"] == "test"])}
            flach = [x for tr in bester["alle"].values() for x in tr]
            ergebnis[sid][tf] = {
                "par": bester["par"], "lern": bester["lern"], "test": bester["test"], "coins": coins,
                "kurve": _kurve(flach), "grenze": min(D["t"][int(D["n"] * 2 / 3)] for D in reihen.values()).date().isoformat(),
                "von": min(D["t"][0] for D in reihen.values()).date().isoformat(),
                "bis": max(D["t"][-1] for D in reihen.values()).date().isoformat(),
                "varianten": [{"par": v["par"], "lern": v["lern"], "test": v["test"]} for v in varianten],
                "letzte": sorted(flach, key=lambda x: x["ein"])[-25:],
                "long": statistik([x for x in flach if x["seite"] > 0]), "short": statistik([x for x in flach if x["seite"] < 0]),
            }
            log(f"  {sid:9s} {tf:4s} {json.dumps(bester['par'])} Lern n{bester['lern']['n']} Ø{bester['lern']['avgR']:+.2f}R "
                f"| Test n{bester['test'].get('n')} Ø{(bester['test'].get('avgR') or 0):+.2f}R PF{(bester['test'].get('pf') or 0):.2f} "
                f"Treffer{(bester['test'].get('treffer') or 0) * 100:.0f}% Rendite{(bester['test'].get('rendite') or 0) * 100:+.0f}%")
    # Vergleich: Bitcoin halten im gleichen Zeitraum (4h-Reihe)
    btc = daten.get(("BTC", "1h"))
    vergleich = {}
    if btc is not None:
        s = pd.Series(btc["c"], index=btc["t"]).resample("1D").last().dropna()
        vergleich["Bitcoin halten"] = [[t.date().isoformat(), round(float(v / s.iloc[0] - 1), 4)] for t, v in s.iloc[::3].items()]
    return {"strategien": ergebnis, "vergleich": vergleich, "dauer_s": round(time.time() - t0),
            "datum": dt.date.today().isoformat(), "coins": COINS, "timeframes": list(TIMEFRAMES)}


def bericht(F):
    z = []
    for sid, tfs in F["strategien"].items():
        for tf, r in tfs.items():
            T, Lr = r["test"], r["lern"]
            z.append(f"CHART {sid:9s} {tf:4s} {json.dumps(r['par'])} | Lern n{Lr['n']} Ø{(Lr.get('avgR') or 0):+.2f}R "
                     f"PF{(Lr.get('pf') or 0):.2f} | Test n{T.get('n')} Ø{(T.get('avgR') or 0):+.2f}R PF{(T.get('pf') or 0):.2f} "
                     f"Treffer{(T.get('treffer') or 0) * 100:.0f}% Rendite{(T.get('rendite') or 0) * 100:+.0f}% DD{(T.get('maxdd') or 0) * 100:.0f}% "
                     f"t{(T.get('t') or 0):.1f} | Long Ø{(r['long'].get('avgR') or 0):+.2f}R Short Ø{(r['short'].get('avgR') or 0):+.2f}R")
            besten = sorted(r["coins"].items(), key=lambda kv: -(kv[1]["test"].get("avgR") or -9))
            z.append("      Coins Test Ø R: " + " ".join(f"{c}:{(v['test'].get('avgR') or 0):+.2f}({v['test'].get('n', 0)})" for c, v in besten))
    return "\n".join(z)


# ---------------------------------------------------------------------------
# Live: was die Strategien auf den aktuellen Hyperliquid-Kerzen machen würden
# ---------------------------------------------------------------------------
def live(F, start):
    out = {}
    start = pd.Timestamp(start)
    for sid, tfs in (F or {}).get("strategien", {}).items():
        out[sid] = {}
        for tf, r in tfs.items():
            trades, offen, signale = [], [], []
            for coin in COINS:
                try:
                    df = lade_hl(coin, tf)
                except Exception:
                    df = None
                if df is None or len(df) < 300:
                    continue
                D = _ind(df)
                st = ERKENNER[sid](D, r["par"])
                for s in st:
                    if D["t"][s["i"]] >= start:
                        signale.append({"coin": coin, "zeit": D["t"][s["i"]].isoformat(), "seite": s["seite"], "art": s["art"],
                                        "entry": s["entry"], "stopp": s["stopp"]})
                lauf_offen = []
                tr = simuliere(D, [s for s in st if D["t"][s["i"]] >= start], r["par"], lauf_offen)
                for x in tr + lauf_offen:
                    x["coin"] = coin
                trades += tr
                offen += lauf_offen
            out[sid][tf] = {"trades": sorted(trades, key=lambda x: x["ein"])[-60:], "offen": offen,
                            "signale": sorted(signale, key=lambda x: x["zeit"])[-60:], "stat": statistik(trades),
                            "kurve": _kurve(trades)}
            time.sleep(0.2)
    return out


def lauf(dep, cfg, faellig=None):
    k = dep.setdefault("krypto", {})
    C = k.get("chart") or {}
    if faellig is None:
        faellig = not C.get("forschung") or (dt.date.today() - dt.date.fromisoformat(C["forschung"]["datum"])).days >= 7
    if faellig:
        C["forschung"] = forschen()
    C.setdefault("start", dt.date.today().isoformat())
    C["live"] = live(C["forschung"], C["start"])
    C["stand"] = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    C["info"] = STRATEGIEN
    k["chart"] = C
    return "Chart-Strategien: " + ("Forschung aktualisiert, " if faellig else "") + "Live-Simulation aktualisiert"
