# -*- coding: utf-8 -*-
"""
Verbindung zu Leons eigenem freelancer.com-Konto (nur lesend, über ein persönliches OAuth-Token).

Was das Radar damit macht:
- erkennt eigene Gebote automatisch  -> "beworben" (kein Knopfdruck nötig), inkl. Gebotsbetrag
- erkennt Zuschlag / Absage          -> "gewonnen" / "verloren" (damit lernt das Radar echte Gewinnquoten)
- liest den Verifizierungsstatus      -> schaltet gesperrte Auftragsarten automatisch frei
- meldet neue Kunden-Nachrichten      -> Push aufs Handy (ntfy)

Ohne Secret FREELANCER_TOKEN passiert nichts. Das Radar schreibt nie etwas ins Konto (keine Gebote, keine Nachrichten).
"""
from datetime import datetime, timezone

import requests

import einstellungen as E
import quellen as Q

API = "https://www.freelancer.com/api"
OFFEN = ("open", "active", "frozen_awaiting_client", "")
ZUSCHLAG = ("awarded", "accepted")


def _get(pfad, params=None):
    try:
        r = requests.get(API + pfad, params=params, timeout=30,
                         headers={"freelancer-oauth-v1": E.FREELANCER_TOKEN, "User-Agent": "auftrags-radar (privat)"})
    except requests.RequestException as ex:
        return None, f"Verbindung: {ex.__class__.__name__}"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}: {r.text[:160]}"
    try:
        return r.json().get("result") or {}, None
    except ValueError:
        return None, "keine JSON-Antwort"


def _post(pfad, daten):
    try:
        r = requests.post(API + pfad, json=daten, timeout=30,
                          headers={"freelancer-oauth-v1": E.FREELANCER_TOKEN, "User-Agent": "auftrags-radar (privat)"})
    except requests.RequestException as ex:
        return None, f"Verbindung: {ex.__class__.__name__}"
    try:
        j = r.json()
    except ValueError:
        j = {}
    if r.status_code != 200 or j.get("status") == "error":
        return None, (j.get("message") or r.text[:200] or f"HTTP {r.status_code}")
    return j.get("result") or {}, None


def gebote_abgeben(J, push):
    """Gebote, die Leon im Dashboard mit „Jetzt bieten“ freigegeben hat, über die offizielle API abgeben.
    Nur auf ausdrückliche Freigabe – das Radar bietet nie von selbst."""
    wuensche = J.pop("bieten", [])
    if not wuensche:
        return False
    if not E.FREELANCER_TOKEN:
        push("Gebot nicht abgegeben: Das Secret FREELANCER_TOKEN fehlt.", "Gebot fehlgeschlagen")
        return False
    ich, f = _get("/users/0.1/self/")
    if f:
        push(f"Gebot nicht abgegeben – Konto nicht erreichbar ({f[:80]}).", "Gebot fehlgeschlagen")
        return False
    erledigt = J.setdefault("konto", {}).setdefault("gebote_abgegeben", [])
    for w in wuensche:
        pid = str(w["id"]).replace("fl-", "")
        e = (J.get("eintraege") or {}).get(w["id"], {})
        titel = e.get("titel") or pid
        if pid in erledigt:
            continue
        if not w.get("text"):
            w["text"] = (e.get("ki") or {}).get("bewerbung") or ""
        if not w.get("betrag") or len(w.get("text") or "") < 100:
            push(f"{titel}\nBetrag fehlt oder Bewerbungstext zu kurz (mind. 100 Zeichen).", "Gebot nicht abgegeben")
            continue
        res, f = _post("/projects/0.1/bids/", {"project_id": int(pid), "bidder_id": ich.get("id"), "amount": float(w["betrag"]),
                                               "period": int(w.get("tage") or 3), "milestone_percentage": 100,
                                               "description": w["text"][:4000]})
        if f:
            print("Gebot-Fehler:", f)
            if "bid" in f.lower() and ("enough" in f.lower() or "no more" in f.lower() or "limit" in f.lower()):
                f = "Keine Gebote mehr frei – freelancer.com füllt sie nach und nach auf. Später nochmal versuchen."
            if "required skills" in f:
                fehlt = ", ".join((e.get("tags") or [])[:5])
                f = (f"Dir fehlt im freelancer.com-Profil einer dieser Skills: {fehlt}. Profil → Skills ergänzen "
                     "(kostenlos bis zu 20), dann nochmal bieten – das Gebot wurde NICHT verbraucht.")
            push(f"{titel}\n{f[:300]}", "Gebot nicht abgegeben")
            continue
        erledigt.append(pid)
        J.setdefault("feedback", []).append({"zeit": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                             "id": w["id"], "aktion": "beworben", "betrag": None, "von": "radar"})
        push(f"{titel}\n{w['betrag']} {e.get('waehrung') or ''} · {w.get('tage')} Tage", "✅ Gebot abgegeben")
    return True


def _ts(x):
    try:
        return datetime.fromtimestamp(int(x), timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return None


def kickoff_text(p, b):
    """Erste Nachricht nach dem Zuschlag (Englisch – die Sprache fast aller Kunden auf freelancer.com)."""
    tage = b.get("period") or 3
    return ("Hi, thank you for awarding me the project! To get started right away, could you please create the milestone "
            "and send me all files and details I should work with (source documents, examples, preferred format)? "
            f"As soon as the milestone is in place I'll start and deliver within {tage} day{'s' if tage != 1 else ''}. "
            "If anything is unclear I'll ask early. Looking forward to working with you!")


def _suche(d, pfad=""):
    """Alle Felder finden, die nach Gebots-Kontingent aussehen."""
    funde = {}
    if isinstance(d, dict):
        for k, v in d.items():
            p = f"{pfad}.{k}" if pfad else k
            if any(w in k.lower() for w in ("bid", "quota")) and not isinstance(v, (dict, list)):
                funde[p] = v
            funde.update(_suche(v, p))
    elif isinstance(d, list):
        for i, v in enumerate(d[:3]):
            funde.update(_suche(v, f"{pfad}[{i}]"))
    return funde


def gebote_limit():
    """Gebote pro Monat laut freelancer.com-Mitgliedschaft (kostenlos: 6)."""
    res, f = _get("/users/0.1/self/", {"membership_details": "true"})
    try:
        return int((res or {}).get("membership_package", {}).get("bid_limit")) if not f else None
    except (TypeError, ValueError):
        return None


def abgleichen(J, push):
    """Gleicht Konto und Journal ab. Gibt True zurück, wenn sich etwas geändert hat."""
    if not E.FREELANCER_TOKEN:
        return False
    K = J.setdefault("konto", {})
    vorher = repr(sorted((K.get("gebote") or {}).items())) + str(K.get("verifiziert")) + str(K.get("fehler"))

    ich, f = _get("/users/0.1/self/", {"status": "true", "reputation": "true", "jobs": "true"})
    if f:
        print("Konto:", f)
        if f.startswith("HTTP 401") and not K.get("fehler_gemeldet"):
            push("Das freelancer.com-Token ist abgelaufen oder ungültig. Bitte ein neues erzeugen und das Secret "
                 "FREELANCER_TOKEN ersetzen.", "Konto-Verbindung unterbrochen")
            K["fehler_gemeldet"] = True
        K["fehler"] = f[:120]
        return vorher != repr(sorted((K.get("gebote") or {}).items())) + str(K.get("verifiziert")) + str(K.get("fehler"))
    K.pop("fehler", None)
    K.pop("fehler_gemeldet", None)
    status = ich.get("status") or {}
    K["name"] = ich.get("username")
    K["skills"] = [j.get("name") for j in (ich.get("jobs") or []) if isinstance(j, dict) and j.get("name")]
    K["id"] = ich.get("id")
    K["status"] = {k: bool(v) for k, v in status.items() if isinstance(v, bool)}
    print("Konto-Status:", {k: v for k, v in status.items() if isinstance(v, bool)})
    # „Verified by Freelancer“ (KYC) ist das, was Stundenprojekte ab 50 $/Std. verlangen; Ausweis allein reicht nicht
    verifiziert = bool(status.get("freelancer_verified_user")) if "freelancer_verified_user" in status \
        else bool(status.get("identity_verified"))
    if verifiziert and not K.get("verifiziert"):
        push("Dein Konto ist verifiziert – das Radar zeigt ab jetzt auch Stundenprojekte ab 50 $/Std.", "Verifizierung erkannt")
    K["verifiziert"] = verifiziert
    E.FL_VERIFIZIERT = E.FL_VERIFIZIERT or verifiziert
    K["abgleich"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lim = gebote_limit()
    if lim:
        K["gebote_limit"] = lim

    # ---- eigene Gebote
    res, f = _get("/projects/0.1/bids/", {"bidders[]": K["id"], "limit": 100, "project_details": "true",
                                           "full_description": "true", "job_details": "true", "upgrade_details": "true"})
    if f:
        print("Gebote:", f)
        K["fehler"] = "Gebote: " + f[:100]
    else:
        projekte = res.get("projects") or {}
        if isinstance(projekte, list):
            projekte = {str(p.get("id")): p for p in projekte}
        E_ = J.setdefault("eintraege", {})
        letzter = {}
        for fb in J.get("feedback", []):
            letzter[fb["id"]] = fb["aktion"]
        gebote = K.setdefault("gebote", {})
        for b in res.get("bids") or []:
            pid = str(b.get("project_id"))
            p = projekte.get(pid) or {}
            i = f"fl-{pid}"
            if i not in E_ and p:
                e = Q.fl_eintrag(p, {}, "eigenes Gebot")
                if e:
                    e["erst_gesehen"] = e["zuletzt"] = K["abgleich"]
                    E_[i] = e
            if i in E_ and p:
                E_[i]["status_fl"] = (p.get("frontend_project_status") or p.get("status") or "").lower()
            cur = ((p.get("currency") or {}).get("code") or "USD").upper()
            kurs = E.USD_JE_EINHEIT.get(cur, 1.0)
            betrag_eur = round((b.get("amount") or 0) * kurs * E.USD_EUR, 2)
            award = (b.get("award_status") or "").lower()
            pstatus = (p.get("frontend_project_status") or p.get("status") or "").lower()
            if b.get("retracted"):
                zustand = "zurückgezogen"
            elif award in ZUSCHLAG:
                zustand = "gewonnen"
            elif award in ("rejected", "revoked", "canceled", "cancelled") or (pstatus and pstatus not in OFFEN):
                zustand = "verloren"
            else:
                zustand = "offen"
            alt = gebote.get(i, {})
            neu_erkannt = not alt and bool(K.get("gebote_bekannt")) and pid not in (K.get("gebote_abgegeben") or [])
            gebote[i] = {"titel": (E_.get(i) or {}).get("titel") or p.get("title") or pid,
                         "url": (E_.get(i) or {}).get("url") or f"https://www.freelancer.com/projects/{p.get('seo_url') or pid}",
                         "betrag": b.get("amount"), "waehrung": cur, "betrag_eur": betrag_eur, "tage": b.get("period"),
                         "zeit": _ts(b.get("time_submitted")), "zustand": zustand, "award": award or None,
                         "text": (b.get("description") or "")[:3000],
                         "projekt_status": pstatus or None}
            aktion = {"offen": "beworben", "gewonnen": "gewonnen", "verloren": "verloren"}.get(zustand)
            if aktion and letzter.get(i) != aktion and not (aktion == "beworben" and letzter.get(i) in ("gewonnen", "verloren")):
                J.setdefault("feedback", []).append({"zeit": K["abgleich"], "id": i, "aktion": aktion,
                                                     "betrag": betrag_eur if aktion != "verloren" else None, "von": "konto"})
                letzter[i] = aktion
            if neu_erkannt and zustand == "offen":
                push(f"{gebote[i]['titel']}\n{b.get('amount')} {cur} · {b.get('period') or '?'} Tage – direkt auf freelancer.com abgegeben. "
                     "Das Radar verfolgt es jetzt und meldet sich bei Zuschlag oder Nachricht.", "📝 Gebot erkannt")
            if zustand == "gewonnen":
                gebote[i]["kickoff"] = alt.get("kickoff") or kickoff_text(p, b)
            if zustand == "gewonnen" and alt.get("zustand") != "gewonnen":
                push(f"{gebote[i]['titel']} – {b.get('amount')} {cur}\n\n1) Diese Nachricht an den Kunden schicken:\n"
                     f"{gebote[i]['kickoff']}\n\n2) Erst anfangen, wenn der Meilenstein bezahlt ist – dann Aufgabe und Dateien an Claude.",
                     "🎉 Zuschlag erhalten!")
        K["gebote_bekannt"] = True
        print(f"Konto {K.get('name')}: {len(gebote)} Gebote, verifiziert={verifiziert}, Skills im Profil: {len(K.get('skills') or [])}")
        for i, g in sorted(gebote.items(), key=lambda x: x[1].get("zeit") or "")[-3:]:
            print(f"  Gebot {g.get('zeit')} | {g.get('titel', '')[:45]} | {g.get('betrag')} {g.get('waehrung')} | Text {len(g.get('text') or '')} Zeichen: "
                  f"{(g.get('text') or '')[:90]!r}")

    # ---- neue Nachrichten von Kunden
    res, f = _get("/messages/0.1/threads/", {"last_message": "true", "user_details": "true", "limit": 20})
    if f:
        print("Nachrichten:", f)
        K["nachrichten_fehler"] = f[:100]
    else:
        K.pop("nachrichten_fehler", None)
        nutzer = res.get("users") or {}
        seit = K.get("nachricht_seit") or 0
        neu_max = seit
        neue = []
        for t in res.get("threads") or []:
            tt = t.get("thread") or {}
            msgs = t.get("messages") if isinstance(t.get("messages"), list) else []
            m = t.get("message") or tt.get("message") or t.get("last_message") or (msgs[-1] if msgs else {}) or {}
            zeit = (m.get("time_created") or tt.get("time_updated") or tt.get("time_created") or t.get("time_updated") or 0)
            von = m.get("from_user")
            ungelesen = (t.get("message_unread_count") or 0) > 0 or t.get("is_read") is False
            if not zeit or (von is not None and von == K["id"]):
                continue
            neu_max = max(neu_max, zeit)
            if seit and zeit > seit and ungelesen:
                u = nutzer.get(str(von)) or {}
                name = u.get("display_name") or u.get("username") or "Kunde"
                anh = [a.get("filename") or a.get("name") or "" for a in (t.get("attachments") or []) if isinstance(a, dict)]
                warn = [x for x in anh if re.search(r"\.(zip|rar|7z|exe|scr|bat|cmd|msi|js|vbs|iso|apk|dmg)$", x.lower())]
                text = (m.get("message") or "").strip()[:140] or "(neue Nachricht)"
                zeile = f"{name}: {text}"
                if warn:
                    zeile += f"\n⚠️ Anhang {warn[0]} – NICHT öffnen (typisch für Schadsoftware). Um Text/PDF bitten."
                neue.append(zeile)
        if seit and neue:
            try:
                requests.post(f"https://ntfy.sh/{E.NTFY_THEMA}", data="\n\n".join(neue[:3]).encode("utf-8"), timeout=20,
                              headers={"Title": "Neue Nachricht auf freelancer.com".encode("utf-8"),
                                       "Click": "https://www.freelancer.com/messages", "Tags": "speech_balloon",
                                       "Priority": "high"}) if E.NTFY_THEMA else None
            except requests.RequestException:
                pass
        thr = res.get("threads") or []
        print(f"Nachrichten: {len(thr)} Threads, seit {seit}, neueste {neu_max}, neu {len(neue)}",
              [((t.get('thread') or {}).get('message') or {}).get('time_created') for t in thr][:3],
              [t.get('message_unread_count') for t in thr][:3])
        K["nachricht_seit"] = neu_max or int(datetime.now(timezone.utc).timestamp())
        K["ungelesen"] = len(neue)

    nachher = repr(sorted((K.get("gebote") or {}).items())) + str(K.get("verifiziert")) + str(K.get("fehler"))
    return vorher != nachher or bool(K.get("ungelesen"))
