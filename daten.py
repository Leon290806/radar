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
    """Liest die Indexliste von Wikipedia. Rückgabe: [(Ticker, Name, Sektor, Branche)]."""
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
        sc = next((c for n, c in namen.items() if "sector" in n or n in ("branche", "sektor")), None)
        bc = next((c for n, c in namen.items() if "sub-industry" in n or "sub industry" in n), None)
        ticks = tab[tc].astype(str).str.strip()
        leer = pd.Series("", index=tab.index)
        nam = tab[nc].astype(str).str.strip() if nc is not None else ticks
        sek = tab[sc].astype(str).str.strip() if sc is not None else leer
        bra = tab[bc].astype(str).str.strip() if bc is not None else sek
        return [(t, n, s_, b) for t, n, s_, b in zip(ticks, nam, sek, bra) if t and t.lower() != "nan"]
    raise ValueError(f"Keine passende Tabelle auf {url}")


def _us(paare):
    return [(t.replace(".", "-").upper(), *rest) for t, *rest in paare]


def _de(paare):
    out = []
    for t, *rest in paare:
        t = t.split(":")[-1].strip().upper()
        out.append((t if "." in t else t + ".DE", *rest))
    return out


def lade_universum(namen, max_alter_tage=7):
    """Rückgabe: (Liste Ticker, dict Ticker->Firmenname, Hinweise, dict Ticker->(Sektor, Branche))."""
    pfad = _c("universum_v2.pkl")
    if os.path.exists(pfad):
        c = _lies(pfad)
        if c["namen"] == list(namen) and (dt.date.today() - c["datum"]).days <= max_alter_tage:
            return c["ticker"], c["firmen"], c["hinweise"], c.get("sektoren", {})
    q = {
        "sp500": ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", ["symbol", "ticker"], ["security", "company"], 400, _us),
        "nasdaq100": ("https://en.wikipedia.org/wiki/Nasdaq-100", ["ticker", "symbol"], ["company", "security"], 80, _us),
        "dax": ("https://en.wikipedia.org/wiki/DAX", ["ticker", "symbol", "ticker symbol"], ["company", "name"], 30, _de),
        "mdax": ("https://en.wikipedia.org/wiki/MDAX", ["ticker", "symbol", "ticker symbol"], ["company", "name"], 40, _de),
        # mittlere und kleine Werte: hier wirken Insider- und Zahlen-Effekte laut Forschung am stärksten
        "sp400": ("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", ["symbol", "ticker"], ["security", "company"], 300, _us),
        "sp600": ("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", ["symbol", "ticker"], ["security", "company"], 400, _us),
        "sdax": ("https://en.wikipedia.org/wiki/SDAX", ["ticker", "symbol", "ticker symbol"], ["company", "name"], 40, _de),
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
                paare += _de([(t, t, "", "") for t in DAX_RESERVE])
                hinweise.append("DAX-Liste aus Reserve verwendet.")
            else:
                hinweise.append(f"Universum {n} nicht geladen ({e}).")
    firmen, sektoren = {}, {}
    for t, n, sek, bra in paare:
        if re.fullmatch(r"[A-Z0-9\-\.]+", t) and t not in firmen:
            firmen[t] = n
            if sek and sek.lower() != "nan":
                sektoren[t] = (sek, bra if bra and bra.lower() != "nan" else sek)
    ticker = list(firmen)
    _schreib(pfad, {"namen": list(namen), "datum": dt.date.today(), "ticker": ticker, "firmen": firmen,
                    "hinweise": hinweise, "sektoren": sektoren})
    return ticker, firmen, hinweise, sektoren


# ---------------------------------------------------------------------------
# Kurse (nicht dividendenbereinigt, damit Einstiegskurse echten Kursen entsprechen)
# ---------------------------------------------------------------------------
def lade_kurse(ticker, jahre=3, stapel=100, max_alter_std=4):
    ticker = list(dict.fromkeys(ticker))
    pfad = _c("kurse.pkl")
    if os.path.exists(pfad):
        c = _lies(pfad)
        alter = (time.time() - c.get("zeit", 0)) / 3600
        if alter < max_alter_std and c["jahre"] >= jahre and set(ticker) <= set(c["ticker"]):
            return c["daten"]
    import yfinance as yf
    teile = {f: [] for f in FELDER}
    for i in range(0, len(ticker), stapel):
        teil = ticker[i:i + stapel]
        print(f"  Kurse {i + 1}-{i + len(teil)} von {len(ticker)}")
        df = None
        for v in range(3):
            try:
                df = yf.download(teil, start=(dt.date.today() - dt.timedelta(days=int(jahre * 365.25) + 5)).isoformat(),
                                 interval="1d", auto_adjust=False,
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
    _schreib(pfad, {"zeit": time.time(), "jahre": jahre, "ticker": ticker, "daten": daten})
    return daten


def bereinige(daten):
    C = daten["Close"]
    gueltig = C.notna().mean(axis=1) > 0.2      # Tage, an denen fast nichts gehandelt wurde, entfernen
    idx, cols = C.index[gueltig], C.columns
    out = {}
    for f in FELDER:
        d = daten[f].reindex(index=idx, columns=cols)
        out[f] = d if f == "Volume" else d.ffill(limit=5)
    for f in ("Open", "High", "Low"):
        out[f] = out[f].fillna(out["Close"])
    return out


# ---------------------------------------------------------------------------
# Insider: gemeinsames Format
# ---------------------------------------------------------------------------
INSIDER_SPALTEN = ["datum", "handel", "ticker", "insider", "name", "rolle", "kat", "typ", "stueck", "preis",
                   "wert", "waehrung", "plan", "land", "bestand"]   # bestand = Stück NACH der Transaktion (nur USA)


def rollen_kategorie(text):
    t = " " + re.sub(r"[^a-z0-9%äöü ]", " ", str(text).lower()) + " "
    hat = lambda *w: any(re.search(r"\b" + re.escape(x) + r"\b", t) for x in w)
    if hat("chief executive", "ceo", "vorstandsvorsitzender", "vorsitzender des vorstands"):
        return "CEO"
    if hat("chief financial", "cfo", "finanzvorstand", "principal financial"):
        return "CFO"
    if hat("president", "chief", "officer", "coo", "cto", "evp", "svp", "vice president", "vorstand", "geschäftsführer"):
        return "Vorstand"
    if hat("director", "aufsichtsrat", "board", "chairman", "chair", "verwaltungsrat"):
        return "Direktor"
    if hat("10%", "10", "tenpercentowner", "percent"):
        return "10%-Eigner"
    return "Sonstige"


def _leer():
    return pd.DataFrame(columns=INSIDER_SPALTEN)


# ---------------------------------------------------------------------------
# SEC (USA)
# ---------------------------------------------------------------------------
class SecFehler(RuntimeError):
    pass


def ua_bereinigen(ua):
    """Unsichtbare Zeichen (Zeilenumbruch, Umlaute) aus dem User-Agent entfernen – die führen sonst zu Fehlern."""
    ua = re.sub(r"\s+", " ", str(ua or "")).strip()
    ua = ua.encode("ascii", "ignore").decode("ascii")
    return ua or "StrategieRadar privat kontakt@example.com"


def _sec(url, ua, ok404=False, timeout=(15, 120)):
    ua = ua_bereinigen(ua)
    letzter = ""
    for v in range(5):
        try:
            r = requests.get(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, timeout=timeout)
        except Exception as e:
            letzter = f"{type(e).__name__}: {e}"
            time.sleep(2 * (v + 1))
            continue
        if r.status_code in (403, 404) and ok404:
            return None      # Datei existiert (noch) nicht – S3 meldet das teils als 403
        if r.status_code in (429, 500, 502, 503, 504):
            letzter = f"HTTP {r.status_code}"
            time.sleep(4 * (v + 1))
            continue
        if r.status_code >= 400:
            raise SecFehler(f"HTTP {r.status_code} für {url}")
        time.sleep(0.12)     # SEC erlaubt max. 10 Anfragen/Sekunde
        return r
    raise SecFehler(f"SEC nicht erreichbar ({letzter}): {url}")


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


def _datum(s):
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        d = pd.to_datetime(s, format=fmt, errors="coerce")
        if d.notna().mean() > 0.5:
            return d
    return pd.to_datetime(s, errors="coerce")


def insider_quartal(jahr, q, ua):
    """Offizieller SEC-Datensatz eines abgeschlossenen Quartals (Käufe und Verkäufe, Form 4).
    Rückgabe None = nicht verfügbar."""
    pfad = _c(f"insider_v3_{jahr}q{q}.pkl")
    if os.path.exists(pfad):
        return _lies(pfad)
    r, fehler = None, []
    for basis in ("datastandardsinnovation", "structureddata"):
        url = f"https://www.sec.gov/files/{basis}/data/insider-transactions-data-sets/{jahr}q{q}_form345.zip"
        try:
            r = _sec(url, ua, ok404=True)
        except SecFehler as e:
            fehler.append(str(e))
            r = None
        if r is not None and r.content[:2] == b"PK":
            break
        r = None
    if r is None:
        if fehler:
            raise SecFehler(fehler[0])
        return None
    z = zipfile.ZipFile(io.BytesIO(r.content))
    namen = {n.split("/")[-1].upper(): n for n in z.namelist()}
    lies = lambda n: pd.read_csv(z.open(namen[n]), sep="\t", dtype=str, low_memory=False)
    sub, tr, own = lies("SUBMISSION.TSV"), lies("NONDERIV_TRANS.TSV"), lies("REPORTINGOWNER.TSV")
    tr = tr[tr["TRANS_CODE"].isin(["P", "S"])]
    own = own.drop_duplicates("ACCESSION_NUMBER")
    df = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER", how="left")
    for typ in ("DOCUMENT_TYPE", "FORM_TYPE"):
        if typ in df.columns:
            df = df[df[typ].astype(str).str.strip() == "4"]
            break

    def sp(namen, standard=""):
        for n in namen:
            if n in df.columns:
                return df[n].fillna("").astype(str)
        return pd.Series(standard, index=df.index, dtype=str)

    titel, bez = sp(["RPTOWNER_TITLE"]), sp(["RPTOWNER_RELATIONSHIP"])
    rolle = titel.where(titel.str.strip() != "", bez)
    stueck = pd.to_numeric(df["TRANS_SHARES"], errors="coerce")
    preis = pd.to_numeric(df["TRANS_PRICEPERSHARE"], errors="coerce")
    out = pd.DataFrame({
        "datum": _datum(df["FILING_DATE"]),
        "handel": _datum(sp(["TRANS_DATE"])) if "TRANS_DATE" in df.columns else pd.NaT,
        "ticker": sp(["ISSUERTRADINGSYMBOL"]).str.upper().str.strip().str.replace(".", "-", regex=False),
        "insider": sp(["RPTOWNERCIK", "RPTOWNERNAME"], "?"),
        "name": sp(["RPTOWNERNAME"]).str.title(),
        "rolle": rolle,
        "kat": rolle.map(rollen_kategorie),
        "typ": df["TRANS_CODE"].map({"P": "Kauf", "S": "Verkauf"}),
        "stueck": stueck, "preis": preis, "wert": stueck * preis, "waehrung": "USD",
        "plan": sp(["AFF10B5ONE"], "0").str.lower().isin(["1", "true", "y"]),
        "land": "USA",
        "bestand": pd.to_numeric(sp(["SHRS_OWND_FOLWNG_TRANS"]), errors="coerce"),
    }).dropna(subset=["datum", "wert"])
    out = out[out["wert"] > 0].reset_index(drop=True)
    _schreib(pfad, out)
    return out


def _form4_parse(xml_text, datum):
    m = re.search(r"<ownershipDocument>.*?</ownershipDocument>", xml_text, re.S)
    if not m:
        return []
    try:
        root = ET.fromstring(m.group(0))
    except ET.ParseError:
        return []
    sym = (root.findtext("issuer/issuerTradingSymbol") or "").upper().strip().replace(".", "-")
    ow = root.find("reportingOwner")
    cik = ow.findtext("reportingOwnerId/rptOwnerCik", "") if ow is not None else ""
    name = ow.findtext("reportingOwnerId/rptOwnerName", "") if ow is not None else ""
    rolle = ow.findtext("reportingOwnerRelationship/officerTitle", "") if ow is not None else ""
    if not rolle and ow is not None:
        rel = ow.find("reportingOwnerRelationship")
        if rel is not None:
            if (rel.findtext("isDirector") or "").strip() in ("1", "true"):
                rolle = "Director"
            elif (rel.findtext("isTenPercentOwner") or "").strip() in ("1", "true"):
                rolle = "10% Owner"
    plan = (root.findtext("aff10b5One") or "").strip().lower() in ("1", "true")
    out = []
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = t.findtext("transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue
        try:
            sh = float(t.findtext("transactionAmounts/transactionShares/value") or 0)
            px = float(t.findtext("transactionAmounts/transactionPricePerShare/value") or 0)
        except ValueError:
            continue
        hd = pd.to_datetime(t.findtext("transactionDate/value"), errors="coerce")
        try:
            bestand = float(t.findtext("postTransactionAmounts/sharesOwnedFollowingTransaction/value") or "nan")
        except ValueError:
            bestand = float("nan")
        if sh * px > 0:
            out.append({"datum": pd.Timestamp(datum), "handel": hd, "ticker": sym, "insider": cik or name,
                        "name": name.title(), "rolle": rolle, "kat": rollen_kategorie(rolle),
                        "typ": "Kauf" if code == "P" else "Verkauf", "stueck": sh, "preis": px, "wert": sh * px,
                        "waehrung": "USD", "plan": plan, "land": "USA", "bestand": bestand})
    return out


def insider_tag(d, ua, ciks):
    """Alle Form-4-Käufe/-Verkäufe eines Tages für Firmen im Universum (täglicher EDGAR-Index)."""
    pfad = _c(f"form4_v3_{d:%Y%m%d}.pkl")
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
        for f in sorted(dateien):
            try:
                rr = _sec(f"https://www.sec.gov/Archives/{f}", ua, ok404=True)
                if rr is not None:
                    zeilen += _form4_parse(rr.text, d)
            except Exception:
                continue
    df = pd.DataFrame(zeilen, columns=INSIDER_SPALTEN)
    if d < dt.date.today():          # heutigen Tag nicht cachen (kann noch wachsen)
        _schreib(pfad, df)
    return df


def lade_insider_usa(von, ua, universum, status):
    """SEC: abgeschlossene Quartale aus dem offiziellen Datensatz, der Rest aus täglichen Form-4-Meldungen.
    Fällt ein Quartalsdatensatz aus, werden (bis zu 3 Quartale zurück) die Tagesmeldungen genutzt."""
    heute = dt.date.today()
    jetzt = _quartal(heute)
    teile, taeglich = [], []
    j, q = _quartal(von)
    zurueck = 0
    quartale = []
    while (j, q) < jetzt:
        quartale.append((j, q))
        j, q = (j + 1, 1) if q == 4 else (j, q + 1)
    for k, (j, q) in enumerate(quartale):
        try:
            df = insider_quartal(j, q, ua)
            if df is not None:
                teile.append(df)
                status["quellen"].append(f"SEC {j}Q{q}: {len(df)} Transaktionen (Quartalsdatensatz)")
                print(f"  SEC {j}Q{q}: {len(df)} Transaktionen")
                continue
            grund = "nicht veröffentlicht"
        except Exception as e:
            grund = str(e)[:160]
        if len(quartale) - k <= 3:
            taeglich.append((j, q))
            status["quellen"].append(f"SEC {j}Q{q}: Quartalsdatensatz fehlt ({grund}) – nutze Tagesmeldungen")
        else:
            status["luecken"].append(f"SEC {j}Q{q}: {grund}")
    ciks = {c for c, t in sec_ciks(ua).items() if t in universum}
    tage = []
    for j, q in taeglich:
        tage += list(pd.bdate_range(max(dt.date(j, 3 * q - 2, 1), von), min(dt.date(j + (q == 4), (3 * q) % 12 + 1, 1) - dt.timedelta(days=1), heute)))
    tage += list(pd.bdate_range(max(dt.date(jetzt[0], 3 * jetzt[1] - 2, 1), von), heute))
    print(f"  SEC Tagesmeldungen: {len(tage)} Tage, {len(ciks)} Firmen")
    for i, d in enumerate(tage):
        try:
            teile.append(insider_tag(d.date(), ua, ciks))
        except Exception as e:
            status["luecken"].append(f"SEC Tagesindex {d.date()}: {str(e)[:120]}")
        if i % 20 == 19:
            print(f"    {i + 1}/{len(tage)} Tage")
    if len(tage):
        status["quellen"].append(f"SEC Tagesmeldungen: {len(tage)} Handelstage ab {tage[0].date()}")
    teile = [t for t in teile if t is not None and len(t)]
    if not teile:
        return _leer()
    df = pd.concat(teile, ignore_index=True)
    df = df[(pd.to_datetime(df["datum"]) >= pd.Timestamp(von)) & df["ticker"].isin(universum)]
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# BaFin (Deutschland): Directors' Dealings nach Art. 19 MAR
# ---------------------------------------------------------------------------
BAFIN_URL = "https://portal.mvp.bafin.de/database/DealingsInfo/sucheForm.do"
_RECHTSFORM = r"\b(aktiengesellschaft|ag|se|kgaa|co|gmbh|n\.?v|s\.?a|plc|holding|group|& co|und co)\b"


def _norm(name):
    n = str(name).lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    n = re.sub(_RECHTSFORM, " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _zahl_de(x):
    s = str(x).strip().replace("\xa0", "")
    if not s or s.lower() == "nan":
        return np.nan
    s = re.sub(r"[^0-9,.\-]", "", s)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


def lade_insider_de(von, firmen_de, status):
    """Directors' Dealings aus der BaFin-Datenbank (CSV-Export). firmen_de: {Ticker: Firmenname}."""
    if not firmen_de:
        return _leer()
    pfad = _c(f"bafin_{dt.date.today():%Y%m%d}.pkl")
    if os.path.exists(pfad):
        roh = _lies(pfad)
    else:
        params = {"meldepflichtigerName": "", "emittentName": "", "emittentIsin": "", "emittentButton": "Suche Emittent",
                  "zeitraum": "0", "zeitraumVon": von.strftime("%d.%m.%Y"), "zeitraumBis": dt.date.today().strftime("%d.%m.%Y"),
                  "d-4000784-e": "1", "6578706f7274": "1", "locale": "de_DE"}
        r = requests.get(BAFIN_URL, params=params, headers=BROWSER_UA, timeout=(15, 120))
        r.raise_for_status()
        roh = None
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                txt = r.content.decode(enc)
                roh = pd.read_csv(io.StringIO(txt), sep=";", dtype=str)
                if roh.shape[1] > 5:
                    break
            except Exception:
                roh = None
        if roh is None or roh.shape[1] <= 5:
            raise ValueError("BaFin-Export nicht lesbar (Format geändert?)")
        _schreib(pfad, roh)

    def spalte(*worte):
        for c in roh.columns:
            cl = c.lower()
            if all(w in cl for w in worte):
                return roh[c]
        return pd.Series("", index=roh.index)

    emittent = spalte("emittent")
    wiki = {_norm(n): t for t, n in firmen_de.items()}

    def ticker_zu(name):
        n = _norm(name)
        if n in wiki:
            return wiki[n]
        for wn, t in wiki.items():
            if wn and (n.startswith(wn) or wn.startswith(n)) and min(len(n), len(wn)) >= 3:
                return t
        erste = n.split(" ")[0] if n else ""
        for wn, t in wiki.items():
            if erste and len(erste) >= 4 and wn.split(" ")[0] == erste:
                return t
        return None

    art = spalte("art", "gesch").str.lower()
    preis = spalte("preis").map(_zahl_de)
    vol = spalte("volumen").map(_zahl_de)
    datum = pd.to_datetime(spalte("mitteilung"), dayfirst=True, errors="coerce")
    if datum.isna().all():
        datum = pd.to_datetime(spalte("datum"), dayfirst=True, errors="coerce")
    handel = pd.to_datetime(spalte("datum", "gesch"), dayfirst=True, errors="coerce")
    rolle = spalte("position")
    name = spalte("meldepflicht")
    df = pd.DataFrame({
        "datum": datum.fillna(handel), "handel": handel, "ticker": emittent.map(ticker_zu),
        "insider": name, "name": name.str.title(), "rolle": rolle, "kat": rolle.map(rollen_kategorie),
        "typ": np.where(art.str.contains("kauf") & ~art.str.contains("verkauf"), "Kauf",
                        np.where(art.str.contains("verkauf"), "Verkauf", "Sonstiges")),
        "stueck": vol / preis, "preis": preis, "wert": vol, "waehrung": "EUR", "plan": False, "land": "DE",
        "bestand": np.nan,
    })
    df = df[df["ticker"].notna() & df["typ"].isin(["Kauf", "Verkauf"]) & (df["wert"] > 0)
            & (pd.to_datetime(df["datum"]) >= pd.Timestamp(von))]
    status["quellen"].append(f"BaFin Directors' Dealings: {len(roh)} Meldungen, {len(df)} davon DAX/MDAX zugeordnet")
    return df[INSIDER_SPALTEN].reset_index(drop=True)


def _alte_caches_loeschen():
    """Caches im alten Format (ohne Bestandsangabe) entfernen, damit der Zwischenspeicher nicht wächst."""
    try:
        for f in os.listdir(CACHE):
            if f.startswith(("insider_v2_", "form4_v2_")) or f == "universum.pkl":
                os.remove(os.path.join(CACHE, f))
    except OSError:
        pass


def lade_insider(von, ua, universum, firmen, laender=("USA", "DE")):
    """Alle Insider-Transaktionen ab `von`. Rückgabe: (DataFrame, Statusdict)."""
    _alte_caches_loeschen()
    status = {"ok": False, "quellen": [], "luecken": [], "fehler": [], "anzahl": 0}
    teile = []
    us = {t for t in universum if waehrung(t) == "USD"}
    if "USA" in laender and us:
        try:
            teile.append(lade_insider_usa(von, ua, us, status))
        except Exception as e:
            status["fehler"].append(f"USA (SEC): {type(e).__name__}: {e}")
    de = {t: firmen.get(t, t) for t in universum if waehrung(t) == "EUR"}
    if "DE" in laender and de:
        try:
            teile.append(lade_insider_de(von, de, status))
        except Exception as e:
            status["fehler"].append(f"Deutschland (BaFin): {type(e).__name__}: {e}")
    teile = [t for t in teile if t is not None and len(t)]
    df = pd.concat(teile, ignore_index=True) if teile else _leer()
    df["datum"] = pd.to_datetime(df["datum"])
    status["ok"] = len(df) > 0
    status["anzahl"] = int(len(df))
    if len(df):
        status["von"] = str(df["datum"].min().date())
        status["bis"] = str(df["datum"].max().date())
    return df, status


# ---------------------------------------------------------------------------
# SEC: Odd-Lot-Tender
# ---------------------------------------------------------------------------
def suche_oddlot(ua, tage=30):
    ende = dt.date.today()
    ua = ua_bereinigen(ua)
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
def demo_daten(tage=1400, n=160, seed=11):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=tage)
    aktien = [f"DEMO{i:03d}" for i in range(n)] + [f"DEM{i:02d}.DE" for i in range(15)]
    bench = ["SPY", "^GSPC", "QQQ", "URTH", "^GDAXI"]
    alle = aktien + bench + ["EURUSD=X"]
    markt = np.repeat(rng.normal(0.0004, 0.0012, tage // 50 + 1), 50)[:tage] + rng.normal(0, 0.009, tage)
    C = {}
    for t in alle:
        if t == "EURUSD=X":
            C[t] = 1.12 * np.exp(np.cumsum(rng.normal(0, 0.004, tage)))
            continue
        beta = {"SPY": 1.0, "^GSPC": 1.0, "QQQ": 1.25, "URTH": 0.85, "^GDAXI": 0.8}.get(t, rng.uniform(0.6, 1.4))
        eigen = np.repeat(rng.normal(0.0002, 0.0012, tage // 60 + 1), 60)[:tage]
        extra = {"QQQ": rng.normal(0.0002, 0.004, tage), "URTH": rng.normal(-0.0001, 0.003, tage),
                 "^GDAXI": rng.normal(0, 0.006, tage)}.get(t)
        r = beta * markt + (0 if t in ("SPY", "^GSPC") else (extra if extra is not None else eigen + rng.normal(0, rng.uniform(0.008, 0.02), tage)))
        C[t] = rng.uniform(20, 300) * np.exp(np.cumsum(r))
    C = pd.DataFrame(C, index=idx)
    C["^GSPC"] = C["SPY"] * 10
    V = pd.DataFrame(rng.uniform(5e5, 4e6, C.shape), index=idx, columns=alle)
    spruenge = []
    for z in range(80):
        t = aktien[int(rng.integers(0, n))] if z < 75 else aktien[z - 75]
        k = int(rng.integers(300, tage - 2)) if z < 75 else tage - 1
        s = rng.uniform(0.06, 0.14) if z % 6 or z >= 75 else -rng.uniform(0.06, 0.14)
        C.loc[C.index[k]:, t] *= (1 + s)
        V.iloc[k, V.columns.get_loc(t)] *= 6
        drift = rng.normal(0.0015 if s > 0 else -0.001, 0.002)
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
    namen = ["Jane Doe", "John Roe", "Max Muster", "Erika Beispiel", "Alex Sample"]
    rollen = [("Chief Executive Officer", "CEO"), ("Chief Financial Officer", "CFO"), ("Director", "Direktor"),
              ("EVP Operations", "Vorstand"), ("10% Owner", "10%-Eigner")]
    zeilen = []

    def zeile(d, t, j, wert, typ="Kauf", plan=False):
        de = t.endswith(".DE")
        rl = rollen[j % 5]
        px = float(C[t].iloc[d])
        return {"datum": idx[d], "handel": idx[max(d - 2, 0)], "ticker": t, "insider": f"P{j}", "name": namen[j % 5],
                "rolle": "Vorstand" if de and rl[1] in ("CEO", "Vorstand") else ("Aufsichtsrat" if de and rl[1] == "Direktor" else rl[0]),
                "kat": rl[1], "typ": typ, "stueck": wert / px, "preis": px, "wert": float(wert),
                "waehrung": "EUR" if de else "USD", "plan": plan, "land": "DE" if de else "USA",
                # Bestand danach: mal kleiner Aufstockungskauf, mal starke Aufstockung
                "bestand": np.nan if de else wert / px * (1 + float(rng.choice([0.3, 2, 8, 40, 400])))}
    for _ in range(60):
        t = aktien[int(rng.integers(0, len(aktien)))]
        k = int(rng.integers(300, tage - 1))
        for j in range(int(rng.integers(1, 4))):
            zeilen.append(zeile(k, t, j, rng.uniform(3e4, 9e5)))
    for _ in range(120):
        t = aktien[int(rng.integers(0, len(aktien)))]
        k = int(rng.integers(tage - 60, tage - 1))
        zeilen.append(zeile(k, t, int(rng.integers(0, 5)), rng.uniform(1e5, 8e6), "Verkauf", bool(rng.random() < 0.6)))
    for t in aktien[:12]:
        for j in range(3):
            zeilen.append(zeile(tage - 2, t, j, 450_000.0))
    for t in aktien[n:n + 3]:
        for j in range(2):
            zeilen.append(zeile(tage - 5, t, j, 180_000.0))
    firmen = {t: f"Demo Firma {t[-3:]}" for t in aktien[:n]}
    firmen.update({t: f"Demo AG {t[3:5]}" for t in aktien[n:]})
    sek = [("Health Care", "Managed Health Care"), ("Health Care", "Biotechnology"), ("Information Technology", "Software"),
           ("Financials", "Banks"), ("Industrials", "Machinery"), ("Consumer Discretionary", "Retail"),
           ("Energy", "Oil & Gas"), ("Utilities", "Electric Utilities")]
    sektoren = {t: sek[i % len(sek)] for i, t in enumerate(aktien)}
    status = {"ok": True, "quellen": ["DEMO: erfundene Insider-Daten"], "luecken": [], "fehler": [],
              "anzahl": len(zeilen), "von": str(idx[300].date()), "bis": str(idx[-2].date())}
    return kurse, aktien, firmen, pd.DataFrame(zeilen, columns=INSIDER_SPALTEN), status, sektoren
