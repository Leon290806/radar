# -*- coding: utf-8 -*-
"""Bitcoin-Radar: tägliche Langfrist-Bewertung (Power Law, On-Chain, Zyklus, Stimmung) mit gelernter Gesamtnote."""
import json
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(1, os.path.dirname(HIER))

import einstellungen as E  # noqa: E402
import daten  # noqa: E402
import analyse as AN  # noqa: E402
import seite  # noqa: E402
import schutz  # noqa: E402


def laden():
    try:
        if E.PASSWORT and os.path.exists(E.JOURNAL):
            return schutz.journal_laden(E.JOURNAL, E.PASSWORT)
        if not E.PASSWORT and os.path.exists(E.JOURNAL_KLAR):
            return json.load(open(E.JOURNAL_KLAR, encoding="utf-8"))
    except Exception as ex:
        print("Journal nicht lesbar:", type(ex).__name__)
    return {}


def speichern(J):
    if E.PASSWORT:
        schutz.journal_speichern(J, E.JOURNAL, E.PASSWORT)
    else:
        os.makedirs(os.path.dirname(E.JOURNAL_KLAR), exist_ok=True)
        json.dump(J, open(E.JOURNAL_KLAR, "w", encoding="utf-8"), ensure_ascii=False)


def push(text, titel, dringend=False):
    if not E.NTFY_THEMA:
        return
    try:
        requests.post(f"https://ntfy.sh/{E.NTFY_THEMA}", data=text.encode("utf-8"), timeout=20,
                      headers={"Title": titel.encode("utf-8"), "Click": E.DASHBOARD_URL, "Tags": "chart_with_upwards_trend",
                               "Priority": "high" if dringend else "default"})
    except requests.RequestException:
        pass


def _geld(x):
    return f"{x:,.0f} $".replace(",", ".")


def main():
    t0 = time.time()
    J = laden()
    prot = []
    cm = daten.coinmetrics()
    fng = daten.fear_greed()
    J["bgeo"] = daten.bgeo(J.get("bgeo", {}), prot)
    print("CoinMetrics:", len(cm), "Tage · Fear & Greed:", len(fng), "Tage")
    A = AN.analyse(cm, fng)
    stand = int(time.time() * 1000)
    D = seite.daten(A, J["bgeo"], stand, [{"zeit": p["zeit"], "text": p["text"]} for p in J.get("protokoll", [])])
    zone, score = D["zone"], D["score"]
    print(f"Stand {D['datum']}: Kurs {D['preis']:.0f} $, Score {score}, Zone {zone}, Power-Law fair {D['pl']['fair']:.0f} $")

    alt = J.get("zone")
    stats = {z["zone"]: z for z in D["zonen"]}.get(zone) or {}
    hist = (f"Historisch nach dieser Zone: 12 Monate später im Median {stats['median_12m'] * 100:+.0f} %, "
            f"in {stats['anteil_plus'] * 100:.0f} % der Fälle im Plus." if stats.get("median_12m") is not None else "")
    if alt and alt != zone:
        push(f"Neue Zone: {zone} (vorher {alt}), Score {score:.0f}/100.\nKurs {_geld(D['preis'])} · fairer Wert (Power Law) {_geld(D['pl']['fair'])}.\n{hist}",
             f"₿ Bitcoin-Radar: {zone}", dringend=zone in ("Strong Buy", "Strong Sell"))
        prot.append(f"Zonenwechsel: {alt} → {zone} (Score {score:.0f})")
    elif not alt:
        push(f"Aktuelle Einschätzung: {zone}, Score {score:.0f}/100.\nKurs {_geld(D['preis'])} · fairer Wert (Power Law) {_geld(D['pl']['fair'])}.\n{hist}\n"
             "Ab jetzt Push bei jedem Zonenwechsel und montags eine Kurzübersicht.", "₿ Bitcoin-Radar gestartet")
    jetzt = datetime.now(ZoneInfo(E.ZEITZONE))
    woche = jetzt.strftime("%G-%V")
    if alt and jetzt.weekday() == 0 and J.get("wochen_push") != woche:
        J["wochen_push"] = woche
        k = D["kennzahlen"]
        push(f"{zone} · Score {score:.0f}/100 (vor 7 Tagen {D['score_vor'][7] or 0:.0f})\nKurs {_geld(D['preis'])} · MVRV-Z {k['mvrv_z']:.2f} · "
             f"Fear & Greed {k['fng']:.0f}\nTag {D['zyklus']['tag']} nach dem Halving.", "₿ Bitcoin-Radar: Wochenstand")
    J["zone"], J["score"], J["stand"] = zone, score, stand
    J["protokoll"] = ([{"zeit": stand, "text": p} for p in prot] + J.get("protokoll", []))[:60]
    J["verlauf"] = (J.get("verlauf", []) + [[D["datum"], score, zone]])[-400:]
    D["protokoll"] = J["protokoll"][:30]

    speichern(J)
    html = seite.erstelle(D)
    if E.PASSWORT:
        html = schutz.dashboard_sperren(html, E.PASSWORT)
    os.makedirs(os.path.dirname(E.SEITE), exist_ok=True)
    open(E.SEITE, "w", encoding="utf-8").write(html)
    print(f"Fertig in {time.time() - t0:.0f} s, Seite {len(html) // 1024} KB")


if __name__ == "__main__":
    main()
