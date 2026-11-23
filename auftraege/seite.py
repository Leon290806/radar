# -*- coding: utf-8 -*-
"""Baut das Dashboard als eine HTML-Datei: Radar-Design (app.css) + eigene Ergänzungen + Daten als JSON."""
import json
import os

import einstellungen as E

FELDER = ("id", "quelle", "art", "titel", "url", "kat", "kat_name", "machbar", "chance", "wert_eur", "ew_eur", "leon_min",
          "eur_pro_std", "gebote", "alter_tage", "frisch", "aussortiert", "gruende", "empfehlbar", "feedback", "betrag_echt",
          "erst_gesehen", "typ", "rang", "repo_ok", "kunde", "flags", "gebot", "versuche", "ki_regel", "repo", "frist", "schwer", "suchbegriff")


def _lies(*teile):
    with open(os.path.join(*teile), encoding="utf-8") as f:
        return f.read()


def konto_daten(J):
    K = J.get("konto") or {}
    gebote = sorted(({"id": i, **g} for i, g in (K.get("gebote") or {}).items()), key=lambda g: g.get("zeit") or "", reverse=True)
    return {"verbunden": bool(E.FREELANCER_TOKEN), "name": K.get("name"), "verifiziert": K.get("verifiziert"),
            "abgleich": K.get("abgleich"), "fehler": K.get("fehler"), "nachrichten_fehler": K.get("nachrichten_fehler"),
            "gebote": gebote[:30]}


def daten(J):
    eintraege = []
    for e in J.get("eintraege", {}).values():
        d = {k: e.get(k) for k in FELDER if e.get(k) is not None}
        d["text"] = (e.get("text") or "")[:600]
        if e.get("art") == "freelance" and e.get("waehrung"):
            d["waehrung"] = e["waehrung"]
            d["kurs"] = E.USD_JE_EINHEIT.get(str(e["waehrung"]).upper())
        d["tags"] = (e.get("tags") or [])[:5]
        if e.get("ki"):
            d["ki"] = {k: e["ki"].get(k) for k in ("loesung", "risiko", "bewerbung", "preis_vorschlag_eur", "claude_stunden",
                                                   "leon_minuten", "grund", "modell")}
        eintraege.append(d)
    letzte = {}
    for f in J.get("feedback", []):
        letzte[f["id"]] = f
    erg = {"beworben": 0, "gewonnen": 0, "verloren": 0, "uninteressant": 0, "gesperrt": 0, "umsatz": 0.0}
    for f in letzte.values():
        a = f["aktion"]
        erg[a] = erg.get(a, 0) + 1
        if a in ("gewonnen", "verloren"):
            erg["beworben"] += 1
        if a == "gewonnen":
            erg["umsatz"] += f.get("betrag") or 0
    quellen = {}
    for name, st in J.get("quellen", {}).items():
        quellen[name] = {"status": st.get("status"), "laeufe": st.get("laeufe", [])[-30:]}
    return {
        "stand": J.get("stand"), "repo": E.REPO, "top": J.get("top", []), "eintraege": eintraege,
        "laeufe": [{k: v for k, v in l.items()} for l in J.get("laeufe", [])[-90:]],
        "quellen": quellen, "suchbegriffe": J.get("suchbegriffe", {}), "gelernt": J.get("gelernt", {}),
        "protokoll": J.get("protokoll", [])[:80], "ergebnis": erg,
        "feedback": sorted(letzte.values(), key=lambda f: f.get("zeit") or "", reverse=True)[:100],
        "konto": konto_daten(J),
        "ki": {"aktiv": bool(E.ANTHROPIC_KEY), "modell": E.KI_MODELL, "heute": J.get("ki_tag", {}).get("n", 0),
               "max": E.KI_MAX_PRO_TAG, "hart": E.KI_HART_PRO_TAG},
        "annahmen": {"gewinn_basis": E.GEWINN_BASIS, "leon_min": E.LEON_MIN, "usd_eur": E.USD_EUR,
                     "kategorien": {k: {"name": v["name"], "machbar": v["machbar"]} for k, v in E.KATEGORIEN.items()},
                     "frisch_tage": E.FRISCH_TAGE, "push_ab": E.PUSH_AB_EUR,
                     "ziel_netto": E.ZIEL_NETTO_EUR, "netto_faktor": E.NETTO_FAKTOR, "top_min_chance": E.TOP_MIN_CHANCE, "top_max_gebote": E.TOP_MAX_GEBOTE, "top_volle_chance": E.TOP_VOLLE_CHANCE},
    }


def erstelle(J):
    D = json.dumps(daten(J), ensure_ascii=False, separators=(",", ":"), allow_nan=False, default=str).replace("</", "<\\/")
    css = _lies(E.REPO_WURZEL, "app.css") + "\n" + _lies(E.BASIS, "web", "auftraege.css")
    js = _lies(E.BASIS, "web", "auftraege.js")
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex"><meta name="color-scheme" content="light dark">
<title>Auftrags-Radar</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400..800&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body><main></main>
<script type="application/json" id="daten">{D}</script>
<script>{js}</script>
</body></html>"""
