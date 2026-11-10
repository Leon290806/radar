# -*- coding: utf-8 -*-
"""
Krypto-Modul: Funding-Rate-Arbitrage (marktneutral), zuerst nur simuliert.

Idee: Coin kaufen (Spot) und gleich viel per Perpetual leerverkaufen. Der Kurs ist abgesichert, man erhält die
Funding-Gebühr, die Hebel-Käufer an Leerverkäufer zahlen (meist positiv, im Hype hoch, im Bärenmarkt ~0 oder negativ).

„Smart“:
  - Rotation: nur die Coins mit der höchsten erwarteten Funding-Rate halten (Signal = Durchschnitt der letzten Tage)
  - Schwelle: nur investieren, wenn es sich nach Kosten lohnt – sonst Stablecoin-Zins
  - Trägheit: nur wechseln, wenn der neue Coin deutlich mehr bringt (Gebühren!)
  - Hebel 1–3× auf die abgesicherte Position; Zwangsschließung wird simuliert, wenn ein Tageshoch über der
    Liquidationsgrenze liegt (Kosten + Neueröffnung)
Daten: Hyperliquid (stündliches Funding, ab 2023) und Binance-Archiv (8-Std.-Funding, ab 2020, inkl. Bärenmarkt 2022).
Alles nur Simulation – es werden keine Orders gesendet.
"""
import datetime as dt
import io
import itertools
import json
import math
import os
import time
import zipfile

import numpy as np
import pandas as pd
import requests

HL = "https://api.hyperliquid.xyz/info"
BV = "https://data.binance.vision/data"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "krypto")
BINANCE_COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC", "DOT", "TRX", "BCH", "ATOM", "NEAR"]
TAG_MS = 86_400_000


def _c(name):
    os.makedirs(CACHE, exist_ok=True)
    return os.path.join(CACHE, name)


def _hl(body, versuche=4):
    for v in range(versuche):
        try:
            r = requests.post(HL, json=body, timeout=30)
            if r.status_code == 429:
                time.sleep(3 * (v + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if v == versuche - 1:
                raise
            time.sleep(2 * (v + 1))
    return None


# ---------------------------------------------------------------------------
# Hyperliquid
# ---------------------------------------------------------------------------
def hl_markt():
    """Aktuelle Funding-Raten aller Hyperliquid-Perps. Rückgabe: DataFrame (coin, funding_h, apr, oi_usd, vol_usd, preis)."""
    meta, ctx = _hl({"type": "metaAndAssetCtxs"})
    zeilen = []
    for u, c in zip(meta["universe"], ctx):
        if u.get("isDelisted"):
            continue
        try:
            f, px = float(c.get("funding") or 0), float(c.get("markPx") or 0)
            zeilen.append({"coin": u["name"], "funding_h": f, "apr": f * 24 * 365, "preis": px,
                           "oi_usd": float(c.get("openInterest") or 0) * px, "vol_usd": float(c.get("dayNtlVlm") or 0),
                           "max_hebel": u.get("maxLeverage")})
        except (TypeError, ValueError):
            continue
    return pd.DataFrame(zeilen)


def _hl_funding(coin, start_ms):
    pfad = _c(f"hl_funding_{coin}.json")
    alt = json.load(open(pfad)) if os.path.exists(pfad) else []
    t0 = (alt[-1]["time"] + 1) if alt else start_ms
    jetzt = int(time.time() * 1000)
    neu = []
    while t0 < jetzt - 3_600_000:
        teil = _hl({"type": "fundingHistory", "coin": coin, "startTime": int(t0)}) or []
        if not teil:
            break
        neu += [{"time": int(x["time"]), "r": float(x["fundingRate"])} for x in teil]
        if len(teil) < 450:
            break
        t0 = int(teil[-1]["time"]) + 1
        time.sleep(0.25)
    if neu:
        alt += neu
        json.dump(alt, open(pfad, "w"))
    return alt


def _hl_kerzen(coin, start_ms):
    pfad = _c(f"hl_kerzen_{coin}.json")
    alt = json.load(open(pfad)) if os.path.exists(pfad) else []
    t0 = (alt[-1]["t"] + TAG_MS) if alt else start_ms
    if t0 < int(time.time() * 1000) - TAG_MS:
        teil = _hl({"type": "candleSnapshot", "req": {"coin": coin, "interval": "1d", "startTime": int(t0),
                                                      "endTime": int(time.time() * 1000)}}) or []
        voll = [{"t": int(k["t"]), "h": float(k["h"]), "c": float(k["c"])} for k in teil if int(k["T"]) < time.time() * 1000]
        if voll:
            alt = [k for k in alt if k["t"] < voll[0]["t"]] + voll
            json.dump(alt, open(pfad, "w"))
    return alt


def lade_hl(n_coins=25, min_vol=20e6, start="2023-06-01"):
    """Tägliche Funding-Summe, Schlusskurs und Tageshoch der liquidesten Hyperliquid-Perps."""
    m = hl_markt()
    coins = list(m[m["vol_usd"] >= min_vol].sort_values("vol_usd", ascending=False)["coin"].head(n_coins))
    start_ms = int(pd.Timestamp(start).timestamp() * 1000)
    F, P, H = {}, {}, {}
    for c in coins:
        try:
            fh = pd.DataFrame(_hl_funding(c, start_ms))
            if fh.empty:
                continue
            fh["tag"] = pd.to_datetime(fh["time"], unit="ms").dt.normalize()
            F[c] = fh.groupby("tag")["r"].sum()
            k = pd.DataFrame(_hl_kerzen(c, start_ms))
            if not k.empty:
                k["tag"] = pd.to_datetime(k["t"], unit="ms").dt.normalize()
                k = k.set_index("tag")
                P[c], H[c] = k["c"], k["h"]
        except Exception:
            continue
    F = pd.DataFrame(F).sort_index()
    heute = pd.Timestamp.utcnow().tz_localize(None).normalize()
    F = F[F.index < heute]                                  # nur vollständige Tage
    return F, pd.DataFrame(P).reindex(F.index), pd.DataFrame(H).reindex(F.index), m


# ---------------------------------------------------------------------------
# Binance-Archiv (öffentliche Monatsdateien, ab 2020)
# ---------------------------------------------------------------------------
def _bv_monat(pfad_url, cache_name):
    pfad = _c(cache_name)
    if os.path.exists(pfad):
        return pd.read_pickle(pfad)
    r = requests.get(pfad_url, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        roh = z.read(z.namelist()[0]).decode()
    df = pd.read_csv(io.StringIO(roh), header=None)
    if not str(df.iloc[0, 0]).replace(".", "").isdigit():
        df = df.iloc[1:].reset_index(drop=True)
    df.to_pickle(pfad)
    return df


def lade_binance(coins=BINANCE_COINS, start="2020-01"):
    monate = pd.period_range(start, pd.Timestamp.utcnow().tz_localize(None) - pd.offsets.MonthBegin(1), freq="M")
    F, P, H = {}, {}, {}
    for c in coins:
        s = f"{c}USDT"
        fz, kz = [], []
        for m in monate:
            try:
                f = _bv_monat(f"{BV}/futures/um/monthly/fundingRate/{s}/{s}-fundingRate-{m}.zip", f"bn_f_{s}_{m}.pkl")
                k = _bv_monat(f"{BV}/spot/monthly/klines/{s}/1d/{s}-1d-{m}.zip", f"bn_k_{s}_{m}.pkl")
            except Exception:
                continue
            if f is not None:
                fz.append(f)
            if k is not None:
                kz.append(k)
        if not fz:
            continue
        f = pd.concat(fz)
        ts = pd.to_numeric(f.iloc[:, 0], errors="coerce")
        f = pd.DataFrame({"tag": pd.to_datetime(ts, unit="ms").dt.normalize(), "r": pd.to_numeric(f.iloc[:, -1], errors="coerce")})
        F[c] = f.dropna().groupby("tag")["r"].sum()
        if kz:
            k = pd.concat(kz)
            t = pd.to_numeric(k.iloc[:, 0], errors="coerce")
            t = np.where(t > 1e14, t / 1000, t)              # Binance nutzt seit 2025 Mikrosekunden
            k = pd.DataFrame({"tag": pd.to_datetime(t, unit="ms").normalize(), "h": pd.to_numeric(k.iloc[:, 2], errors="coerce"),
                              "c": pd.to_numeric(k.iloc[:, 4], errors="coerce")}).dropna().drop_duplicates("tag").set_index("tag")
            P[c], H[c] = k["c"], k["h"]
    F = pd.DataFrame(F).sort_index()
    return F, pd.DataFrame(P).reindex(F.index), pd.DataFrame(H).reindex(F.index)


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
STANDARD = {"N": 3, "LOOKBACK": 3, "SCHWELLE": 0.10, "HEBEL": 2, "TRAEGHEIT": 0.05, "KOSTEN": 0.0015, "STABLE": 0.04,
            "LIQ_KOSTEN": 0.025, "MODUS": "standard", "STAKING": False, "ZINS": False,
            "MARGIN_ZINS": 0.04, "LEIH_ZINS": 0.08}
# Staking-Rendite des gekauften Coins (nur bei Coins, die man staken kann – grobe, vorsichtige Werte)
STAKING_RENDITE = {"ETH": 0.03, "SOL": 0.065}

# Alle Varianten, die nebeneinander laufen. Das Labor wählt je Variante Coins, Signal-Länge und Mindest-Funding.
PROFILE = [
    {"id": "h1", "name": "Sicher · ohne Hebel", "kurz": "1×", "par": {"MODUS": "standard", "HEBEL": 1},
     "text": "Spot kaufen, Perp leerverkaufen, keine Leihe. Kaum Zwangsschließungen."},
    {"id": "h2", "name": "Standard · Hebel 2×", "kurz": "2×", "par": {"MODUS": "standard", "HEBEL": 2},
     "text": "Ein Drittel des Kapitals als Sicherheit auf der Short-Seite, zwei Drittel arbeiten."},
    {"id": "h3", "name": "Offensiv · Hebel 3×", "kurz": "3×", "par": {"MODUS": "standard", "HEBEL": 3},
     "text": "Mehr Kapital arbeitet, aber Zwangsschließung schon ab ca. +30 % Tagesanstieg."},
    {"id": "profi", "name": "Profi · Portfolio-Margin + Staking + Zins", "kurz": "PM 2×",
     "par": {"MODUS": "pm", "HEBEL": 2, "STAKING": True, "ZINS": True},
     "text": "Der gekaufte Coin dient als Sicherheit (Portfolio-Margin), ETH/SOL werden gestakt, Leihe kostet 8 % p.a."},
    {"id": "max", "name": "Maximal · Portfolio-Margin 5×", "kurz": "PM 5×",
     "par": {"MODUS": "pm", "HEBEL": 5, "STAKING": True, "ZINS": True},
     "text": "Fünffache Position mit geliehenem Geld – zeigt, was Hebel bringt und kostet."},
    {"id": "cross", "name": "Cross-Exchange · Hyperliquid vs. Binance", "kurz": "Cross 2×",
     "par": {"MODUS": "cross", "HEBEL": 2},
     "text": "Short-Perp auf Hyperliquid, Long-Perp auf Binance – verdient den Funding-Unterschied, ohne Spot."},
]
GRID = {"N": (1, 3, 5), "LOOKBACK": (1, 3, 7), "SCHWELLE": (0.05, 0.10, 0.20)}


def _auswahl(sj, pos, p):
    """Welche Coins halten? sj = erwartete Funding-Rendite p.a. je Coin (Signal), pos = bisher gehaltene Coins."""
    kand = sorted([(v, c) for c, v in sj.items() if np.isfinite(v) and v >= p["SCHWELLE"]], reverse=True)
    ziel = [c for _, c in kand[:p["N"]]]
    behalten = [c for c in pos if np.isfinite(sj.get(c, np.nan)) and sj[c] >= p["SCHWELLE"] / 2
                and (not ziel or sj[c] >= sj[ziel[-1]] - p["TRAEGHEIT"])]
    return (behalten + [c for c in ziel if c not in behalten])[:p["N"]]


def _aufbau(p):
    """Nominal je Kapital, geliehener Anteil, Sicherheit in USDC und Liquidationsgrenze je nach Modus."""
    h = p["HEBEL"]
    if p["MODUS"] == "pm":                       # Spot dient als Sicherheit; über 1× wird USDC geliehen
        nominal = 0.95 * h
        return nominal, max(0.0, nominal - 1.0), 0.0, 1.2 / h
    if p["MODUS"] == "cross":                    # zwei Perps auf zwei Börsen, je Seite Margin = Nominal / Hebel
        nominal = h / 2
        return nominal, 0.0, 1.0, 0.9 / h
    nominal = h / (h + 1)                        # Spot + Short-Margin
    return nominal, 0.0, nominal / h, 0.9 / h


def simulieren(F, P, H, par, von=None, bis=None, zustand=None, protokoll=False):
    """Tageweise Simulation. F = tägliche Funding-Summe (bei cross: Differenz der Börsen), P/H = Schluss/Tageshoch.
    Signal aus Daten bis gestern, Ertrag heute."""
    p = {**STANDARD, **(par or {})}
    idx = F.index
    a = idx.searchsorted(pd.Timestamp(von)) if von is not None else 0
    b = idx.searchsorted(pd.Timestamp(bis), side="right") if bis is not None else len(idx)
    a = max(a, p["LOOKBACK"] + 1)
    sig = F.rolling(p["LOOKBACK"], min_periods=p["LOOKBACK"]).mean().shift(1) * 365
    Fn, Sn = F.to_numpy(), sig.to_numpy()
    Pn = P.reindex(index=idx, columns=F.columns).to_numpy()
    Hn = H.reindex(index=idx, columns=F.columns).to_numpy()
    cols = list(F.columns)
    ci = {c: k for k, c in enumerate(cols)}
    z = zustand or {"eq": 1.0, "pos": {}}
    eq, pos, meta = z["eq"], dict(z["pos"]), dict(z.get("meta") or {})
    nominal, leihe, margin, liq_grenze = _aufbau(p)
    kurve, ereignisse, gehalten, tage = [], [], [], []
    for d in range(a, b):
        iso = idx[d].date().isoformat()
        sj = {cols[k]: Sn[d, k] for k in range(len(cols)) if np.isfinite(Fn[d, k])}
        neu = _auswahl(sj, pos, p)
        anteil = 1.0 / p["N"]
        kosten = 0.0
        for c in [c for c in pos if c not in neu]:
            kosten += pos[c] * nominal * p["KOSTEN"]
            m = meta.pop(c, {})
            ereignisse.append((idx[d], "raus", c, sj.get(c), m.get("ertrag", 0.0), m.get("seit")))
        for c in [c for c in neu if c not in pos]:
            kosten += anteil * nominal * p["KOSTEN"]
            meta[c] = {"seit": iso, "ertrag": -anteil * nominal * p["KOSTEN"]}
            ereignisse.append((idx[d], "rein", c, sj.get(c), None, None))
        pos = {c: anteil for c in neu}
        ertrag, zeilen = 0.0, []
        for c, w in pos.items():
            k = ci.get(c)
            if k is None:
                continue
            f = Fn[d, k] if np.isfinite(Fn[d, k]) else 0.0
            e = w * nominal * f
            if p["STAKING"] and p["MODUS"] != "cross":
                e += w * nominal * STAKING_RENDITE.get(c, 0.0) / 365
            if p["ZINS"]:
                e += w * margin * p["MARGIN_ZINS"] / 365 - w * leihe * p["LEIH_ZINS"] / 365
            ertrag += e
            meta.setdefault(c, {"seit": iso, "ertrag": 0.0})["ertrag"] += e
            # Zwangsschließung: Tagesbewegung über der Grenze (Short: Anstieg; bei cross auch Absturz für die Long-Seite)
            if d > 0 and np.isfinite(Pn[d - 1, k]) and Pn[d - 1, k] > 0:
                hoch = Hn[d, k] / Pn[d - 1, k] - 1 if np.isfinite(Hn[d, k]) else 0.0
                tief = 1 - Pn[d, k] / Pn[d - 1, k] if (p["MODUS"] == "cross" and np.isfinite(Pn[d, k])) else 0.0
                if max(hoch, tief) >= liq_grenze:
                    kosten += w * nominal * p["LIQ_KOSTEN"]
                    meta[c]["ertrag"] -= w * nominal * p["LIQ_KOSTEN"]
                    ereignisse.append((idx[d], "liquidiert", c, sj.get(c), None, None))
            zeilen.append([c, round(float(f * 365), 4), round(float(e), 6)])
        frei = 1.0 - sum(pos.values())
        ertrag += frei * p["STABLE"] / 365
        eq = float(eq * (1 + ertrag - kosten))
        kurve.append((idx[d], eq))
        gehalten.append(len(pos))
        if protokoll:
            tage.append({"d": iso, "eq": round(eq, 6), "pos": zeilen, "frei": round(frei, 3),
                         "ertrag": round(float(ertrag), 6), "kosten": round(float(kosten), 6)})
    return {"kurve": kurve, "ereignisse": ereignisse, "zustand": {"eq": eq, "pos": pos, "meta": meta}, "tage": tage,
            "investiert": float(np.mean([g > 0 for g in gehalten])) if gehalten else 0.0}


def kennzahlen(kurve):
    if len(kurve) < 20:
        return None
    eq = np.array([k[1] for k in kurve], dtype=float)
    r = np.diff(eq) / eq[:-1]
    jahre = len(eq) / 365
    cagr = (eq[-1] / eq[0]) ** (1 / jahre) - 1 if eq[0] > 0 and eq[-1] > 0 else -1.0
    dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    sharpe = float(r.mean() / r.std() * math.sqrt(365)) if r.std() > 0 else 0.0
    return {"cagr": float(cagr), "maxdd": dd, "sharpe": sharpe, "ziel": float(cagr - 0.5 * abs(dd))}


def jahre_tabelle(kurve):
    s = pd.Series([k[1] for k in kurve], index=pd.DatetimeIndex([k[0] for k in kurve]))
    j = s.resample("YE").last()
    vor = pd.concat([pd.Series([s.iloc[0]]), j.iloc[:-1]]).to_numpy()
    return {str(t.year): round(float(v / a - 1), 4) for t, v, a in zip(j.index, j.to_numpy(), vor)}


def forschen(F, P, H, name, basis=None, grenze=None):
    """Alle Grid-Varianten mit festem Modus/Hebel (basis): gewählt nach Lernteil, geprüft auf Testteil."""
    idx = F.index
    if len(idx) < 200:
        return {"name": name, "fehler": "zu wenig Daten"}
    g = pd.Timestamp(grenze) if grenze is not None else idx[len(idx) * 2 // 3]
    erg = []
    for werte in itertools.product(*GRID.values()):
        par = {**(basis or {}), **dict(zip(GRID.keys(), werte))}
        sim = simulieren(F, P, H, par)
        lern = kennzahlen([k for k in sim["kurve"] if k[0] < g])
        test = kennzahlen([k for k in sim["kurve"] if k[0] >= g])
        erg.append({"par": par, "lern": lern, "test": test, "gesamt": kennzahlen(sim["kurve"]),
                    "liq": sum(1 for e in sim["ereignisse"] if e[1] == "liquidiert"),
                    "wechsel": sum(1 for e in sim["ereignisse"] if e[1] == "rein"), "investiert": sim["investiert"]})
    gueltig = [e for e in erg if e["lern"]]
    bester = max(gueltig, key=lambda e: e["lern"]["ziel"]) if gueltig else None
    sim = simulieren(F, P, H, bester["par"]) if bester else None
    return {"name": name, "von": idx[0].date().isoformat(), "bis": idx[-1].date().isoformat(), "grenze": g.date().isoformat(),
            "coins": list(F.columns), "varianten": sorted(erg, key=lambda e: -(e["lern"] or {}).get("ziel", -9))[:10],
            "bester": bester, "jahre": jahre_tabelle(sim["kurve"]) if sim else {},
            "kurve": [[k[0].date().isoformat(), round(k[1], 5)] for k in sim["kurve"]][::2] if sim else [],
            "funding_jahre": {str(y): round(float(v), 4) for y, v in (F.mean(axis=1) * 365).groupby(F.index.year).mean().items()}}


def bericht(f):
    """Nur Statistik (keine Positionen) fürs Protokoll."""
    if not f or f.get("fehler"):
        return f"{(f or {}).get('name', '?')}: {(f or {}).get('fehler', 'keine Daten')}"
    k = lambda v: "–" if not v else f"{v['cagr'] * 100:+6.1f}% DD{v['maxdd'] * 100:6.1f}% S{v['sharpe']:5.1f}"
    b = f.get("bester") or {}
    return (f"KRYPTO {f['name']} {f['von']}–{f['bis']} (Lern bis {f['grenze']}) · {json.dumps(b.get('par'))} "
            f"Lern {k(b.get('lern'))} | Test {k(b.get('test'))} | Liq {b.get('liq')} · Jahre "
            + " ".join(f"{j}:{v * 100:+.1f}%" for j, v in f["jahre"].items()))


def _r(x, n=4):
    try:
        x = float(x)
        return round(x, n) if np.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _vergleich(kurve, serien):
    """Vergleichsreihen auf die Daten der Kurve legen (Wochenenden mit letztem Kurs), Start = 0 %."""
    if not kurve:
        return {}
    tage = pd.DatetimeIndex([x[0] for x in kurve])
    out = {}
    for name, s in serien.items():
        try:
            s = pd.Series(s).dropna()
            s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
            s = s[~s.index.duplicated()].sort_index()
            w = s.reindex(s.index.union(tage)).ffill().reindex(tage)
            if w.notna().sum() < 2:
                continue
            basis = w.dropna().iloc[0]
            out[name] = [_r(v / basis - 1) if np.isfinite(v) else None for v in w.to_numpy()]
        except Exception:
            continue
    return out


def _cross_daten(F, Fb):
    """Funding-Differenz Hyperliquid minus Binance für gemeinsame Coins (nur Tage mit beiden Daten)."""
    gem = [c for c in F.columns if c in Fb.columns]
    if not gem:
        return pd.DataFrame()
    a, b = F[gem], Fb[gem].reindex(F.index)
    return (a - b).where(a.notna() & b.notna()).dropna(how="all")


def _jetzt(F, zustand, par, letzter):
    p = {**STANDARD, **par}
    sig = (F.tail(p["LOOKBACK"]).mean() * 365).dropna()
    halten = _auswahl(sig.to_dict(), (zustand or {}).get("pos") or {}, p)
    nominal, leihe, margin, liq = _aufbau(p)
    meta = (zustand or {}).get("meta") or {}
    alt = list(((zustand or {}).get("pos") or {}).keys())
    erw = 0.0
    for c in halten:
        e = sig.get(c, 0) * nominal
        if p["STAKING"] and p["MODUS"] != "cross":
            e += STAKING_RENDITE.get(c, 0) * nominal
        if p["ZINS"]:
            e += margin * p["MARGIN_ZINS"] - leihe * p["LEIH_ZINS"]
        erw += e / p["N"]
    erw += (1 - len(halten) / p["N"]) * p["STABLE"]
    return {"ab": (pd.Timestamp(letzter) + pd.Timedelta(days=1)).date().isoformat(), "nominal": nominal, "leihe": leihe,
            "hebel": p["HEBEL"], "modus": p["MODUS"], "liq": liq,
            "halten": [{"coin": c, "signal": _r(sig.get(c)), "anteil": round(1 / p["N"], 4), "seit": (meta.get(c) or {}).get("seit"),
                        "ertrag": _r((meta.get(c) or {}).get("ertrag")),
                        "staking": STAKING_RENDITE.get(c) if p["STAKING"] and p["MODUS"] != "cross" else None} for c in halten],
            "rein": [c for c in halten if c not in alt], "raus": [c for c in alt if c not in halten],
            "erwartet": _r(erw), "schwelle": p["SCHWELLE"], "n": p["N"], "lookback": p["LOOKBACK"]}


def bericht_alle(cfg):
    """Alle Profile rechnen und nur die Statistik ausgeben (für den Forschungs-Workflow)."""
    F, P, H, _ = lade_hl(getattr(cfg, "KRYPTO_COINS", 25))
    Fb, Pb, Hb = lade_binance()
    g = F.index[len(F.index) * 2 // 3]
    z = []
    for pr in PROFILE:
        D = _cross_daten(F, Fb) if pr["par"]["MODUS"] == "cross" else F
        z.append(bericht(forschen(D, P, H, pr["name"], pr["par"], g)))
    z.append(bericht(forschen(Fb, Pb, Hb, "Binance ab 2020 · 2×", {"MODUS": "standard", "HEBEL": 2})))
    return "\n".join(z)


# ---------------------------------------------------------------------------
# Täglicher Lauf: alle Profile forschen (wöchentlich) und live simulieren (täglich)
# ---------------------------------------------------------------------------
def lauf(dep, cfg, forschung_faellig=None, bench=None):
    k = dep.get("krypto") or {}
    if k.get("version") != 2:                               # Umstellung auf mehrere Profile: neu beginnen
        k = {"version": 2}
    if forschung_faellig is None:
        fd = k.get("forschung_datum")
        forschung_faellig = not fd or (pd.Timestamp.utcnow().tz_localize(None) - pd.Timestamp(fd)).days >= 7
    F, P, H, markt = lade_hl(getattr(cfg, "KRYPTO_COINS", 25))
    if F.empty:
        raise RuntimeError("Keine Hyperliquid-Daten")
    Fb = Pb = Hb = None
    if forschung_faellig or not k.get("profile"):
        try:
            Fb, Pb, Hb = lade_binance()
        except Exception as e:
            k["binance_fehler"] = str(e)[:200]
        grenze = F.index[len(F.index) * 2 // 3]
        profile = {}
        for pr in PROFILE:
            if pr["par"]["MODUS"] == "cross":
                D = _cross_daten(F, Fb) if Fb is not None and not Fb.empty else pd.DataFrame()
                res = forschen(D, P, H, pr["name"], pr["par"], grenze) if len(D) > 200 else {"name": pr["name"], "fehler": "keine Binance-Daten"}
            else:
                res = forschen(F, P, H, pr["name"], pr["par"], grenze)
            profile[pr["id"]] = res
        k["profile"] = profile
        if Fb is not None and not Fb.empty:
            k["binance"] = forschen(Fb, Pb, Hb, "Binance ab 2020 · Standard 2×", {"MODUS": "standard", "HEBEL": 2})
        k["forschung_datum"] = F.index[-1].date().isoformat()
    # Live-Simulation je Profil (Cross nur im Backtest – Binance-Livedaten sind von GitHub aus gesperrt)
    serien = dict(bench or {})
    if "BTC" in P.columns:
        serien["Bitcoin"] = P["BTC"]
    live = k.get("live") or {}
    letzter = F.index[-1].date().isoformat()
    for pr in PROFILE:
        res = (k["profile"] or {}).get(pr["id"]) or {}
        par = ((res.get("bester") or {}).get("par")) or {**pr["par"]}
        L = live.get(pr["id"])
        if pr["par"]["MODUS"] == "cross":
            live[pr["id"]] = {"nur_backtest": True, "par": par}
            continue
        if not L:
            L = {"start": letzter, "zustand": {"eq": 1.0, "pos": {}}, "kurve": [[letzter, 1.0]], "letzter_tag": letzter,
                 "ereignisse": [], "protokoll": []}
        neue = F.index[F.index > pd.Timestamp(L["letzter_tag"])]
        if len(neue):
            sim = simulieren(F, P, H, par, von=neue[0], zustand=L["zustand"], protokoll=True)
            L["zustand"] = sim["zustand"]
            L["kurve"] += [[t.date().isoformat(), round(v, 6)] for t, v in sim["kurve"]]
            L["ereignisse"] = (L["ereignisse"] + [[t.date().isoformat(), a, c, _r(sg), _r(er), seit]
                                                  for t, a, c, sg, er, seit in sim["ereignisse"]])[-200:]
            L["protokoll"] = (L["protokoll"] + sim["tage"])[-90:]
            L["letzter_tag"] = letzter
        L["par"] = par
        L["jetzt"] = _jetzt(F, L["zustand"], par, letzter)
        live[pr["id"]] = L
    k["live"] = live
    # Vergleichsreihen (gleiche Tage wie die Kurven)
    k["vergleich_bt"] = _vergleich((k["profile"].get("h2") or {}).get("kurve") or [], serien)
    erste_live = next((L for L in live.values() if L.get("kurve")), None)
    k["vergleich_live"] = _vergleich(erste_live["kurve"], serien) if erste_live else {}
    sig7 = (F.tail(7).mean() * 365)
    m = markt.sort_values("apr", ascending=False)
    k["markt"] = [{"coin": r.coin, "apr": round(r.apr, 4), "signal": _r(sig7.get(r.coin)) if r.coin in sig7 else None,
                   "oi": round(r.oi_usd), "vol": round(r.vol_usd), "preis": r.preis} for r in m.head(60).itertuples() if r.vol_usd >= 5e6]
    k["profil_info"] = [{"id": p["id"], "name": p["name"], "kurz": p["kurz"], "text": p["text"]} for p in PROFILE]
    k["stand"] = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    k.pop("fehler", None)
    dep["krypto"] = k
    h2 = live.get("h2") or {}
    return f"Krypto: {len(PROFILE)} Profile simuliert" + (" · Forschung aktualisiert" if forschung_faellig else ""), \
        ", ".join(((h2.get("zustand") or {}).get("pos") or {}).keys()) or "Stablecoin"
