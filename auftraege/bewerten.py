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
    """Kategorie aus Skill-Tags (stark), Titel (mittel) und Beschreibung (schwach). Zu wenig Hinweise -> 'sonstiges'."""
    tags = " ".join(e.get("tags") or []).lower()
    titel = (e.get("titel") or "").lower()
    text = (e.get("text") or "").lower()
    punkte = {k: 3 * len(_treffer(m, tags)) + 2 * len(_treffer(m, titel)) + min(2, len(_treffer(m, text)))
              for k, m in _KAT.items()}
    beste = max(punkte, key=punkte.get)
    if e.get("art") == "bounty":
        return "programmierung" if punkte[beste] < 2 else beste
    if e.get("art") == "wettbewerb":
        return "ki" if punkte["ki"] >= 2 else ("programmierung" if punkte[beste] < 2 else beste)
    return beste if punkte[beste] >= 2 else "sonstiges"


def wert_usd(e):
    """Was Leon realistisch bekommt (vor Gebühren), in USD."""
    if e["art"] == "freelance":
        lo, hi, avg = e.get("budget_min_usd") or 0, e.get("budget_max_usd") or 0, e.get("gebot_avg_usd") or 0
        if e.get("typ") == "hourly":
            satz = avg or lo or 15
            return min(satz, 60) * 6  # Annahme: ~6 abrechenbare Stunden
        if avg:
            basis = min(avg, hi) if hi else avg
        else:
            basis = lo or hi  # ohne Gebote: Untergrenze des Budgets (vorsichtig)
        return max(basis, 0)
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
        if any(f.startswith(("pool:", "enterprise:")) for f in (e.get("flags") or [])):
            p *= 0.3  # eingeschränkter Bieterkreis (z. B. Preferred-Freelancer-Pool)
        k = e.get("kunde") or {}
        if k and not k.get("bewertungen"):
            p *= 0.8  # neue Auftraggeber springen öfter ab
        if k and not k.get("zahlung_ok"):
            p *= 0.6
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
    sprache = (e.get("sprache") or "en").lower()[:2]
    if e["art"] == "freelance" and sprache not in ("en", "de"):
        machbar *= 0.6  # Leon kann Ergebnis und Kommunikation in dieser Sprache schlecht prüfen
        schwer = schwer + [f"Sprache {sprache}"]
    verboten = _treffer(_VERBOTEN, text)
    gruende = []
    if verboten:
        gruende.append("aussortiert wegen: " + ", ".join(sorted(set(verboten)))[:80])
    if e["art"] == "freelance":
        for k, grund in E.FL_SPERR_UPGRADES.items():
            if grund and e.get("upgrades", {}).get(k) and not (k in ("recruiter", "pf_only") and E.FL_PREFERRED):
                verboten = verboten or ["gesperrt"]
                gruende.append("Für dein Konto gesperrt: " + grund)
        if e.get("typ") == "hourly" and (e.get("budget_min_usd") or 0) >= E.FL_STUNDE_VERIFIZIERT_AB_USD and not E.FL_VERIFIZIERT:
            verboten = verboten or ["gesperrt"]
            gruende.append(f"Für dein Konto gesperrt: ab {E.FL_STUNDE_VERIFIZIERT_AB_USD} $/Std. nur mit „Verified by Freelancer“")
        if any(f.startswith(("pool:", "enterprise:")) for f in (e.get("flags") or [])):
            gruende.append("Eingeschränkter Bieterkreis möglich (Pool/Enterprise)")
        treffer_fl = [f for f in (e.get("flags") or []) if f in gelernt.get("gesperrt_flags", [])]
        if treffer_fl:
            verboten = verboten or ["gesperrt"]
            gruende.append("Für dein Konto gesperrt (gelernt): " + ", ".join(treffer_fl))
        k = e.get("kunde") or {}
        if k.get("seit") and not k.get("bewertungen"):
            try:
                neu = (datetime.now(timezone.utc) - datetime.fromisoformat(k["seit"])).days < 14
            except ValueError:
                neu = False
            if neu:
                gruende.append("Auftraggeber neu und ohne Bewertungen")
    if e["art"] == "bounty" and e.get("repo_ok") is False:
        verboten = verboten or ["Repo unbekannt"]
        gruende.append("Repository zu neu oder zu unbekannt – mögliche Falle")
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
    if e["art"] == "freelance" and (e.get("budget_min_usd") or 0) > 20000 and not ki.get("preis_vorschlag_eur"):
        verboten = verboten or ["unplausibles Budget"]
        gruende.append("Budget unplausibel hoch (Tippfehler oder Lockangebot)")
    if ki.get("preis_vorschlag_eur"):
        try:
            kp = float(ki["preis_vorschlag_eur"])
            wert_eur = min(0.5 * wert_eur + 0.5 * kp, 3 * kp)  # KI-Preis begrenzt Fantasie-Budgets
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
    e["rang"] = round(rang(e), 2)
    return e


def rang(e):
    """Sortierwert der Top 5: erwarteter Wert, bei weniger als 10 % Chance anteilig abgewertet."""
    return e.get("ew_eur", 0) * min(1.0, e.get("chance", 0) / E.TOP_VOLLE_CHANCE)


def top_tauglich(e):
    if not empfehlbar(e) or e.get("chance", 0) < E.TOP_MIN_CHANCE:
        return False
    if e.get("art") == "bounty" and e.get("repo_ok") is not True:
        return False
    return not (e.get("art") == "freelance" and (e.get("gebote") or 0) > E.TOP_MAX_GEBOTE)


def empfehlbar(e):
    return (not e.get("aussortiert")) and e.get("frisch") and e.get("machbar", 0) >= 0.5 and \
        e.get("wert_eur", 0) >= 25 and not e.get("feedback")
