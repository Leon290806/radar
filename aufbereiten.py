# -*- coding: utf-8 -*-
"""Bereitet alle Daten fürs Dashboard als ein JSON-Objekt auf (das Dashboard rendert daraus im Browser)."""
import datetime as dt
import math

import numpy as np
import pandas as pd

import daten
import engine
import kennzahlen as kz

TAGE_DETAIL = 260


def _r(x, n=4):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, n) if math.isfinite(x) else None


def _liste(serie, n=2):
    return [_r(v, n) for v in serie]


def _sauber(o):
    """Rekursiv JSON-tauglich machen (NaN -> None, numpy -> Python)."""
    if isinstance(o, dict):
        return {str(k): _sauber(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sauber(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return _r(o, 6)
    if isinstance(o, (pd.Timestamp, dt.date)):
        return o.isoformat()[:10]
    return o


# ---------------------------------------------------------------------------
# Markt
# ---------------------------------------------------------------------------
def marktlage(C_alle, benchmarks):
    out = []
    for name, t in [("S&P 500", "^GSPC")] + [(n, t) for n, t in benchmarks if n != "S&P 500"]:
        if t not in C_alle or C_alle[t].dropna().shape[0] < 210:
            continue
        c = C_alle[t].ffill().dropna()
        sma = c.rolling(200).mean()
        out.append({"name": name, "ticker": t, "kurs": _r(c.iloc[-1], 2), "abst": _r(c.iloc[-1] / sma.iloc[-1] - 1),
                    "auf": bool(c.iloc[-1] > sma.iloc[-1]), "m1": _r(c.iloc[-1] / c.iloc[-22] - 1),
                    "ytd": _r(c.iloc[-1] / c[c.index.year < c.index[-1].year].iloc[-1] - 1) if (c.index.year < c.index[-1].year).any() else None})
    return out


# ---------------------------------------------------------------------------
# Insider
# ---------------------------------------------------------------------------
def insider_daten(ins, status, s, firmen, cfg, score):
    """Feed (jede Transaktion mit Auffälligkeit) und Rangliste der auffälligsten Kauf-Aktivitäten."""
    C = s["C"]
    ins = s.get("insider") if s.get("insider") is not None else ins
    if ins is None or ins.empty:
        return {"status": status, "feed": [], "cluster": []}
    if "firma" not in ins.columns:
        ins = engine.insider_merkmale(ins)
    ende = pd.Timestamp(C.index[-1])
    df = ins[pd.to_datetime(ins["datum"]) > ende - pd.Timedelta(days=cfg.INSIDER_FEED_TAGE)].copy()
    df = df[((df["typ"] == "Kauf") & (df["wert"] >= 10_000)) | ((df["typ"] == "Verkauf") & (df["wert"] >= cfg.INSIDER_FEED_MIN_VERKAUF))]
    kurs = {t: float(C[t].dropna().iloc[-1]) for t in df["ticker"].unique() if t in C.columns and C[t].notna().any()}
    sc = {t: float(score[t].iloc[-1]) for t in df["ticker"].unique() if t in score.columns}
    hoch = C.iloc[-252:].max()
    umsatz = s["umsatz"].iloc[-1] if "umsatz" in s else pd.Series(dtype=float)
    abst = lambda t: (kurs[t] / hoch[t] - 1) if t in kurs and t in hoch.index and hoch[t] > 0 else None
    df = df.sort_values(["datum", "wert"], ascending=[False, False]).head(1500)
    feed = []
    for z in df.itertuples():
        k = kurs.get(z.ticker)
        a = gr = None
        if z.typ == "Kauf" and not z.plan:
            a, gr = engine.insider_bewertung(df.loc[[z.Index]], umsatz.get(z.ticker), abst(z.ticker))
        feed.append({"d": pd.Timestamp(z.datum).date().isoformat(),
                     "h": pd.Timestamp(z.handel).date().isoformat() if pd.notna(z.handel) else None,
                     "t": z.ticker, "f": firmen.get(z.ticker, z.ticker), "n": str(z.name), "r": str(z.rolle)[:60], "k": z.kat,
                     "typ": z.typ, "st": _r(z.stueck, 0), "p": _r(z.preis, 2), "w": _r(z.wert, 0), "cur": z.waehrung,
                     "plan": bool(z.plan), "land": z.land, "kurs": _r(k, 2), "firma": bool(z.firma),
                     "seit": _r(k / z.preis - 1) if k and z.preis and z.preis > 0 else None, "score": _r(sc.get(z.ticker), 1),
                     "a": _r(a, 0), "ag": gr or []})
    # Rangliste: alle echten Käufe der letzten Wochen je Aktie gemeinsam bewertet
    kaeufe = df[(df["typ"] == "Kauf") & ~df["plan"].astype(bool)]
    cluster = []
    for t, g in kaeufe.groupby("ticker"):
        pk, gr = engine.insider_bewertung(g, umsatz.get(t), abst(t))
        n = g["insider"].nunique()
        wert = float(g["wert"].sum())
        avg = wert / (g["wert"] / g["preis"].replace(0, np.nan)).sum()
        k = kurs.get(t)
        seit = k / avg - 1 if k and avg and np.isfinite(avg) else None
        imax = float(s["I"][t].iloc[-cfg.INSIDER_FENSTER:].max()) if t in s["I"].columns else 0.0
        cluster.append({"t": t, "f": firmen.get(t, t), "n": int(n), "w": _r(wert, 0), "cur": g["waehrung"].iloc[0],
                        "kat": sorted(set(g["kat"])), "namen": sorted(set(g["name"].astype(str)))[:4],
                        "letzte": pd.Timestamp(g["datum"].max()).date().isoformat(), "avg": _r(avg, 2), "kurs": _r(k, 2),
                        "seit": _r(seit), "land": g["land"].iloc[0], "staerke": _r(pk, 0), "gruende": gr,
                        "label": engine.auffaellig_text(pk), "score": _r(sc.get(t), 1), "imax": _r(imax, 2)})
    cluster.sort(key=lambda x: (x["staerke"], x["w"]), reverse=True)
    return {"status": status, "feed": feed, "cluster": cluster[:40], "grenze": getattr(cfg, "INSIDER_MIN_AUFFAELLIG", 50),
            "n_auff": sum(1 for c in cluster if c["staerke"] >= getattr(cfg, "INSIDER_MIN_AUFFAELLIG", 50))}


# ---------------------------------------------------------------------------
# Ticker-Details
# ---------------------------------------------------------------------------
def ticker_details(ticks, s, score, ins, dep, firmen, status_heute, par):
    C, V = s["C"], s["V"]
    n = len(C)
    a = max(0, n - TAGE_DETAIL)
    tdates = [d.date().isoformat() for d in C.index[a:]]
    rang = s["M"].iloc[-1]
    out = {}
    for t in ticks:
        if t not in C.columns or C[t].iloc[a:].notna().sum() < 20:
            continue
        c = C[t].iloc[a:]
        ev = []
        for i, (pz, ng, ho) in enumerate(zip(s["ev"][t].iloc[a:], s["NEG"][t].iloc[a:], s["HO"][t].iloc[a:].diff().fillna(0))):
            j = a + i
            if pz:
                ev.append({"i": i, "typ": "sprung", "txt": f"Kurssprung {s['plus'][t].iat[j] * 100:+.1f} % ({s['vf'][t].iat[j]:.1f}× Volumen)".replace(".", ",")})
            if ng:
                ev.append({"i": i, "typ": "neg", "txt": f"Kursrutsch {s['plus'][t].iat[j] * 100:+.1f} % ({s['vf'][t].iat[j]:.1f}× Volumen)".replace(".", ",")})
            if ho > 0:
                ev.append({"i": i, "typ": "hoch", "txt": "Ausbruch auf 52-Wochen-Hoch mit Volumen"})
        itx = []
        if ins is not None and len(ins):
            g = ins[(ins["ticker"] == t) & (pd.to_datetime(ins["datum"]) >= C.index[a])].sort_values("datum", ascending=False)
            for z in g.head(60).itertuples():
                i = int(C.index[a:].searchsorted(pd.Timestamp(z.datum)))
                if i >= len(c):
                    i = len(c) - 1
                itx.append({"i": i, "d": pd.Timestamp(z.datum).date().isoformat(), "n": str(z.name), "k": z.kat, "r": str(z.rolle)[:50],
                            "typ": z.typ, "w": _r(z.wert, 0), "p": _r(z.preis, 2), "cur": z.waehrung, "plan": bool(z.plan)})
        trades = []
        for tr in dep["trades"]:
            if tr["ticker"] != t:
                continue
            ein = C.index[a:].searchsorted(pd.Timestamp(tr["einstieg_datum"])) if tr.get("einstieg_datum") else None
            aus = C.index[a:].searchsorted(pd.Timestamp(tr["ausstieg_datum"])) if tr.get("ausstieg_datum") and tr["status"] == "geschlossen" else None
            trades.append({"id": tr["id"], "ein": int(ein) if ein is not None and tr.get("einstieg_datum", "") >= tdates[0] else None,
                           "aus": int(aus) if aus is not None and tr["ausstieg_datum"] >= tdates[0] else None})
        j = C.columns.get_loc(t)
        k = engine.komponenten(s, n - 1, t)
        hoch52 = C[t].iloc[-252:].max()
        out[t] = {
            "f": firmen.get(t, t), "cur": daten.waehrung(t), "a": a, "c": _liste(c), "sma": _liste(s["sma200"][t].iloc[a:]),
            "score": _liste(score[t].iloc[a:], 0), "ev": ev, "ins": itx, "trades": trades,
            "komp": {x: _r(v, 3) for x, v in k.items()}, "sc": _r(score[t].iloc[-1], 1), "status": status_heute.get(t),
            "fakten": {"kurs": _r(c.iloc[-1], 2), "d1": _r(c.iloc[-1] / c.iloc[-2] - 1) if len(c) > 1 else None,
                       "m1": _r(s["m1"][t].iloc[-1]), "m6": _r(C[t].iloc[-1] / C[t].iloc[-127] - 1) if n > 127 else None,
                       "m12": _r(C[t].iloc[-1] / C[t].iloc[-253] - 1) if n > 253 else None,
                       "vola": _r(s["vola"][t].iloc[-1]), "dist200": _r(s["dist200"][t].iloc[-1]),
                       "vom_hoch": _r(c.iloc[-1] / hoch52 - 1), "rang": _r(rang.get(t)), "umsatz": _r((C[t] * V[t]).iloc[-50:].mean(), 0),
                       "neg_sperre": bool(s["neg_sperre"][t].iloc[-1])},
        }
        if k["P"] > 0:
            ev_d = C.index[int(s["letzte"].iat[n - 1, j])]
            out[t]["sprung"] = {"d": ev_d.date().isoformat(), "plus": _r(s["evPlus"][t].iloc[-1]), "vf": _r(s["evVF"][t].iloc[-1], 1),
                                "tage": int(n - 1 - s["letzte"].iat[n - 1, j])}
        inf = s["iinfo"].get((n - 1, t))
        if inf:
            out[t]["ins_sig"] = {"n": inf["n"], "w": _r(inf["wert"], 0), "kat": inf["kat"], "a": inf.get("punkte"),
                                 "g": inf.get("gruende", [])}
    return tdates, out


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------
def dashboard_daten(dep, s, score, par, cfg, C_alle, aktionen, kand, ins, ins_status, firmen, oddlot, hinweise, demo, eurusd):
    kurve = dep["kurve"]
    dates = [k[0] for k in kurve]
    idx = pd.to_datetime(dates)
    eq = pd.Series([k[1] for k in kurve], index=idx)
    eq_n = eq / eq.iloc[0] * 100
    live_idx = next((i for i, k in enumerate(kurve) if k[3] == "Live"), -1)

    benches, bench_reihen = [], {}
    for name, t in cfg.BENCHMARKS:
        if t in C_alle and C_alle[t].notna().any():
            b = C_alle[t].reindex(idx).ffill()
            if b.notna().sum() < 10:
                continue
            b0 = b.dropna().iloc[0]
            bench_reihen[name] = b
            benches.append({"name": name, "ticker": t, "v": _liste(b / b0 * 100)})
    kern = [100.0]
    for i in range(1, len(kurve)):
        r = kurve[i - 1][5] if len(kurve[i - 1]) > 5 else 1
        if r and kurve[i][2] and kurve[i - 1][2]:
            kern.append(kern[-1] * kurve[i][2] / kurve[i - 1][2])
        else:
            kern.append(kern[-1] * (1 + par.GELDMARKT_ZINS) ** (1 / 252))
    kern_s = pd.Series(kern, index=idx)

    stats = {"radar": kz.reihe_kennzahlen(eq, par.GELDMARKT_ZINS), "bench": {}, "relativ": {},
             "trades": kz.trade_kennzahlen(dep["trades"], par.KOSTEN), "monate": kz.monatstabelle(eq),
             "kern": kz.reihe_kennzahlen(kern_s, par.GELDMARKT_ZINS)}
    for name, b in bench_reihen.items():
        stats["bench"][name] = kz.reihe_kennzahlen(b, par.GELDMARKT_ZINS)
        stats["relativ"][name] = kz.relativ(eq, b)
    dd = (eq / eq.cummax() - 1)

    # Trades
    trades = []
    for tr in sorted(dep["trades"], key=lambda t: (t["signal_datum"], t["id"]), reverse=True):
        x = {k: tr.get(k) for k in ("id", "ticker", "firma", "modus", "signal_datum", "score", "gewicht", "gruende", "typen",
                                     "status", "einstieg_datum", "einstieg_kurs", "ausstieg_datum", "ausstieg_kurs",
                                     "ausstieg_grund", "ergebnis", "markt", "ueber_markt", "stopp", "stopp_start", "kurs",
                                     "tage", "limit", "stopp_hinweis", "hoechst", "komp", "merkmale", "parameter", "signal_kurs")}
        x["cur"] = daten.waehrung(tr["ticker"])
        if tr["status"] == "offen":
            x["anteil"] = tr["stueck"] * tr["kurs"] / eq.iloc[-1]
            x["lauf"] = tr["kurs"] / tr["einstieg_kurs"] - 1
        trades.append(x)
    offen = [t for t in trades if t["status"] == "offen"]
    kern_w = max(0.0, 1 - sum(t["anteil"] for t in offen))

    # Aktionen
    akt = []
    for a in aktionen:
        tr = a["trade"]
        akt.append({"typ": a["typ"], "id": tr["id"], "ticker": tr["ticker"], "eur": _r(a.get("eur"), 0),
                    "stueck": a.get("stueck"), "text": tr.get("verkaufen_geplant") or tr.get("ausstieg_grund")})

    # Scanner
    st = dep.get("kandidaten_status", {})
    schwelle = par.SCHWELLE if bool(s["regime"].iat[-1]) else par.SCHWELLE_RISK_OFF
    scanner = []
    for t, sc, k in kand:
        stt = st.get(t)
        if stt is None:
            stt = (f"Score {sc:.0f} – es fehlen {schwelle - sc:.0f} Punkte" if sc < schwelle else "über der Schwelle")
        scanner.append({"t": t, "f": firmen.get(t, t), "sc": _r(sc, 1), "komp": {x: _r(v, 3) for x, v in k.items()}, "status": stt,
                        "kurs": _r(s["C"][t].iloc[-1], 2), "m1": _r(s["m1"][t].iloc[-1]), "m12": _r(s["m12"][t].iloc[-1]),
                        "kauf": stt.startswith("KAUFSIGNAL")})

    insd = insider_daten(ins, ins_status, s, firmen, cfg, score)
    ticks = list(dict.fromkeys([x["t"] for x in scanner] + [t["ticker"] for t in trades]
                               + [c["t"] for c in insd["cluster"][:30]] + [f["t"] for f in insd["feed"][:80]]))
    tdates, details = ticker_details(ticks, s, score, ins, dep, firmen, st, par)

    regime_txt = marktlage(C_alle, cfg.BENCHMARKS)
    L = dep.get("lernen") or {}
    par_d = {k: getattr(par, k) for k in ("SCHWELLE", "SCHWELLE_RISK_OFF", "HALTEDAUER", "STOPP_ATR_START", "STOPP_ATR_NACHZIEH",
                                           "GEWICHT_MOMENTUM", "GEWICHT_PEAD", "GEWICHT_INSIDER", "GEWICHT_HOCH",
                                           "MAX_POSITIONEN", "MAX_NEU_PRO_TAG", "GEWICHT_MIN", "GEWICHT_MAX",
                                           "MAX_VERLUST_PRO_TRADE", "KOSTEN", "LERN_INTERVALL", "LERN_FENSTER",
                                           "LERN_MARGE", "LERN_MIN_TRADES", "FILTER", "MAX_GAP_EINSTIEG",
                                           "MAX_JE_BRANCHE", "MAX_JE_SEKTOR", "INSIDER_MIN_AUFFAELLIG")}
    return _sauber({
        "meta": {"stand": dep["letzter_tag"], "erstellt": dt.datetime.now().strftime("%d.%m.%Y %H:%M"), "demo": demo,
                 "start": dates[0], "live_seit": dep.get("live_seit"), "tage_live": sum(1 for k in kurve if k[3] == "Live"),
                 "regime": bool(s["regime"].iat[-1]), "regime_abst": _r(s["regime_abst"].iloc[-1]), "schwelle": schwelle,
                 "zeige_euro": bool(par.ZEIGE_EURO), "kapital": par.KAPITAL_EUR, "eurusd": _r(eurusd, 4),
                 "universum": int(s["C"].shape[1])},
        "markt": regime_txt, "dates": dates, "eq": _liste(eq_n), "bench": benches, "kern": _liste(pd.Series(kern) / kern[0] * 100),
        "invest": [k[4] for k in kurve], "dd": _liste(dd, 4), "live_idx": live_idx,
        "trades": trades, "kern_w": kern_w, "aktionen": akt, "stats": stats, "scanner": scanner,
        "insider": insd, "tdates": tdates, "tick": details, "lernen": L, "par": par_d, "oddlot": oddlot, "hinweise": hinweise,
    })
