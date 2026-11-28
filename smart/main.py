# -*- coding: utf-8 -*-
"""
Smart-Money-Radar: beobachtet beständige Top-Trader auf Hyperliquid und testet per Papier-Handel,
ob man mit ihnen Geld verdient hätte. Es werden NIE echte Orders gesendet.
Ablauf je Lauf (alle ~15 Min.): Preise -> (einmal täglich) Trader-Auswahl -> Positionen -> Konsens ->
Papier-Portfolio + Einzel-Kopie-Test -> Push bei Papier-Trades -> Dashboard (alle 2 Std. oder bei Trades).
"""
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
import hl  # noqa: E402
import auswahl  # noqa: E402
import signale as SG  # noqa: E402
import spiegel as SP  # noqa: E402
import polymarket as PMK  # noqa: E402
import wetter as WX  # noqa: E402
import seite  # noqa: E402
import schutz  # noqa: E402


def _laden(pfad):
    if not os.path.exists(pfad):
        return None
    try:
        if E.PASSWORT:
            return schutz.journal_laden(pfad, E.PASSWORT)
        with open(pfad, encoding="utf-8") as f:
            return json.load(f)
    except Exception as ex:
        print("Laden fehlgeschlagen:", pfad, type(ex).__name__)
        return None


def zustand_laden():
    """Neuesten Stand nehmen: Zwischenstand aus dem GitHub-Cache oder den zuletzt ins Repo geschriebenen."""
    kandidaten = [_laden(E.JOURNAL_CACHE), _laden(E.JOURNAL if E.PASSWORT else E.JOURNAL_KLAR)]
    kandidaten = [k for k in kandidaten if k]
    if not kandidaten:
        return {}
    return max(kandidaten, key=lambda s: s.get("stand", 0))


def _speichern(S, pfad):
    if E.PASSWORT:
        schutz.journal_speichern(S, pfad, E.PASSWORT)
    else:
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        with open(pfad.replace(".enc", ".json"), "w", encoding="utf-8") as f:
            json.dump(S, f, ensure_ascii=False)


def push(text, titel):
    if not E.NTFY_THEMA:
        return
    try:
        requests.post(f"https://ntfy.sh/{E.NTFY_THEMA}", data=text.encode("utf-8"), timeout=20,
                      headers={"Title": titel.encode("utf-8"), "Click": E.DASHBOARD_URL, "Tags": "brain"})
    except requests.RequestException:
        pass


def _preis(x):
    return f"{x:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".") if x < 10 else f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def push_ereignisse(ereignisse):
    for art, d in ereignisse[:E.MAX_PUSH_PRO_LAUF]:
        richtung = "LONG" if d["r"] > 0 else "SHORT"
        if art == "auf":
            push(f"{d['gleich']} von {d['n']} beobachteten Top-Tradern sind {richtung} in {d['coin']}.\n"
                 f"Papier-Einstieg zu {_preis(d['ein'])} $ ({round(d['notional'])} $ simuliert). Nur Test, keine echte Order.",
                 f"🧠 Smart Money: {richtung} {d['coin']}")
        else:
            vz = "+" if d["ergebnis"] >= 0 else ""
            push(f"Konsens in {d['coin']} ist weg – Papier-Position geschlossen.\nErgebnis: {vz}{d['ergebnis']:.0f} $ ({vz}{d['pct'] * 100:.1f} %).",
                 f"🧠 Smart Money: {d['coin']} geschlossen")


def _kurz(a, namen):
    return namen.get(a) or (a[:6] + "…" + a[-4:])


def push_spiegel(ereignisse, namen):
    start = [e for e in ereignisse if e.get("grund") == "Start"]
    if start:
        einsatz = sum(e["notional"] for e in start)
        push(f"{len(start)} Positionen von {len({e['a'] for e in start})} Tradern gespiegelt, {einsatz:,.0f} $ im Markt.".replace(",", ".") +
             "\nAb jetzt Push bei Spiegel-Trades ab " + f"{E.SPIEGEL_PUSH_AB:,.0f} $".replace(",", ".") + " und abends der Tagesstand. Nur Papier-Test.",
             "🪞 Spiegel-Portfolio gestartet")
        ereignisse = [e for e in ereignisse if e.get("grund") != "Start"]
    gross = [e for e in ereignisse if e["art"] in ("auf", "zu") and e["notional"] >= E.SPIEGEL_PUSH_AB]
    if not gross:
        return
    zeilen = []
    for e in gross[:6]:
        richtung = "LONG" if e["r"] > 0 else "SHORT"
        if e["art"] == "auf":
            zeilen.append(f"+ {richtung} {e['coin']} {e['notional']:,.0f} $ ({_kurz(e['a'], namen)})".replace(",", "."))
        else:
            vz = "+" if e["ergebnis"] >= 0 else ""
            zeilen.append(f"– {e['coin']} zu, {vz}{e['ergebnis']:,.0f} $ ({_kurz(e['a'], namen)})".replace(",", "."))
    if len(gross) > 6:
        zeilen.append(f"… und {len(gross) - 6} weitere")
    push("\n".join(zeilen) + "\nNur Papier-Test.", f"🪞 Spiegel-Portfolio: {len(gross)} Trade{'s' if len(gross) > 1 else ''}")


def tages_push(S, preise):
    jetzt = datetime.now(ZoneInfo(E.ZEITZONE))
    heute = jetzt.date().isoformat()
    if jetzt.hour < E.TAGES_PUSH_STUNDE or S.get("tages_push") == heute:
        return
    S["tages_push"] = heute
    sp, ko = S.get("spiegel") or {}, S.get("portfolio") or {}
    btc = (preise.get("BTC") or {}).get("px")
    def r(x, k):
        return (x / k - 1) * 100 if x and k else 0
    w_sp = SP.wert(sp, preise) if sp else None
    w_ko = SG.portfolio_wert(ko, preise) if ko else None
    b = r(btc, sp.get("btc_start")) if btc and sp.get("btc_start") else 0
    heute_trades = sum(1 for t in sp.get("trades", []) if t["zeit_aus"] > SG.jetzt_ms() - 86_400_000)
    push(f"Spiegel-Portfolio: {r(w_sp, sp.get('kapital')):+.1f} % ({w_sp:,.0f} $)\n".replace(",", ".") +
         f"Konsens-Portfolio: {r(w_ko, E.START_KAPITAL):+.1f} %\nBitcoin halten: {b:+.1f} %\n"
         f"{len(sp.get('pos', {}))} offene Spiegel-Positionen, {heute_trades} Abschlüsse in 24 Std. Nur Papier-Test.",
         "🧠 Smart Money: Tagesstand")


def migrieren(P):
    """Konsens-Test lief anfangs mit 10.000 $ – auf das neue Startkapital hochskalieren (Prozente bleiben gleich)."""
    alt = P.get("kapital", 10_000.0)
    if not P or abs(alt - E.START_KAPITAL) < 1:
        return
    f = E.START_KAPITAL / alt
    for k in ("cash", "gebuehren", "funding"):
        P[k] = P.get(k, 0.0) * f
    for p in P.get("pos", {}).values():
        for k in ("menge", "notional", "geb_ein", "funding"):
            if k in p:
                p[k] *= f
    for t in P.get("trades", []):
        for k in ("notional", "ergebnis"):
            t[k] = round(t.get(k, 0) * f, 2)
    P["verlauf"] = [[v[0], round(v[1] * f, 2), round(v[2] * f, 2) if v[2] else None] for v in P.get("verlauf", [])]
    P["kapital"] = E.START_KAPITAL


def bewegungen(alt, neu, namen):
    """Was die Trader seit dem letzten Lauf getan haben (für den Verlauf im Dashboard)."""
    out, t = [], SG.jetzt_ms()
    for a, pos in neu.items():
        vorher = alt.get(a)
        if vorher is None:
            continue
        for coin, p in pos.items():
            w = vorher.get(coin)
            if not w:
                out.append({"zeit": t, "a": a, "coin": coin, "art": "eröffnet", "r": p["r"], "wert": p["wert"]})
            elif w["r"] != p["r"]:
                out.append({"zeit": t, "a": a, "coin": coin, "art": "gedreht", "r": p["r"], "wert": p["wert"]})
        for coin, w in vorher.items():
            if coin not in pos:
                out.append({"zeit": t, "a": a, "coin": coin, "art": "geschlossen", "r": w["r"], "wert": w["wert"]})
    return out


def main():
    t0 = time.time()
    S = zustand_laden()
    S.setdefault("protokoll", [])
    prot = []
    preise = hl.preise()
    print("Preise:", len(preise), "Coins, BTC", (preise.get("BTC") or {}).get("px"))

    neu_ausgewaehlt = False
    letzte = (S.get("auswahl_info") or {}).get("zeit", 0)
    if not S.get("trader") or (SG.jetzt_ms() - letzte) > E.AUSWAHL_ALLE_STD * 3_600_000 or os.environ.get("SMART_NEU_AUSWAHL") == "1":
        trader, abgelehnt, info = auswahl.auswaehlen(prot)
        if trader:
            alt = {t["adresse"] for t in S.get("trader", [])}
            S["trader"], S["abgelehnt"], S["auswahl_info"] = trader, abgelehnt, info
            neu_ausgewaehlt = True
            dazu = len({t["adresse"] for t in trader} - alt)
            weg = len(alt - {t["adresse"] for t in trader})
            konten_txt = f"{info['konten']:,}".replace(",", ".")
            prot.append(f"Auswahl: {info['ausgewaehlt']} Trader aus {konten_txt} Konten ({info['bestanden']} bestanden, {dazu} neu, {weg} ausgeschieden)")
        print("Auswahl:", info)

    namen = {t["adresse"]: t.get("name") for t in S.get("trader", [])}
    snap, konten = SG.schnappschuss(S.get("trader", []), prot)
    alt_snap = S.get("snap") or {}
    erster = not alt_snap
    rel, alt_rel = SG.relevant(snap), SG.relevant(alt_snap)
    bew = bewegungen(alt_rel, rel, namen)
    S["bewegungen"] = (bew + S.get("bewegungen", []))[:300]
    K = SG.konsens(rel)

    P = S.get("portfolio") or SG.neues_portfolio(preise)
    migrieren(P)
    P["kapital"] = E.START_KAPITAL
    SG.funding_verbuchen(P, preise)
    ereignisse = SG.konsens_handeln(P, K, preise)
    wert = SG.portfolio_wert(P, preise)
    btc = (preise.get("BTC") or {}).get("px")
    if not P["verlauf"] or SG.jetzt_ms() - P["verlauf"][-1][0] > 55 * 60_000 or ereignisse:
        bench = E.START_KAPITAL * btc / P["btc_start"] if btc and P.get("btc_start") else None
        P["verlauf"].append([SG.jetzt_ms(), round(wert, 2), round(bench, 2) if bench else None])
        P["verlauf"] = P["verlauf"][-9000:]
    P["trades"] = P["trades"][-500:]
    S["portfolio"] = P

    SPG = S.get("spiegel") or SP.neues(preise)
    SP.funding(SPG, preise)
    sp_ereignisse = SP.handeln(SPG, S.get("trader", []), snap, konten, preise)
    sp_wert = SP.wert(SPG, preise)
    if not SPG["verlauf"] or SG.jetzt_ms() - SPG["verlauf"][-1][0] > 55 * 60_000 or any(e["art"] in ("auf", "zu") for e in sp_ereignisse):
        bench = SPG["kapital"] * btc / SPG["btc_start"] if btc and SPG.get("btc_start") else None
        SPG["verlauf"].append([SG.jetzt_ms(), round(sp_wert, 2), round(bench, 2) if bench else None])
        SPG["verlauf"] = SPG["verlauf"][-9000:]
    S["spiegel"] = SPG

    try:
        PMK.lauf(S, prot)
    except Exception as ex:
        prot.append(f"Polymarket-Tracking: {type(ex).__name__}")
    try:
        WX.lauf(S, prot)
    except Exception as ex:
        prot.append(f"Wetter-Scanner: {type(ex).__name__}")

    EK = S.get("einzel") or {}
    SG.einzel_kopie(EK, alt_rel, rel, preise, erster)
    S["einzel"] = EK
    S["snap"], S["konten"], S["konsens"] = snap, konten, K
    S["preise"] = {c: preise[c]["px"] for c in set(K) | set(P["pos"]) | {p["coin"] for p in SPG["pos"].values()} | {"BTC", "ETH", "SOL"} if c in preise}
    S["stand"] = SG.jetzt_ms()
    S["protokoll"] = ([{"zeit": S["stand"], "text": p} for p in prot] + S["protokoll"])[:150]
    S["laeufe"] = (S.get("laeufe", []) + [{"zeit": S["stand"], "dauer": round(time.time() - t0), "trader": len(snap),
                                            "signale": sum(1 for c in K.values() if c["signal"]), "trades": len(ereignisse)}])[-300:]

    print(f"Spiegel: {sp_wert:.2f} $, {len(SPG['pos'])} Positionen, {len(sp_ereignisse)} Trades in diesem Lauf")
    print(f"Trader: {len(snap)}, Konsens-Signale: {sum(1 for c in K.values() if c['signal'])}, Papier-Ereignisse: {len(ereignisse)}, "
          f"Portfolio: {wert:.2f} $, Bewegungen: {len(bew)}")
    for z in prot:
        print(" ", z)

    push_ereignisse(ereignisse)
    push_spiegel(sp_ereignisse, namen)
    tages_push(S, preise)

    gross = any(e["art"] in ("auf", "zu") and e["notional"] >= E.SPIEGEL_PUSH_AB for e in sp_ereignisse)
    faellig = (neu_ausgewaehlt or ereignisse or gross or not os.path.exists(E.SEITE)
               or SG.jetzt_ms() - S.get("commit_zeit", 0) >= E.COMMIT_ALLE_MIN * 60_000)
    if faellig:
        S["commit_zeit"] = SG.jetzt_ms()
        _speichern(S, E.JOURNAL)
        html = seite.erstelle(S)
        if E.PASSWORT:
            html = schutz.dashboard_sperren(html, E.PASSWORT)
        os.makedirs(os.path.dirname(E.SEITE), exist_ok=True)
        with open(E.SEITE, "w", encoding="utf-8") as f:
            f.write(html)
        print("Dashboard und Journal geschrieben.")
    _speichern(S, E.JOURNAL_CACHE)


if __name__ == "__main__":
    main()
