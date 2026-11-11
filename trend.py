"""Trend-Baustein.

1) Aktien-Kern: Wohin mit dem Geld, das nicht in Einzelaktien steckt? S&P 500 oder Nasdaq 100, ohne oder mit
   Hebel (1×, 2×, 3× täglich gehebelt wie SSO/QLD/UPRO/TQQQ), mit oder ohne Trendfilter (raus in den Geldmarkt,
   wenn der Index unter seiner Trendlinie liegt). Getestet ab 1986 (S&P zusätzlich ab 1971) mit nachgebauten
   Hebel-ETFs inkl. Gebühren und Finanzierungskosten, gegengeprüft mit den echten Hebel-ETFs.
2) Krypto-Trend: BTC und ETH halten, solange der Trend steht, sonst Stablecoin-Zins. Mit und ohne Hebel
   (Perp, echte Funding-Kosten von Binance).

Gewählt wird nur auf dem Lernteil, geprüft auf dem Testteil (Daten, die bei der Wahl unbekannt waren).
"""
import datetime as dt
import json
import math
import os
import time

import numpy as np
import pandas as pd

VERSION = 1
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "trend")

# ---------------------------------------------------------------------------
# Einstellungen Aktien-Kern
# ---------------------------------------------------------------------------
INDIZES = {
    "sp500": {"name": "S&P 500", "ticker": "^GSPC", "div": 0.020},
    "ndx": {"name": "Nasdaq 100", "ticker": "^NDX", "div": 0.008},
}
# Gebühren (TER) der US-Hebel-ETFs – europäische 2×-ETFs sind meist günstiger (0,35–0,6 %), wir rechnen vorsichtig
TER = {1: 0.0009, 2: 0.0090, 3: 0.0095}
SPREAD = 0.004          # Aufschlag auf den Geldmarktzins für den geliehenen Teil (Swap-Finanzierung)
KOSTEN_AKTIE = 0.001    # je Wechsel (Spread + Gebühr)
VERZ_AKTIE = 2          # vorsichtig: Signal zum Schluss, gehandelt erst am Folgetag
GRENZE_AKTIE = "2014-01-01"
LERN_START_AKTIE = "1986-08-01"   # ab hier gibt es beide Indizes mit 200-Tage-Linie (inkl. Crash 1987)
US_ETF = {("sp500", 1): "SPY", ("sp500", 2): "SSO", ("sp500", 3): "UPRO",
          ("ndx", 1): "QQQ", ("ndx", 2): "QLD", ("ndx", 3): "TQQQ"}
EU_ETF = {("sp500", 1): "z. B. iShares Core S&P 500 UCITS (CSPX) oder ein MSCI-USA-ETF",
          ("sp500", 2): "z. B. Xtrackers S&P 500 2x Leveraged Daily Swap UCITS",
          ("sp500", 3): "in der EU nur als ETP (z. B. WisdomTree S&P 500 3x Daily Leveraged)",
          ("ndx", 1): "z. B. iShares Nasdaq 100 UCITS (CNDX)",
          ("ndx", 2): "z. B. Amundi Nasdaq-100 Daily (2x) Leveraged UCITS (LQQ)",
          ("ndx", 3): "in der EU nur als ETP (z. B. WisdomTree Nasdaq 100 3x Daily Leveraged, QQQ3)"}
AKTIEN_TICKER = ["^GSPC", "^NDX", "^IRX", "SPY", "QQQ", "SSO", "QLD", "UPRO", "TQQQ", "URTH", "^GDAXI"]
FILTER_AKTIE = {
    "kein": {"name": "immer investiert", "art": "kein"},
    "sma200": {"name": "200-Tage-Linie", "art": "sma", "n": 200, "band": 0.0},
    "sma150": {"name": "150-Tage-Linie", "art": "sma", "n": 150, "band": 0.0},
    "sma100": {"name": "100-Tage-Linie", "art": "sma", "n": 100, "band": 0.0},
    "sma200b1": {"name": "200-Tage-Linie ±1 %", "art": "sma", "n": 200, "band": 0.01},
    "sma200b3": {"name": "200-Tage-Linie ±3 %", "art": "sma", "n": 200, "band": 0.03},
    "kreuz": {"name": "50/200-Kreuz", "art": "kreuz", "n": 50, "m": 200},
}

# ---------------------------------------------------------------------------
# Einstellungen Krypto-Trend
# ---------------------------------------------------------------------------
KRYPTO = {"BTC": "BTC-USD", "ETH": "ETH-USD"}
KOSTEN_KRYPTO = 0.002       # je Wechsel (Gebühr + Spread)
VERZ_KRYPTO = 2             # Tageskerze schließt 0 Uhr UTC, der Radar läuft abends → vorsichtig 2 Tage
FUNDING_VORHER = 0.0003     # angenommene Funding-Kosten je Tag vor Beginn der Binance-Daten (≈ 11 % p.a.)
GRENZE_KRYPTO = "2022-01-01"          # Testteil enthält den Bärenmarkt 2022 und die Erholung danach
LERN_START_KRYPTO = "2018-07-01"      # ab hier gibt es BTC und ETH mit 200-Tage-Linie
FILTER_KRYPTO = {
    "kein": {"name": "immer investiert", "art": "kein"},
    "sma50": {"name": "50-Tage-Linie", "art": "sma", "n": 50, "band": 0.0},
    "sma100": {"name": "100-Tage-Linie", "art": "sma", "n": 100, "band": 0.0},
    "sma200": {"name": "200-Tage-Linie", "art": "sma", "n": 200, "band": 0.0},
    "kreuz": {"name": "20/100-Kreuz", "art": "kreuz", "n": 20, "m": 100},
    "don20": {"name": "Ausbruch 20 Tage / Ausstieg 10", "art": "donchian", "n": 20, "m": 10},
    "don50": {"name": "Ausbruch 50 Tage / Ausstieg 20", "art": "donchian", "n": 50, "m": 20},
    "mom30": {"name": "30-Tage-Momentum", "art": "mom", "n": 30},
    "mom90": {"name": "90-Tage-Momentum", "art": "mom", "n": 90},
}
KRYPTO_KORB = {"BTC": ["BTC"], "ETH": ["ETH"], "BTC+ETH": ["BTC", "ETH"]}


def _c(name):
    os.makedirs(CACHE, exist_ok=True)
    return os.path.join(CACHE, name)


# ---------------------------------------------------------------------------
# Daten
# ---------------------------------------------------------------------------
def lade_yahoo(ticker, start="1970-01-01"):
    """Lange Tageshistorie (bereinigt um Dividenden). Zwischengespeichert für einen Tag."""
    import hashlib
    heute = dt.date.today().isoformat()
    pfad = _c(f"yahoo_{heute}_{hashlib.md5((start + ','.join(sorted(ticker))).encode()).hexdigest()[:8]}.pkl")
    if os.path.exists(pfad):
        return pd.read_pickle(pfad)
    for f in os.listdir(CACHE):
        if f.startswith("yahoo_") and heute not in f:
            os.remove(os.path.join(CACHE, f))
    import yfinance as yf
    df = None
    for v in range(3):
        try:
            df = yf.download(list(ticker), start=start, interval="1d", auto_adjust=True, progress=False, threads=True,
                             group_by="column")
            if df is not None and not df.empty:
                break
        except Exception as e:
            print(f"  Yahoo-Fehler ({str(e)[:80]}), neuer Versuch")
        time.sleep(5 * (v + 1))
    out = {}
    for f in ("Close", "Low", "High"):
        d = df[f] if isinstance(df.columns, pd.MultiIndex) else df[[f]].rename(columns={f: ticker[0]})
        d.index = pd.to_datetime(d.index)
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        out[f] = d.sort_index()
    pd.to_pickle(out, pfad)
    return out


def _zins(Y, idx):
    """Geldmarktzins je Tag aus der 13-Wochen-T-Bill-Rendite (^IRX, in Prozent)."""
    irx = Y["Close"].get("^IRX")
    if irx is None:
        return pd.Series(0.03 / 252, index=idx)
    z = (irx / 100).reindex(idx).ffill().fillna(0.03).clip(lower=0)
    return z / 252


# ---------------------------------------------------------------------------
# Signale und Simulation
# ---------------------------------------------------------------------------
def signal(close, f, hoch=None):
    """True = am Ende dieses Tages investiert sein."""
    c = close.astype(float)
    art = f["art"]
    if art == "kein":
        return pd.Series(True, index=c.index)
    if art == "sma":
        sma = c.rolling(f["n"], min_periods=f["n"]).mean().to_numpy()
        x, b = c.to_numpy(), f.get("band", 0.0)
        out = np.zeros(len(x), dtype=bool)
        an = False
        for i in range(len(x)):
            if not np.isfinite(sma[i]):
                an = False
            elif x[i] > sma[i] * (1 + b):
                an = True
            elif x[i] < sma[i] * (1 - b):
                an = False
            out[i] = an
        return pd.Series(out, index=c.index)
    if art == "kreuz":
        a = c.rolling(f["n"], min_periods=f["n"]).mean()
        b = c.rolling(f["m"], min_periods=f["m"]).mean()
        return (a > b).fillna(False)
    if art == "donchian":
        hi = c.rolling(f["n"], min_periods=f["n"]).max().shift(1).to_numpy()
        lo = c.rolling(f["m"], min_periods=f["m"]).min().shift(1).to_numpy()
        x = c.to_numpy()
        out = np.zeros(len(x), dtype=bool)
        an = False
        for i in range(len(x)):
            if np.isfinite(hi[i]) and x[i] > hi[i]:
                an = True
            elif np.isfinite(lo[i]) and x[i] < lo[i]:
                an = False
            out[i] = an
        return pd.Series(out, index=c.index)
    if art == "mom":
        return (c / c.shift(f["n"]) - 1 > 0).fillna(False)
    raise ValueError(art)


def simulieren(r_an, r_aus, sig, kosten, verz):
    """Tagesrenditen der Strategie. sig = Signal zum Tagesschluss, gehandelt mit Verzögerung verz."""
    pos = sig.shift(verz).fillna(False).astype(float)
    wechsel = pos.diff().abs().fillna(0)
    r = pos * r_an + (1 - pos) * r_aus - wechsel * kosten
    return r.clip(lower=-0.99), pos


def gehebelt(r_index, zins_d, L):
    """Täglich gehebelte Rendite wie bei einem Hebel-ETF: L × Index − Finanzierung des geliehenen Teils − TER."""
    return (L * r_index - (L - 1) * (zins_d + SPREAD / 252) - TER[L] / 252).clip(lower=-0.99)


def kennzahlen(r, pos=None, zins_d=None):
    r = r.dropna()
    if len(r) < 60:
        return None
    eq = (1 + r).cumprod()
    jahre = max((r.index[-1] - r.index[0]).days / 365.25, 1e-9)
    tage_pa = len(r) / jahre
    cagr = float(eq.iloc[-1] ** (1 / jahre) - 1) if eq.iloc[-1] > 0 else -1.0
    vol = float(r.std() * math.sqrt(tage_pa))
    rf = float(zins_d.reindex(r.index).mean() * 252) if zins_d is not None else 0.0
    jr = (1 + r).groupby(r.index.year).prod() - 1
    out = {"cagr": cagr, "maxdd": float((eq / eq.cummax() - 1).min()), "vol": vol,
           "sharpe": (cagr - rf) / vol if vol > 0 else None, "schlechtester_tag": float(r.min()),
           "schlechtestes_jahr": float(jr.min()), "gesamt": float(eq.iloc[-1] - 1),
           "von": r.index[0].date().isoformat(), "bis": r.index[-1].date().isoformat()}
    if pos is not None:
        p = pos.reindex(r.index)
        out["im_markt"] = float(p.mean())
        out["wechsel_pa"] = float(p.diff().abs().sum() / jahre)
    return out


def _kurve(r, punkte=420):
    eq = (1 + r.dropna()).cumprod()
    if eq.empty:
        return []
    s = max(1, len(eq) // punkte)
    t = eq.iloc[::s]
    if t.index[-1] != eq.index[-1]:
        t = pd.concat([t, eq.iloc[-1:]])
    return [[d.date().isoformat(), round(float(v - 1), 4)] for d, v in t.items()]


def _jahre(r):
    jr = (1 + r.dropna()).groupby(r.dropna().index.year).prod() - 1
    return {int(j): round(float(v), 4) for j, v in jr.items()}


def _seit(sig):
    """Seit wann gilt der aktuelle Zustand?"""
    s = sig.dropna()
    if s.empty:
        return None
    w = s.iloc[-1]
    anders = s[s != w]
    return (anders.index[-1] + pd.Timedelta(days=1)).date().isoformat() if len(anders) else s.index[0].date().isoformat()


# ---------------------------------------------------------------------------
# Aktien-Kern
# ---------------------------------------------------------------------------
def aktien_forschen(Y=None, log=print):
    t0 = time.time()
    Y = Y or lade_yahoo(AKTIEN_TICKER, start="1970-01-01")
    C = Y["Close"]
    idx = C["^GSPC"].dropna().index
    zins = _zins(Y, idx)
    grenze = pd.Timestamp(GRENZE_AKTIE)
    lstart = pd.Timestamp(LERN_START_AKTIE)
    roh = {}
    for k, ix in INDIZES.items():
        p = C[ix["ticker"]].reindex(idx).ffill()
        r = (p.pct_change() + ix["div"] / 252).where(p.notna())
        roh[k] = {"preis": p, "r": r}
    # Gegenprobe: nachgebaute Hebel-ETFs gegen die echten
    probe = []
    for (k, L), t in US_ETF.items():
        if t not in C or C[t].notna().sum() < 500:
            continue
        echt = C[t].dropna()
        e_r = echt.pct_change().dropna()
        n_r = gehebelt(roh[k]["r"], zins, L).reindex(e_r.index).dropna()
        e_r = e_r.reindex(n_r.index)
        jahre = (e_r.index[-1] - e_r.index[0]).days / 365.25
        probe.append({"etf": t, "index": INDIZES[k]["name"], "hebel": L, "von": e_r.index[0].date().isoformat(),
                      "echt_cagr": float((1 + e_r).prod() ** (1 / jahre) - 1), "nachbau_cagr": float((1 + n_r).prod() ** (1 / jahre) - 1),
                      "korrelation": float(np.corrcoef(e_r, n_r)[0, 1])})
    varianten, serien = [], {}
    for k in INDIZES:
        for L in (1, 2, 3):
            r_an = gehebelt(roh[k]["r"], zins, L)
            for fid, f in FILTER_AKTIE.items():
                sig = signal(roh[k]["preis"], f)
                r, pos = simulieren(r_an, zins, sig, KOSTEN_AKTIE, VERZ_AKTIE)
                start = roh[k]["preis"].first_valid_index() + pd.Timedelta(days=300)
                r, pos = r[r.index >= start], pos[pos.index >= start]
                vid = f"{k}_{L}x_{fid}"
                serien[vid] = (r, pos, sig)
                varianten.append({"id": vid, "index": k, "index_name": INDIZES[k]["name"], "hebel": L, "filter": fid,
                                  "filter_name": f["name"], "name": f"{INDIZES[k]['name']} {L}× · {f['name']}",
                                  "etf_us": US_ETF[(k, L)], "etf_eu": EU_ETF[(k, L)],
                                  "lern": kennzahlen(r[(r.index >= lstart) & (r.index < grenze)], pos, zins),
                                  "test": kennzahlen(r[r.index >= grenze], pos, zins),
                                  "lang": kennzahlen(r, pos, zins),
                                  "letzte5": kennzahlen(r[r.index >= r.index[-1] - pd.Timedelta(days=5 * 365)], pos, zins)})
    ref = next(v for v in varianten if v["id"] == "sp500_1x_kein")
    dd_grenze = ref["lern"]["maxdd"]
    gueltig = [v for v in varianten if v["lern"] and v["lern"]["maxdd"] >= dd_grenze]
    bester = max(gueltig, key=lambda v: v["lern"]["cagr"])
    aktuell = next(v for v in varianten if v["id"] == "sp500_1x_sma200")
    # Kurven (monatlich) für die wichtigsten Varianten
    zeige = list(dict.fromkeys([bester["id"], "sp500_1x_kein", "ndx_1x_kein", "sp500_1x_sma200", "sp500_2x_sma200",
                                "ndx_2x_sma200", "ndx_3x_sma200", "sp500_2x_kein"]))
    kurven = {}
    for vid in zeige:
        r = serien[vid][0]
        kurven[vid] = {"ab1986": _kurve(r[r.index >= lstart]), "test": _kurve(r[r.index >= grenze])}
    jahre = {vid: _jahre(serien[vid][0][serien[vid][0].index >= lstart]) for vid in zeige}
    for v in varianten:
        sig = serien[v["id"]][2]
        v["jetzt_an"] = bool(sig.iloc[-1])
        v["seit"] = _seit(sig)
    # Vergleich im Testteil: MSCI World / DAX (ohne Hebel, immer investiert)
    vergleich = {}
    for n, t in (("MSCI World", "URTH"), ("DAX", "^GDAXI")):
        if t in C and C[t].notna().sum() > 500:
            r = C[t].dropna().pct_change().dropna()
            vergleich[n] = {"test": _kurve(r[r.index >= grenze]), "ab1986": _kurve(r[r.index >= lstart]),
                            "kennzahlen_test": kennzahlen(r[r.index >= grenze])}
    jetzt = _aktien_jetzt(bester, roh, serien)
    log(f"  Trend Aktien: {len(varianten)} Varianten in {time.time() - t0:.0f} s")
    return {"version": VERSION, "datum": dt.date.today().isoformat(), "grenze": GRENZE_AKTIE, "lern_start": LERN_START_AKTIE,
            "varianten": varianten, "bester": bester["id"], "bisher": aktuell["id"], "dd_grenze": dd_grenze,
            "kurven": kurven, "jahre": jahre, "probe": probe, "vergleich": vergleich, "jetzt": jetzt,
            "annahmen": {"ter": TER, "spread": SPREAD, "kosten": KOSTEN_AKTIE, "verzoegerung": VERZ_AKTIE,
                         "dividende": {k: v["div"] for k, v in INDIZES.items()}},
            "dauer_s": round(time.time() - t0)}


def _aktien_jetzt(v, roh, serien):
    f = FILTER_AKTIE[v["filter"]]
    p = roh[v["index"]]["preis"].dropna()
    out = {"index": v["index_name"], "kurs": float(p.iloc[-1]), "datum": p.index[-1].date().isoformat(), "an": v["jetzt_an"],
           "seit": v["seit"], "halten": (v["etf_us"] if v["jetzt_an"] else "Geldmarkt"), "filter": f["name"]}
    if f["art"] == "sma":
        sma = float(p.rolling(f["n"]).mean().iloc[-1])
        out.update({"linie": sma, "abstand": float(p.iloc[-1] / sma - 1),
                    "rein_ab": sma * (1 + f.get("band", 0)), "raus_ab": sma * (1 - f.get("band", 0))})
    elif f["art"] == "kreuz":
        out.update({"linie": float(p.rolling(f["m"]).mean().iloc[-1]), "kurz": float(p.rolling(f["n"]).mean().iloc[-1])})
    return out


def kern_serie(T, idx, Y=None):
    """Wertentwicklung des gewählten Kerns (inkl. Trendfilter und Geldmarkt) als Kursreihe auf idx."""
    v = next(x for x in T["varianten"] if x["id"] == T["bester"])
    Y = Y or lade_yahoo(AKTIEN_TICKER, start="1970-01-01")
    C = Y["Close"]
    alle = C["^GSPC"].dropna().index
    zins = _zins(Y, alle)
    ix = INDIZES[v["index"]]
    p = C[ix["ticker"]].reindex(alle).ffill()
    r_an = gehebelt((p.pct_change() + ix["div"] / 252).where(p.notna()), zins, v["hebel"])
    r, pos = simulieren(r_an, zins, signal(p, FILTER_AKTIE[v["filter"]]), KOSTEN_AKTIE, VERZ_AKTIE)
    eq = (1 + r.fillna(0)).cumprod()
    return eq.reindex(idx, method="ffill"), pos.reindex(idx, method="ffill")


# ---------------------------------------------------------------------------
# Krypto-Trend
# ---------------------------------------------------------------------------
def _funding():
    try:
        import krypto
        F, _, _ = krypto.lade_binance(coins=["BTC", "ETH"], start="2019-09")
        return F
    except Exception as e:
        print(f"  Funding-Daten nicht ladbar ({str(e)[:80]}) – Annahme {FUNDING_VORHER * 365:.0%} p.a.")
        return pd.DataFrame()


def krypto_forschen(Y=None, F=None, log=print, start_live=None):
    t0 = time.time()
    Y = Y or lade_yahoo(["BTC-USD", "ETH-USD", "^IRX", "SPY", "URTH", "^GDAXI"], start="2014-09-01")
    F = _funding() if F is None else F
    heute = pd.Timestamp(dt.datetime.utcnow().date())
    preise, tief = {}, {}
    for c, t in KRYPTO.items():
        p = Y["Close"][t].dropna()
        p = p[p.index < heute]                                  # laufende Tageskerze weglassen
        preise[c], tief[c] = p, Y["Low"][t].reindex(p.index)
    idx = preise["BTC"].index
    zins = _zins(Y, idx).reindex(idx).ffill().fillna(0.03 / 252) * 252 / 365   # Kalendertage
    grenze, lstart = pd.Timestamp(GRENZE_KRYPTO), pd.Timestamp(LERN_START_KRYPTO)
    einzeln = {}
    for c in KRYPTO:
        p = preise[c].reindex(idx)
        r = p.pct_change()
        f = (F[c].reindex(idx) if c in F else pd.Series(np.nan, index=idx))
        f = f.fillna(FUNDING_VORHER)
        drop = (tief[c].reindex(idx) / p.shift(1) - 1)
        for L in (1, 2):
            r_an = r if L == 1 else (L * r - (L - 1) * f)
            if L > 1:                                            # Liquidation, wenn der Tagestiefstkurs zu weit fällt
                r_an = r_an.where(~(drop * L <= -0.9), -0.9)
            for fid, fd in FILTER_KRYPTO.items():
                sig = signal(p, fd).where(p.notna(), False)
                rr, pos = simulieren(r_an, zins, sig, KOSTEN_KRYPTO, VERZ_KRYPTO)
                rr = rr.where(p.shift(1).notna())
                einzeln[(c, L, fid)] = (rr, pos, sig)
    varianten, serien = [], {}
    for korb, coins in KRYPTO_KORB.items():
        for L in (1, 2):
            for fid, fd in FILTER_KRYPTO.items():
                teile = [einzeln[(c, L, fid)] for c in coins]
                r = pd.concat([t[0] for t in teile], axis=1).mean(axis=1, skipna=False) if len(teile) > 1 else teile[0][0]
                pos = pd.concat([t[1] for t in teile], axis=1).mean(axis=1)
                start = r.first_valid_index() + pd.Timedelta(days=210)
                r, pos = r[r.index >= start].dropna(), pos[pos.index >= start]
                vid = f"{korb}_{L}x_{fid}"
                serien[vid] = (r, pos, [t[2] for t in teile])
                varianten.append({"id": vid, "korb": korb, "hebel": L, "filter": fid, "filter_name": fd["name"],
                                  "name": f"{korb} {L}× · {fd['name']}",
                                  "lern": kennzahlen(r[(r.index >= lstart) & (r.index < grenze)], pos, zins * 365 / 252),
                                  "test": kennzahlen(r[r.index >= grenze], pos, zins * 365 / 252),
                                  "lang": kennzahlen(r, pos, zins * 365 / 252),
                                  "jetzt": {c: bool(s.iloc[-1]) for c, s in zip(coins, [t[2] for t in teile])},
                                  "seit": {c: _seit(s) for c, s in zip(coins, [t[2] for t in teile])}})
    ref = next(v for v in varianten if v["id"] == "BTC_1x_kein")
    gueltig = [v for v in varianten if v["lern"] and v["lern"]["maxdd"] >= ref["lern"]["maxdd"] and v["hebel"] == 1] + \
              [v for v in varianten if v["lern"] and v["hebel"] > 1 and v["lern"]["maxdd"] >= -0.6]
    bester = max(gueltig, key=lambda v: v["lern"]["cagr"])
    zeige = list(dict.fromkeys([bester["id"], "BTC_1x_kein", "ETH_1x_kein", "BTC_1x_sma200", "BTC+ETH_1x_sma100",
                                "BTC_1x_don20", "BTC+ETH_2x_sma100"]))
    kurven = {vid: {"lang": _kurve(serien[vid][0]), "test": _kurve(serien[vid][0][serien[vid][0].index >= grenze])} for vid in zeige}
    jahre = {vid: _jahre(serien[vid][0]) for vid in zeige}
    vergleich = {}
    for n, t in (("S&P 500", "SPY"), ("MSCI World", "URTH"), ("DAX", "^GDAXI")):
        if t in Y["Close"]:
            r = Y["Close"][t].dropna().pct_change().dropna()
            vergleich[n] = {"test": _kurve(r[r.index >= grenze]), "lang": _kurve(r[r.index >= serien["BTC_1x_kein"][0].index[0]])}
    # Live-Papier-Simulation der gewählten Variante ab Startdatum
    start_live = start_live or dt.date.today().isoformat()
    r_b, pos_b, sigs = serien[bester["id"]]
    seit_start = r_b[r_b.index >= pd.Timestamp(start_live)]
    coins = KRYPTO_KORB[bester["korb"]]
    jetzt = []
    for c, s in zip(coins, sigs):
        p = preise[c]
        fd = FILTER_KRYPTO[bester["filter"]]
        z = {"coin": c, "an": bool(s.iloc[-1]), "seit": _seit(s), "kurs": float(p.iloc[-1]), "datum": p.index[-1].date().isoformat()}
        if fd["art"] == "sma":
            sma = float(p.rolling(fd["n"]).mean().iloc[-1])
            z.update({"linie": sma, "abstand": float(p.iloc[-1] / sma - 1)})
        elif fd["art"] == "donchian":
            z.update({"rein_ab": float(p.iloc[-fd["n"] - 1:-1].max()), "raus_ab": float(p.iloc[-fd["m"] - 1:-1].min())})
        elif fd["art"] == "mom":
            z.update({"momentum": float(p.iloc[-1] / p.iloc[-fd["n"] - 1] - 1)})
        elif fd["art"] == "kreuz":
            z.update({"kurz": float(p.rolling(fd["n"]).mean().iloc[-1]), "linie": float(p.rolling(fd["m"]).mean().iloc[-1])})
        # Wechsel-Protokoll der letzten 2 Jahre
        w = s.astype(int).diff().fillna(0)
        z["wechsel"] = [{"datum": d.date().isoformat(), "an": bool(s.loc[d]), "kurs": float(p.loc[d])}
                        for d in w[w != 0].index if d >= p.index[-1] - pd.Timedelta(days=730)][-12:]
        jetzt.append(z)
    log(f"  Trend Krypto: {len(varianten)} Varianten in {time.time() - t0:.0f} s")
    return {"version": VERSION, "datum": dt.date.today().isoformat(), "grenze": GRENZE_KRYPTO, "lern_start": LERN_START_KRYPTO,
            "varianten": varianten, "bester": bester["id"], "kurven": kurven, "jahre": jahre, "vergleich": vergleich,
            "jetzt": jetzt, "start": start_live,
            "live": {"kurve": _kurve(seit_start, 200), "stat": kennzahlen(seit_start) if len(seit_start) >= 60 else
                     {"gesamt": float((1 + seit_start).prod() - 1) if len(seit_start) else 0.0, "tage": int(len(seit_start))}},
            "annahmen": {"kosten": KOSTEN_KRYPTO, "verzoegerung": VERZ_KRYPTO, "funding_vorher": FUNDING_VORHER},
            "dauer_s": round(time.time() - t0)}


# ---------------------------------------------------------------------------
# Bericht und Lauf
# ---------------------------------------------------------------------------
def _k(x):
    if not x:
        return "–"
    return (f"{x['cagr'] * 100:+6.1f}% p.a. DD{x['maxdd'] * 100:4.0f}% Sharpe {x['sharpe'] or 0:.2f}"
            + (f" Markt {x['im_markt'] * 100:.0f}% Wechsel {x['wechsel_pa']:.1f}/J" if "im_markt" in x else ""))


def bericht(A=None, K=None):
    z = []
    if A:
        z.append(f"TREND AKTIEN · Lern {A['lern_start']}–{A['grenze']} · Test ab {A['grenze']} · gewählt {A['bester']}")
        for p in A["probe"]:
            z.append(f"  Gegenprobe {p['etf']:5s} ab {p['von']}: echt {p['echt_cagr'] * 100:+.1f}% p.a. · Nachbau {p['nachbau_cagr'] * 100:+.1f}% · Korr {p['korrelation']:.3f}")
        for v in sorted(A["varianten"], key=lambda v: -(v["lern"] or {}).get("cagr", -9)):
            z.append(f"  {v['name']:42s} | Lern {_k(v['lern'])} | Test {_k(v['test'])} | ab Start {_k(v['lang'])} | jetzt {'AN' if v['jetzt_an'] else 'aus'}")
    if K:
        z.append(f"TREND KRYPTO · Lern {K['lern_start']}–{K['grenze']} · Test ab {K['grenze']} · gewählt {K['bester']}")
        for v in sorted(K["varianten"], key=lambda v: -(v["lern"] or {}).get("cagr", -9)):
            z.append(f"  {v['name']:42s} | Lern {_k(v['lern'])} | Test {_k(v['test'])} | ab Start {_k(v['lang'])}")
    return "\n".join(z)


def lauf(dep, cfg, faellig=None):
    """Täglich: aktuelle Signale; Forschung wöchentlich (oder bei neuer Version)."""
    T = dep.setdefault("trend", {})
    if T.get("version") != VERSION:
        T.clear()
        T["version"] = VERSION
    alt_an = (T.get("aktien") or {}).get("jetzt", {}).get("an")
    alt_k = {z["coin"]: z["an"] for z in (T.get("krypto") or {}).get("jetzt", [])}
    T["aktien"] = aktien_forschen()
    T["krypto"] = krypto_forschen(start_live=(T.get("krypto") or {}).get("start") or T.get("krypto_start"))
    T.setdefault("krypto_start", T["krypto"]["start"])
    T["stand"] = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    # Wechsel für die Push-Nachricht
    T["wechsel"] = []
    a = T["aktien"]["jetzt"]
    if alt_an is not None and alt_an != a["an"]:
        T["wechsel"].append(f"Kern: {a['index']} {'über' if a['an'] else 'unter'} der Trendlinie → {'kaufen: ' + a['halten'] if a['an'] else 'raus in den Geldmarkt'}")
    for z in T["krypto"]["jetzt"]:
        if z["coin"] in alt_k and alt_k[z["coin"]] != z["an"]:
            T["wechsel"].append(f"Krypto-Trend {z['coin']}: {'Aufwärtstrend → kaufen' if z['an'] else 'Trend gebrochen → raus in Stablecoins'}")
    return "Trend: Signale aktualisiert" + (f" ({len(T['wechsel'])} Wechsel)" if T["wechsel"] else "")


if __name__ == "__main__":
    A = aktien_forschen()
    K = krypto_forschen()
    print(bericht(A, K))
