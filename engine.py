# -*- coding: utf-8 -*-
"""
Signal-Engine und Musterdepot.

1. Für jede Aktie und jeden Tag wird ein Überzeugungs-Score (0–100) berechnet:
   Momentum (30 %) + frischer Quartalszahlen-Sprung (40 %) + Insider-Cluster-Kauf (40 %).
   Momentum allein reicht nie – es braucht mindestens einen Auslöser.
2. Liegt der Score über der Schwelle, gibt es EINE Empfehlung, Gewicht 12–35 % je nach Score.
3. Das Musterdepot führt jede Empfehlung aus (Kauf zur nächsten Eröffnung) und verwaltet
   Stopps und Zeitstopp. So siehst du für jede Empfehlung, wie sie ausgegangen ist.
Rückblick und Live-Betrieb laufen durch denselben Code.
"""
import numpy as np
import pandas as pd

JAHR = 252


def atr(H, L, C, n=20):
    v = C.shift(1)
    tr = np.maximum(H - L, np.maximum((H - v).abs(), (L - v).abs()))
    return tr.rolling(n, min_periods=10).mean()


# ---------------------------------------------------------------------------
# Signale
# ---------------------------------------------------------------------------
def _insider(ins, C, elig, cfg):
    I = np.zeros(C.shape)
    info = {}
    if ins is None or ins.empty:
        return pd.DataFrame(I, index=C.index, columns=C.columns), info
    ins = ins[(~ins["plan"].astype(bool)) & (ins["wert"] >= cfg.INSIDER_MIN_KAUF) & ins["ticker"].isin(C.columns)].copy()
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
            rollen = " ".join(f["rolle"].astype(str)).upper()
            if any(k in rollen for k in ("CEO", "CFO", "CHIEF", "PRESIDENT")):
                s = min(1.0, s + 0.1)
            avg = wert / (f["wert"] / f["preis"].replace(0, np.nan)).sum()
            if not np.isfinite(avg) or Cn[d, j] < 0.9 * avg:      # Kurs schon deutlich unter Insider-Preis
                continue
            I[d, j] = s
            info[(d, t)] = {"n": int(n), "wert": float(wert),
                            "rollen": sorted({str(r) for r in f["rolle"] if str(r) not in ("", "nan")})[:3]}
    return pd.DataFrame(I, index=C.index, columns=C.columns), info


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

    # PEAD: Kurssprung mit Volumen, der gehalten wird
    v1 = C.shift(1)
    plus, gap = C / v1 - 1, O / v1 - 1
    vf = V / V.rolling(50, min_periods=30).mean().shift(1)
    ev = (gap >= cfg.PEAD_GAP_MIN) & (plus >= cfg.PEAD_TAGESPLUS_MIN) & (vf >= cfg.PEAD_VOLUMEN_FAKTOR) & elig
    pos = np.arange(len(C), dtype=float)
    lim = cfg.PEAD_MAX_ALTER
    letzte = pd.DataFrame(np.where(ev.to_numpy(), pos[:, None], np.nan), index=C.index, columns=C.columns).ffill(limit=lim)
    seit = letzte.rsub(pos, axis=0)
    evC = C.where(ev).ffill(limit=lim)
    evVF = vf.where(ev).ffill(limit=lim)
    evPlus = plus.where(ev).ffill(limit=lim)
    frisch = pd.DataFrame(np.where(seit <= cfg.PEAD_FRISCH, 1.0, np.where(seit <= lim, 0.6, 0.0)),
                          index=C.index, columns=C.columns)
    P = (frisch * (C >= evC) * (0.5 + evVF / 10).clip(upper=1.0)).fillna(0.0)

    I, iinfo = _insider(insider, C, elig, cfg) if cfg.INSIDER_AKTIV else (C * 0.0, {})

    score = (100 * (cfg.GEWICHT_MOMENTUM * M + cfg.GEWICHT_PEAD * P + cfg.GEWICHT_INSIDER * I)).where(elig, 0.0).clip(upper=100)
    rc = kurse["Close"][regime_ticker].ffill() if regime_ticker in kurse["Close"] else C.mean(axis=1)
    regime = (rc > rc.rolling(200).mean()).reindex(C.index).fillna(True)
    return {"O": O, "H": H, "L": L, "C": C, "A": A, "M": M, "P": P, "I": I, "score": score, "regime": regime,
            "letzte": letzte, "evPlus": evPlus, "evVF": evVF, "iinfo": iinfo}


def gruende(s, d, t):
    g = []
    p = s["P"].iat[d, s["P"].columns.get_loc(t)]
    if p > 0:
        j = s["C"].columns.get_loc(t)
        ev_d = s["C"].index[int(s["letzte"].iat[d, j])]
        g.append(f"Kurssprung +{s['evPlus'].iat[d, j] * 100:.0f} % am {ev_d:%d.%m.} "
                 f"({s['evVF'].iat[d, j]:.0f}× Volumen), Niveau gehalten")
    inf = s["iinfo"].get((d, t))
    if inf:
        rollen = f" ({', '.join(inf['rollen'])})" if inf["rollen"] else ""
        wert = f"{inf['wert'] / 1e6:.2f} Mio." if inf["wert"] >= 1e6 else f"{inf['wert'] / 1e3:.0f} Tsd."
        g.append(f"{inf['n']} Insider kauften für {wert.replace('.', ',', 1) if 'Mio' in wert else wert} $ eigene Aktien{rollen}")
    m = s["M"].iat[d, s["M"].columns.get_loc(t)]
    if m > 0:
        g.append(f"Aufwärtstrend, stärker als {m * 100:.0f} % aller Aktien")
    return g


def gewicht(score, stop_pct, schwelle, cfg):
    x = np.clip((score - schwelle) / max(90 - schwelle, 1), 0, 1)
    w = cfg.GEWICHT_MIN + x * (cfg.GEWICHT_MAX - cfg.GEWICHT_MIN)
    return float(min(w, cfg.MAX_VERLUST_PRO_TRADE / max(stop_pct, 1e-6)))


# ---------------------------------------------------------------------------
# Musterdepot
# ---------------------------------------------------------------------------
def neues_depot():
    return {"version": 2, "cash": 100.0, "trades": [], "kurve": [], "naechste_id": 1,
            "letzter_tag": None, "live_seit": None, "start": None}


def _equity(dep, s, d):
    wert = dep["cash"]
    for tr in dep["trades"]:
        if tr["status"] == "offen":
            wert += tr["stueck"] * float(s["C"][tr["ticker"]].iat[d])
    return wert


def tag_verarbeiten(dep, s, d, cfg, modus, firmen, bench=None, pruefe_pead=None):
    """Einen Handelstag d (Index-Position) abarbeiten: Ausführungen, Stopps, neue Signale."""
    O, H, L, C, A = s["O"], s["H"], s["L"], s["C"], s["A"]
    datum = C.index[d]
    iso = datum.date().isoformat()
    K = cfg.KOSTEN
    eq_vortag = dep["kurve"][-1][1] if dep["kurve"] else 100.0

    # 1) geplante Verkäufe zur Eröffnung
    for tr in dep["trades"]:
        if tr["status"] == "offen" and tr.get("verkaufen_geplant"):
            px = float(O[tr["ticker"]].iat[d])
            dep["cash"] += tr["stueck"] * px * (1 - K)
            _schliessen(tr, iso, px, tr["verkaufen_geplant"], K)

    # 2) geplante Käufe zur Eröffnung
    for tr in dep["trades"]:
        if tr["status"] != "geplant":
            continue
        o = float(O[tr["ticker"]].iat[d])
        if not np.isfinite(o) or o > tr["signal_kurs"] * (1 + cfg.MAX_GAP_EINSTIEG):
            tr.update(status="verpasst", ausstieg_grund="Eröffnung zu hoch – ausgelassen", ausstieg_datum=iso)
            continue
        invest = min(tr["gewicht"] * tr["equity_signal"], dep["cash"])
        tr["stueck"] = invest / (o * (1 + K))
        dep["cash"] -= tr["stueck"] * o * (1 + K)
        tr.update(status="offen", einstieg_datum=iso, einstieg_kurs=o, hoechst=o, tage=0,
                  stopp=o - cfg.STOPP_ATR_START * tr["atr"])

    # 3) offene Positionen: Stopp, Nachziehen, Zeitstopp
    for tr in dep["trades"]:
        if tr["status"] != "offen" or tr.get("verkaufen_geplant"):
            continue
        t = tr["ticker"]
        tr["stopp_vortag"] = tr["stopp"]
        lo, op = float(L[t].iat[d]), float(O[t].iat[d])
        if lo <= tr["stopp"]:
            px = min(op, tr["stopp"])
            dep["cash"] += tr["stueck"] * px * (1 - K)
            _schliessen(tr, iso, px, "Stopp", K)
            continue
        c, a = float(C[t].iat[d]), float(A[t].iat[d])
        tr["hoechst"] = max(tr["hoechst"], c)
        if np.isfinite(a):
            tr["stopp"] = max(tr["stopp"], tr["hoechst"] - cfg.STOPP_ATR_NACHZIEH * a)
        tr["tage"] += 1
        tr["kurs"] = c
        if tr["tage"] >= cfg.HALTEDAUER:
            tr["verkaufen_geplant"] = f"Zeitstopp ({cfg.HALTEDAUER} Tage)"

    eq = _equity(dep, s, d)
    b = float(bench.iat[d]) if bench is not None and np.isfinite(bench.iat[d]) else None
    dep["kurve"].append([iso, round(eq, 4), b, modus])

    # 4) neue Empfehlung(en) auf Basis des heutigen Schlusskurses
    schwelle = cfg.SCHWELLE if bool(s["regime"].iat[d]) else cfg.SCHWELLE_RISK_OFF
    reihe = s["score"].iloc[d]
    kand = reihe[reihe >= schwelle].sort_values(ascending=False)
    belegt = {tr["ticker"] for tr in dep["trades"] if tr["status"] in ("offen", "geplant")}
    kuerzlich = {tr["ticker"] for tr in dep["trades"] if tr.get("ausstieg_datum")
                 and (datum - pd.Timestamp(tr["ausstieg_datum"])).days < 14}
    neu = 0
    for t, sc in kand.items():
        if neu >= cfg.MAX_NEU_PRO_TAG:
            break
        if t in belegt or t in kuerzlich:
            continue
        aktiv = [tr for tr in dep["trades"] if tr["status"] in ("offen", "geplant")]
        if len(aktiv) >= cfg.MAX_POSITIONEN:
            break
        reserviert = sum(tr["gewicht"] * tr["equity_signal"] for tr in aktiv if tr["status"] == "geplant")
        frei = (dep["cash"] - reserviert) / eq
        if frei < cfg.MIN_CASH_FUER_KAUF:
            break
        j = s["P"].columns.get_loc(t)
        if pruefe_pead is not None and s["P"].iat[d, j] > 0:
            ev_d = s["C"].index[int(s["letzte"].iat[d, j])].date()
            if not pruefe_pead(t, ev_d):
                sc = sc - 100 * cfg.GEWICHT_PEAD * s["P"].iat[d, j]
                if sc < schwelle:
                    continue
        c, a = float(C[t].iat[d]), float(A[t].iat[d])
        if not (np.isfinite(c) and np.isfinite(a) and c > 0):
            continue
        w = min(gewicht(sc, cfg.STOPP_ATR_START * a / c, schwelle, cfg), frei)
        dep["trades"].append({
            "id": dep["naechste_id"], "ticker": t, "firma": firmen.get(t, t), "modus": modus,
            "signal_datum": iso, "score": round(float(sc), 1), "gewicht": round(w, 4),
            "gruende": gruende(s, d, t), "signal_kurs": c, "atr": a, "equity_signal": eq,
            "status": "geplant", "limit": c * (1 + cfg.MAX_GAP_EINSTIEG), "stopp_hinweis": c - cfg.STOPP_ATR_START * a,
        })
        dep["naechste_id"] += 1
        neu += 1
    dep["letzter_tag"] = iso
    return dep


def _schliessen(tr, iso, px, grund, K):
    tr.update(status="geschlossen", ausstieg_datum=iso, ausstieg_kurs=px, ausstieg_grund=grund,
              ergebnis=(px * (1 - K)) / (tr["einstieg_kurs"] * (1 + K)) - 1)
    tr.pop("verkaufen_geplant", None)


def kandidaten(s, d, n=5):
    reihe = s["score"].iloc[d].sort_values(ascending=False).head(n)
    return [(t, float(v)) for t, v in reihe.items() if v > 0]
