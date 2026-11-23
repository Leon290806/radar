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


def _ts(x):
    try:
        return datetime.fromtimestamp(int(x), timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return None


def abgleichen(J, push):
    """Gleicht Konto und Journal ab. Gibt True zurück, wenn sich etwas geändert hat."""
    if not E.FREELANCER_TOKEN:
        return False
    K = J.setdefault("konto", {})
    vorher = repr(sorted((K.get("gebote") or {}).items())) + str(K.get("verifiziert")) + str(K.get("fehler"))

    ich, f = _get("/users/0.1/self/", {"status": "true", "reputation": "true"})
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
    K["id"] = ich.get("id")
    K["status"] = {k: bool(v) for k, v in status.items() if isinstance(v, bool)}
    verifiziert = bool(status.get("freelancer_verified_user") or status.get("identity_verified"))
    if verifiziert and not K.get("verifiziert"):
        push("Dein Konto ist verifiziert – das Radar zeigt ab jetzt auch Stundenprojekte ab 50 $/Std.", "Verifizierung erkannt")
    K["verifiziert"] = verifiziert
    E.FL_VERIFIZIERT = E.FL_VERIFIZIERT or verifiziert
    K["abgleich"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

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
            gebote[i] = {"titel": (E_.get(i) or {}).get("titel") or p.get("title") or pid,
                         "url": (E_.get(i) or {}).get("url") or f"https://www.freelancer.com/projects/{p.get('seo_url') or pid}",
                         "betrag": b.get("amount"), "waehrung": cur, "betrag_eur": betrag_eur, "tage": b.get("period"),
                         "zeit": _ts(b.get("time_submitted")), "zustand": zustand, "award": award or None,
                         "projekt_status": pstatus or None}
            aktion = {"offen": "beworben", "gewonnen": "gewonnen", "verloren": "verloren"}.get(zustand)
            if aktion and letzter.get(i) != aktion and not (aktion == "beworben" and letzter.get(i) in ("gewonnen", "verloren")):
                J.setdefault("feedback", []).append({"zeit": K["abgleich"], "id": i, "aktion": aktion,
                                                     "betrag": betrag_eur if aktion != "verloren" else None, "von": "konto"})
                letzter[i] = aktion
            if zustand == "gewonnen" and alt.get("zustand") != "gewonnen":
                push(f"{gebote[i]['titel']}\n{b.get('amount')} {cur} – Erst anfangen, wenn der Meilenstein bezahlt ist. "
                     "Dann die Aufgabe an Claude geben.", "🎉 Zuschlag erhalten!")
        print(f"Konto {K.get('name')}: {len(gebote)} Gebote, verifiziert={verifiziert}")

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
            m = t.get("message") or t.get("last_message") or {}
            zeit = m.get("time_created") or t.get("time_updated") or 0
            von = m.get("from_user")
            if not zeit or von == K["id"]:
                continue
            neu_max = max(neu_max, zeit)
            if seit and zeit > seit:
                u = nutzer.get(str(von)) or {}
                neue.append(f"{u.get('display_name') or u.get('username') or 'Kunde'}: {(m.get('message') or '')[:140]}")
        if seit and neue:
            try:
                requests.post(f"https://ntfy.sh/{E.NTFY_THEMA}", data="\n\n".join(neue[:3]).encode("utf-8"), timeout=20,
                              headers={"Title": "Neue Nachricht auf freelancer.com".encode("utf-8"),
                                       "Click": "https://www.freelancer.com/messages", "Tags": "speech_balloon",
                                       "Priority": "high"}) if E.NTFY_THEMA else None
            except requests.RequestException:
                pass
        K["nachricht_seit"] = neu_max or int(datetime.now(timezone.utc).timestamp())
        K["ungelesen"] = len(neue)

    nachher = repr(sorted((K.get("gebote") or {}).items())) + str(K.get("verifiziert")) + str(K.get("fehler"))
    return vorher != nachher or bool(K.get("ungelesen"))
