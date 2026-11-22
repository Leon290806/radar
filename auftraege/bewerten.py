# -*- coding: utf-8 -*-
"""
Bewertung: Kategorie, Machbarkeit durch Claude, Gewinnchance, erwarteter Wert in Euro und Euro pro Leon-Stunde.
Alle Annahmen stehen offen im Code, damit man sie im Dashboard nachvollziehen kann.
"""
import re
from datetime import datetime, timezone

import einstellungen as E


def _muster(wort):
    w = re.escape(wort.strip().lower())
    return re.compile(r"(?<![a-z0-9äöü])" + w + r"(?![a-z0-9äöü])")


_KAT = {k: [(w.strip(), _muster(w)) for w in v["kw"]] for k, v in E.KATEGORIEN.items()}
_SCHWER = [(w.strip(), _muster(w)) for w in E.SCHWER]
_VERBOTEN = [(w.strip(), _muster(w)) for w in E.VERBOTEN]


def _treffer(muster, text):
    return [w for w, m in muster if m.search(text)]


def alter_tage(e):
    t = e.get("erstellt")
    if not t:
        return None
    try:
        d = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d).total_seconds() / 86400
    except ValueError:
        return None


def kategorie(e):
    text = " ".join([e.get("titel", ""), e.get("text", ""), " ".join(e.get("tags") or [])]).lower()
    punkte = {k: len(_treffer(m, text)) for k, m in _KAT.items()}
    beste = max(punkte, key=punkte.get)
    if e.get("art") == "bounty":
        return "programmierung" if punkte[beste] == 0 else beste
    if e.get("art") == "wettbewerb":
        return "ki" if punkte["ki"] else ("programmierung" if punkte[beste] == 0 else beste)
    return beste if punkte[beste] > 0 else "sonstiges"


def wert_usd(e):
    """Was Leon realistisch bekommt (vor Gebühren), in USD."""
    if e["art"] == "freelance":
        lo, hi, avg = e.get("budget_min_usd") or 0, e.get("budget_max_usd") or 0, e.get("gebot_avg_usd") or 0
        if e.get("typ") == "hourly":
            satz = avg or (lo + hi) / 2 or 15
            return min(satz, 60) * 6  # Annahme: ~6 abrechenbare Stunden
        basis = avg or (lo + hi) / 2 or lo
        if hi:
            basis = min(basis, hi)
        return max(basis, lo)
    b = e.get("betrag") or 0
    if e.get("waehrung") == "EUR":
        b /= E.USD_EUR
    if e["art"] == "wettbewerb":
        return b * 0.25  # nur ein Teil des Preisgeldes geht an einen Gewinner
    if e["art"] == "gesuch" and not b:
        return 400  # unbekanntes Budget: vorsichtige Annahme
    return b


def gewinnchance(e, gelernt):
    basis = E.GEWINN_BASIS.get(e["art"], 0.1)
    n = e.get("gebote") or 0
    if e["art"] == "freelance":
        p = basis / (1 + n / 15)
        if (e.get("sprache") == "de") or re.search(r"\b(german|deutsch)\b", (e.get("titel", "") + e.get("text", "")).lower()):
            p *= 1.6
    elif e["art"] == "bounty":
        p = basis / (1 + (e.get("versuche") or 0) / 2 + n / 12)
        if e.get("zugewiesen"):
            p *= 0.2
    elif e["art"] == "wettbewerb":
        p = basis / (1 + n / 400)
    else:
        p = basis / (1 + n / 10)
    p *= gelernt.get("quelle_mult", {}).get(e["quelle"], 1.0)
    return max(0.005, min(p, 0.8))


def bewerte(e, gelernt):
    text = " ".join([e.get("titel", ""), e.get("text", ""), " ".join(e.get("tags") or [])]).lower()
    kat = kategorie(e)
    machbar = E.KATEGORIEN.get(kat, {}).get("machbar", 0.45)
    schwer = _treffer(_SCHWER, text)
    if schwer:
        machbar *= 0.45
    if e["art"] == "wettbewerb":
        machbar *= E.WETTBEWERB_MACHBAR_FAKTOR
    verboten = _treffer(_VERBOTEN, text)
    gruende = []
    if verboten:
        gruende.append("aussortiert wegen: " + ", ".join(sorted(set(verboten)))[:80])
    if e["art"] == "bounty" and e.get("ki_regel") == "verbietet":
        verboten = verboten or ["KI-Beiträge verboten"]
        gruende.append("Projekt verbietet KI-Beiträge")

    ki = e.get("ki") or {}
    if ki.get("machbar") is not None:
        machbar = 0.3 * machbar + 0.7 * float(ki["machbar"])
    if ki.get("verboten"):
        verboten = verboten or ["laut KI-Prüfung unseriös/regelwidrig"]
        gruende.append(ki.get("grund") or "KI-Prüfung: nicht annehmen")

    usd = wert_usd(e)
    if e["art"] == "freelance":
        usd = usd - max(usd * E.FREELANCER_GEBUEHR, 5)
    wert_eur = max(usd, 0) * E.USD_EUR
    if ki.get("preis_vorschlag_eur"):
        try:
            wert_eur = 0.5 * wert_eur + 0.5 * float(ki["preis_vorschlag_eur"])
        except (TypeError, ValueError):
            pass
    wert_eur *= gelernt.get("wert_mult", {}).get(e["quelle"], 1.0)
    deckel = E.WERT_DECKEL_EUR.get(e["art"])
    if deckel and wert_eur > deckel:
        gruende.append(f"Wert auf {deckel} € gedeckelt (großes Projekt)")
        wert_eur = deckel

    p = gewinnchance(e, gelernt)
    interesse = gelernt.get("kat_mult", {}).get(kat, 1.0)
    ew = wert_eur * p * machbar * interesse

    bew, liefer = E.LEON_MIN.get(e["art"], (8, 30))
    if ki.get("leon_minuten"):
        try:
            liefer = max(10, min(int(ki["leon_minuten"]), 240))
        except (TypeError, ValueError):
            pass
    leon_min = bew + p * liefer
    pro_std = ew / (leon_min / 60) if leon_min else 0

    alter = alter_tage(e)
    frisch = alter is None or alter <= E.FRISCH_TAGE.get(e["art"], 7)
    e.update({
        "kat": kat, "kat_name": E.KATEGORIEN.get(kat, {}).get("name", "Sonstiges"),
        "machbar": round(machbar, 3), "chance": round(p, 4), "wert_eur": round(wert_eur, 2),
        "ew_eur": round(ew, 2), "leon_min": round(leon_min, 1), "eur_pro_std": round(pro_std, 1),
        "aussortiert": bool(verboten), "gruende": gruende, "schwer": [s for s in schwer][:3],
        "alter_tage": None if alter is None else round(alter, 1), "frisch": frisch,
    })
    return e


def empfehlbar(e):
    return (not e.get("aussortiert")) and e.get("frisch") and e.get("machbar", 0) >= 0.5 and \
        e.get("wert_eur", 0) >= 25 and not e.get("feedback")
