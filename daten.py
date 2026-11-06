# -*- coding: utf-8 -*-
"""Datenquellen: Indexmitglieder (Wikipedia), Kurse (Yahoo Finance),
Insider-Käufe und Odd-Lot-Angebote (SEC EDGAR), Demo-Daten."""
import datetime as dt
import io
import os
import pickle
import re
import time
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pandas as pd
import requests

FELDER = ["Open", "High", "Low", "Close", "Volume"]
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StrategieRadar/2.0"}
CACHE = "cache"

DAX_RESERVE = ["ADS", "AIR", "ALV", "BAS", "BAYN", "BEI", "BMW", "BNR", "CBK", "CON", "DB1", "DBK",
               "DHL", "DTE", "DTG", "ENR", "EOAN", "FRE", "G1A", "HEI", "HEN3", "HNR1", "IFX", "MBG",
               "MRK", "MTX", "MUV2", "P911", "PAH3", "QIA", "RHM", "RWE", "SAP", "SHL", "SIE", "SRT3",
               "SY1", "VNA", "VOW3", "ZAL"]


def _c(name):
    os.makedirs(CACHE, exist_ok=True)
    return os.path.join(CACHE, name)


def _lies(pfad):
    with open(pfad, "rb") as f:
        return pickle.load(f)


def _schreib(pfad, obj):
    with open(pfad, "wb") as f:
        pickle.dump(obj, f)


def waehrung(t):
    return "EUR" if t.upper().endswith((".DE", ".F", ".PA", ".AS", ".MI", ".MC", ".BR", ".VI")) else "USD"


# ---------------------------------------------------------------------------
# Universum
# ---------------------------------------------------------------------------
def _wiki(url, tick_spalten, name_spalten, min_zeilen):
    r = requests.get(url, headers=BROWSER_UA, timeout=30)
    r.raise_for_status()
    for tab in pd.read_html(io.StringIO(r.text)):
        if len(tab) < min_zeilen:
            continue
        namen = {str(c[-1] if isinstance(c, tuple) else c).strip().lower(): c for c in tab.columns}
        tc = next((namen[n] for n in tick_spalten if n in namen), None)
        if tc is None:
            continue
        nc = next((namen[n] for n in name_spalten if n in namen), None)
        ticks = tab[tc].astype(str).str.strip()
        nam = tab[nc].astype(str).str.strip() if nc is not None else ticks
        return [(t, n) for t, n in zip(ticks, nam) if t and t.lower() != "nan"]
    raise ValueError(f"Keine passende Tabelle auf {url}")


def _us(paare):
    return [(t.replace(".", "-").upper(), n) for t, n in paare]


def _de(paare):
    out = []
    for t, n in paare:
        t = t.split(":")[-1].strip().upper()
        out.append((t if "." in t else t + ".DE", n))
    return out


def lade_universum(namen, max_alter_tage=7):
    """Rückgabe: (Liste Ticker, dict Ticker->Firmenname, Hinweise)."""
    pfad = _c("universum.pkl")
    if os.path.exists(pfad):
        c = _lies(pfad)
        if c["namen"] == list(namen) and (dt.date.today() - c["datum"]).days <= max_alter_tage:
            return c["ticker"], c["firmen"], c["hinweise"]
    q = {
        "sp500": ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", ["symbol", "ticker"], ["security", "company"], 400, _us),
        "nasdaq100": ("https://en.wikipedia.org/wiki/Nasdaq-100", ["ticker", "symbol"], ["company", "security"], 80, _us),
        "dax": ("https://en.wikipedia.org/wiki/DAX", ["ticker", "symbol", "ticker symbol"], ["company", "name"], 30, _de),
        "mdax": ("https://en.wikipedia.org/wiki/MDAX", ["ticker", "symbol", "ticker symbol"], ["company", "name"], 40, _de),
    }
    paare, hinweise = [], []
    for n in namen:
        if n not in q:
            continue
        url, ts, ns, mz, f = q[n]
        try:
            paare += f(_wiki(url, ts, ns, mz))
        except Exception as e:
            if n == "dax":
                paare += _de([(t, t) for t in DAX_RESERVE])
                hinweise.append("DAX-Liste aus Reserve verwendet.")
            else:
                hinweise.append(f"Universum {n} nicht geladen ({e}).")
    firmen = {}
    for t, n in paare:
        if re.fullmatch(r"[A-Z0-9\-\.]+", t) and t not in firmen:
            firmen[t] = n
    ticker = list(firmen)
    _schreib(pfad, {"namen": list(namen), "datum": dt.date.today(), "ticker": ticker, "firmen": firmen, "hinweise": hinweise})
    return ticker, firmen, hinweise


# ---------------------------------------------------------------------------
# Kurse (nicht dividendenbereinigt, damit Einstiegskurse echten Kursen entsprechen)
# ---------------------------------------------------------------------------
def lade_kurse(ticker, jahre=3, stapel=100):
    ticker = list(dict.fromkeys(ticker))
    pfad = _c("kurse.pkl")
    if os.path.exists(pfad):
        c = _lies(pfad)
        if c["datum"] == dt.date.today() and c["jahre"] >= jahre and set(ticker) <= set(c["ticker"]):
            return c["daten"]
    import yfinance as yf
    teile = {f: [] for f in FELDER}
    for i in range(0, len(ticker), stapel):
        teil = ticker[i:i + stapel]
        print(f"  Kurse {i + 1}-{i + len(teil)} von {len(ticker)}")
        df = None
        for v in range(3):
            try:
                df = yf.download(teil, period=f"{jahre}y", interval="1d", auto_adjust=False,
                                 progress=False, threads=True, group_by="column")
                break
            except Exception as e:
                print(f"    Fehler ({e}), neuer Versuch")
                time.sleep(5 * (v + 1))
        if df is None or df.empty:
            continue
        for f in FELDER:
            if isinstance(df.columns, pd.MultiIndex):
                if f in df.columns.get_level_values(0):
                    teile[f].append(df[f])
            elif f in df.columns:
                teile[f].append(df[[f]].rename(columns={f: teil[0]}))
        time.sleep(1)
    roh = {}
    for f, v in teile.items():
        d = pd.concat(v, axis=1) if v else pd.DataFrame()
        if not d.empty:
            d = d.loc[:, ~d.columns.duplicated()]
            d.index = pd.to_datetime(d.index)
            if getattr(d.index, "tz", None) is not None:
                d.index = d.index.tz_localize(None)
            d = d.sort_index().dropna(axis=1, how="all")
        roh[f] = d
    daten = bereinige(roh)
    _schreib(pfad, {"datum": dt.date.today(), "jahre": jahre, "ticker": ticker, "daten": daten})
    return daten


def bereinige(daten):
    C = daten["Close"]
    # Tage, an denen fast nichts gehandelt wurde (z. B. Wochenend-Artefakte), entfernen
    gueltig = C.notna().mean(axis=1) > 0.2
    idx, cols = C.index[gueltig], C.columns
    out = {}
    for f in FELDER:
        d = daten[f].reindex(index=idx, columns=cols)
        out[f] = d if f == "Volume" else d.ffill(limit=5)
    for f in ("Open", "High", "Low"):
        out[f] = out[f].fillna(out["Close"])
    return out


# ---------------------------------------------------------------------------
# SEC: Hilfsfunktionen
# ---------------------------------------------------------------------------
def _sec(url, ua, ok404=False):
    for v in range(5):
        try:
            r = requests.get(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, timeout=60)
        except requests.RequestException:
            time.sleep(2 * (v + 1))
            continue
        if r.status_code in (403, 404) and ok404:
            return None      # Datei existiert (noch) nicht – S3 meldet das teils als 403
        if r.status_code in (429, 500, 502, 503):
            time.sleep(3 * (v + 1))
            continue
        r.raise_for_status()
        time.sleep(0.12)     # SEC erlaubt max. 10 Anfragen/Sekunde
        return r
    raise RuntimeError(f"SEC nicht erreichbar: {url}")


def _quartal(d):
    return d.year, (d.month - 1) // 3 + 1


def sec_ciks(ua):
    pfad = _c("sec_ciks.pkl")
    if os.path.exists(pfad) and (time.time() - os.path.getmtime(pfad)) < 7 * 86400:
        return _lies(pfad)
    j = _sec("https://www.sec.gov/files/company_tickers.json", ua).json()
    m = {int(v["cik_str"]): v["ticker"].upper().replace(".", "-") for v in j.values()}
    _schreib(pfad, m)
    return m


# ---------------------------------------------------------------------------
# SEC: Insider-Käufe
# ---------------------------------------------------------------------------
def _datum(s):
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        d = pd.to_datetime(s, format=fmt, errors="coerce")
        if d.notna().mean() > 0.5:
            return d
    return pd.to_datetime(s, errors="coerce")


def insider_quartal(jahr, q, ua):
    """Offizieller SEC-Datensatz eines abgeschlossenen Quartals. None = noch nicht veröffentlicht."""
    pfad = _c(f"insider_{jahr}q{q}.pkl")
    if os.path.exists(pfad):
        return _lies(pfad)
    r = None
    for basis in ("datastandardsinnovation", "structureddata"):
        r = _sec(f"https://www.sec.gov/files/{basis}/data/insider-transactions-data-sets/{jahr}q{q}_form345.zip", ua, ok404=True)
        if r is not None:
            break
    if r is None:
        return None
    z = zipfile.ZipFile(io.BytesIO(r.content))
    namen = {n.split("/")[-1].upper(): n for n in z.namelist()}
    lies = lambda n: pd.read_csv(z.open(namen[n]), sep="\t", dtype=str, low_memory=False)
    sub, tr, own = lies("SUBMISSION.TSV"), lies("NONDERIV_TRANS.TSV"), lies("REPORTINGOWNER.TSV")
    tr = tr[tr["TRANS_CODE"] == "P"]
    if "TRANS_ACQUIRED_DISP_CD" in tr.columns:
        tr = tr[tr["TRANS_ACQUIRED_DISP_CD"] == "A"]
    own = own.drop_duplicates("ACCESSION_NUMBER")
    df = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER", how="left")
    for typ in ("DOCUMENT_TYPE", "FORM_TYPE"):
        if typ in df.columns:
            df = df[df[typ].astype(str).str.strip() == "4"]
            break
    def sp(namen, standard=""):
        for n in namen:
            if n in df.columns:
                return df[n].astype(str)
        return pd.Series(standard, index=df.index, dtype=str)
    out = pd.DataFrame({
        "datum": _datum(df["FILING_DATE"]),
        "ticker": sp(["ISSUERTRADINGSYMBOL"]).str.upper().str.strip().str.replace(".", "-", regex=False),
        "insider": sp(["RPTOWNERCIK", "RPTOWNERNAME"], "?"),
        "name": sp(["RPTOWNERNAME"]),
        "rolle": sp(["RPTOWNER_TITLE", "RPTOWNER_RELATIONSHIP"]),
        "wert": pd.to_numeric(df["TRANS_SHARES"], errors="coerce") * pd.to_numeric(df["TRANS_PRICEPERSHARE"], errors="coerce"),
        "preis": pd.to_numeric(df["TRANS_PRICEPERSHARE"], errors="coerce"),
        "plan": sp(["AFF10B5ONE"], "0").str.lower().isin(["1", "true", "y"]),
    }).dropna(subset=["datum", "wert"])
    out = out[out["wert"] > 0]
    _schreib(pfad, out)
    return out


def _form4_parse(xml_text, datum):
    m = re.search(r"<ownershipDocument>.*?</ownershipDocument>", xml_text, re.S)
    if not m:
        return []
    root = ET.fromstring(m.group(0))
    sym = (root.findtext("issuer/issuerTradingSymbol") or "").upper().strip().replace(".", "-")
    ow = root.find("reportingOwner")
    cik = ow.findtext("reportingOwnerId/rptOwnerCik", "") if ow is not None else ""
    name = ow.findtext("reportingOwnerId/rptOwnerName", "") if ow is not None else ""
    rolle = ow.findtext("reportingOwnerRelationship/officerTitle", "") if ow is not None else ""
    if not rolle and ow is not None and (ow.findtext("reportingOwnerRelationship/isDirector", "") in ("1", "true")):
        rolle = "Director"
    plan = (root.findtext("aff10b5One") or "").strip().lower() in ("1", "true")
    out = []
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        if t.findtext("transactionCoding/transactionCode") != "P":
            continue
        if t.findtext("transactionAmounts/transactionAcquiredDisposedCode/value") not in (None, "A"):
            continue
        try:
            sh = float(t.findtext("transactionAmounts/transactionShares/value") or 0)
            px = float(t.findtext("transactionAmounts/transactionPricePerShare/value") or 0)
        except ValueError:
            continue
        if sh * px > 0:
            out.append({"datum": pd.Timestamp(datum), "ticker": sym, "insider": cik or name, "name": name,
                        "rolle": rolle, "wert": sh * px, "preis": px, "plan": plan})
    return out


def insider_tag(d, ua, ciks):
    """Alle Form-4-Käufe eines Tages für Firmen im Universum (aus dem täglichen EDGAR-Index)."""
    pfad = _c(f"form4_{d:%Y%m%d}.pkl")
    if os.path.exists(pfad):
        return _lies(pfad)
    j, q = _quartal(d)
    r = _sec(f"https://www.sec.gov/Archives/edgar/daily-index/{j}/QTR{q}/form.{d:%Y%m%d}.idx", ua, ok404=True)
    zeilen = []
    if r is not None:
        dateien = set()
        for z in r.text.splitlines():
            m = re.match(r"^4\s+.+?\s+(\d{1,10})\s+(\d{8}|\d{4}-\d{2}-\d{2})\s+(edgar/\S+)\s*$", z)
            if m and int(m.group(1)) in ciks:
                dateien.add(m.group(3))
        for i, f in enumerate(sorted(dateien)):
            try:
                rr = _sec(f"https://www.sec.gov/Archives/{f}", ua, ok404=True)
                if rr is not None:
                    zeilen += _form4_parse(rr.text, d)
            except Exception:
                continue
    df = pd.DataFrame(zeilen, columns=["datum", "ticker", "insider", "name", "rolle", "wert", "preis", "plan"])
    if d < dt.date.today():          # heutigen Tag nicht cachen (kann noch wachsen)
        _schreib(pfad, df)
    return df


def lade_insider(von, ua, universum, meldungen=None):
    """Insider-Käufe ab Datum `von` bis heute.
    Abgeschlossene Quartale: offizieller SEC-Datensatz. Laufendes Quartal (und das vorige, falls
    dessen Datensatz noch nicht veröffentlicht ist): tägliche Form-4-Meldungen."""
    meldungen = meldungen if meldungen is not None else []
    teile = []
    heute = dt.date.today()
    jetzt = _quartal(heute)
    vorher = (jetzt[0] - 1, 4) if jetzt[1] == 1 else (jetzt[0], jetzt[1] - 1)
    taeglich_ab = dt.date(jetzt[0], 3 * jetzt[1] - 2, 1)
    j, q = _quartal(von)
    while (j, q) < jetzt:
        df = insider_quartal(j, q, ua)
        if df is not None:
            teile.append(df)
            print(f"  Quartal {j}Q{q}: {len(df)} Insider-Käufe (SEC-Datensatz)")
        elif (j, q) == vorher:
            taeglich_ab = dt.date(j, 3 * q - 2, 1)
        else:
            meldungen.append(f"SEC-Datensatz {j}Q{q} nicht gefunden – Lücke in den Insider-Daten.")
        j, q = (j + 1, 1) if q == 4 else (j, q + 1)
    ciks = {c for c, t in sec_ciks(ua).items() if t in universum}
    tage = pd.bdate_range(max(taeglich_ab, von), heute)
    print(f"  Tägliche Form-4-Meldungen ab {tage[0].date() if len(tage) else '-'}: {len(tage)} Tage, {len(ciks)} Firmen")
    for i, d in enumerate(tage):
        teile.append(insider_tag(d.date(), ua, ciks))
        if i % 10 == 9:
            print(f"    {i + 1}/{len(tage)} Tage")
    teile = [t for t in teile if t is not None and len(t)]
    if not teile:
        return pd.DataFrame(columns=["datum", "ticker", "insider", "name", "rolle", "wert", "preis", "plan"])
    df = pd.concat(teile, ignore_index=True)
    df = df[(pd.to_datetime(df["datum"]) >= pd.Timestamp(von)) & df["ticker"].isin(universum)]
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# SEC: Odd-Lot-Tender
# ---------------------------------------------------------------------------
def suche_oddlot(ua, tage=30):
    ende = dt.date.today()
    params = {"q": '"odd lot"', "forms": "SC TO-I", "dateRange": "custom",
              "startdt": (ende - dt.timedelta(days=tage)).isoformat(), "enddt": ende.isoformat()}
    r = requests.get("https://efts.sec.gov/LATEST/search-index", params=params,
                     headers={"User-Agent": ua, "Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    treffer = {}
    for h in r.json().get("hits", {}).get("hits", []):
        s = h.get("_source", {})
        name = (s.get("display_names") or ["?"])[0]
        cik = (s.get("ciks") or [""])[0]
        datum, adsh = s.get("file_date", ""), s.get("adsh", "")
        if cik in treffer and treffer[cik]["datum"] >= datum:
            continue
        m = re.search(r"\(([A-Z0-9 ,\.\-]+)\)\s*\(CIK", name)
        datei = h.get("_id", ":").split(":", 1)[-1]
        treffer[cik] = {
            "firma": re.sub(r"\s*\(.*$", "", name).strip(),
            "ticker": [t.strip() for t in m.group(1).split(",")] if m else [],
            "datum": datum,
            "link": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}/{datei}" if cik and adsh else "",
        }
    return sorted(treffer.values(), key=lambda x: x["datum"], reverse=True)


# ---------------------------------------------------------------------------
# Demo-Daten
# ---------------------------------------------------------------------------
def demo_daten(tage=800, n=160, seed=11):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=tage)
    aktien = [f"DEMO{i:03d}" for i in range(n)]
    alle = aktien + ["SPY", "^GSPC", "^GDAXI", "EURUSD=X"]
    markt = np.repeat(rng.normal(0.0004, 0.0012, tage // 50 + 1), 50)[:tage] + rng.normal(0, 0.009, tage)
    C = {}
    for t in alle:
        if t == "EURUSD=X":
            C[t] = 1.12 * np.exp(np.cumsum(rng.normal(0, 0.004, tage)))
            continue
        beta = 1.0 if t in ("SPY", "^GSPC", "^GDAXI") else rng.uniform(0.6, 1.4)
        eigen = np.repeat(rng.normal(0.0002, 0.0012, tage // 60 + 1), 60)[:tage]
        r = beta * markt + (0 if t in ("SPY", "^GSPC") else eigen + rng.normal(0, rng.uniform(0.008, 0.02), tage))
        C[t] = rng.uniform(20, 300) * np.exp(np.cumsum(r))
    C = pd.DataFrame(C, index=idx)
    V = pd.DataFrame(rng.uniform(5e5, 4e6, C.shape), index=idx, columns=alle)
    # Quartalszahlen-Sprünge mit anschließender Drift (mal mit, mal ohne Erfolg)
    spruenge = []
    for z in range(63):
        t = aktien[int(rng.integers(0, n))] if z < 60 else aktien[z - 60]
        k = int(rng.integers(300, tage - 2)) if z < 60 else tage - 1
        s = rng.uniform(0.06, 0.14)
        C.loc[C.index[k]:, t] *= (1 + s)
        V.iloc[k, V.columns.get_loc(t)] *= 6
        drift = rng.normal(0.0015, 0.002)
        if k + 1 < tage:
            C.loc[C.index[k + 1]:, t] *= np.exp(np.cumsum(np.full(tage - k - 1, drift)))
        spruenge.append((t, k, s))
    O = C.shift(1) * (1 + rng.normal(0, 0.003, C.shape))
    O.iloc[0] = C.iloc[0]
    for t, k, s in spruenge:
        O.iloc[k, O.columns.get_loc(t)] = C[t].iloc[k - 1] * (1 + s * 0.7)
    H = np.maximum(O, C) * (1 + np.abs(rng.normal(0, 0.006, C.shape)))
    L = np.minimum(O, C) * (1 - np.abs(rng.normal(0, 0.006, C.shape)))
    kurse = {"Open": O, "High": H, "Low": L, "Close": C, "Volume": V}
    # Insider-Cluster
    zeilen = []
    for _ in range(45):
        t = aktien[int(rng.integers(0, n))]
        k = int(rng.integers(300, tage - 1))
        for j in range(int(rng.integers(1, 4))):
            zeilen.append({"datum": idx[k], "ticker": t, "insider": f"P{j}", "name": ["Jane Doe", "John Roe", "Max Muster"][j],
                           "rolle": ["CEO", "CFO", "Director"][j], "wert": float(rng.uniform(5e4, 9e5)),
                           "preis": float(C[t].iloc[k]), "plan": False})
    # frische Cluster-Käufe kurz vor heute, damit die Demo eine aktuelle Empfehlung zeigt
    for t in aktien[:12]:
        for j in range(3):
            zeilen.append({"datum": idx[-2], "ticker": t, "insider": f"Q{j}", "name": "Demo Insider",
                           "rolle": ["CEO", "CFO", "Director"][j], "wert": 450_000.0,
                           "preis": float(C[t].iloc[-2]), "plan": False})
    firmen = {t: f"Demo Firma {t[-3:]}" for t in aktien}
    return kurse, aktien, firmen, pd.DataFrame(zeilen)
