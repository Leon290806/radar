# -*- coding: utf-8 -*-
"""
Lernen und Selbstoptimierung:
1. Feedback (beworben / gewonnen / verloren / uninteressant) kommt über GitHub-Issues mit Titel "[Auftrag] ...".
2. Daraus: Gewinnquote je Quelle, Interesse je Kategorie, Abweichung echter Beträge vom geschätzten Wert.
3. Quellen im Test werden nach ihrer Ausbeute befördert oder stillgelegt.
4. Suchbegriffe: jeder Lauf testet neue Begriffe, schwache aktive Begriffe fliegen raus.
Jede Änderung landet mit Begründung im Protokoll (Reiter "Lernen").
"""
import re
from datetime import datetime, timezone

import requests

import einstellungen as E

AKTIONEN = {"beworben", "gewonnen", "verloren", "uninteressant", "pruefen", "gesperrt", "bieten"}


def jetzt():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def protokoll(J, text):
    J.setdefault("protokoll", []).insert(0, {"zeit": jetzt(), "text": text})
    J["protokoll"] = J["protokoll"][:200]


# ------------------------------------------------------------------ Feedback über GitHub-Issues
def feedback_holen(J):
    if not E.GITHUB_TOKEN:
        return 0
    h = {"Authorization": "Bearer " + E.GITHUB_TOKEN, "Accept": "application/vnd.github+json"}
    try:
        r = requests.get(f"https://api.github.com/repos/{E.REPO}/issues?state=open&per_page=100", headers=h, timeout=25)
    except requests.RequestException:
        return 0
    if r.status_code != 200:
        return 0
    n = 0
    for it in r.json():
        titel = it.get("title", "")
        if not titel.startswith("[Auftrag]") or it.get("pull_request"):
            continue
        body = (it.get("body") or "") + "\n" + titel
        if re.search(r"aktion:\s*bieten", body) and "### " in body:
            bloecke = re.split(r"^### ", it.get("body") or "", flags=re.M)[1:]
            m_n = re.search(r"nicht-interessant:\s*([^\n]+)", it.get("body") or "")
            for i in (m_n.group(1).split(",") if m_n else []):
                i = i.strip()
                if re.fullmatch(r"[a-z]{2}-[\w-]+", i):
                    J.setdefault("feedback", []).append({"zeit": it.get("created_at"), "id": i, "aktion": "uninteressant", "betrag": None})
            for b in bloecke:
                m_i = re.match(r"\s*([a-z]{2}-[\w-]+)", b)
                m_b = re.search(r"betrag:\s*([\d.,]+)", b)
                m_t = re.search(r"tage:\s*(\d+)", b)
                m_x = re.search(r"text:\s*\n(.*?)(?:\n\(Vom Auftrags-Radar|\Z)", b, re.S)
                if not (m_i and m_b):
                    continue
                try:
                    betrag = float(m_b.group(1).replace(",", "."))
                except ValueError:
                    continue
                J.setdefault("bieten", []).append({"id": m_i.group(1), "betrag": betrag, "tage": int(m_t.group(1)) if m_t else 3,
                                                   "text": m_x.group(1).strip() if m_x else "", "issue": it.get("number")})
                n += 1
            try:
                requests.post(f"https://api.github.com/repos/{E.REPO}/issues/{it['number']}/comments", headers=h, timeout=20,
                              json={"body": "Vom Auftrags-Radar übernommen – die Gebote werden jetzt abgegeben."})
                requests.patch(f"https://api.github.com/repos/{E.REPO}/issues/{it['number']}", headers=h, timeout=20,
                               json={"state": "closed", "state_reason": "completed"})
            except requests.RequestException:
                pass
            continue
        m_id = re.search(r"id:\s*([a-z]{2}-[\w-]+)", body)
        m_ak = re.search(r"aktion:\s*(\w+)", body)
        m_bt = re.search(r"betrag:\s*([\d.,]+)", body)
        if m_id and m_ak and m_ak.group(1) in AKTIONEN:
            betrag = None
            if m_bt:
                try:
                    betrag = float(m_bt.group(1).replace(".", "").replace(",", ".")) if "," in m_bt.group(1) else float(m_bt.group(1))
                except ValueError:
                    betrag = None
            if m_ak.group(1) == "pruefen":
                J.setdefault("pruef_wunsch", []).append(m_id.group(1))
            elif m_ak.group(1) == "bieten":
                roh = it.get("body") or ""
                m_tg = re.search(r"tage:\s*(\d+)", roh)
                m_tx = re.search(r"text:\s*\n(.*?)(?:\n\(Vom Auftrags-Radar|\Z)", roh, re.S)
                J.setdefault("bieten", []).append({"id": m_id.group(1), "betrag": betrag,
                                                   "tage": int(m_tg.group(1)) if m_tg else 3,
                                                   "text": (m_tx.group(1).strip() if m_tx else ""), "issue": it.get("number")})
            else:
                J.setdefault("feedback", []).append({"zeit": it.get("created_at"), "id": m_id.group(1),
                                                     "aktion": m_ak.group(1), "betrag": betrag})
            n += 1
        try:
            requests.post(f"https://api.github.com/repos/{E.REPO}/issues/{it['number']}/comments", headers=h, timeout=20,
                          json={"body": "Vom Auftrags-Radar übernommen. Danke!" if m_id else "Format nicht erkannt."})
            requests.patch(f"https://api.github.com/repos/{E.REPO}/issues/{it['number']}", headers=h, timeout=20,
                           json={"state": "closed", "state_reason": "completed"})
        except requests.RequestException:
            pass
    if n:
        protokoll(J, f"{n} Rückmeldung(en) übernommen.")
    return n


def feedback_anwenden(J):
    """Letzter Stand je Eintrag zählt. Markiert Einträge und berechnet die gelernten Faktoren."""
    letzter = {}
    for f in J.get("feedback", []):
        letzter[f["id"]] = f
    eintraege = J.get("eintraege", {})
    for i, f in letzter.items():
        if i in eintraege:
            eintraege[i]["feedback"] = f["aktion"]
            if f.get("betrag"):
                eintraege[i]["betrag_echt"] = f["betrag"]

    stat_q, stat_k = {}, {}
    for i, f in letzter.items():
        e = eintraege.get(i)
        if not e:
            continue
        for tab, key in ((stat_q, e["quelle"]), (stat_k, e.get("kat", "sonstiges"))):
            s = tab.setdefault(key, {"beworben": 0, "gewonnen": 0, "verloren": 0, "uninteressant": 0, "umsatz": 0.0,
                                     "geschaetzt": 0.0, "erwartet_p": 0.0})
            a = f["aktion"]
            if a in ("beworben", "gewonnen", "verloren"):
                s["beworben"] += 1
                s["erwartet_p"] += e.get("chance", 0.1)
            if a in ("gewonnen", "verloren", "uninteressant"):
                s[a] += 1
            if a == "gewonnen":
                s["umsatz"] += f.get("betrag") or e.get("wert_eur", 0)
                s["geschaetzt"] += e.get("wert_eur", 0)

    gelernt = {"quelle_mult": {}, "kat_mult": {}, "wert_mult": {}, "stat_quelle": stat_q, "stat_kat": stat_k}
    alt = J.get("gelernt", {})
    for q, s in stat_q.items():
        entschieden = s["gewonnen"] + s["verloren"]
        if entschieden >= 2 and s["beworben"]:
            p0 = s["erwartet_p"] / s["beworben"]
            k = 4  # Vorsicht: wenige Ergebnisse zählen wenig
            rate = (s["gewonnen"] + k * p0) / (entschieden + k)
            gelernt["quelle_mult"][q] = round(max(0.3, min(3.0, rate / max(p0, 1e-3))), 3)
        if s["gewonnen"] and s["geschaetzt"]:
            gelernt["wert_mult"][q] = round(max(0.4, min(2.5, (s["umsatz"] + 2 * s["geschaetzt"]) / (3 * s["geschaetzt"]))), 3)
    for k, s in stat_k.items():
        gesamt = s["beworben"] + s["uninteressant"]
        if gesamt >= 2:
            gelernt["kat_mult"][k] = round(max(0.3, min(1.5, 0.5 + (s["beworben"] + 1) / (gesamt + 2))), 3)
    for art in ("quelle_mult", "kat_mult", "wert_mult"):
        for k, v in gelernt[art].items():
            vorher = alt.get(art, {}).get(k)
            if vorher is None or abs(vorher - v) >= 0.05:
                name = {"quelle_mult": "Gewinnchance", "kat_mult": "Interesse", "wert_mult": "Wert-Schätzung"}[art]
                protokoll(J, f"{name} für {k}: Faktor {vorher if vorher is not None else 1.0:.2f} → {v:.2f} (aus deinen Rückmeldungen).")
    # Welche Merkmale haben Aufträge, die für Leons Konto gesperrt waren?
    gesperrt = [eintraege[i] for i, f in letzter.items() if f["aktion"] == "gesperrt" and i in eintraege]
    andere = [e for e in eintraege.values() if e.get("art") == "freelance" and e.get("feedback") != "gesperrt" and e.get("flags")]
    gelernt["gesperrt_flags"] = list(alt.get("gesperrt_flags", []))
    if gesperrt and andere:
        zaehler = {}
        for e in gesperrt:
            for fl in e.get("flags") or []:
                zaehler[fl] = zaehler.get(fl, 0) + 1
        for fl, n in zaehler.items():
            anteil_andere = sum(1 for e in andere if fl in (e.get("flags") or [])) / len(andere)
            if n >= 2 and anteil_andere < 0.15 and fl not in gelernt["gesperrt_flags"]:
                gelernt["gesperrt_flags"].append(fl)
                protokoll(J, f"Gelernt: Aufträge mit Merkmal „{fl}“ sind für dein Konto gesperrt ({n}× gemeldet) – werden künftig aussortiert.")
    J["gelernt"] = gelernt
    return gelernt


# ------------------------------------------------------------------ Quellen im Test befördern / stilllegen
def quellen_pruefen(J):
    for name, st in J.get("quellen", {}).items():
        hist = st.get("laeufe", [])[-12:]
        if len(hist) < 5:
            continue
        ok = sum(1 for h in hist if not h.get("fehler_total"))
        gut = sum(h.get("empfehlbar", 0) for h in hist) / len(hist)
        if st["status"] == "test" and ok >= 4 and gut >= 0.5:
            st["status"] = "aktiv"
            protokoll(J, f"Quelle {name} befördert: im Schnitt {gut:.1f} brauchbare Treffer pro Lauf.")
        elif st["status"] == "test" and len(hist) >= 10 and (gut < 0.1 or ok < 3):
            st["status"] = "pausiert"
            st["pausiert_seit"] = jetzt()
            protokoll(J, f"Quelle {name} pausiert: in 10 Läufen kaum Brauchbares ({gut:.2f}/Lauf) oder zu viele Fehler.")
        elif st["status"] == "aktiv" and len(hist) >= 12 and ok <= 3:
            st["status"] = "test"
            protokoll(J, f"Quelle {name} zurück in den Test: meist Fehler in den letzten Läufen.")
        elif st["status"] == "pausiert":
            seit = st.get("pausiert_seit", "")
            if seit and (datetime.now(timezone.utc) - datetime.fromisoformat(seit)).days >= 14:
                st["status"], st["laeufe"] = "test", []
                protokoll(J, f"Quelle {name} wird nach 14 Tagen Pause erneut getestet.")


# ------------------------------------------------------------------ Suchbegriffe optimieren (freelancer.com)
def suchbegriffe(J):
    sb = J.setdefault("suchbegriffe", {"aktiv": list(E.FREELANCER_START), "kandidaten": list(E.FREELANCER_KANDIDATEN),
                                       "stat": {}, "ausgemustert": []})
    for k in E.FREELANCER_KANDIDATEN:  # neue Kandidaten aus den Einstellungen übernehmen
        if k not in sb["aktiv"] and k not in sb["kandidaten"] and k not in sb["ausgemustert"]:
            sb["kandidaten"].append(k)
    test = sb["kandidaten"][:2]
    return sb["aktiv"] + test, test


def suchbegriffe_auswerten(J, eintraege_lauf, getestet):
    sb = J["suchbegriffe"]
    for q in set(sb["aktiv"]) | set(getestet):
        treffer = [e for e in eintraege_lauf if e.get("suchbegriff") == q]
        gut = [e for e in treffer if e.get("empfehlbar")]
        s = sb["stat"].setdefault(q, {"laeufe": 0, "treffer": 0, "gut": 0, "ew": 0.0})
        s["laeufe"] += 1
        s["treffer"] += len(treffer)
        s["gut"] += len(gut)
        s["ew"] += sum(e.get("ew_eur", 0) for e in gut)
    for q in getestet:
        s = sb["stat"][q]
        if q in sb["kandidaten"]:
            sb["kandidaten"].remove(q)
        if s["gut"] >= 1:
            sb["aktiv"].append(q)
            protokoll(J, f"Suchbegriff „{q}“ aufgenommen: {s['gut']} brauchbare Treffer im Test.")
        else:
            sb["kandidaten"].append(q)  # später nochmal
            if s["laeufe"] >= 3:
                sb["kandidaten"].remove(q)
                sb["ausgemustert"].append(q)
                protokoll(J, f"Suchbegriff „{q}“ ausgemustert: in 3 Tests nichts Brauchbares.")
    # schwache aktive Begriffe ausmustern (nach 15 Läufen ohne einen brauchbaren Treffer)
    for q in list(sb["aktiv"]):
        s = sb["stat"].get(q, {})
        if s.get("laeufe", 0) >= 15 and s.get("gut", 0) == 0 and len(sb["aktiv"]) > 6:
            sb["aktiv"].remove(q)
            sb["ausgemustert"].append(q)
            protokoll(J, f"Suchbegriff „{q}“ entfernt: 15 Läufe ohne brauchbaren Treffer.")
