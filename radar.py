# -*- coding: utf-8 -*-
"""
Strategie-Radar – täglicher Lauf.

  python radar.py                 normaler Tageslauf (holt Daten, aktualisiert Journal + Dashboard)
  python radar.py --demo          Probelauf mit erfundenen Daten
  python radar.py --neu           Journal verwerfen und neu mit Rückblick starten
  python radar.py --neu --rueckblick 500   längerer Rückblick (mehr Daten, dauert länger)

Der Radar handelt nicht selbst. Er führt ein Musterdepot und sagt dir, was zu tun ist.
"""
import argparse
import datetime as dt
import json
import math
import os
import webbrowser
from zoneinfo import ZoneInfo

import pandas as pd
import requests

import config as cfg
import daten
import engine
import aufbereiten
import dashboard
import schutz
import lernen


def lade_journal(pfad):
    try:
        with open(pfad, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def speichere_journal(dep, pfad):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    tmp = pfad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dep, f, ensure_ascii=False, indent=1, default=float)
    os.replace(tmp, pfad)


def unfertigen_tag_entfernen(kurse):
    """Läuft das Skript während der US-Handelszeit, ist der letzte Tag noch nicht fertig."""
    jetzt = dt.datetime.now(ZoneInfo("America/New_York"))
    letzter = kurse["Close"].index[-1].date()
    if letzter == jetzt.date() and jetzt.time() < dt.time(16, 20):
        print("US-Handel läuft noch – heutiger Tag wird ignoriert.")
        return {f: v.iloc[:-1] for f, v in kurse.items()}
    return kurse


def pead_pruefer():
    """Bestätigt live, dass ein Kurssprung von Quartalszahlen kam (nicht z. B. von einer Übernahme)."""
    import yfinance as yf

    def pruefe(ticker, ev_datum):
        try:
            ed = yf.Ticker(ticker).get_earnings_dates(limit=12)
            if ed is None or ed.empty:
                return True                    # keine Info -> nicht blockieren
            return any(0 <= (ev_datum - d.date()).days <= 3 for d in ed.index)
        except Exception:
            return True
    return pruefe


def baue_aktionen(dep, eurusd):
    letzter = dep["letzter_tag"]
    out = []
    for tr in dep["trades"]:
        if tr["status"] == "geplant" and tr["signal_datum"] == letzter:
            fx = eurusd if daten.waehrung(tr["ticker"]) == "USD" else 1.0
            eur = tr["gewicht"] * cfg.KAPITAL_EUR
            out.append({"typ": "kaufen", "trade": tr, "eur": eur, "stueck": int(math.floor(eur * fx / tr["signal_kurs"]))})
    for tr in dep["trades"]:
        if tr["status"] == "offen" and tr.get("verkaufen_geplant"):
            out.append({"typ": "verkaufen", "trade": tr})
        elif tr["status"] == "geschlossen" and tr.get("ausstieg_datum") == letzter and tr["ausstieg_grund"] == "Stopp":
            out.append({"typ": "gestoppt", "trade": tr})
        elif tr["status"] == "offen" and tr.get("stopp_vortag") and tr["stopp"] > tr["stopp_vortag"] * 1.005:
            out.append({"typ": "stopp", "trade": tr})
    return out


def benachrichtigen(aktionen):
    if not cfg.NTFY_THEMA or not aktionen:
        return
    teile = []
    for a in aktionen:
        tr = a["trade"]
        if a["typ"] == "kaufen":
            teile.append(f"KAUFEN {tr['ticker']}: {tr['gewicht']:.0%} des Portfolios (ca. {a['eur']:.0f} EUR), "
                         f"Limit {tr['limit']:.2f}, Stopp {tr['stopp_hinweis']:.2f}")
        elif a["typ"] == "verkaufen":
            teile.append(f"VERKAUFEN {tr['ticker']} zur Eröffnung ({tr['verkaufen_geplant']})")
        elif a["typ"] == "gestoppt":
            teile.append(f"AUSGESTOPPT {tr['ticker']} ({tr['ergebnis']:+.1%})")
        elif a["typ"] == "stopp":
            teile.append(f"Stopp {tr['ticker']} auf {tr['stopp']:.2f} anheben")
    wichtig = any(a["typ"] != "stopp" for a in aktionen)
    titel = "Radar: neue Empfehlung" if any(a["typ"] == "kaufen" for a in aktionen) else "Radar: Update"
    headers = {"Title": titel, "Priority": "high" if wichtig else "low", "Tags": "chart_with_upwards_trend"}
    if cfg.DASHBOARD_URL:
        headers["Click"] = cfg.DASHBOARD_URL
    try:
        requests.post(f"https://ntfy.sh/{cfg.NTFY_THEMA}", data="\n".join(teile).encode("utf-8"),
                      headers=headers, timeout=20)
    except Exception as e:
        print(f"Push-Nachricht fehlgeschlagen: {e}")


def main():
    ap = argparse.ArgumentParser(description="Strategie-Radar")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--neu", action="store_true", help="Journal neu beginnen")
    ap.add_argument("--rueckblick", type=int, default=cfg.RUECKBLICK_TAGE)
    ap.add_argument("--lernen", action="store_true", help="Lernmodul sofort ausführen")
    ap.add_argument("--kein-browser", action="store_true")
    args = ap.parse_args()

    pw = "" if args.demo else cfg.RADAR_PASSWORT
    if os.environ.get("CI") and not pw:
        raise SystemExit("RADAR_PASSWORT fehlt (GitHub: Settings → Secrets → Actions). Ohne Passwort wäre alles öffentlich lesbar.")
    journal_pfad = "speicher/journal_demo.json" if args.demo else (cfg.JOURNAL_DATEI_GESCHUETZT if pw else cfg.JOURNAL_DATEI)
    dash_pfad = "docs/demo.html" if args.demo else cfg.DASHBOARD_DATEI
    dep = None
    if not (args.neu or args.demo) and os.path.exists(journal_pfad):
        try:
            dep = schutz.journal_laden(journal_pfad, pw) if pw else lade_journal(journal_pfad)
        except Exception:
            raise SystemExit("Journal lässt sich nicht öffnen – Passwort geändert? Mit --neu neu beginnen.")
    hinweise = []
    if dep is not None and dep.get("version", 2) < engine.VERSION:
        dep = None
        hinweise.append(f"Journal wurde mit den neuen Regeln (Version {engine.VERSION}) neu aufgebaut.")

    print("Strategie-Radar" + (" – DEMO" if args.demo else ""))
    bench_ticker = [t for _, t in cfg.BENCHMARKS]
    if args.demo:
        kurse, aktien, firmen, insider, ins_status, sektoren = daten.demo_daten()
    else:
        aktien, firmen, h, sektoren = daten.lade_universum(cfg.UNIVERSEN)
        hinweise += h
        offen = [t["ticker"] for t in (dep or {}).get("trades", []) if t["status"] in ("offen", "geplant")]
        aktien = list(dict.fromkeys(aktien + cfg.ZUSATZ_TICKER + offen))
        jahre = max(3, 2 + math.ceil((max(args.rueckblick, cfg.LERN_FENSTER) if dep is None else cfg.LERN_FENSTER) / 250))
        print(f"{len(aktien)} Aktien – Kurse laden ({jahre} Jahre) ...")
        kurse = daten.lade_kurse(list(dict.fromkeys(aktien + ["SPY", "^GSPC", "EURUSD=X"] + bench_ticker)), jahre=jahre)
        kurse = unfertigen_tag_entfernen(kurse)
        insider, ins_status = None, {"ok": False, "quellen": [], "luecken": [], "fehler": ["Insider-Modul ausgeschaltet"], "anzahl": 0}
        if cfg.INSIDER_AKTIV:
            idx = kurse["Close"].index
            tage_zurueck = max(args.rueckblick if dep is None else 30, cfg.LERN_FENSTER) + 40 + cfg.INSIDER_HISTORIE_TAGE
            von = (idx[max(0, len(idx) - tage_zurueck)] - pd.Timedelta(days=20)).date()
            print(f"Insider-Transaktionen ab {von} laden (SEC, BaFin) ...")
            insider, ins_status = daten.lade_insider(von, cfg.SEC_USER_AGENT, set(aktien), firmen, cfg.INSIDER_LAENDER)
            print(f"  {ins_status['anzahl']} Transaktionen · Fehler: {ins_status['fehler'] or 'keine'}")
            for f in ins_status["fehler"]:
                hinweise.append(f"Insider-Daten: {f}")

    C_alle = kurse["Close"]
    aktien = [t for t in aktien if t in C_alle.columns and C_alle[t].notna().sum() > 270]
    print(f"Signale berechnen für {len(aktien)} Aktien ...")
    s = engine.berechne_signale(kurse, aktien, insider, cfg, sektoren=sektoren)
    idx = s["C"].index
    bench = C_alle["SPY"].reindex(idx).ffill() if "SPY" in C_alle else None
    eurusd = float(C_alle["EURUSD=X"].dropna().iloc[-1]) if "EURUSD=X" in C_alle else 1.1

    if dep is None:
        dep = engine.neues_depot()
        start = max(300, len(idx) - 1 - args.rueckblick)
        tage = list(range(start, len(idx)))
        dep["start"] = idx[start].date().isoformat()
        print(f"Neues Journal: Rückblick ab {dep['start']} ({len(tage)} Handelstage)")
    else:
        letzter = pd.Timestamp(dep["letzter_tag"])
        tage = [d for d in range(len(idx)) if idx[d] > letzter]
        fehlend = [t["ticker"] for t in dep["trades"] if t["status"] in ("offen", "geplant") and t["ticker"] not in s["C"].columns]
        if fehlend:
            hinweise.append("Keine Kurse für offene Position(en): " + ", ".join(fehlend))
    par = lernen.parameter(cfg, dep.get("parameter"))
    score = engine.kombiniere(s, par)
    pruefer = None if args.demo else pead_pruefer()
    for d in tage:
        letzter_tag = d == len(idx) - 1
        modus = "Live" if (dep["live_seit"] or letzter_tag) else "Rückblick"
        engine.tag_verarbeiten(dep, s, d, par, modus, firmen, bench, pruefe_pead=pruefer if letzter_tag else None,
                               score=score, status_merken=letzter_tag)
    if dep["live_seit"] is None:
        dep["live_seit"] = dep["letzter_tag"]
    if tage or args.lernen:
        print(lernen.lernen(dep, s, cfg, bench, erzwingen=args.lernen))
        par = lernen.parameter(cfg, dep.get("parameter"))
        score = engine.kombiniere(s, par)
    if pw:
        schutz.journal_speichern(dep, journal_pfad, pw)
    else:
        speichere_journal(dep, journal_pfad)

    aktionen = baue_aktionen(dep, eurusd)
    kand = engine.kandidaten(s, len(idx) - 1, 30, score)

    oddlot = []
    if cfg.ODDLOT_AKTIV and not args.demo:
        try:
            oddlot = daten.suche_oddlot(cfg.SEC_USER_AGENT, cfg.ODDLOT_TAGE)
        except Exception as e:
            hinweise.append(f"Odd-Lot-Suche fehlgeschlagen ({e}).")

    print("Dashboard bauen ...")
    D = aufbereiten.dashboard_daten(dep, s, score, par, cfg, C_alle, aktionen, kand, insider, ins_status, firmen,
                                    oddlot, hinweise, args.demo, eurusd)
    html = dashboard.erstelle(D)
    if pw:
        html = schutz.dashboard_sperren(html, pw)
    os.makedirs(os.path.dirname(dash_pfad), exist_ok=True)
    with open(dash_pfad, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nStand {dep['letzter_tag']} – {len(tage)} neue(r) Handelstag(e) verarbeitet")
    if not aktionen:
        print("Heute nichts zu tun.")
    for a in aktionen:
        tr = a["trade"]
        print(f"  {a['typ'].upper():10s} {tr['ticker']}  " + (f"{tr['gewicht']:.0%}" if a["typ"] == "kaufen" else ""))
    print(f"Dashboard: {os.path.abspath(dash_pfad)} ({len(html) / 1e6:.1f} MB)")

    if tage and not args.demo:
        benachrichtigen(aktionen)
    if not args.kein_browser and not os.environ.get("CI"):
        webbrowser.open("file://" + os.path.abspath(dash_pfad))


if __name__ == "__main__":
    main()
