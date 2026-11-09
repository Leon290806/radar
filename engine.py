# -*- coding: utf-8 -*-
"""
Signal-Engine und Musterdepot.

Bausteine des Scores (0–100):
  Momentum   – Stärke der letzten 6–12 Monate (nur im Aufwärtstrend)
  Zahlen     – positiver Kurssprung mit Volumen (meist Quartalszahlen), der gehalten wird (PEAD)
  Insider    – Vorstände/Direktoren kaufen mit eigenem Geld, am stärksten als Cluster
  52W-Hoch   – Ausbruch auf ein neues 52-Wochen-Hoch mit erhöhtem Volumen
Warnsignal:
  Negativer Kurssprung – Kursrutsch mit Volumen: gehaltene Aktie wird verkauft, Kauf 20 Tage gesperrt.

Momentum + 52W-Hoch allein erreichen nie die Kaufschwelle – es braucht einen Auslöser (Zahlen oder Insider).
Rückblick, Live-Betrieb und Lernmodul laufen durch denselben Code.
"""
import numpy as np
import pandas as pd

JAHR = 252
MERKMALE = {
    "score": "Score", "vola": "Schwankung p.a.", "dist200": "Abstand zur 200-Tage-Linie",
    "sprung": "Größe Kurssprung", "m1": "Kursplus letzter Monat", "regime": "Markt über 200-Tage-Linie",
}


def atr(H, L, C, n=20):
    v = C.shift(1)
    tr = np.maximum(H - L, np.maximum((H - v).abs(), (L - v).abs()))
    return tr.rolling(n, min_periods=10).mean()


# ---------------------------------------------------------------------------
# Signale
# ---------------------------------------------------------------------------
ROLLEN_GEWICHT = {"CEO": 1.0, "CFO": 1.0, "Vorstand": 0.8, "Direktor": 0.6, "10%-Eigner": 0.3, "Sonstige": 0.4}
_FIRMA = (r"(?i)\b(?:llc|l\.p\.|lp|fund|funds|capital|partners|holdings?|trust|inc|corp|corporation|management|ltd|"
          r"limited|gmbh|plc|group|investments?|advisors?|ventures|foundation|stiftung|beteiligungs\w*)\b")


def insider_merkmale(ins):
    """Ergänzt je Transaktion die Merkmale für die Anomalie-Bewertung:
    firma     – Käufer ist ein Investor/eine Gesellschaft, keine Person aus dem Management
    erstkauf  – erster Kauf dieser Person in dieser Aktie seit über 12 Monaten (nur wenn die Vorgeschichte bekannt ist)
    routine   – dieselbe Person hat ziemlich genau ein Jahr vorher auch gekauft (Routine, kaum Information)
    hist      – Vorgeschichte (12 Monate) liegt in den Daten vor"""
    if ins is None or ins.empty:
        return ins
    df = ins.copy()
    df["datum"] = pd.to_datetime(df["datum"])
    if "bestand" not in df.columns:
        df["bestand"] = np.nan
    df["bestand"] = pd.to_numeric(df["bestand"], errors="coerce")
    df["firma"] = df["name"].astype(str).str.contains(_FIRMA, regex=True)
    df["erstkauf"], df["routine"], df["hist"] = False, False, False
    kauf = (df["typ"] == "Kauf") & ~df["plan"].astype(bool)
    beginn = df["datum"].min()
    tag = np.timedelta64(1, "D")
    for _, g in df[kauf].groupby(["ticker", "insider"]):
        d = g["datum"].to_numpy()
        reihen = np.argsort(d, kind="stable")
        d, ix = d[reihen], g.index.to_numpy()[reihen]
        for k in range(len(d)):
            frueher = d[:k][d[:k] < d[k] - 5 * tag]            # Käufe derselben Person davor (nicht dieselbe Meldung)
            hist = d[k] - 365 * tag >= beginn
            letzte = frueher.max() if len(frueher) else None
            df.at[ix[k], "hist"] = bool(hist or letzte is not None)
            df.at[ix[k], "erstkauf"] = bool(hist and (letzte is None or d[k] - letzte > 365 * tag))
            df.at[ix[k], "routine"] = bool(((frueher >= d[k] - 400 * tag) & (frueher <= d[k] - 330 * tag)).any())
    return df


def insider_bewertung(f, umsatz=None, abst_hoch=None):
    """Wie ungewöhnlich ist ein Insider-Kauf? f = Käufe (ohne Sparpläne) einer Aktie im Fenster,
    mit den Spalten aus insider_merkmale. Rückgabe: (Punkte 0–100, Gründe).

    Bausteine (Forschung: Seyhun; Lakonishok & Lee; Cohen, Malloy & Pomorski 2012):
      Cluster (bis 25)   – mehrere Insider kaufen gleichzeitig
      Rolle (bis 15)     – CEO/CFO wissen am meisten, Großaktionäre/Fonds am wenigsten
      Bestandsplus (25)  – Kauf im Verhältnis zu dem, was die Person schon besitzt (50 Tsd. bei 50 Mio. Bestand = Rauschen)
      Größe (bis 15)     – absolute Summe und Summe im Verhältnis zum Tagesumsatz der Aktie
      Erstkauf (bis 10)  – erster Kauf seit über einem Jahr; Routinekäufe (jedes Jahr gleich) geben Abzug
      Gegen den Trend (10) – Kauf nach deutlichem Kursrückgang
    """
    gr = []
    pers = f[~f["firma"].astype(bool)]
    n = int(pers["insider"].nunique())
    wert = float(f["wert"].sum())
    pkt = {0: 0, 1: 0, 2: 12, 3: 20}.get(n, 25)
    if n >= 2:
        gr.append(f"{n} Insider gleichzeitig")
    if n:
        kats = set(pers["kat"])
        pkt += 15 * max(ROLLEN_GEWICHT.get(k, 0.4) for k in kats)
        top = [k for k in ("CEO", "CFO") if k in kats]
        if top:
            gr.append(" und ".join(top) + " kauf" + ("en" if len(top) > 1 else "t"))
    else:
        pkt += 3
        gr.append("nur Investor/Gesellschaft, kein Manager")
    # Bestandsplus
    auf = []
    for _, g in pers.groupby("insider"):
        b = g["bestand"].max()
        if not np.isfinite(b) or b <= 0:
            continue
        st = g["stueck"].sum()
        vor = b - st
        auf.append(st / vor if vor > 0.01 * st else np.inf)
    if auf:
        a = max(auf)
        if not np.isfinite(a):
            pkt += 15
            gr.append("neue Position (vorher keine Aktien)")
        else:
            pkt += next(p for g_, p in ((1.0, 25), (0.5, 22), (0.2, 18), (0.1, 14), (0.05, 9), (0.02, 4), (-1, 0)) if a >= g_)
            if a >= 0.1:
                gr.append(f"Bestand +{a * 100:.0f} %")
            elif a < 0.02:
                gr.append(f"klein: nur +{a * 100:.1f} % auf den eigenen Bestand".replace(".", ","))
    else:
        pkt += 7                                 # unbekannt (z. B. BaFin-Meldungen)
    # Größe
    pkt += 10 * float(np.clip(np.log10(max(wert, 1.0) / 1e4) / 2, 0, 1))
    if umsatz is not None and np.isfinite(umsatz) and umsatz > 0 and wert / umsatz >= 0.1:
        pkt += 5
        gr.append("groß im Verhältnis zum Handelsvolumen")
    # Erstkauf / Routine
    if n:
        if pers["erstkauf"].astype(bool).any():
            pkt += 10
            gr.append("erster Kauf seit über 12 Monaten")
        elif pers["routine"].astype(bool).all():
            pkt -= 5
            gr.append("Routinekauf (wie im Vorjahr)")
        elif not pers["hist"].astype(bool).any():
            pkt += 4
    # gegen den Trend
    if abst_hoch is not None and np.isfinite(abst_hoch):
        if abst_hoch <= -0.20:
            pkt += 10
            gr.append(f"kauft nach Kursrückgang ({abst_hoch * 100:.0f} % vom Hoch)".replace("-", "−"))
        elif abst_hoch <= -0.10:
            pkt += 5
    return float(np.clip(pkt, 0, 100)), gr


def auffaellig_text(p):
    return "stark" if p >= 70 else "auffällig" if p >= 50 else "normal"


def _insider(ins, C, umsatz, cfg):
    """Insider-Baustein: nur echte Anomalien (Bewertung ab INSIDER_MIN_AUFFAELLIG) zählen."""
    I = np.zeros(C.shape)
    Ip = np.zeros(C.shape)
    info = {}
    leer = pd.DataFrame(I, index=C.index, columns=C.columns)
    if ins is None or ins.empty:
        return leer, leer.copy(), info
    k = ins[(ins["typ"] == "Kauf") & (~ins["plan"].astype(bool)) & (ins["wert"] >= cfg.INSIDER_MIN_KAUF)
            & ins["ticker"].isin(C.columns)].copy()
    if k.empty:
        return leer, leer.copy(), info
    idx = C.index
    # verfügbar ab dem Handelstag NACH dem Meldedatum (kein Blick in die Zukunft)
    k["pos"] = idx.searchsorted(pd.to_datetime(k["datum"]).values, side="right")
    k = k[k["pos"] < len(idx)]
    W = cfg.INSIDER_FENSTER
    grenze = min(40, getattr(cfg, "INSIDER_MIN_AUFFAELLIG", 50))   # genaue Schwelle erst beim Score (Forschung wählt 50 oder 70)
    Cn = C.to_numpy()
    hoch = C.rolling(252, min_periods=60).max().to_numpy()
    Un = umsatz.to_numpy()
    for t, g in k.groupby("ticker"):
        j = C.columns.get_loc(t)
        p = g["pos"].to_numpy()
        wechsel = sorted({int(x) for x in np.concatenate([p, p + W]) if x < len(idx)})
        for a, b in zip(wechsel, wechsel[1:] + [len(idx)]):
            f = g[(p <= a) & (p > a - W)]
            if f.empty:
                continue
            p0 = max(int(f["pos"].max()) - 1, 0)          # Tag der letzten Meldung
            abst = Cn[p0, j] / hoch[p0, j] - 1 if np.isfinite(hoch[p0, j]) and hoch[p0, j] > 0 else None
            pk, gr = insider_bewertung(f, Un[p0, j], abst)
            if pk < grenze:
                continue
            staerke = float(np.clip((pk - 35) / 45, 0, 1))
            avg = f["wert"].sum() / (f["wert"] / f["preis"].replace(0, np.nan)).sum()
            if not np.isfinite(avg):
                continue
            inf = {"n": int(f["insider"].nunique()), "wert": float(f["wert"].sum()), "kat": sorted(set(f["kat"]))[:3],
                   "punkte": round(pk), "gruende": gr}
            for d in range(a, min(b, len(idx))):
                if Cn[d, j] < 0.9 * avg:                     # Kurs schon deutlich unter Insider-Preis
                    continue
                I[d, j] = staerke
                Ip[d, j] = pk
                info[(d, t)] = inf
    return pd.DataFrame(I, index=C.index, columns=C.columns), pd.DataFrame(Ip, index=C.index, columns=C.columns), info


def _regime(c):
    c = c.ffill()
    sma = c.rolling(200, min_periods=150).mean()
    return c > sma, c / sma - 1


def berechne_signale(kurse, aktien, insider, cfg, regime_ticker="^GSPC", sektoren=None):
    O, H, L, C, V = (kurse[f][aktien] for f in ("Open", "High", "Low", "Close", "Volume"))
    A = atr(H, L, C)
    umsatz = (C * V).rolling(50, min_periods=30).mean()
    elig = (C >= cfg.MIN_PREIS) & (umsatz >= cfg.MIN_UMSATZ) & C.shift(260).notna()

    # Momentum
    r = C / C.shift(1) - 1
    vola = r.rolling(63, min_periods=40).std() * np.sqrt(JAHR)
    m12, m6, m1 = C.shift(21) / C.shift(252) - 1, C.shift(21) / C.shift(126) - 1, C / C.shift(21) - 1
    sma50, sma200 = C.rolling(50).mean(), C.rolling(200).mean()
    trend = (C > sma200) & (sma50 > sma200)
    roh = ((m12 + m6) / 2 / vola).where(elig & trend & (m1 < 0.4))
    M = roh.rank(axis=1, pct=True).fillna(0.0)

    # Kurssprünge (positiv = Chance, negativ = Warnung)
    v1 = C.shift(1)
    plus, gap = C / v1 - 1, O / v1 - 1
    vf = V / V.rolling(50, min_periods=30).mean().shift(1)
    ev = (gap >= cfg.PEAD_GAP_MIN) & (plus >= cfg.PEAD_TAGESPLUS_MIN) & (vf >= cfg.PEAD_VOLUMEN_FAKTOR) & elig
    neg = (gap <= -cfg.PEAD_GAP_MIN) & (plus <= -cfg.PEAD_TAGESPLUS_MIN) & (vf >= cfg.PEAD_VOLUMEN_FAKTOR)
    pos = np.arange(len(C), dtype=float)
    lim = cfg.PEAD_MAX_ALTER
    letzte = pd.DataFrame(np.where(ev.to_numpy(), pos[:, None], np.nan), index=C.index, columns=C.columns).ffill(limit=lim)
    seit = letzte.rsub(pos, axis=0)
    evC = C.where(ev).ffill(limit=lim)
    evVF = vf.where(ev).ffill(limit=lim)
    evPlus = plus.where(ev).ffill(limit=lim)
    frisch = pd.DataFrame(np.where(seit <= cfg.PEAD_FRISCH, 1.0, np.where(seit <= lim, 0.6, 0.0)),
                          index=C.index, columns=C.columns)
    neg_sperre = neg.astype(float).rolling(cfg.NEG_SPERRE, min_periods=1).max().fillna(0) > 0
    P = (frisch * (C >= evC) * (0.5 + evVF / 10).clip(upper=1.0)).fillna(0.0).where(~neg_sperre, 0.0)

    # 52-Wochen-Hoch-Ausbruch mit Volumen
    hoch252 = C.shift(1).rolling(251, min_periods=200).max()
    h_ev = (C >= hoch252) & (vf >= cfg.HOCH_VOLUMEN_FAKTOR) & elig
    Hs = (h_ev.astype(float).rolling(cfg.HOCH_FENSTER, min_periods=1).max().fillna(0) > 0) \
        & (C >= 0.97 * C.rolling(252, min_periods=200).max())
    Hs = Hs.astype(float).where(trend, 0.0)

    insider = insider_merkmale(insider) if insider is not None else None
    I, Ipkt, iinfo = _insider(insider, C, umsatz, cfg) if cfg.INSIDER_AKTIV else (C * 0.0, C * 0.0, {})
    # Größenklasse nach Handelsumsatz (0 = klein, 1 = mittel, 2 = groß), je Tag unter allen handelbaren Aktien
    rang_u = umsatz.where(elig).rank(axis=1, pct=True)
    groesse = pd.DataFrame(np.where(rang_u.isna(), np.nan, np.where(rang_u < 1 / 3, 0, np.where(rang_u < 2 / 3, 1, 2))),
                           index=C.index, columns=C.columns)
    spanne = (H - L).replace(0, np.nan)
    stark = (C - L) / spanne >= 0.7                       # Schluss im oberen Drittel der Tagesspanne
    # Kurzfrist-Umkehr: große Aktien unter den 5 % größten Verlierern der letzten 5 Tage
    r5 = C / C.shift(5) - 1
    umkehr = (r5.where(elig & (groesse == 2)).rank(axis=1, pct=True) <= 0.05)
    # Kauf nach Kursrutsch: negativer Kurssprung in den letzten 5 Tagen (Überreaktion)
    neg_kauf = (neg & elig).astype(float).rolling(5, min_periods=1).max().fillna(0) > 0
    evGroesse = groesse.where(ev).ffill(limit=lim)
    evStark = stark.where(ev).astype(float).ffill(limit=lim)

    rc = kurse["Close"][regime_ticker] if regime_ticker in kurse["Close"] else C.mean(axis=1)
    regime, regime_abst = _regime(rc)
    regime = regime.reindex(C.index).fillna(True)
    s = {"O": O, "H": H, "L": L, "C": C, "V": V, "A": A, "M": M, "P": P, "I": I, "Ipkt": Ipkt, "HO": Hs, "NEG": neg,
         "groesse": groesse, "evGroesse": evGroesse, "umkehr": umkehr, "neg_kauf": neg_kauf, "r5": r5, "evStark": evStark, "h_ev": h_ev, "neg_ev": neg, "stark": stark,
         "neg_sperre": neg_sperre, "regime": regime, "regime_abst": regime_abst.reindex(C.index),
         "letzte": letzte, "evPlus": evPlus, "evVF": evVF, "iinfo": iinfo, "elig": elig,
         "vola": vola, "dist200": C / sma200 - 1, "m1": m1, "m12": m12, "m6": m6, "sma200": sma200,
         "plus": plus, "vf": vf, "gap": gap, "ev": ev, "umsatz": umsatz, "insider": insider,
         "sektor": {t: v for t, v in (sektoren or {}).items() if t in C.columns}}
    s["score"] = kombiniere(s, cfg)
    return s


def p_eff(s, par):
    """Zahlen-Baustein nach den Regeln aus der Forschung (z. B. nur kleine/mittlere Aktien, nur starker Schluss)."""
    if not getattr(par, "PEAD_AKTIV", True):
        return s["P"] * 0.0
    m = s["evGroesse"].isin(list(getattr(par, "PEAD_GROESSEN", (0, 1, 2))))
    if getattr(par, "PEAD_STARKER_SCHLUSS", False):
        m &= s["evStark"] > 0.5
    return s["P"].where(m, 0.0)


def i_eff(s, par):
    """Insider-Baustein: nur Anomalien ab der Schwelle (50 oder 70 Punkte)."""
    if not getattr(par, "INSIDER_TRIGGER", True):
        return s["I"] * 0.0
    return s["I"].where(s["Ipkt"] >= getattr(par, "INSIDER_MIN_AUFFAELLIG", 50), 0.0)


def kombiniere(s, par):
    """Score mit den Gewichten aus par zusammensetzen."""
    roh = (par.GEWICHT_MOMENTUM * s["M"] + par.GEWICHT_PEAD * p_eff(s, par) + par.GEWICHT_INSIDER * i_eff(s, par)
           + par.GEWICHT_HOCH * s["HO"])
    sperre = s["neg_sperre"] if getattr(par, "NEG_SPERRE_AKTIV", True) else False
    return (100 * roh).where(s["elig"] & ~sperre, 0.0).clip(upper=100)


def komponenten(s, d, t, par=None):
    j = s["C"].columns.get_loc(t)
    P, I = float(s["P"].iat[d, j]), float(s["I"].iat[d, j])
    if par is not None:
        g = s["evGroesse"].iat[d, j]
        if (not getattr(par, "PEAD_AKTIV", True) or not np.isfinite(g) or int(g) not in list(getattr(par, "PEAD_GROESSEN", (0, 1, 2)))
                or (getattr(par, "PEAD_STARKER_SCHLUSS", False) and not s["evStark"].iat[d, j] > 0.5)):
            P = 0.0
        if not getattr(par, "INSIDER_TRIGGER", True) or s["Ipkt"].iat[d, j] < getattr(par, "INSIDER_MIN_AUFFAELLIG", 50):
            I = 0.0
    return {"M": float(s["M"].iat[d, j]), "P": P, "I": I, "H": float(s["HO"].iat[d, j])}


def merkmale(s, d, t, score):
    j = s["C"].columns.get_loc(t)

    def w(k):
        v = s[k].iat[d, j]
        return float(v) if np.isfinite(v) else 0.0
    sp = float(s["evPlus"].iat[d, j]) if s["P"].iat[d, j] > 0 and np.isfinite(s["evPlus"].iat[d, j]) else 0.0
    return {"score": round(float(score), 1), "vola": round(w("vola"), 3), "dist200": round(w("dist200"), 3),
            "sprung": round(sp, 3), "m1": round(w("m1"), 3), "regime": 1 if bool(s["regime"].iat[d]) else 0}


def signal_typen(k):
    typen = []
    if k["P"] > 0:
        typen.append("Zahlen")
    if k["I"] > 0:
        typen.append("Insider")
    if k.get("H", 0) > 0:
        typen.append("52W-Hoch")
    if k["M"] > 0:
        typen.append("Momentum")
    return typen


def gruende(s, d, t, k=None):
    g = []
    j = s["C"].columns.get_loc(t)
    if (k["P"] if k else s["P"].iat[d, j]) > 0:
        ev_d = s["C"].index[int(s["letzte"].iat[d, j])]
        g.append(f"Kurssprung +{s['evPlus'].iat[d, j] * 100:.0f} % am {ev_d:%d.%m.} "
                 f"({s['evVF'].iat[d, j]:.0f}× Volumen), Niveau gehalten")
    inf = s["iinfo"].get((d, t)) if (k["I"] if k else 1) > 0 else None
    if inf:
        rollen = f" ({', '.join(inf['kat'])})" if inf["kat"] else ""
        wert = f"{inf['wert'] / 1e6:.2f}".replace(".", ",") + " Mio." if inf["wert"] >= 1e6 else f"{inf['wert'] / 1e3:.0f} Tsd."
        warum = f" – {', '.join(inf.get('gruende', [])[:3])}" if inf.get("gruende") else ""
        g.append(f"Insider-Anomalie {inf.get('punkte', 0)}/100: {inf['n']} Insider kauften für {wert} eigene Aktien{rollen}{warum}")
    if s["HO"].iat[d, j] > 0:
        g.append("Ausbruch auf ein neues 52-Wochen-Hoch mit erhöhtem Volumen")
    m = s["M"].iat[d, j]
    if m > 0:
        g.append(f"Aufwärtstrend, stärker als {m * 100:.0f} % aller Aktien")
    return g


def gewicht(score, stop_pct, schwelle, par):
    x = np.clip((score - schwelle) / max(90 - schwelle, 1), 0, 1)
    w = par.GEWICHT_MIN + x * (par.GEWICHT_MAX - par.GEWICHT_MIN)
    return float(min(w, par.MAX_VERLUST_PRO_TRADE / max(stop_pct, 1e-6)))


def filter_ok(mk, filter_liste):
    for f in filter_liste or []:
        v = mk.get(f["merkmal"])
        if v is None:
            continue
        if f["op"] == "<=" and not v <= f["wert"]:
            return False, f["text"]
        if f["op"] == ">=" and not v >= f["wert"]:
            return False, f["text"]
    return True, ""


# ---------------------------------------------------------------------------
# Musterdepot
# ---------------------------------------------------------------------------
VERSION = 7


def neues_depot():
    return {"version": VERSION, "cash": 100.0, "trades": [], "kurve": [], "naechste_id": 1,
            "letzter_tag": None, "live_seit": None, "start": None, "parameter": {}, "lernen": {},
            "kandidaten_status": {}}


def _np(s, score=None, bench=None):
    """Numpy-Kopien für die schnelle Tages-Simulation (einmal je Signal-Satz bzw. Score)."""
    n = s.get("_np")
    if n is None:
        n = {k: s[k].to_numpy(dtype=float) for k in ("O", "H", "L", "C", "A", "M", "HO")}
        n["NEG"] = s["NEG"].fillna(False).to_numpy(dtype=bool)
        for k in ("umkehr", "neg_kauf", "elig"):
            n[k] = s[k].fillna(False).to_numpy(dtype=bool)
        n["regime"] = s["regime"].to_numpy(dtype=bool)
        n["cols"] = list(s["C"].columns)
        n["J"] = {t: j for j, t in enumerate(n["cols"])}
        s["_np"] = n
    if score is not None and n.get("score_id") != id(score):
        n["score"], n["score_id"], n["score_ref"] = score.to_numpy(dtype=float), id(score), score  # Referenz halten: id bleibt eindeutig
    if bench is not None and n.get("bench_id") != id(bench):
        n["bench"], n["bench_id"], n["bench_ref"] = bench.to_numpy(dtype=float), id(bench), bench
    return n


def _equity(dep, s, d):
    n = _np(s)
    wert = dep["cash"]
    for tr in dep["trades"]:
        if tr["status"] == "offen":
            j = n["J"].get(tr["ticker"])
            px = float(n["C"][d, j]) if j is not None else float("nan")
            wert += tr["stueck"] * (px if np.isfinite(px) else float(tr.get("kurs") or tr.get("einstieg_kurs") or 0))
    return wert


def tag_verarbeiten(dep, s, d, par, modus, firmen, bench=None, pruefe_pead=None, score=None, status_merken=False):
    """Einen Handelstag d (Index-Position) abarbeiten: Kern-Rendite, Ausführungen, Stopps, neue Signale.

    Nicht investiertes Geld ("Kern") liegt im S&P-500-ETF, solange der Markt über seiner
    200-Tage-Linie liegt, sonst im Geldmarkt.
    """
    C = s["C"]
    score = s["score"] if score is None else score
    N = _np(s, score, bench)
    J = N["J"]
    O, L, Cn, A = N["O"], N["L"], N["C"], N["A"]
    B = N.get("bench") if bench is not None else None
    datum = C.index[d]
    iso = datum.date().isoformat()
    K = par.KOSTEN

    # 0) Kern: Rendite auf das freie Geld
    if d > 0 and dep["cash"] > 0:
        if par.KERN_AKTIV and B is not None and N["regime"][d - 1] \
                and np.isfinite(B[d]) and np.isfinite(B[d - 1]):
            dep["cash"] *= B[d] / B[d - 1]
        else:
            dep["cash"] *= (1 + par.GELDMARKT_ZINS) ** (1 / 252)

    # 1) geplante Verkäufe zur Eröffnung
    for tr in dep["trades"]:
        if tr["status"] == "offen" and tr.get("verkaufen_geplant"):
            if tr["ticker"] not in J or not np.isfinite(O[d, J[tr["ticker"]]]):
                continue                                # heute keine Kursdaten – Verkauf morgen erneut
            px = float(O[d, J[tr["ticker"]]])
            dep["cash"] += tr["stueck"] * px * (1 - K)
            _schliessen(tr, iso, px, tr["verkaufen_geplant"], K, bench, C.index)

    # 2) geplante Käufe zur Eröffnung
    for tr in dep["trades"]:
        if tr["status"] != "geplant":
            continue
        o = float(O[d, J[tr["ticker"]]]) if tr["ticker"] in J else float("nan")
        if not np.isfinite(o) or o > tr["signal_kurs"] * (1 + par.MAX_GAP_EINSTIEG):
            tr.update(status="verpasst", ausstieg_grund="Eröffnung zu hoch – ausgelassen", ausstieg_datum=iso)
            continue
        invest = min(tr["gewicht"] * tr["equity_signal"], dep["cash"])
        tr["stueck"] = invest / (o * (1 + K))
        dep["cash"] -= tr["stueck"] * o * (1 + K)
        regeln = tr.get("parameter", {})
        st0 = o - regeln.get("STOPP_ATR_START", par.STOPP_ATR_START) * tr["atr"]
        gz = regeln.get("GEWINNZIEL_ATR", 0) or 0
        tr.update(status="offen", einstieg_datum=iso, einstieg_kurs=o, hoechst=o, tage=0, stopp=st0, kurs=o,
                  stopp_start=st0, ziel=(o + gz * tr["atr"]) if gz > 0 else None)

    # 3) offene Positionen: Stopp, Nachziehen, Zeitstopp, Warnsignal
    for tr in dep["trades"]:
        if tr["status"] != "offen" or tr.get("verkaufen_geplant"):
            continue
        t = tr["ticker"]
        if t not in J or not np.isfinite(Cn[d, J[t]]):  # Kursdaten fehlen heute (Download-Fehler) – Position unverändert lassen
            tr["fehlt_tage"] = tr.get("fehlt_tage", 0) + 1
            if tr["fehlt_tage"] >= 5 and tr.get("kurs"):  # dauerhaft keine Daten: zum letzten Kurs schließen
                dep["cash"] += tr["stueck"] * tr["kurs"] * (1 - K)
                _schliessen(tr, iso, tr["kurs"], "Kursdaten fehlen", K, bench, C.index)
            continue
        tr["fehlt_tage"] = 0
        j = J[t]
        tr["stopp_vortag"] = tr["stopp"]
        lo, op, hi = float(L[d, j]), float(O[d, j]), float(N["H"][d, j])
        if lo <= tr["stopp"]:                           # Stopp zuerst (vorsichtig, falls beides am selben Tag)
            px = min(op, tr["stopp"])
            dep["cash"] += tr["stueck"] * px * (1 - K)
            _schliessen(tr, iso, px, "Stopp", K, bench, C.index)
            continue
        if tr.get("ziel") and hi >= tr["ziel"]:         # Gewinnziel erreicht (Limit-Verkauf)
            px = max(op, tr["ziel"])
            dep["cash"] += tr["stueck"] * px * (1 - K)
            _schliessen(tr, iso, px, "Gewinnziel", K, bench, C.index)
            continue
        c, a = float(Cn[d, j]), float(A[d, j])
        regeln = tr.get("parameter", {})            # offene Trades behalten die Regeln vom Kauftag
        nz = regeln.get("STOPP_ATR_NACHZIEH", par.STOPP_ATR_NACHZIEH)
        hd = regeln.get("HALTEDAUER", par.HALTEDAUER)
        tr["hoechst"] = max(tr["hoechst"], c)
        if np.isfinite(a):
            tr["stopp"] = max(tr["stopp"], tr["hoechst"] - nz * a)
        tr["tage"] += 1
        tr["kurs"] = c
        if getattr(par, "EXIT_NEG_SPRUNG", True) and N["NEG"][d, j]:
            tr["verkaufen_geplant"] = "Negativer Kurssprung"
        elif tr["tage"] >= hd:
            tr["verkaufen_geplant"] = f"Zeitstopp ({hd} Tage)"

    eq = _equity(dep, s, d)
    b = float(B[d]) if B is not None and np.isfinite(B[d]) else None
    investiert = 1 - dep["cash"] / eq if eq > 0 else 0.0
    dep["kurve"].append([iso, round(eq, 4), b, modus, round(investiert, 3), 1 if N["regime"][d] else 0])

    # 4) neue Empfehlung(en) auf Basis des heutigen Schlusskurses
    schwelle = par.SCHWELLE if N["regime"][d] else par.SCHWELLE_RISK_OFF
    reihe = np.nan_to_num(N["score"][d])
    untergrenze = schwelle - 25 if status_merken else schwelle
    # Faktor-Auslöser (nur wenn das Forschungslabor sie in echten Daten belegt hat)
    m_d = np.nan_to_num(N["M"][d])
    prio_w = getattr(par, "TRIGGER_PRIO", None) or {}
    fak = np.zeros(len(reihe), dtype=bool)
    prio = np.where(reihe >= schwelle, prio_w.get("E", 0.0), -1.0)      # Ereignis-Auslöser (Zahlen/Insider)
    for flag, key, maske in (("MOMENTUM_TRIGGER", "M", lambda: m_d >= 0.9),
                             ("HOCH_TRIGGER", "H", lambda: (np.nan_to_num(N["HO"][d]) > 0) & (m_d > 0)),
                             ("UMKEHR_TRIGGER", "U", lambda: N["umkehr"][d]),
                             ("NEG_KAUF_TRIGGER", "N", lambda: N["neg_kauf"][d])):
        if getattr(par, flag, False):
            m = maske() & N["elig"][d]
            fak |= m
            prio = np.where(m, np.maximum(prio, prio_w.get(key, 0.0)), prio)
    wahl = np.nonzero((reihe >= untergrenze) | fak)[0]
    # Reihenfolge: zuerst der Auslöser mit der höchsten belegten Mehrrendite, dann der Score
    wahl = wahl[np.lexsort((-reihe[wahl], -prio[wahl]))]
    cols = N["cols"]
    faktor = {cols[jj]: bool(fak[jj]) for jj in wahl}
    status = {}
    if len(wahl):
        belegt = {tr["ticker"] for tr in dep["trades"] if tr["status"] in ("offen", "geplant")}
        grenze14 = (datum - pd.Timedelta(days=14)).date().isoformat()
        kuerzlich = {tr["ticker"] for tr in dep["trades"] if (tr.get("ausstieg_datum") or "") > grenze14}
        neu = 0
        n_aktiv = sum(1 for tr in dep["trades"] if tr["status"] in ("offen", "geplant"))
        for jj in wahl:
            t, sc = cols[jj], float(reihe[jj])
            if not status_merken and (neu >= par.MAX_NEU_PRO_TAG or n_aktiv >= par.MAX_POSITIONEN):
                break                                   # nichts mehr zu kaufen – Rest nur für die Status-Anzeige nötig
            if sc < schwelle and not faktor.get(t, False):
                status[t] = f"Score {sc:.0f} – es fehlen {schwelle - sc:.0f} Punkte bis zur Schwelle {schwelle}"
                continue
            if t in belegt:
                status[t] = "Bereits im Portfolio"
                continue
            if t in kuerzlich:
                status[t] = "Gesperrt: vor weniger als 14 Tagen verkauft"
                continue
            if neu >= par.MAX_NEU_PRO_TAG:
                status[t] = "Nicht heute: max. eine neue Empfehlung pro Tag – ein stärkerer Kandidat hat Vorrang"
                continue
            aktiv = [tr for tr in dep["trades"] if tr["status"] in ("offen", "geplant")]
            if len(aktiv) >= par.MAX_POSITIONEN:
                status[t] = f"Portfolio voll ({par.MAX_POSITIONEN} Positionen)"
                continue
            sek = s.get("sektor") or {}
            if t in sek:
                se, br = sek[t]
                gleich_br = [x["ticker"] for x in aktiv if sek.get(x["ticker"], ("", ""))[1] == br]
                gleich_se = [x["ticker"] for x in aktiv if sek.get(x["ticker"], ("", ""))[0] == se]
                if len(gleich_br) >= getattr(par, "MAX_JE_BRANCHE", 1):
                    status[t] = f"Klumpenrisiko: Branche „{br}“ schon im Portfolio ({', '.join(gleich_br)})"
                    continue
                if len(gleich_se) >= getattr(par, "MAX_JE_SEKTOR", 2):
                    status[t] = f"Klumpenrisiko: schon {len(gleich_se)} Aktien aus „{se}“ ({', '.join(gleich_se)})"
                    continue
            reserviert = sum(tr["gewicht"] * tr["equity_signal"] for tr in aktiv if tr["status"] == "geplant")
            frei = (dep["cash"] - reserviert) / eq
            if frei < par.MIN_CASH_FUER_KAUF:
                status[t] = "Kein freies Kapital"
                continue
            k = komponenten(s, d, t, par)
            if k["P"] <= 0 and k["I"] <= 0 and not faktor.get(t, False):
                status[t] = "Kein Auslöser: Es braucht einen Kurssprung nach Zahlen, eine Insider-Anomalie oder einen belegten Faktor-Auslöser"
                continue
            if pruefe_pead is not None and k["P"] > 0:
                ev_d = s["C"].index[int(s["letzte"].iat[d, s["C"].columns.get_loc(t)])].date()
                if not pruefe_pead(t, ev_d):
                    sc = sc - 100 * par.GEWICHT_PEAD * k["P"]
                    k["P"] = 0.0
                    if (sc < schwelle or k["I"] <= 0) and not faktor.get(t, False):
                        status[t] = ("Kurssprung kam nicht von Quartalszahlen (z. B. Übernahme/News) – "
                                     f"ohne diesen Baustein nur Score {sc:.0f}")
                        continue
            mk = merkmale(s, d, t, sc)
            ok, grund = filter_ok(mk, par.FILTER)
            if not ok:
                status[t] = f"Gelernter Filter greift: {grund}"
                continue
            c, a = float(Cn[d, jj]), float(A[d, jj])
            if not (np.isfinite(c) and np.isfinite(a) and c > 0):
                status[t] = "Kursdaten unvollständig"
                continue
            w = min(gewicht(sc, par.STOPP_ATR_START * a / c, schwelle, par), frei)
            typen, gr = signal_typen(k), gruende(s, d, t, k)
            if getattr(par, "UMKEHR_TRIGGER", False) and N["umkehr"][d, jj]:
                typen.insert(0, "Umkehr")
                gr.insert(0, f"Kurzfrist-Verlierer: {s['r5'].iat[d, jj] * 100:+.1f} % in 5 Tagen – große Aktien erholen sich danach im Schnitt (belegt)".replace(".", ","))
            if getattr(par, "NEG_KAUF_TRIGGER", False) and N["neg_kauf"][d, jj]:
                typen.insert(0, "Rücksetzer")
                gr.insert(0, "Kursrutsch mit Volumen in den letzten Tagen – Überreaktion, die sich im Schnitt wieder erholt (belegt)")
            if getattr(par, "MOMENTUM_TRIGGER", False) and m_d[jj] >= 0.9 and "Momentum" in typen:
                typen.remove("Momentum")
                typen.insert(0, "Momentum")
            dep["trades"].append({
                "id": dep["naechste_id"], "ticker": t, "firma": firmen.get(t, t), "modus": modus,
                "signal_datum": iso, "score": round(float(sc), 1), "gewicht": round(w, 4),
                "gruende": gr, "typen": typen, "komp": {x: round(v, 3) for x, v in k.items()},
                "merkmale": mk, "signal_kurs": c, "atr": a, "equity_signal": eq, "status": "geplant",
                "limit": c * (1 + par.MAX_GAP_EINSTIEG), "stopp_hinweis": c - par.STOPP_ATR_START * a,
                "ziel_hinweis": (c + par.GEWINNZIEL_ATR * a) if getattr(par, "GEWINNZIEL_ATR", 0) else None,
                "parameter": {"SCHWELLE": schwelle, "HALTEDAUER": par.HALTEDAUER, "STOPP_ATR_NACHZIEH": par.STOPP_ATR_NACHZIEH,
                              "STOPP_ATR_START": par.STOPP_ATR_START, "GEWINNZIEL_ATR": getattr(par, "GEWINNZIEL_ATR", 0)},
            })
            status[t] = "KAUFSIGNAL – Kauf zur nächsten Eröffnung"
            dep["naechste_id"] += 1
            neu += 1
            n_aktiv += 1
    if status_merken:
        dep["kandidaten_status"] = status
    dep["letzter_tag"] = iso
    return dep


def _schliessen(tr, iso, px, grund, K, bench=None, idx=None):
    tr.update(status="geschlossen", ausstieg_datum=iso, ausstieg_kurs=px, ausstieg_grund=grund,
              ergebnis=(px * (1 - K)) / (tr["einstieg_kurs"] * (1 + K)) - 1, kurs=px)
    tr.pop("verkaufen_geplant", None)
    if bench is not None and idx is not None:
        try:
            b0 = float(bench.iat[idx.get_loc(pd.Timestamp(tr["einstieg_datum"]))])
            b1 = float(bench.iat[idx.get_loc(pd.Timestamp(iso))])
            tr["markt"] = b1 / b0 - 1
            tr["ueber_markt"] = tr["ergebnis"] - tr["markt"]
        except (KeyError, ZeroDivisionError):
            pass


def kandidaten(s, d, n=5, score=None, par=None):
    score = s["score"] if score is None else score
    reihe = score.iloc[d].sort_values(ascending=False).head(n)
    return [(t, float(v), komponenten(s, d, t, par)) for t, v in reihe.items() if v > 0]
