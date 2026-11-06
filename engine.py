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
def _insider(ins, C, cfg):
    I = np.zeros(C.shape)
    info = {}
    if ins is None or ins.empty:
        return pd.DataFrame(I, index=C.index, columns=C.columns), info
    ins = ins[(ins["typ"] == "Kauf") & (~ins["plan"].astype(bool)) & (ins["wert"] >= cfg.INSIDER_MIN_KAUF)
              & ins["ticker"].isin(C.columns)].copy()
    if ins.empty:
        return pd.DataFrame(I, index=C.index, columns=C.columns), info
    idx = C.index
    # verfügbar ab dem Handelstag NACH dem Meldedatum (kein Blick in die Zukunft)
    ins["pos"] = idx.searchsorted(pd.to_datetime(ins["datum"]).values, side="right")
    ins = ins[ins["pos"] < len(idx)]
    W = cfg.INSIDER_FENSTER
    Cn = C.to_numpy()
    for t, g in ins.groupby("ticker"):
        j = C.columns.get_loc(t)
        tage = sorted({d for p in g["pos"].unique() for d in range(p, min(p + W, len(idx)))})
        for d in tage:
            f = g[(g["pos"] <= d) & (g["pos"] > d - W)]
            n, wert = f["insider"].nunique(), f["wert"].sum()
            if n >= 3 and wert >= 1e6:
                s = 1.0
            elif n >= 3 or (n >= 2 and wert >= 5e5):
                s = 0.75
            elif n >= 2 and wert >= 1e5:
                s = 0.5
            elif wert >= 1e6:
                s = 0.4
            else:
                continue
            if f["kat"].isin(["CEO", "CFO"]).any():
                s = min(1.0, s + 0.1)
            avg = wert / (f["wert"] / f["preis"].replace(0, np.nan)).sum()
            if not np.isfinite(avg) or Cn[d, j] < 0.9 * avg:      # Kurs schon deutlich unter Insider-Preis
                continue
            I[d, j] = s
            info[(d, t)] = {"n": int(n), "wert": float(wert), "kat": sorted(set(f["kat"]))[:3]}
    return pd.DataFrame(I, index=C.index, columns=C.columns), info


def _regime(c):
    c = c.ffill()
    sma = c.rolling(200, min_periods=150).mean()
    return c > sma, c / sma - 1


def berechne_signale(kurse, aktien, insider, cfg, regime_ticker="^GSPC"):
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

    I, iinfo = _insider(insider, C, cfg) if cfg.INSIDER_AKTIV else (C * 0.0, {})

    rc = kurse["Close"][regime_ticker] if regime_ticker in kurse["Close"] else C.mean(axis=1)
    regime, regime_abst = _regime(rc)
    regime = regime.reindex(C.index).fillna(True)
    s = {"O": O, "H": H, "L": L, "C": C, "V": V, "A": A, "M": M, "P": P, "I": I, "HO": Hs, "NEG": neg,
         "neg_sperre": neg_sperre, "regime": regime, "regime_abst": regime_abst.reindex(C.index),
         "letzte": letzte, "evPlus": evPlus, "evVF": evVF, "iinfo": iinfo, "elig": elig,
         "vola": vola, "dist200": C / sma200 - 1, "m1": m1, "m12": m12, "m6": m6, "sma200": sma200,
         "plus": plus, "vf": vf, "gap": gap, "ev": ev}
    s["score"] = kombiniere(s, cfg)
    return s


def kombiniere(s, par):
    """Score mit den Gewichten aus par zusammensetzen."""
    roh = (par.GEWICHT_MOMENTUM * s["M"] + par.GEWICHT_PEAD * s["P"] + par.GEWICHT_INSIDER * s["I"]
           + par.GEWICHT_HOCH * s["HO"])
    return (100 * roh).where(s["elig"] & ~s["neg_sperre"], 0.0).clip(upper=100)


def komponenten(s, d, t):
    j = s["C"].columns.get_loc(t)
    return {"M": float(s["M"].iat[d, j]), "P": float(s["P"].iat[d, j]), "I": float(s["I"].iat[d, j]),
            "H": float(s["HO"].iat[d, j])}


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


def gruende(s, d, t):
    g = []
    j = s["C"].columns.get_loc(t)
    if s["P"].iat[d, j] > 0:
        ev_d = s["C"].index[int(s["letzte"].iat[d, j])]
        g.append(f"Kurssprung +{s['evPlus'].iat[d, j] * 100:.0f} % am {ev_d:%d.%m.} "
                 f"({s['evVF'].iat[d, j]:.0f}× Volumen), Niveau gehalten")
    inf = s["iinfo"].get((d, t))
    if inf:
        rollen = f" ({', '.join(inf['kat'])})" if inf["kat"] else ""
        wert = (f"{inf['wert'] / 1e6:.2f} Mio." if inf["wert"] >= 1e6 else f"{inf['wert'] / 1e3:.0f} Tsd.").replace(".", ",", 1)
        g.append(f"{inf['n']} Insider kauften für {wert} eigene Aktien{rollen}")
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
VERSION = 4


def neues_depot():
    return {"version": VERSION, "cash": 100.0, "trades": [], "kurve": [], "naechste_id": 1,
            "letzter_tag": None, "live_seit": None, "start": None, "parameter": {}, "lernen": {},
            "kandidaten_status": {}}


def _equity(dep, s, d):
    wert = dep["cash"]
    for tr in dep["trades"]:
        if tr["status"] == "offen":
            wert += tr["stueck"] * float(s["C"][tr["ticker"]].iat[d])
    return wert


def tag_verarbeiten(dep, s, d, par, modus, firmen, bench=None, pruefe_pead=None, score=None, status_merken=False):
    """Einen Handelstag d (Index-Position) abarbeiten: Kern-Rendite, Ausführungen, Stopps, neue Signale.

    Nicht investiertes Geld ("Kern") liegt im S&P-500-ETF, solange der Markt über seiner
    200-Tage-Linie liegt, sonst im Geldmarkt.
    """
    O, L, C, A = s["O"], s["L"], s["C"], s["A"]
    score = s["score"] if score is None else score
    datum = C.index[d]
    iso = datum.date().isoformat()
    K = par.KOSTEN

    # 0) Kern: Rendite auf das freie Geld
    if d > 0 and dep["cash"] > 0:
        if par.KERN_AKTIV and bench is not None and bool(s["regime"].iat[d - 1]) \
                and np.isfinite(bench.iat[d]) and np.isfinite(bench.iat[d - 1]):
            dep["cash"] *= bench.iat[d] / bench.iat[d - 1]
        else:
            dep["cash"] *= (1 + par.GELDMARKT_ZINS) ** (1 / 252)

    # 1) geplante Verkäufe zur Eröffnung
    for tr in dep["trades"]:
        if tr["status"] == "offen" and tr.get("verkaufen_geplant"):
            px = float(O[tr["ticker"]].iat[d])
            dep["cash"] += tr["stueck"] * px * (1 - K)
            _schliessen(tr, iso, px, tr["verkaufen_geplant"], K, bench, C.index)

    # 2) geplante Käufe zur Eröffnung
    for tr in dep["trades"]:
        if tr["status"] != "geplant":
            continue
        o = float(O[tr["ticker"]].iat[d])
        if not np.isfinite(o) or o > tr["signal_kurs"] * (1 + par.MAX_GAP_EINSTIEG):
            tr.update(status="verpasst", ausstieg_grund="Eröffnung zu hoch – ausgelassen", ausstieg_datum=iso)
            continue
        invest = min(tr["gewicht"] * tr["equity_signal"], dep["cash"])
        tr["stueck"] = invest / (o * (1 + K))
        dep["cash"] -= tr["stueck"] * o * (1 + K)
        st0 = o - par.STOPP_ATR_START * tr["atr"]
        tr.update(status="offen", einstieg_datum=iso, einstieg_kurs=o, hoechst=o, tage=0, stopp=st0, kurs=o,
                  stopp_start=st0)

    # 3) offene Positionen: Stopp, Nachziehen, Zeitstopp, Warnsignal
    for tr in dep["trades"]:
        if tr["status"] != "offen" or tr.get("verkaufen_geplant"):
            continue
        t = tr["ticker"]
        tr["stopp_vortag"] = tr["stopp"]
        lo, op = float(L[t].iat[d]), float(O[t].iat[d])
        if lo <= tr["stopp"]:
            px = min(op, tr["stopp"])
            dep["cash"] += tr["stueck"] * px * (1 - K)
            _schliessen(tr, iso, px, "Stopp", K, bench, C.index)
            continue
        c, a = float(C[t].iat[d]), float(A[t].iat[d])
        regeln = tr.get("parameter", {})            # offene Trades behalten die Regeln vom Kauftag
        nz = regeln.get("STOPP_ATR_NACHZIEH", par.STOPP_ATR_NACHZIEH)
        hd = regeln.get("HALTEDAUER", par.HALTEDAUER)
        tr["hoechst"] = max(tr["hoechst"], c)
        if np.isfinite(a):
            tr["stopp"] = max(tr["stopp"], tr["hoechst"] - nz * a)
        tr["tage"] += 1
        tr["kurs"] = c
        if par.EXIT_NEG_SPRUNG and bool(s["NEG"][t].iat[d]):
            tr["verkaufen_geplant"] = "Negativer Kurssprung"
        elif tr["tage"] >= hd:
            tr["verkaufen_geplant"] = f"Zeitstopp ({hd} Tage)"

    eq = _equity(dep, s, d)
    b = float(bench.iat[d]) if bench is not None and np.isfinite(bench.iat[d]) else None
    investiert = 1 - dep["cash"] / eq if eq > 0 else 0.0
    dep["kurve"].append([iso, round(eq, 4), b, modus, round(investiert, 3), 1 if bool(s["regime"].iat[d]) else 0])

    # 4) neue Empfehlung(en) auf Basis des heutigen Schlusskurses
    schwelle = par.SCHWELLE if bool(s["regime"].iat[d]) else par.SCHWELLE_RISK_OFF
    reihe = score.iloc[d]
    untergrenze = schwelle - 25 if status_merken else schwelle
    kand = reihe[reihe >= untergrenze].sort_values(ascending=False)
    status = {}
    if not kand.empty:
        belegt = {tr["ticker"] for tr in dep["trades"] if tr["status"] in ("offen", "geplant")}
        kuerzlich = {tr["ticker"] for tr in dep["trades"] if tr.get("ausstieg_datum")
                     and (datum - pd.Timestamp(tr["ausstieg_datum"])).days < 14}
        neu = 0
        for t, sc in kand.items():
            if sc < schwelle:
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
            reserviert = sum(tr["gewicht"] * tr["equity_signal"] for tr in aktiv if tr["status"] == "geplant")
            frei = (dep["cash"] - reserviert) / eq
            if frei < par.MIN_CASH_FUER_KAUF:
                status[t] = "Kein freies Kapital"
                continue
            k = komponenten(s, d, t)
            if k["P"] <= 0 and k["I"] <= 0:
                status[t] = "Kein Auslöser: nur Momentum/52W-Hoch – es braucht einen Kurssprung nach Zahlen oder Insider-Käufe"
                continue
            if pruefe_pead is not None and k["P"] > 0:
                ev_d = s["C"].index[int(s["letzte"].iat[d, s["C"].columns.get_loc(t)])].date()
                if not pruefe_pead(t, ev_d):
                    sc = sc - 100 * par.GEWICHT_PEAD * k["P"]
                    k["P"] = 0.0
                    if sc < schwelle or k["I"] <= 0:
                        status[t] = ("Kurssprung kam nicht von Quartalszahlen (z. B. Übernahme/News) – "
                                     f"ohne diesen Baustein nur Score {sc:.0f}")
                        continue
            mk = merkmale(s, d, t, sc)
            ok, grund = filter_ok(mk, par.FILTER)
            if not ok:
                status[t] = f"Gelernter Filter greift: {grund}"
                continue
            c, a = float(C[t].iat[d]), float(A[t].iat[d])
            if not (np.isfinite(c) and np.isfinite(a) and c > 0):
                status[t] = "Kursdaten unvollständig"
                continue
            w = min(gewicht(sc, par.STOPP_ATR_START * a / c, schwelle, par), frei)
            dep["trades"].append({
                "id": dep["naechste_id"], "ticker": t, "firma": firmen.get(t, t), "modus": modus,
                "signal_datum": iso, "score": round(float(sc), 1), "gewicht": round(w, 4),
                "gruende": gruende(s, d, t), "typen": signal_typen(k), "komp": {x: round(v, 3) for x, v in k.items()},
                "merkmale": mk, "signal_kurs": c, "atr": a, "equity_signal": eq, "status": "geplant",
                "limit": c * (1 + par.MAX_GAP_EINSTIEG), "stopp_hinweis": c - par.STOPP_ATR_START * a,
                "parameter": {"SCHWELLE": schwelle, "HALTEDAUER": par.HALTEDAUER, "STOPP_ATR_NACHZIEH": par.STOPP_ATR_NACHZIEH},
            })
            status[t] = "KAUFSIGNAL – Kauf zur nächsten Eröffnung"
            dep["naechste_id"] += 1
            neu += 1
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


def kandidaten(s, d, n=5, score=None):
    score = s["score"] if score is None else score
    reihe = score.iloc[d].sort_values(ascending=False).head(n)
    return [(t, float(v), komponenten(s, d, t)) for t, v in reihe.items() if v > 0]
