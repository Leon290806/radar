# -*- coding: utf-8 -*-
"""Bewertung durch Claude (Anthropic-API): Machbarkeit, Lösungsweg, Risiko und ein ehrlicher Bewerbungstext."""
import json
import re

import requests

import einstellungen as E

SYSTEM = """Du prüfst Aufträge für Leon Neff, Einzelunternehmer (LN Automation, Deutschland), dualer Student mit wenig Zeit.
Claude (eine KI) erledigt die eigentliche Arbeit: Code (Python, JS/TS, Go, Rust), Excel/VBA, Datenaufbereitung, PDF-Auslesen,
einfache Websites, Vektor-Logos als SVG (schlicht), Texte und Übersetzungen DE/EN, KI-Prompts, E-Rechnung (XRechnung/ZUGFeRD),
Recherche mit öffentlichen Quellen. Claude kann NICHT: Videos, Telefonate, Vor-Ort-Arbeit, Fotobearbeitung, native Mobile-Apps
ausliefern, laufende Live-Betreuung. Leon bewirbt sich selbst und liefert ab.
Antworte NUR mit einem JSON-Objekt, ohne Text davor oder danach."""

VORLAGE = """Auftrag:
Quelle: {quelle} | Art: {art} | Budget/Betrag: {budget} | Konkurrenz (Gebote/Kommentare): {gebote}
Titel: {titel}
Beschreibung: {text}
Tags: {tags}
{extra}
{preis}

Gib zurück:
{{"machbar": Zahl 0..1 (wie vollständig und gut Claude das liefern kann),
 "verboten": true/false (true bei Regelverstoß, Betrug, Täuschung, Prüfungsleistung, Scraping gegen Nutzungsbedingungen, Personendaten, Plattform verbietet KI),
 "grund": "kurz, falls verboten oder heikel",
 "loesung": "1 Satz: was Claude konkret liefert",
 "claude_stunden": Zahl,
 "leon_minuten": Zahl (Leons Aufwand für Abstimmung und Abliefern, falls er den Zuschlag bekommt),
 "risiko": "1 Satz",
 "preis_vorschlag_eur": Zahl (realistischer Preis, mit dem Leon gewinnen kann),
 "bewerbung": "3-5 Sätze in der Sprache des Auftrags, kopierfertig, ehrlich, darf KI-gestützte Arbeit erwähnen, keine erfundenen Referenzen oder Jahre Erfahrung, mit Preis und Lieferzeit. Bei Bounties: kurzer Kommentar, mit dem Leon die Aufgabe anfragt, inkl. Offenlegung KI-gestützter Arbeit. Bei Wettbewerben: die nächsten 3 Schritte."}}"""


def bewerte(e):
    if not E.ANTHROPIC_KEY:
        return None, "kein API-Schlüssel"
    if e["art"] == "freelance":
        budget = f"{e.get('budget_min_usd', 0):.0f}–{e.get('budget_max_usd', 0):.0f} USD ({e.get('typ')}), Ø-Gebot {e.get('gebot_avg_usd', 0):.0f} USD"
    else:
        budget = f"{e.get('betrag') or 'unbekannt'} {e.get('waehrung') or ''}"
    extra = ""
    if e["art"] == "bounty":
        extra = f"Repository: {e.get('repo')} | KI-Regel laut CONTRIBUTING: {e.get('ki_regel', 'unbekannt')} | Versuche: {e.get('versuche', 0)}"
    g = e.get("gebot") or {}
    preis = (f"Empfohlenes Gebot: {g['betrag_usd']} USD {g['einheit']}" + (f", Lieferung in {g['tage']} Tagen" if g.get("tage") else "") +
             ". Leon ist neu auf der Plattform; verwende genau diesen Preis im Bewerbungstext.") if g else ""
    prompt = VORLAGE.format(quelle=e["quelle"], art=e["art"], budget=budget, gebote=e.get("gebote", 0), preis=preis,
                            titel=e.get("titel", ""), text=(e.get("text") or "")[:2500],
                            tags=", ".join(e.get("tags") or []), extra=extra)
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=90, headers={
            "x-api-key": E.ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": E.KI_MODELL, "max_tokens": 1600, "system": SYSTEM,
                  "messages": [{"role": "user", "content": prompt}]})
    except requests.RequestException as ex:
        return None, f"Verbindung: {ex.__class__.__name__}"
    if r.status_code != 200:
        return None, f"API HTTP {r.status_code}: {r.text[:160]}"
    try:
        text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
        m = re.search(r"\{.*\}", text, re.S)
        daten = json.loads(m.group(0), strict=False)  # erlaubt Zeilenumbrüche im Bewerbungstext
    except (ValueError, AttributeError):
        return None, "Antwort nicht lesbar"
    erlaubt = {"machbar", "verboten", "grund", "loesung", "claude_stunden", "leon_minuten", "risiko", "preis_vorschlag_eur", "bewerbung"}
    daten = {k: v for k, v in daten.items() if k in erlaubt}
    try:
        daten["machbar"] = max(0.0, min(1.0, float(daten.get("machbar", 0.5))))
    except (TypeError, ValueError):
        daten["machbar"] = 0.5
    daten["modell"] = E.KI_MODELL
    return daten, None
