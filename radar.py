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
import forschung
import broker
import krypto
import chartstrategien
import trend


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


def _p(x, n=1):
    return f"{x * 100:+.{n}f} %".replace(".", ",")


def _lauf(tr):
    try:
        return tr["kurs"] / tr["einstieg_kurs"] - 1
    except (KeyError, TypeError, ZeroDivisionError):
        return 0.0


def tagesfazit(dep, aktionen, s, par):
    """Kurzer Text: was der Radar heute getan hat und was er gerade denkt."""
    z = []
    for a in aktionen:
        tr = a["trade"]
        if a["typ"] == "kaufen":
            z.append(f"🟢 KAUFEN {tr['ticker']}: {tr['gewicht']:.0%} des Portfolios zur Eröffnung, Limit {tr['limit']:.2f}, "
                     f"Stopp {tr['stopp_hinweis']:.2f}. Grund: {(tr.get('gruende') or ['–'])[0]}")
        elif a["typ"] == "verkaufen":
            z.append(f"🔴 VERKAUFEN {tr['ticker']} zur Eröffnung ({tr['verkaufen_geplant']}), Stand {_p(_lauf(tr))}")
        elif a["typ"] == "gestoppt":
            z.append(f"⛔ AUSGESTOPPT {tr['ticker']}: {_p(tr['ergebnis'])}")
        elif a["typ"] == "stopp":
            z.append(f"↗ Stopp {tr['ticker']} nachgezogen auf {tr['stopp']:.2f}")
    if not z:
        z.append("Heute keine Änderung.")
    # Depot
    k = dep["kurve"]
    offen = [t for t in dep["trades"] if t["status"] == "offen"]
    if len(k) >= 2:
        heute = k[-1][1] / k[-2][1] - 1
        live = next((x for x in k if x[0] >= (dep.get("live_seit") or k[0][0])), k[0])
        z.append(f"\n📊 Musterdepot heute {_p(heute)} · seit Live-Start {_p(k[-1][1] / live[1] - 1)} · {len(offen)}/{par.MAX_POSITIONEN} Positionen")
    if offen:
        best, schlecht = max(offen, key=_lauf), min(offen, key=_lauf)
        z.append(f"Bester: {best['ticker']} {_p(_lauf(best))} · Schwächster: {schlecht['ticker']} {_p(_lauf(schlecht))}")
    # Markt und Gedanke
    reg = bool(s["regime"].iloc[-1])
    abst = float(s["regime_abst"].iloc[-1]) if "regime_abst" in s else None
    z.append(f"🌍 Markt: {'Aufwärtstrend' if reg else 'Abwärtstrend'}" + (f" (S&P 500 {_p(abst)} zur 200-Tage-Linie)" if abst is not None else "")
             + ("" if reg else " – freies Geld im Geldmarkt"))
    status = dep.get("kandidaten_status") or {}
    if not any(a["typ"] == "kaufen" for a in aktionen):
        if len(offen) >= par.MAX_POSITIONEN:
            gedanke = "Portfolio ist voll – neue Signale erst, wenn eine Position schließt."
        else:
            warte = [f"{t}: {v}" for t, v in status.items() if "KAUF" not in v and "Bereits" not in v][:1]
            gedanke = "Kein Signal stark genug." + (f" Nächster Kandidat – {warte[0]}" if warte else "")
        z.append(f"💭 {gedanke}")
    # Krypto-Simulation
    kr = ((dep.get("krypto") or {}).get("live") or {})
    for pid, name in (("h2", "Krypto 2×"), ("profi", "Krypto Profi")):
        L = kr.get(pid) or {}
        if L.get("kurve"):
            j = L.get("jetzt") or {}
            haelt = ", ".join(h["coin"] for h in j.get("halten") or []) or "Stablecoin"
            z.append(f"🪙 {name}: hält {haelt} · erwartet {_p(j.get('erwartet') or 0)} p.a. · seit Start "
                     f"{_p(L['kurve'][-1][1] / L['kurve'][0][1] - 1, 2)}")
    # Broker
    b = dep.get("broker") or {}
    if b.get("verbunden"):
        kt, st = b.get("konto") or {}, b.get("start") or {}
        if kt.get("equity"):
            z.append(f"🏦 Alpaca: {kt['equity']:,.0f} $".replace(",", ".")
                     + (f" ({_p(kt['equity'] / st['equity'] - 1)} seit Start)" if st.get("equity") else "")
                     + f" · {len(b.get('positionen') or [])} Positionen · {len(b.get('orders') or [])} offene Orders")
        if b.get("fehler"):
            z.append("⚠ Broker-Fehler: " + b["fehler"][0][:150])
    return "\n".join(z)


def benachrichtigen(dep, aktionen, s, par):
    """Push-Nachricht nach jedem Tageslauf: Aktionen + Kurzfazit. Wichtig = Kauf, Verkauf, Stopp ausgelöst, Broker-Fehler."""
    if not cfg.NTFY_THEMA:
        return
    try:
        text = tagesfazit(dep, aktionen, s, par)
        kauf = sum(a["typ"] == "kaufen" for a in aktionen)
        raus = sum(a["typ"] in ("verkaufen", "gestoppt") for a in aktionen)
        fehler = bool((dep.get("broker") or {}).get("fehler"))
        teile = ([f"{kauf} Kauf"] if kauf else []) + ([f"{raus} Verkauf"] if raus else [])
        titel = f"Radar {pd.Timestamp(dep['letzter_tag']):%d.%m.}: " + (", ".join(teile) if teile else "Tagesfazit")
        headers = {"Title": titel.encode("utf-8"), "Priority": "high" if (kauf or raus or fehler) else "default",
                   "Tags": "chart_with_upwards_trend"}
        if cfg.DASHBOARD_URL:
            headers["Click"] = cfg.DASHBOARD_URL
        requests.post(f"https://ntfy.sh/{cfg.NTFY_THEMA}", data=text.encode("utf-8"), headers=headers, timeout=20)
    except Exception as e:
        print(f"Push-Nachricht fehlgeschlagen: {str(e)[:120]}")


def main():
    ap = argparse.ArgumentParser(description="Strategie-Radar")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--neu", action="store_true", help="Journal neu beginnen")
    ap.add_argument("--rueckblick", type=int, default=cfg.RUECKBLICK_TAGE)
    ap.add_argument("--lernen", action="store_true", help="Lernmodul sofort ausführen")
    ap.add_argument("--forschung", action="store_true", help="Forschungslabor sofort ausführen")
    ap.add_argument("--kein-browser", action="store_true")
    ap.add_argument("--bericht", action="store_true", help="nur Forschungsbericht ins Protokoll (ohne Journal, ohne Dashboard)")
    args = ap.parse_args()

    pw = "" if args.demo else cfg.RADAR_PASSWORT
    if os.environ.get("CI") and not pw and not args.bericht:
        raise SystemExit("RADAR_PASSWORT fehlt (GitHub: Settings → Secrets → Actions). Ohne Passwort wäre alles öffentlich lesbar.")
    journal_pfad = "speicher/journal_demo.json" if args.demo else (cfg.JOURNAL_DATEI_GESCHUETZT if pw else cfg.JOURNAL_DATEI)
    dash_pfad = "docs/demo.html" if args.demo else cfg.DASHBOARD_DATEI
    dep = None
    if not (args.neu or args.demo or args.bericht) and os.path.exists(journal_pfad):
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
        jahre = max(3, 2 + math.ceil((max(args.rueckblick, cfg.LERN_FENSTER) if dep is None else cfg.LERN_FENSTER) / 250),
                    cfg.FORSCHUNG_JAHRE if cfg.FORSCHUNG_AKTIV else 0)
        print(f"{len(aktien)} Aktien – Kurse laden ({jahre} Jahre) ...")
        kurse = daten.lade_kurse(list(dict.fromkeys(aktien + ["SPY", "^GSPC", "EURUSD=X"] + bench_ticker)), jahre=jahre)
        kurse = unfertigen_tag_entfernen(kurse)
        insider, ins_status = None, {"ok": False, "quellen": [], "luecken": [], "fehler": ["Insider-Modul ausgeschaltet"], "anzahl": 0}
        if cfg.INSIDER_AKTIV:
            idx = kurse["Close"].index
            tage_zurueck = max(args.rueckblick if dep is None else 30, cfg.LERN_FENSTER) + 40 + cfg.INSIDER_HISTORIE_TAGE
            von = (idx[0] if cfg.FORSCHUNG_AKTIV else idx[max(0, len(idx) - tage_zurueck)] - pd.Timedelta(days=20)).date()
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
    # Kern (freies Geld) laut Trend-Baustein: Index, Hebel und Trendfilter mit der besten Lern-Bilanz
    trend_aktien = None
    if getattr(cfg, "TREND_AKTIV", True) and not args.demo:
        try:
            print("Trend-Baustein: Kern-Varianten testen ...")
            trend_aktien = trend.aktien_forschen()
            fest = getattr(cfg, "TREND_KERN_FEST", None)
            if fest and any(v["id"] == fest for v in trend_aktien["varianten"]):
                trend_aktien["bester"] = fest
                trend_aktien["jetzt"] = trend.aktien_jetzt_fuer(trend_aktien)
            if getattr(cfg, "TREND_KERN", True):
                s["kern"], s["kern_pos"] = trend.kern_serie(trend_aktien, idx)
                s["kern_name"] = next(v["name"] for v in trend_aktien["varianten"] if v["id"] == trend_aktien["bester"])
                s.pop("_np", None)
                print(f"  Kern: {s['kern_name']}")
        except Exception as e:
            print(f"Trend-Baustein: Fehler ({str(e)[:150]}) – Kern bleibt S&P 500 mit 200-Tage-Linie")
            trend_aktien = None
    eurusd = float(C_alle["EURUSD=X"].dropna().iloc[-1]) if "EURUSD=X" in C_alle else 1.1

    if args.bericht:
        tmp = engine.neues_depot()
        grenze = idx[max(300, len(idx) - 1 - cfg.RUECKBLICK_TAGE)]
        print(forschung.forschen(tmp, s, s.get("insider"), cfg, bench, grenze))
        print(forschung.bericht(tmp["forschung"], s, bench))
        if getattr(cfg, "KRYPTO_AKTIV", False):
            try:
                print(krypto.bericht_alle(cfg))
            except Exception as e:
                print(f"Krypto-Bericht fehlgeschlagen: {str(e)[:200]}")
            try:
                print(chartstrategien.bericht(chartstrategien.forschen()))
            except Exception as e:
                print(f"Krypto-Bericht fehlgeschlagen: {str(e)[:200]}")
        try:
            print(trend.bericht(trend_aktien, trend.krypto_forschen()))
        except Exception as e:
            print(f"Trend-Bericht fehlgeschlagen: {str(e)[:200]}")
        return

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
    if cfg.FORSCHUNG_AKTIV and (forschung.faellig(dep, idx, cfg.FORSCHUNG_INTERVALL) or args.forschung):
        print("Forschungslabor ...")
        print(forschung.forschen(dep, s, insider if s.get("insider") is None else s["insider"], cfg, bench, dep["start"]))
        for g in (dep.get("forschung") or {}).get("gedanken", []):     # nur Statistik, keine Positionen
            print("  - " + g)
    par = lernen.alle_parameter(cfg, dep)
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
        par = lernen.alle_parameter(cfg, dep)
        score = engine.kombiniere(s, par)
    if not args.demo:
        try:
            kt, k_an = getattr(cfg, "BROKER_KERN_TICKER", "SPY"), bool(s["regime"].iloc[-1])
            if trend_aktien and getattr(cfg, "TREND_KERN", True):
                vb = next(v for v in trend_aktien["varianten"] if v["id"] == trend_aktien["bester"])
                kt, k_an = vb["etf_us"], bool(trend_aktien["jetzt"]["an"])
            kk = trend.letzter_kurs(kt) if kt not in C_alle.columns else (float(C_alle[kt].dropna().iloc[-1]) if C_alle[kt].notna().any() else None)
            print(broker.synchronisieren(dep, cfg, k_an, kk, kern=kt))
        except Exception as e:
            print(f"Broker: Fehler ({str(e)[:120]})")
    if not args.demo and getattr(cfg, "KRYPTO_AKTIV", False):
        try:
            kb = {n: C_alle[t] for n, t in cfg.BENCHMARKS if t in C_alle.columns}
            print(krypto.lauf(dep, cfg, bench=kb)[0])
            print(chartstrategien.lauf(dep, cfg))
        except Exception as e:
            print(f"Krypto: Fehler ({str(e)[:150]})")
            (dep.setdefault("krypto", {}))["fehler"] = str(e)[:300]
    if not args.demo and getattr(cfg, "TREND_AKTIV", True):
        try:
            print(trend.lauf(dep, cfg, aktien=trend_aktien))
        except Exception as e:
            print(f"Trend: Fehler ({str(e)[:150]})")
    if pw:
        schutz.journal_speichern(dep, journal_pfad, pw)
    else:
        speichere_journal(dep, journal_pfad)

    aktionen = baue_aktionen(dep, eurusd)
    kand = engine.kandidaten(s, len(idx) - 1, 30, score, par)

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
    if os.environ.get("CI"):
        aktionen_log = []        # Protokoll ist bei öffentlichem Repository sichtbar – Empfehlungen nur im Dashboard
    else:
        aktionen_log = aktionen
        if not aktionen:
            print("Heute nichts zu tun.")
    for a in aktionen_log:
        tr = a["trade"]
        print(f"  {a['typ'].upper():10s} {tr['ticker']}  " + (f"{tr['gewicht']:.0%}" if a["typ"] == "kaufen" else ""))
    print(f"Dashboard: {os.path.abspath(dash_pfad)} ({len(html) / 1e6:.1f} MB)")

    if tage and not args.demo:
        benachrichtigen(dep, aktionen, s, par)
    if not args.kein_browser and not os.environ.get("CI"):
        webbrowser.open("file://" + os.path.abspath(dash_pfad))


if __name__ == "__main__":
    main()
