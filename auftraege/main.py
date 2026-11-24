# -*- coding: utf-8 -*-
"""
Auftrags-Radar: scannt öffentliche Auftragsquellen, bewertet, lernt aus Rückmeldungen und baut das Dashboard.
Start: python auftraege/main.py   (lokal ohne Passwort wird unverschlüsselt in speicher/auftraege.json gespeichert)
"""
import json
import os
import sys
import traceback
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(1, os.path.dirname(HIER))

import requests  # noqa: E402

import einstellungen as E  # noqa: E402
import quellen as Q  # noqa: E402
import bewerten as B  # noqa: E402
import lernen as L  # noqa: E402
import ki as KI  # noqa: E402
import konto  # noqa: E402
import seite  # noqa: E402

UEBERNEHMEN = ("erst_gesehen", "ki", "ki_fehler", "ki_versuche", "repo_ok", "feedback", "betrag_echt", "ki_regel", "versuche", "benachrichtigt")


def journal_laden():
    if E.PASSWORT and os.path.exists(E.JOURNAL):
        import schutz
        return schutz.journal_laden(E.JOURNAL, E.PASSWORT)
    if not E.PASSWORT and os.path.exists(E.JOURNAL_KLAR):
        with open(E.JOURNAL_KLAR, encoding="utf-8") as f:
            return json.load(f)
    return {"version": 1, "eintraege": {}, "laeufe": [], "quellen": {}, "feedback": [], "protokoll": []}


def journal_speichern(J):
    if E.PASSWORT:
        import schutz
        schutz.journal_speichern(J, E.JOURNAL, E.PASSWORT)
    else:
        os.makedirs(os.path.dirname(E.JOURNAL_KLAR), exist_ok=True)
        with open(E.JOURNAL_KLAR, "w", encoding="utf-8") as f:
            json.dump(J, f, ensure_ascii=False, indent=1)


def push(text, titel):
    if not E.NTFY_THEMA:
        return
    try:
        requests.post(f"https://ntfy.sh/{E.NTFY_THEMA}", data=text.encode("utf-8"), timeout=20,
                      headers={"Title": titel.encode("utf-8"), "Click": E.DASHBOARD_URL, "Tags": "moneybag"})
    except requests.RequestException:
        pass


def morgen_push(J):
    """Einmal am Morgen (erster Lauf ab 6 Uhr Berliner Zeit): wie viele Aufträge auf Freigabe warten."""
    jetzt = datetime.now(ZoneInfo(E.ZEITZONE))
    if jetzt.hour < 6 or J.get("morgen_push") == jetzt.date().isoformat():
        return
    ids = J.get("heute") or []
    if not ids:
        return
    E_ = J["eintraege"]
    ew = sum(E_[i]["ew_eur"] for i in ids if i in E_)
    uebrig = max(0, ((J.get("konto") or {}).get("gebote_limit") or E.FL_GEBOTE_MONAT) - B.gebote_im_monat(J))
    zeilen = "\n".join(f"• {E_[i]['titel'][:60]}" for i in ids[:5] if i in E_)
    push(f"{len(ids)} Aufträge warten auf deine Freigabe (zusammen ca. {ew:.0f} € erwarteter Wert, {uebrig} Gebote übrig).\n{zeilen}",
         "☀️ Deine Aufträge für heute")
    J["morgen_push"] = jetzt.date().isoformat()


def seite_schreiben(J):
    html = seite.erstelle(J)
    os.makedirs(os.path.dirname(E.SEITE), exist_ok=True)
    if E.PASSWORT:
        import schutz
        html = schutz.dashboard_sperren(html, E.PASSWORT)
    with open(E.SEITE, "w", encoding="utf-8") as f:
        f.write(html)


def nur_konto(J, geaendert):
    """Schneller Lauf alle 30 Minuten: nur Konto (Gebote, Zuschläge, Nachrichten). Speichert nur bei Änderungen,
    damit nicht jede halbe Stunde ein Commit und ein Seiten-Upload entsteht."""
    if not geaendert:
        print("Konto: nichts Neues.")
        return
    gelernt = L.feedback_anwenden(J)
    for e in J.get("eintraege", {}).values():
        B.bewerte(e, gelernt)
        e["empfehlbar"] = B.empfehlbar(e)
    J["top"] = [i for i in J.get("top", []) if J["eintraege"].get(i, {}).get("empfehlbar")]
    J["heute"] = B.heute_liste(J)
    seite_schreiben(J)
    journal_speichern(J)
    print("Konto: Änderungen gespeichert.")


def main():
    J = journal_laden()
    jetzt = datetime.now(timezone.utc)
    lauf = {"zeit": jetzt.isoformat(timespec="seconds"), "quellen": {}, "neu": 0, "ki": 0, "ki_fehler": 0}
    if not J.get("laeufe"):
        L.protokoll(J, "Auftrags-Radar gestartet. Startwerte für Gewinnchancen und Machbarkeit stehen im Reiter Lernen.")

    L.feedback_holen(J)
    geboten = konto.gebote_abgeben(J, push)
    konto_neu = konto.abgleichen(J, push) or geboten
    if E.MODUS == "konto":
        return nur_konto(J, konto_neu)

    # 1) Scannen
    begriffe, getestet = L.suchbegriffe(J)
    neue_liste = []
    for name, (fn, start) in Q.QUELLEN.items():
        st = J.setdefault("quellen", {}).setdefault(name, {"status": start, "laeufe": []})
        if st["status"] == "pausiert":
            continue
        try:
            daten, fehler = Q.freelancer(begriffe) if fn == "freelancer" else fn()
        except Exception as ex:  # eine kaputte Quelle darf den Lauf nicht stoppen
            daten, fehler = [], [f"{ex.__class__.__name__}: {ex}"]
            traceback.print_exc()
        lauf["quellen"][name] = {"n": len(daten), "fehler": fehler[:5], "empfehlbar": 0}
        print(f"{name}: {len(daten)} Einträge, {len(fehler)} Fehler", ("– " + " | ".join(fehler[:2])) if fehler else "")
        neue_liste.extend(daten)

    # 2) Zusammenführen (doppelte Treffer aus mehreren Suchbegriffen zusammenfassen)
    E_ = J.setdefault("eintraege", {})
    dieser_lauf = {}
    nach_url = {v.get("url"): k for k, v in E_.items()}
    urls_lauf = set()
    for e in neue_liste:
        if e["id"] in dieser_lauf or e.get("url") in urls_lauf:
            continue
        if nach_url.get(e.get("url")) not in (None, e["id"]):
            e["id"] = nach_url[e["url"]]  # gleicher Auftrag aus anderer Quelle -> zusammenführen
            if e["id"] in dieser_lauf:
                continue
        urls_lauf.add(e.get("url"))
        alt = E_.get(e["id"])
        if alt:
            for k in UEBERNEHMEN:
                if k in alt:
                    e[k] = alt[k]
        else:
            e["erst_gesehen"] = lauf["zeit"]
            lauf["neu"] += 1
        e["zuletzt"] = lauf["zeit"]
        E_[e["id"]] = e
        dieser_lauf[e["id"]] = e

    # 3) Bounty-Details: Beträge nachladen, KI-Regeln der Projekte prüfen
    neue_bounties = [e for e in dieser_lauf.values() if e["art"] == "bounty" and "versuche" not in e]
    neue_bounties.sort(key=lambda x: x.get("erstellt") or "", reverse=True)  # frische zuerst
    Q.github_betraege_nachladen(neue_bounties)
    for e in neue_bounties:
        e.setdefault("versuche", e.get("versuche", 0))
    cache = J.setdefault("ki_regel_cache", {})
    repo_cache = J.setdefault("repo_cache", {})
    for e in sorted([e for e in dieser_lauf.values() if e["art"] == "bounty" and "repo_ok" not in e],
                    key=lambda x: -(x.get("betrag") or 0))[:40]:
        e["repo_ok"] = Q.github_repo_ok(e.get("repo"), repo_cache)
    for e in sorted([e for e in dieser_lauf.values() if e["art"] == "bounty" and "ki_regel" not in e],
                    key=lambda x: -(x.get("betrag") or 0))[:15]:
        e["ki_regel"] = Q.github_ki_regel(e.get("repo"), cache)

    # 4) Bewerten -> Feedback anwenden -> neu bewerten
    gelernt = J.get("gelernt", {})
    for e in E_.values():
        B.bewerte(e, gelernt)
    gelernt = L.feedback_anwenden(J)
    for e in E_.values():
        B.bewerte(e, gelernt)

    # 5) KI-Bewertung der aussichtsreichsten neuen Kandidaten (mit Kostenbremse)
    from zoneinfo import ZoneInfo
    tag = jetzt.astimezone(ZoneInfo(E.ZEITZONE)).strftime("%Y-%m-%d")
    kt = J.setdefault("ki_tag", {"datum": tag, "n": 0})
    if kt["datum"] != tag:
        kt.update({"datum": tag, "n": 0})
    for e in E_.values():  # Verbindungs-/Konfigurationsfehler beim nächsten Lauf erneut versuchen
        f = str(e.get("ki_fehler", ""))
        if f.startswith(("API HTTP", "Verbindung")) or (f == "Antwort nicht lesbar" and e.get("ki_versuche", 0) < 2):
            e.pop("ki_fehler", None)
    kandidaten = sorted([e for e in E_.values() if B.top_tauglich(e) and not e.get("ki") and not e.get("ki_fehler")],
                        key=lambda x: -x["rang"])
    # 5a) Ausdrückliche Prüf-Wünsche aus dem Dashboard zuerst (zählen nur gegen die harte Obergrenze)
    wunsch = [E_[i] for i in dict.fromkeys(J.pop("pruef_wunsch", [])) if i in E_ and not E_[i].get("ki")]
    for e in wunsch[:E.KI_MAX_PRO_LAUF]:
        if kt["n"] >= E.KI_HART_PRO_TAG:
            break
        daten, fehler = KI.bewerte(e)
        if fehler == "kein API-Schlüssel":
            break
        kt["n"] += 1
        if daten:
            e["ki"] = daten
            e.pop("ki_fehler", None)
            lauf["ki"] += 1
        else:
            print("KI-Fehler (Wunsch):", fehler)
        B.bewerte(e, gelernt)
    # 5b) Automatisch: Tageskontingent; manuell gestartete Läufe dürfen bis zur harten Obergrenze
    grenze_tag = E.KI_HART_PRO_TAG if E.MANUELL else E.KI_MAX_PRO_TAG
    rest = max(0, min(E.KI_MAX_PRO_LAUF, grenze_tag - kt["n"]))
    kandidaten = [e for e in kandidaten if not e.get("ki")]
    for e in kandidaten[:rest]:
        daten, fehler = KI.bewerte(e)
        if fehler == "kein API-Schlüssel":
            break
        e["ki_versuche"] = e.get("ki_versuche", 0) + 1
        kt["n"] += 1
        if daten:
            e["ki"] = daten
            lauf["ki"] += 1
        else:
            e["ki_fehler"] = fehler
            lauf["ki_fehler"] += 1
            print("KI-Fehler:", fehler)
            if fehler.startswith(("API HTTP 4", "Verbindung")):
                e.pop("ki_fehler", None)  # nicht der Auftrag ist schuld -> später erneut
                break  # kein Geld für weitere fehlschlagende Anfragen verschwenden
        B.bewerte(e, gelernt)

    # 6) Statistik je Quelle, Suchbegriffe, Quellen-Status
    for e in dieser_lauf.values():
        e["empfehlbar"] = B.empfehlbar(e)
        if e["empfehlbar"] and e["quelle"] in lauf["quellen"]:
            lauf["quellen"][e["quelle"]]["empfehlbar"] += 1
    for name, s in lauf["quellen"].items():
        st = J["quellen"][name]
        st["laeufe"] = (st.get("laeufe", []) + [{"zeit": lauf["zeit"], "n": s["n"], "empfehlbar": s["empfehlbar"],
                                                  "fehler_total": s["n"] == 0 and bool(s["fehler"])}])[-40:]
    L.suchbegriffe_auswerten(J, list(dieser_lauf.values()), getestet)
    L.quellen_pruefen(J)

    # 7) Top 5 + Push
    for e in E_.values():
        e["empfehlbar"] = B.empfehlbar(e)
    top = sorted([e for e in E_.values() if B.top_tauglich(e)], key=lambda x: -x["rang"])[:5]
    gesendet = 0
    for e in top:
        if e.get("benachrichtigt") or e["ew_eur"] < E.PUSH_AB_EUR or gesendet >= 2:
            continue
        push(f"{e['titel']}\nErwarteter Wert ca. {e['ew_eur']:.0f} € · {e['quelle']} · {e['kat_name']}", "Neue Top-Empfehlung")
        e["benachrichtigt"] = lauf["zeit"]
        gesendet += 1

    # 8) Aufräumen
    grenze = jetzt - timedelta(days=E.AUFBEWAHREN_TAGE)
    for i in list(E_):
        e = E_[i]
        if e.get("feedback"):
            continue
        try:
            if datetime.fromisoformat(e["zuletzt"]) < grenze:
                del E_[i]
        except (KeyError, ValueError):
            pass

    lauf["empfehlbar"] = sum(1 for e in E_.values() if e["empfehlbar"])
    lauf["top_ew"] = round(sum(e["ew_eur"] for e in top), 2)
    J["laeufe"] = (J.get("laeufe", []) + [lauf])[-180:]
    J["top"] = [e["id"] for e in top]
    J["heute"] = B.heute_liste(J)
    J["stand"] = lauf["zeit"]
    morgen_push(J)

    seite_schreiben(J)
    journal_speichern(J)
    from collections import Counter
    fl = [e for e in dieser_lauf.values() if e["art"] == "freelance"]
    if fl:
        zaehl = Counter(f.split(":")[0] for e in fl for f in (e.get("flags") or []))
        print("Merkmale freelancer.com (Anteil):", {k: round(v / len(fl), 2) for k, v in zaehl.most_common(8)})
    print("Empfehlbar je Art:", dict(Counter(e["art"] for e in E_.values() if e["empfehlbar"])))
    # Diagnose: offene freelancer.com-Aufträge mit wenig Konkurrenz, die NICHT empfohlen werden – und warum
    wenig = [e for e in E_.values() if e["art"] == "freelance" and B.noch_offen(e) and (e.get("gebote") or 0) <= 12
             and not e.get("empfehlbar") and not e.get("feedback")]
    print(f"Wenig-Gebote-aber-aussortiert: {len(wenig)}; Skill-Tipps: {J.get('skill_tipps')}")
    gruende_z = Counter()
    for e in wenig:
        g = "; ".join(e.get("gruende") or [])[:150] or f"machbar {e.get('machbar', 0):.2f}, wert {e.get('wert_eur', 0):.0f}, frisch {e.get('frisch')}"
        gruende_z[g.split(";")[0][:60]] += 1
    print("  häufigste Gründe:", gruende_z.most_common(12))
    for e in sorted(wenig, key=lambda x: -(x.get("wert_eur") or 0))[:40]:
        print(f"  WG {e.get('gebote')} | {e.get('budget_min_usd', 0):.0f}-{e.get('budget_max_usd', 0):.0f}$ | m {e.get('machbar', 0):.2f} | "
              f"{e.get('kat')} | {e['titel'][:60]} || {'; '.join(e.get('gruende') or [])[:140]}")
    for e in sorted([e for e in E_.values() if B.top_tauglich(e)], key=lambda x: -x["rang"])[:10]:
        print(f"  EW {e['ew_eur']:8.2f} € | Wert {e['wert_eur']:8.0f} € | p {e['chance']:.3f} | m {e['machbar']:.2f} | "
              f"{e['quelle']} | {e['kat']} | {e['titel'][:70]}")
        if e["art"] == "freelance":
            print(f"      Upgrades {e.get('upgrades')} | Kunde {e.get('kunde')}")
            print(f"      Budget {e.get('budget_min_usd', 0):.0f}–{e.get('budget_max_usd', 0):.0f} USD, Ø-Gebot {e.get('gebot_avg_usd', 0):.0f}, "
                  f"{e.get('typ')}, Währung {e.get('waehrung')}, KI-Preis {(e.get('ki') or {}).get('preis_vorschlag_eur')}")
    print(f"Fertig: {len(dieser_lauf)} im Lauf, {lauf['neu']} neu, {lauf['empfehlbar']} empfehlbar, "
          f"KI {lauf['ki']} (Fehler {lauf['ki_fehler']}), Top-EW {lauf['top_ew']} €")


if __name__ == "__main__":
    main()
