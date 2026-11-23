# -*- coding: utf-8 -*-
"""Einstellungen des Auftrags-Radars. Alles, was man anpassen möchte, steht hier."""
import os

BASIS = os.path.dirname(os.path.abspath(__file__))
REPO_WURZEL = os.path.dirname(BASIS)
JOURNAL = os.path.join(REPO_WURZEL, "speicher", "auftraege.enc")
JOURNAL_KLAR = os.path.join(REPO_WURZEL, "speicher", "auftraege.json")  # nur ohne Passwort (lokal)
SEITE = os.path.join(REPO_WURZEL, "docs", "auftraege", "index.html")

PASSWORT = os.environ.get("RADAR_PASSWORT", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
KI_MODELL = os.environ.get("AUFTRAG_MODELL") or "claude-sonnet-5-5"
KI_MAX_PRO_TAG = int(os.environ.get("AUFTRAG_KI_MAX_PRO_TAG") or "24")   # Kostenbremse
KI_MAX_PRO_LAUF = int(os.environ.get("AUFTRAG_KI_MAX_PRO_LAUF") or "8")
KI_HART_PRO_TAG = int(os.environ.get("AUFTRAG_KI_HART_PRO_TAG") or "60")  # absolute Obergrenze inkl. manueller Prüfungen
MANUELL = os.environ.get("GITHUB_EVENT_NAME") in ("workflow_dispatch", "issues")
ZEITZONE = "Europe/Berlin"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "Leon290806/radar")
NTFY_THEMA = os.environ.get("NTFY_THEMA", "")
PUSH_AB_EUR = float(os.environ.get("AUFTRAG_PUSH_AB_EUR") or "40")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://leon290806.github.io/radar/auftraege/")
KAGGLE_USER = os.environ.get("KAGGLE_USERNAME", "")
KAGGLE_KEY = os.environ.get("KAGGLE_KEY", "")

USER_AGENT = "LN-Automation-Auftragsradar/1.0 (+https://www.ln-automation.de)"
USD_EUR = 0.92          # grobe Umrechnung, nur für die Sortierung
# Feste, grobe Kurse (USD je Einheit). Unbekannte Währungen werden ausgelassen statt falsch bewertet.
USD_JE_EINHEIT = {"USD": 1, "EUR": 1.08, "GBP": 1.27, "CHF": 1.13, "AUD": 0.65, "CAD": 0.73, "NZD": 0.60, "SGD": 0.74,
                  "HKD": 0.128, "JPY": 0.0067, "CNY": 0.14, "INR": 0.012, "PKR": 0.0036, "BDT": 0.0085, "LKR": 0.0033,
                  "IDR": 0.000063, "PHP": 0.017, "MYR": 0.21, "THB": 0.028, "VND": 0.00004, "ZAR": 0.054, "NGN": 0.0007,
                  "KES": 0.0077, "EGP": 0.02, "AED": 0.27, "SAR": 0.27, "TRY": 0.03, "SEK": 0.095, "NOK": 0.093,
                  "DKK": 0.145, "PLN": 0.25, "BRL": 0.18, "MXN": 0.055, "CLP": 0.0011, "COP": 0.00025, "ARS": 0.001}
FREELANCER_GEBUEHR = 0.10  # Plattformgebühr freelancer.com (mind. 5 $)

# Wie lange ein Eintrag als "frisch" gilt (Tage), je Art
FRISCH_TAGE = {"freelance": 4, "bounty": 45, "wettbewerb": 60, "gesuch": 20, "ausschreibung": 30}
AUFBEWAHREN_TAGE = 30

# Leon-Zeit in Minuten: Bewerben + (falls Zuschlag) Abstimmung und Abliefern
LEON_MIN = {
    "freelance": (5, 30),
    "bounty": (5, 25),
    "gesuch": (8, 35),
    "wettbewerb": (30, 120),
    "ausschreibung": (60, 300),  # Unterlagen prüfen, Angebot einreichen, Nachweise
}

# freelancer.com: Sperren für neue, kostenlose Konten
FL_VERIFIZIERT = (os.environ.get("AUFTRAG_FL_VERIFIZIERT") or "").lower() in ("1", "ja", "true")
FL_PREFERRED = (os.environ.get("AUFTRAG_FL_PREFERRED") or "").lower() in ("1", "ja", "true")
FL_SPERR_UPGRADES = {"recruiter": "nur Preferred Freelancer (Recruiter-Projekt)", "pf_only": "nur Preferred Freelancer",
                     "qualified": "nur qualifizierte Freelancer", "nonpublic": "nicht öffentlich", "sealed": None}
FL_STUNDE_VERIFIZIERT_AB_USD = 50
# Sprachen, deren Ergebnis Leon prüfen kann bzw. bei denen Claude sehr sicher ist
SPRACHEN_GUT = ["english", "englisch", "german", "deutsch", "french", "französisch", "spanish", "spanisch",
                "italian", "italienisch", "portuguese", "portugiesisch", "dutch", "niederländisch"]
SPRACHEN_HEIKEL = ["somali", "amharic", "tigrinya", "swahili", "yoruba", "hausa", "igbo", "zulu", "pashto", "dari",
                   "farsi", "persian", "urdu", "hindi", "bengali", "tamil", "telugu", "nepali", "sinhala", "burmese",
                   "khmer", "lao", "thai", "vietnamese", "tagalog", "indonesian", "malay", "arabic", "hebrew",
                   "japanese", "korean", "chinese", "mandarin", "cantonese", "mongolian", "kazakh", "uzbek",
                   "georgian", "armenian", "albanian", "haitian", "creole"]  # ab diesem Stundensatz nur mit "Verified by Freelancer"

# Größere Projekte brauchen mehr als Claude allein (Abstimmung, Verantwortung): Wert wird gedeckelt
WERT_DECKEL_EUR = {"freelance": 2500, "gesuch": 800, "bounty": 5000, "wettbewerb": 5000, "ausschreibung": 10000}
# Wettbewerbe verlangen oft Demo-Video/Pitch und viel Feinschliff
WETTBEWERB_MACHBAR_FAKTOR = 0.5

# Monatsziel
ZIEL_NETTO_EUR = float(os.environ.get("AUFTRAG_ZIEL_NETTO") or "1000")
NETTO_FAKTOR = float(os.environ.get("AUFTRAG_NETTO_FAKTOR") or "0.72")  # nach ~10 % Gebühr und ~20 % Steuern (grob)

# Ranking der Top 5: Mischung aus Wert und echter Chance
TOP_MIN_CHANCE = 0.04      # darunter: Lotto, fliegt aus den Top 5
TOP_MAX_GEBOTE = 80        # mehr Konkurrenz: fliegt aus den Top 5 (Freelance)
TOP_VOLLE_CHANCE = 0.10    # unter 10 % Chance wird der erwartete Wert anteilig abgewertet

# Startwerte für die Gewinnchance (werden durch Feedback gelernt)
GEWINN_BASIS = {"freelance": 0.22, "bounty": 0.30, "gesuch": 0.10, "wettbewerb": 0.04, "ausschreibung": 0.03}
# Ausschreibungen: formale Anforderungen (Referenzen, Eignungsnachweise) senken die Machbarkeit
AUSSCHREIBUNG_MACHBAR_FAKTOR = 0.6
AUSSCHREIBUNG_WERT_UNBEKANNT_EUR = 3000
# CPV-Codes: Übersetzung, Webdesign, Softwareprogrammierung, Datenverarbeitung, Grafikdesign
TED_CPV = ["79530000", "72413000", "72200000", "72212000", "72260000", "72300000", "72310000", "79822500"]
BUND_STICHWORTE = ["übersetzung", "website", "webseite", "internetauftritt", "software", "programmierung", "grafik",
                   "lektorat", "texte", "redaktion", "datenbank", "digitalisierung", "künstliche intelligenz", " ki",
                   "e-rechnung", "excel", "datenaufbereitung", "barrierefrei"]

# Kategorien: Stichworte -> Machbarkeit durch Claude (0..1)
KATEGORIEN = {
    "erechnung":    {"name": "E-Rechnung/DATEV", "machbar": 0.92,
                     "kw": ["xrechnung", "zugferd", "e-rechnung", "erechnung", "e-invoice", "einvoice", "datev", "peppol"]},
    "excel":        {"name": "Excel/VBA", "machbar": 0.9,
                     "kw": ["excel", "vba", "macro", "makro", "spreadsheet", "google sheets", "power query", "pivot", "formula", "xlsx"]},
    "programmierung": {"name": "Programmierung", "machbar": 0.85,
                     "kw": ["python", "script", "skript", "automation", "automate", "api", "javascript", "typescript", "node", "bot ",
                            "fastapi", "django", "flask", "rust", "golang", " go ", "bash", "cli", "bug", "fix"]},
    "daten":        {"name": "Daten/PDF", "machbar": 0.86,
                     "kw": ["data processing", "data cleaning", "csv", "json", "pdf", "extract", "parse", "convert", "database", "sql"]},
    "ki":           {"name": "KI/Prompts", "machbar": 0.82,
                     "kw": ["prompt", "chatgpt", "llm", "openai", "claude", "gpt", "chatbot", "rag", "ai agent", "langchain", "n8n", "make.com", "zapier"]},
    "web":          {"name": "Web/Landingpage", "machbar": 0.76,
                     "kw": ["landing page", "landingpage", "website", "webseite", "html", "css", "wordpress", "react", "next.js", "tailwind"]},
    "uebersetzung": {"name": "Übersetzung", "machbar": 0.86,
                     "kw": ["translate", "translation", "übersetzung", "translator", "german", "deutsch", "localization"]},
    "text":         {"name": "Texte", "machbar": 0.8,
                     "kw": ["copywriting", "article", "blog", "content writing", "product description", "texter", "artikel", "proofread", "lektorat"]},
    "design":       {"name": "Logo/Vektor", "machbar": 0.55,
                     "kw": ["logo", "vector", "svg", "icon", "branding", "brand identity"]},
    "recherche":    {"name": "Recherche", "machbar": 0.65,
                     "kw": ["research", "recherche", "market analysis", "marktanalyse", "competitor"]},
}

# Kann Claude kaum liefern -> Machbarkeit stark senken
SCHWER = ["video", "animation", "after effects", "mobile app", "ios", "android", "flutter", "swift", "kotlin", "unity", "unreal",
          "3d", "blender", "photoshop", "retouch", "voice", "voiceover", "call", "phone", "telefon", "on-site", "onsite", "vor ort",
          "full-time", "full time", "vollzeit", "long term", "long-term", "ongoing", "social media manager", "backlink", "tiktok",
          "instagram growth", "figma", "hardware", "embedded", "plc", "sps", "robot", "robotic", "mechanical", "cad", "autocad",
          "solidworks", "revit", "floor plan", "drafting", "pcb", "electrical", "business partner", "partner wanted", "co-founder", "cofounder", "equity",
          "business development", "sales rep", "sales agent", "lead generation", "cold calling", "virtual assistant", "data entry", "typing",
          "demo video", "pitch video", "attorney", "lawyer", "legal advice", "notary", "courier", "delivery driver", "driver",
          "cfo", "chartered accountant", "tax filing", "photographer", "cleaning", "in person", "in-person", "physical",
          "legal translation", "certified translation", "sworn translation", "native speaker", "nativo", "nativa"]

# Regelwidrig/unseriös -> aussortieren
VERBOTEN = ["visa", "appointment bot", "ticket bot", "sneaker", "captcha", "fake review", "reviews for", "homework", "assignment",
            "thesis", "dissertation", "exam", "essay writing", "crypto", "token presale", "memecoin", "casino", "betting", "gambling",
            "adult", "onlyfans", "followers", "likes", "scrape linkedin", "linkedin scraper", "instagram scraper", "facebook scraper",
            "email list", "leads list", "contact list", "phone verification", "account creation", "bypass", "cheat", "hack ",
            "credit card", "forex signals", "mlm", "commission only", "provision", "pay after", "unpaid", "test task for free",
            # typische Köder für KI-Agenten bei Fake-Bounties
            "wallet address", "airdrop", "conformance mirror", "not reviewed on this mirror",
            "pull requests from human engineers", "settlement"]
# Bounty-Repos müssen etabliert sein (Schutz vor Fallen)
REPO_MIN_STERNE = 25
REPO_MIN_ALTER_TAGE = 90

# Suchbegriffe für freelancer.com: aktiv + Kandidaten zum Testen (der Radar lernt, welche sich lohnen)
FREELANCER_START = ["python script", "excel vba", "data processing", "pdf extract", "german translation", "landing page",
                    "logo vector", "chatgpt prompt", "google sheets", "automation script"]
FREELANCER_KANDIDATEN = ["power query", "n8n", "zapier", "web scraping api", "copywriting german", "proofreading german",
                         "csv cleaning", "json conversion", "wordpress fix", "javascript bug", "fastapi", "react component",
                         "chatbot", "invoice", "datev", "technical writing", "product descriptions", "market research",
                         "svg icon", "sql query", "regex", "excel dashboard", "pdf to excel", "openai api", "rag"]
