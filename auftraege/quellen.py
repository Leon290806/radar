# -*- coding: utf-8 -*-
"""
Quellen: holen öffentliche Aufträge über offizielle Schnittstellen bzw. öffentliche Feeds.
Jede Quelle liefert eine Liste einheitlicher Einträge (dict). Nichts wird eingeloggt, beworben oder eingereicht.
Für Seiten ohne offizielle API wird robots.txt geprüft.
"""
import html
import re
import time
import urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urlparse, quote

import requests

import einstellungen as E

S = requests.Session()
S.headers.update({"User-Agent": E.USER_AGENT, "Accept": "application/json"})
_ROBOTS = {}


def _erlaubt(url):
    """robots.txt respektieren (für Seiten ohne offizielle API)."""
    host = "{0.scheme}://{0.netloc}".format(urlparse(url))
    if host not in _ROBOTS:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = S.get(host + "/robots.txt", timeout=15)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        _ROBOTS[host] = rp
    return _ROBOTS[host].can_fetch(E.USER_AGENT, url)


def _get(url, **kw):
    for versuch in range(3):
        try:
            r = S.get(url, timeout=25, **kw)
            if r.status_code in (429, 502, 503):
                time.sleep(4 * (versuch + 1))
                continue
            return r
        except requests.RequestException:
            time.sleep(3)
    return None


def _text(s, n=1200):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()[:n]


def _iso(ts):
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return str(ts)


def _betrag_aus_text(s):
    """Sucht '$500', '500 USD', '€300', '1.5k $' usw. Gibt (Betrag, Währung) oder (None, None)."""
    if not s:
        return None, None
    m = re.search(r"(\$|€|USD|EUR)\s?([\d][\d,\.]*)\s?(k)?\b", s, re.I) or \
        re.search(r"\b([\d][\d,\.]*)\s?(k)?\s?(\$|€|USD|EUR|dollars?)", s, re.I)
    if not m:
        return None, None
    g = m.groups()
    if g[0] and not g[0][0].isdigit():
        sym, zahl, k = g[0], g[1], g[2]
    else:
        zahl, k, sym = g[0], g[1], g[2]
    zahl = zahl.replace(",", "")
    if zahl.count(".") > 1:
        zahl = zahl.replace(".", "")
    try:
        wert = float(zahl) * (1000 if k else 1)
    except ValueError:
        return None, None
    waehrung = "EUR" if sym and sym.upper() in ("€", "EUR") else "USD"
    return (wert if 10 <= wert <= 100000 else None), waehrung


# ---------------------------------------------------------------- freelancer.com (offizielle API)
def freelancer(suchbegriffe):
    out, fehler = [], []
    for q in suchbegriffe:
        url = ("https://www.freelancer.com/api/projects/0.1/projects/active/?query=" + quote(q) +
               "&limit=40&job_details=true&full_description=true&compact=true&sort_field=time_updated")
        r = _get(url)
        if r is None or r.status_code != 200:
            fehler.append(f"{q}: HTTP {getattr(r, 'status_code', 'Fehler')}")
            continue
        try:
            projekte = r.json().get("result", {}).get("projects", []) or []
        except ValueError:
            fehler.append(f"{q}: keine JSON-Antwort")
            continue
        for p in projekte:
            cur = (p.get("currency") or {})
            kurs = E.USD_JE_EINHEIT.get((cur.get("code") or "USD").upper())
            if kurs is None:
                continue  # unbekannte Währung: lieber auslassen als falsch bewerten
            b = p.get("budget") or {}
            bs = p.get("bid_stats") or {}
            out.append({
                "id": f"fl-{p.get('id')}",
                "quelle": "freelancer.com",
                "art": "freelance",
                "titel": _text(p.get("title"), 200),
                "url": "https://www.freelancer.com/projects/" + str(p.get("seo_url") or p.get("id")),
                "text": _text(p.get("description") or p.get("preview_description")),
                "typ": p.get("type") or "fixed",
                "budget_min_usd": (b.get("minimum") or 0) * kurs,
                "budget_max_usd": (b.get("maximum") or 0) * kurs,
                "gebot_avg_usd": (bs.get("bid_avg") or 0) * kurs,
                "gebote": bs.get("bid_count") or 0,
                "waehrung": cur.get("code"),
                "sprache": p.get("language"),
                "tags": [j.get("name") for j in (p.get("jobs") or []) if j.get("name")],
                "erstellt": _iso(p.get("time_submitted")),
                "suchbegriff": q,
            })
        time.sleep(1.2)
    return out, fehler


# ---------------------------------------------------------------- GitHub-Bounties (offizielle API)
def _gh_headers():
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if E.GITHUB_TOKEN:
        h["Authorization"] = "Bearer " + E.GITHUB_TOKEN
    return h


def github_bounties():
    out, fehler = [], []
    abfragen = ['label:"💎 Bounty" is:issue is:open', 'label:bounty is:issue is:open no:assignee',
                'label:"bounty" is:issue is:open "$" in:title']
    gesehen = set()
    for q in abfragen:
        r = _get("https://api.github.com/search/issues?q=" + quote(q) + "&sort=created&order=desc&per_page=50",
                 headers=_gh_headers())
        if r is None or r.status_code != 200:
            fehler.append(f"GitHub-Suche: HTTP {getattr(r, 'status_code', 'Fehler')}")
            continue
        for it in r.json().get("items", []):
            if it["html_url"] in gesehen or it.get("pull_request"):
                continue
            gesehen.add(it["html_url"])
            labels = " ".join(l.get("name", "") for l in it.get("labels", []))
            betrag, waehr = _betrag_aus_text(labels)
            if betrag is None:
                betrag, waehr = _betrag_aus_text(it.get("title"))
            if betrag is None:
                betrag, waehr = _betrag_aus_text((it.get("body") or "")[:3000])
            repo = it.get("repository_url", "").replace("https://api.github.com/repos/", "")
            out.append({
                "id": "gh-" + str(it["id"]),
                "quelle": "GitHub-Bounty",
                "art": "bounty",
                "titel": _text(it.get("title"), 200),
                "url": it["html_url"],
                "text": _text(it.get("body"), 1500),
                "typ": "bounty",
                "betrag": betrag,
                "waehrung": waehr or "USD",
                "gebote": it.get("comments") or 0,
                "repo": repo,
                "tags": [l.get("name") for l in it.get("labels", [])][:8],
                "erstellt": it.get("created_at"),
                "zugewiesen": bool(it.get("assignee")),
            })
        time.sleep(2.5)  # Such-API: max. 30 Anfragen/Minute
    return out, fehler


def github_betraege_nachladen(eintraege, max_n=40):
    """Bei Bounties ohne Betrag den ersten Bot-Kommentar (z. B. Algora) nach dem Betrag durchsuchen."""
    n = 0
    for e in eintraege:
        if e.get("art") != "bounty" or e.get("betrag") or n >= max_n:
            continue
        m = re.match(r"https://github.com/([^/]+/[^/]+)/issues/(\d+)", e["url"])
        if not m:
            continue
        r = _get(f"https://api.github.com/repos/{m.group(1)}/issues/{m.group(2)}/comments?per_page=10", headers=_gh_headers())
        n += 1
        if r is None or r.status_code != 200:
            continue
        for k in r.json():
            b, w = _betrag_aus_text(k.get("body", "")[:2000])
            if b:
                e["betrag"], e["waehrung"] = b, w
                break
        attempts = sum(1 for k in r.json() if "/attempt" in (k.get("body") or ""))
        e["versuche"] = attempts


def github_repo_ok(repo, cache):
    """Ist das Repository etabliert (Sterne, Alter, nicht archiviert)? Schützt vor Fake-Bounties."""
    if not repo:
        return False
    heute = datetime.now(timezone.utc)
    c = cache.get(repo)
    if c and c.get("geprueft", "")[:10] >= (heute.date().isoformat()[:8] + "01"):  # einmal pro Monat neu prüfen
        return c["ok"]
    r = _get(f"https://api.github.com/repos/{repo}", headers=_gh_headers())
    if r is None or r.status_code != 200:
        return False
    d = r.json()
    try:
        alter = (heute - datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))).days
    except (KeyError, ValueError):
        alter = 0
    ok = (d.get("stargazers_count", 0) >= E.REPO_MIN_STERNE and alter >= E.REPO_MIN_ALTER_TAGE
          and not d.get("archived") and not d.get("disabled"))
    cache[repo] = {"ok": ok, "sterne": d.get("stargazers_count", 0), "alter": alter, "geprueft": heute.isoformat()}
    return ok


def github_ki_regel(repo, cache):
    """Liest CONTRIBUTING/AI-Policy des Projekts: 'verbietet' / 'erlaubt' / 'unbekannt' (zwischengespeichert)."""
    if not repo:
        return "unbekannt"
    if repo in cache:
        return cache[repo]
    urteil = "unbekannt"
    for datei in ("CONTRIBUTING.md", ".github/CONTRIBUTING.md", "AI_POLICY.md", "docs/CONTRIBUTING.md"):
        r = _get(f"https://api.github.com/repos/{repo}/contents/{datei}",
                 headers={**_gh_headers(), "Accept": "application/vnd.github.raw"})
        if r is None or r.status_code != 200:
            continue
        t = r.text.lower()
        if re.search(r"(no|not accept|prohibit|ban|forbid|reject)[^.\n]{0,80}(ai|llm|chatgpt|copilot|generated)", t) or \
           re.search(r"(ai|llm)[- ]generated[^.\n]{0,80}(not|prohibit|ban|reject|close)", t):
            urteil = "verbietet"
        elif re.search(r"(ai|llm)[^.\n]{0,60}(disclos|allowed|permitted|welcome)", t):
            urteil = "erlaubt"
        break
    cache[repo] = urteil
    return urteil


# ---------------------------------------------------------------- Hacker News "Seeking freelancer" (offizielle Algolia-API)
def hackernews():
    out, fehler = [], []
    r = _get("https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&query=Freelancer")
    if r is None or r.status_code != 200:
        return out, [f"HN: HTTP {getattr(r, 'status_code', 'Fehler')}"]
    treffer = [h for h in r.json().get("hits", []) if "freelancer" in (h.get("title") or "").lower()]
    if not treffer:
        return out, ["HN: kein aktueller Freelancer-Thread"]
    faden = treffer[0]
    r2 = _get(f"https://hn.algolia.com/api/v1/items/{faden['objectID']}")
    if r2 is None or r2.status_code != 200:
        return out, [f"HN-Thread: HTTP {getattr(r2, 'status_code', 'Fehler')}"]
    for k in r2.json().get("children", []):
        t = k.get("text") or ""
        if "seeking freelancer" not in _text(t, 80).lower():
            continue
        klar = _text(t, 1500)
        betrag, waehr = _betrag_aus_text(klar)
        out.append({
            "id": f"hn-{k.get('id')}",
            "quelle": "Hacker News",
            "art": "gesuch",
            "titel": klar[18:120].strip(" -|:") or "Seeking freelancer",
            "url": f"https://news.ycombinator.com/item?id={k.get('id')}",
            "text": klar,
            "typ": "gesuch",
            "betrag": betrag,
            "waehrung": waehr or "USD",
            "gebote": len(k.get("children") or []),
            "tags": [],
            "erstellt": k.get("created_at"),
        })
    return out, fehler


# ---------------------------------------------------------------- Devpost-Hackathons (öffentliche JSON, robots.txt geprüft)
def devpost():
    url = "https://devpost.com/api/hackathons?status[]=open&challenge_type[]=online&order_by=prize-amount"
    if not _erlaubt(url):
        return [], ["Devpost: laut robots.txt nicht erlaubt – übersprungen"]
    r = _get(url)
    if r is None or r.status_code != 200:
        return [], [f"Devpost: HTTP {getattr(r, 'status_code', 'Fehler')}"]
    out = []
    try:
        liste = r.json().get("hackathons", [])
    except ValueError:
        return [], ["Devpost: keine JSON-Antwort"]
    for h in liste:
        preis_txt = _text(h.get("prize_amount"), 80)
        betrag, waehr = _betrag_aus_text(preis_txt)
        out.append({
            "id": f"dp-{h.get('id')}",
            "quelle": "Devpost",
            "art": "wettbewerb",
            "titel": _text(h.get("title"), 200),
            "url": h.get("url"),
            "text": _text(" · ".join([t.get("name", "") for t in h.get("themes", [])]) + " · " +
                          str(h.get("submission_period_dates", "")) + " · " + str(h.get("time_left_to_submission", ""))),
            "typ": "wettbewerb",
            "betrag": betrag,
            "waehrung": waehr or "USD",
            "gebote": h.get("registrations_count") or 0,
            "tags": [t.get("name") for t in h.get("themes", [])][:6],
            "erstellt": None,
            "frist": str(h.get("submission_period_dates", "")),
        })
    return out, []


# ---------------------------------------------------------------- Remotive (offizielle API, nur Freelance/Contract)
def remotive():
    r = _get("https://remotive.com/api/remote-jobs?limit=100")
    if r is None or r.status_code != 200:
        return [], [f"Remotive: HTTP {getattr(r, 'status_code', 'Fehler')}"]
    out = []
    for j in r.json().get("jobs", []):
        if (j.get("job_type") or "").lower() not in ("freelance", "contract"):
            continue
        betrag, waehr = _betrag_aus_text(j.get("salary") or "")
        out.append({
            "id": f"rm-{j.get('id')}",
            "quelle": "Remotive",
            "art": "gesuch",
            "titel": _text(j.get("title"), 200) + " – " + _text(j.get("company_name"), 60),
            "url": j.get("url"),
            "text": _text(j.get("description"), 1200),
            "typ": j.get("job_type"),
            "betrag": betrag,
            "waehrung": waehr or "USD",
            "gebote": 0,
            "tags": (j.get("tags") or [])[:8],
            "erstellt": j.get("publication_date"),
        })
    return out, []


# ---------------------------------------------------------------- Kaggle (offizielle API, nur mit Schlüssel)
def kaggle():
    if not (E.KAGGLE_USER and E.KAGGLE_KEY):
        return [], ["Kaggle: kein Schlüssel hinterlegt (optional)"]
    r = _get("https://www.kaggle.com/api/v1/competitions/list?sortBy=prize", auth=(E.KAGGLE_USER, E.KAGGLE_KEY))
    if r is None or r.status_code != 200:
        return [], [f"Kaggle: HTTP {getattr(r, 'status_code', 'Fehler')}"]
    out = []
    for c in r.json():
        betrag, waehr = _betrag_aus_text(str(c.get("reward", "")))
        out.append({
            "id": f"kg-{c.get('id') or c.get('ref')}",
            "quelle": "Kaggle",
            "art": "wettbewerb",
            "titel": _text(c.get("title"), 200),
            "url": c.get("url") or ("https://www.kaggle.com/competitions/" + str(c.get("ref", ""))),
            "text": _text(c.get("description"), 800),
            "typ": "wettbewerb",
            "betrag": betrag,
            "waehrung": waehr or "USD",
            "gebote": c.get("teamCount") or 0,
            "tags": [t.get("name") for t in (c.get("tags") or []) if isinstance(t, dict)][:6],
            "erstellt": c.get("enabledDate"),
            "frist": c.get("deadline"),
        })
    return out, []


# ---------------------------------------------------------------- Algora (öffentliche Bounty-Seite, robots.txt geprüft)
def algora():
    url = "https://algora.io/bounties"
    if not _erlaubt(url):
        return [], ["Algora: laut robots.txt nicht erlaubt – übersprungen"]
    r = _get(url, headers={"Accept": "text/html"})
    if r is None or r.status_code != 200:
        return [], [f"Algora: HTTP {getattr(r, 'status_code', 'Fehler')}"]
    seite = r.text
    out, gesehen = [], set()
    for m in re.finditer(r'href="(https://github\.com/([^/"]+/[^/"]+)/issues/(\d+))"[^>]*>(.*?)</a>', seite, re.S):
        link, repo, nr, inhalt = m.groups()
        if link in gesehen:
            continue
        gesehen.add(link)
        umfeld = seite[max(0, m.start() - 900): m.end() + 900]
        betrag, waehr = _betrag_aus_text(_text(umfeld, 2000))
        titel = _text(inhalt, 200) or f"{repo} #{nr}"
        out.append({"id": f"gh-al-{repo.replace('/', '-')}-{nr}", "quelle": "Algora", "art": "bounty", "titel": titel,
                    "url": link, "text": _text(umfeld, 600), "typ": "bounty", "betrag": betrag, "waehrung": waehr or "USD",
                    "gebote": 0, "repo": repo, "tags": [], "erstellt": None})
    if not out:
        return [], ["Algora: Seite gelesen, aber keine Bounties erkannt (Aufbau geändert?)"]
    return out, []


# Registrierte Quellen: Name -> (Funktion, Startstatus). "test" = wird beobachtet, bis klar ist, ob sie sich lohnt.
QUELLEN = {
    "freelancer.com": ("freelancer", "aktiv"),
    "GitHub-Bounty": (github_bounties, "aktiv"),
    "Algora": (algora, "test"),
    "Hacker News": (hackernews, "test"),
    "Devpost": (devpost, "test"),
    "Remotive": (remotive, "test"),
    "Kaggle": (kaggle, "test"),
}
