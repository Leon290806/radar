# -*- coding: utf-8 -*-
"""
Bitcoin-Langfrist-Bewertung: Indikatoren berechnen, aus der Vergangenheit lernen (walk-forward, ohne Blick in die
Zukunft) und eine Gesamtbewertung von „Strong Sell“ bis „Strong Buy“ ableiten.

Lernprinzip: Jeder Indikator wird in sein historisches Perzentil umgerechnet (nur mit Daten bis zum jeweiligen Tag).
Zu Beginn jedes Jahres wird gemessen, wie stark jedes Perzentil in der Vergangenheit mit der Rendite der folgenden
12 Monate zusammenhing (Rangkorrelation, nur mit bereits abgeschlossenen 12-Monats-Fenstern). Indikatoren, die
zuverlässig vor schwachen Jahren gewarnt haben, bekommen mehr Gewicht. So ist jede Bewertung seit 2014 „echt“:
Sie hätte damals genau so berechnet werden können.
"""
import numpy as np
import pandas as pd

import einstellungen as E

MERKMALE = {
    # Schlüssel: (Name, Erklärung, min. Historie in Tagen) – hoher Wert = teuer
    "pl_abw": ("Power Law", "Abstand des Kurses zum fairen Wert nach dem Power-Law-Modell (Kurs wächst mit einer Potenz der Zeit seit 2009).", 730),
    "mvrv_z": ("MVRV-Z-Score", "Marktwert gegen realisierten Wert (durchschnittlicher Einstandspreis aller Coins), normiert.", 730),
    "mayer": ("Mayer Multiple", "Kurs geteilt durch den 200-Tage-Durchschnitt.", 730),
    "ma200w_ratio": ("200-Wochen-Linie", "Kurs geteilt durch den 200-Wochen-Durchschnitt – historisch die Bärenmarkt-Untergrenze.", 730),
    "puell": ("Puell Multiple", "Tägliche Miner-Einnahmen gegen ihren Jahresdurchschnitt. Niedrig = Miner unter Druck (Kapitulation).", 730),
    "ath_ratio": ("Abstand zum Allzeithoch", "Kurs geteilt durch das bisherige Allzeithoch.", 730),
    "pi": ("Pi-Cycle", "111-Tage-Durchschnitt gegen das Doppelte des 350-Tage-Durchschnitts. Nahe 1 markierte frühere Zyklus-Hochs.", 730),
    "zyklus": ("Halving-Zyklus", "Wie sich frühere Zyklen am selben Tag nach dem Halving in den folgenden 12 Monaten entwickelt haben.", 730),
    "fng": ("Fear & Greed", "Stimmungsindex (0 = extreme Angst, 100 = extreme Gier). Daten seit 2018.", 365),
}


def rahmen(cm_rows, fng_rows):
    df = pd.DataFrame(cm_rows)
    df["datum"] = pd.to_datetime(df["time"]).dt.tz_localize(None).dt.normalize()
    df = df.set_index("datum").drop(columns=["time", "asset"], errors="ignore").apply(pd.to_numeric, errors="coerce")
    df = df.rename(columns={"PriceUSD": "preis", "CapMrktCurUSD": "mcap", "CapMVRVCur": "mvrv", "SplyCur": "angebot",
                            "IssTotUSD": "emission", "HashRate": "hash", "AdrActCnt": "adressen"})
    df = df[~df.index.duplicated()].sort_index().asfreq("D").ffill(limit=5)
    if fng_rows:
        f = pd.Series({pd.Timestamp(int(x["timestamp"]), unit="s").normalize(): float(x["value"]) for x in fng_rows}).sort_index()
        df["fng"] = f.reindex(df.index).ffill(limit=3)
    else:
        df["fng"] = np.nan
    return df.dropna(subset=["preis"])


def _expandierende_regression(x, y, min_n=365):
    n = np.arange(1, len(x) + 1, dtype=float)
    sx, sy, sxx, sxy = np.cumsum(x), np.cumsum(y), np.cumsum(x * x), np.cumsum(x * y)
    nenner = n * sxx - sx * sx
    with np.errstate(divide="ignore", invalid="ignore"):
        b = (n * sxy - sx * sy) / nenner
        a = (sy - b * sx) / n
    b[:min_n], a[:min_n] = np.nan, np.nan
    return a, b


def indikatoren(df):
    p = df["preis"]
    tage = (df.index - pd.Timestamp(E.GENESIS)).days.values.astype(float)
    x, y = np.log10(tage), np.log10(p.values)
    # Power Law: walk-forward (für das Lernen) und mit allen Daten (für die Anzeige heute)
    a_wf, b_wf = _expandierende_regression(x, y)
    df["pl_abw"] = y - (a_wf + b_wf * x)
    b, a = np.polyfit(x, y, 1)
    rest = y - (a + b * x)
    unten, oben = np.quantile(rest, 0.02), np.quantile(rest, 0.98)
    df["pl_fair"] = 10 ** (a + b * x)
    df["pl_unten"] = 10 ** (a + b * x + unten)
    df["pl_oben"] = 10 ** (a + b * x + oben)
    pl = {"a": a, "b": b, "unten": unten, "oben": oben, "abw_heute": float(rest[-1])}
    # On-Chain
    df["realized"] = p / df["mvrv"]
    rc = df["mcap"] / df["mvrv"]
    df["mvrv_z"] = (df["mcap"] - rc) / df["mcap"].expanding(365).std()
    df["nupl"] = 1 - 1 / df["mvrv"]
    df["puell"] = df["emission"] / df["emission"].rolling(365).mean()
    # Preis-Struktur
    df["ma200"] = p.rolling(200).mean()
    df["mayer"] = p / df["ma200"]
    df["ma200w"] = p.rolling(1400).mean()
    df["ma200w_ratio"] = p / df["ma200w"]
    df["ath"] = p.cummax()
    df["ath_ratio"] = p / df["ath"]
    df["pi"] = p.rolling(111).mean() / (2 * p.rolling(350).mean())
    df["hash_ribbon"] = df["hash"].rolling(30).mean() / df["hash"].rolling(60).mean()
    # Zyklus
    hv = pd.to_datetime(E.HALVINGS)
    letzte = np.searchsorted(hv.values, df.index.values, side="right") - 1
    df["zyklus_nr"] = letzte
    df["zyklus_tag"] = [(d - hv[i]).days if i >= 0 else np.nan for d, i in zip(df.index, letzte)]
    df["fwd"] = np.log(p.shift(-E.HORIZONT) / p)
    df["zyklus"] = _zyklus_wf(df)
    return df, pl


def _zyklus_wf(df):
    """Für jeden Tag: mittlere 12-Monats-Rendite früherer Zyklen am selben Zyklustag (±30 Tage), nur mit damals bekannten Daten."""
    tag, nr, fwd = df["zyklus_tag"].values, df["zyklus_nr"].values, df["fwd"].values
    idx = np.arange(len(df))
    out = np.full(len(df), np.nan)
    for t in range(len(df)):
        if np.isnan(tag[t]) or nr[t] < 1:
            continue
        m = (nr < nr[t]) & (np.abs(tag - tag[t]) <= 30) & (idx + E.HORIZONT <= t) & ~np.isnan(fwd)
        if m.sum() >= 20:
            out[t] = -np.nanmean(fwd[m])   # hohe frühere Rendite = günstig -> niedriger Wert
    return out


def perzentile(df):
    P = pd.DataFrame(index=df.index)
    for k, (_, _, mind) in MERKMALE.items():
        s = df[k]
        erst = s.first_valid_index()
        if erst is None:
            P[k] = np.nan
            continue
        r = s.loc[erst:].expanding(min_periods=mind).rank(pct=True)
        P[k] = r.reindex(df.index)
    return P


def lernen(df, P):
    """Jahresweise Gewichte (walk-forward) und daraus der Gesamt-Score je Tag."""
    jahre = range(pd.Timestamp(E.LERN_START).year, df.index[-1].year + 1)
    gewichte, score = {}, pd.Series(np.nan, index=df.index)
    for j in jahre:
        T = pd.Timestamp(f"{j}-01-01")
        train = (df.index <= T - pd.Timedelta(days=E.HORIZONT)) & df["fwd"].notna()
        w = {}
        for k in MERKMALE:
            m = train & P[k].notna()
            if m.sum() < 365:
                w[k] = 0.0
                continue
            c = P.loc[m, k].rank().corr(df.loc[m, "fwd"].rank())  # Rangkorrelation (Spearman) ohne scipy
            w[k] = round(max(0.0, -c), 4) if pd.notna(c) else 0.0
        # Robustheit: kein Indikator bekommt mehr als 30 % – sonst entscheidet ein einziger (z. B. der Zyklus mit nur
        # drei früheren Beispielen) fast allein
        W = pd.Series(w)
        for _ in range(6):
            if W.sum() > 0:
                W = W.clip(upper=E.MAX_GEWICHT * W.sum())
        w = {k: round(float(v / W.sum()), 4) if W.sum() > 0 else 0.0 for k, v in W.items()}
        gewichte[j] = w
        zeit = (df.index >= T) & (df.index < pd.Timestamp(f"{j + 1}-01-01"))
        teil = P.loc[zeit]
        W = pd.Series(w)
        verf = teil.notna().astype(float).mul(W, axis=1)
        summe = verf.sum(axis=1)
        wert = (1 - teil).fillna(0).mul(W, axis=1).sum(axis=1)
        score.loc[zeit] = (100 * wert / summe).where(summe > 0)
    return gewichte, score


def zone(s):
    if pd.isna(s):
        return None
    for grenze, name in E.ZONEN:
        if s >= grenze:
            return name
    return E.ZONEN[-1][1]


def zonen_statistik(df, score):
    z = score.map(zone)
    p = df["preis"]
    fwd3 = p.shift(-91) / p - 1
    fwd12 = p.shift(-E.HORIZONT) / p - 1
    # größter Rückgang in den folgenden 12 Monaten
    tief = p[::-1].rolling(E.HORIZONT, min_periods=30).min()[::-1].shift(-1)
    dd = tief / p - 1
    out = []
    for _, name in E.ZONEN:
        m = (z == name) & fwd12.notna()
        alle = (z == name)
        out.append({"zone": name, "tage": int(alle.sum()), "tage_ausgewertet": int(m.sum()),
                    "median_12m": float(fwd12[m].median()) if m.any() else None,
                    "anteil_plus": float((fwd12[m] > 0).mean()) if m.any() else None,
                    "median_3m": float(fwd3[(z == name) & fwd3.notna()].median()) if ((z == name) & fwd3.notna()).any() else None,
                    "median_rueckgang": float(dd[m].median()) if m.any() else None,
                    "bester_12m": float(fwd12[m].max()) if m.any() else None, "schlechtester_12m": float(fwd12[m].min()) if m.any() else None})
    return out


def backtest(df, score):
    start = score.first_valid_index()
    p = df["preis"].loc[start:]
    z = score.loc[start:].map(zone)
    anteil = z.map(E.ANTEIL_JE_ZONE).ffill().fillna(0.5)
    r = p.pct_change().fillna(0)
    wert, kurve, wechsel = 1.0, [], 0
    akt = anteil.iloc[0]
    for t in range(len(p)):
        wert *= 1 + akt * r.iloc[t]
        ziel = anteil.iloc[t]
        if ziel != akt:
            wert *= 1 - E.GEBUEHR * abs(ziel - akt)
            akt = ziel
            wechsel += 1
        kurve.append(wert)
    kurve = pd.Series(kurve, index=p.index)
    bh = p / p.iloc[0]

    def kz(s):
        jahre = (s.index[-1] - s.index[0]).days / 365.25
        return {"cagr": float(s.iloc[-1] ** (1 / jahre) - 1), "max_dd": float((s / s.cummax() - 1).min()), "faktor": float(s.iloc[-1])}
    return {"strategie": kurve, "halten": bh, "kz_strategie": kz(kurve), "kz_halten": kz(bh), "wechsel": wechsel, "start": str(start.date())}


def sparplan(df, score):
    """Wöchentlicher Sparplan: normal (immer gleich viel) gegen „smart“ (mehr kaufen, wenn günstig, nichts bei Strong Sell)."""
    start = score.first_valid_index()
    p = df["preis"].loc[start:]
    z = score.loc[start:].map(zone)
    tage = p.index[::7]
    n_coins, n_geld, s_coins, s_geld = 0.0, 0.0, 0.0, 0.0
    verlauf = []
    for d in tage:
        n_coins += 100 / p[d]
        n_geld += 100
        f = E.SPARPLAN_FAKTOR.get(z.get(d), 1.0)
        s_coins += 100 * f / p[d]
        s_geld += 100 * f
        verlauf.append((d, n_coins * p[d], n_geld, s_coins * p[d], s_geld))
    jetzt = p.iloc[-1]
    return {"normal": {"eingezahlt": n_geld, "wert": n_coins * jetzt, "kaufpreis": n_geld / n_coins, "faktor": n_coins * jetzt / n_geld},
            "smart": {"eingezahlt": s_geld, "wert": s_coins * jetzt, "kaufpreis": s_geld / s_coins, "faktor": s_coins * jetzt / s_geld},
            "verlauf": verlauf, "start": str(start.date())}


def analyse(cm_rows, fng_rows):
    df = rahmen(cm_rows, fng_rows)
    df, pl = indikatoren(df)
    P = perzentile(df)
    gewichte, score = lernen(df, P)
    return {"df": df, "P": P, "pl": pl, "gewichte": gewichte, "score": score,
            "zonen": zonen_statistik(df, score), "backtest": backtest(df, score), "sparplan": sparplan(df, score)}
