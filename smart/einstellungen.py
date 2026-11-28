# -*- coding: utf-8 -*-
"""Einstellungen des Smart-Money-Radars (Hyperliquid). Alles nur Simulation – es werden nie Orders gesendet."""
import os

BASIS = os.path.dirname(os.path.abspath(__file__))
REPO_WURZEL = os.path.dirname(BASIS)
JOURNAL = os.path.join(REPO_WURZEL, "speicher", "smart.enc")            # wird ins Repo geschrieben (alle paar Stunden)
JOURNAL_CACHE = os.path.join(REPO_WURZEL, "speicher", "smart_cache.enc")  # Zwischenstand pro Lauf (GitHub-Cache, nicht im Repo)
JOURNAL_KLAR = os.path.join(REPO_WURZEL, "speicher", "smart.json")      # nur lokal ohne Passwort
SEITE = os.path.join(REPO_WURZEL, "docs", "smart", "index.html")

PASSWORT = os.environ.get("RADAR_PASSWORT", "")
NTFY_THEMA = os.environ.get("NTFY_THEMA", "")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "Leon290806/radar")

API = "https://api.hyperliquid.xyz/info"
LEADERBOARD = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"

# ---------- Auswahl der Trader (einmal am Tag) ----------
AUSWAHL_ALLE_STD = 24
MIN_KONTO_USD = 50_000          # kleinere Konten sind oft Zufall oder Hebel-Zocker
MIN_AKTIVITAET = 0.3            # Monatsumsatz mindestens 30 % des Kontos (sonst inaktiv)
MAX_UMSCHLAG_MONAT = 60         # Monatsumsatz > 60× Konto = Hochfrequenz/Market-Maker -> nicht kopierbar
KANDIDATEN_PNL = 120            # Vorauswahl: beste nach Gesamtgewinn …
KANDIDATEN_ROI = 80             # … plus beste nach Rendite (ab 200 Tsd. $ Konto)
MIN_TAGE_HISTORIE = 90
MIN_SCHLIESSUNGEN_30T = 8       # genug abgeschlossene Trades im letzten Monat
MIN_HALTEDAUER_STD = 1.0        # kürzer = Scalping, Kopieren kommt zu spät
MAX_TOP_ANTEIL = 0.5            # ein einzelner Trade darf nicht mehr als die Hälfte des Gewinns ausmachen
MAX_DRAWDOWN = 0.6
MIN_MONATE_POSITIV = 0.55
MAX_TRADER = 25

# ---------- Konsens-Signale ----------
MIN_POS_ANTEIL = 0.05           # Position zählt erst ab 5 % des Kontowerts …
MIN_POS_USD = 5_000             # … und mindestens 5.000 $
KONSENS_MIN_TRADER = 3
KONSENS_MIN_ANTEIL = 0.75       # mind. 75 % der Trader im Coin in dieselbe Richtung
KONSENS_AUS_TRADER = 2          # Ausstieg, wenn weniger als 2 Trader übrig …
KONSENS_AUS_ANTEIL = 0.6        # … oder Einigkeit unter 60 % fällt

# ---------- Papier-Portfolio ----------
START_KAPITAL = 100_000.0
POS_ANTEIL = 0.10               # je Position 10 % des Portfolios, ohne Hebel
MAX_POSITIONEN = 10
GEBUEHR = 0.00045               # Taker-Gebühr Hyperliquid (Basisstufe)
SLIPPAGE = 0.0005               # 0,05 % schlechterer Preis beim Ein- und Ausstieg
EINZEL_NOTIONAL = 1_000.0       # Einzel-Kopie-Test: fester Betrag pro kopierter Position

# ---------- Spiegel-Portfolio ----------
SPIEGEL_KAPITAL = 100_000.0      # wird nach Note auf die Trader verteilt
MIN_POS_SPIEGEL_ANTEIL = 0.01    # gespiegelt werden Positionen ab 1 % des Trader-Kontos (mind. 1.000 $)
SPIEGEL_MIN_POS = 200.0          # kleinere Teil-Positionen lohnen die Gebühr nicht
SPIEGEL_ANPASSEN_AB = 0.3        # Größe erst nachziehen, wenn sie mehr als 30 % vom Ziel abweicht
SPIEGEL_PUSH_AB = 3_000.0        # Push bei neuen/geschlossenen Spiegel-Positionen ab 3.000 $
TAGES_PUSH_STUNDE = 20           # Tageszusammenfassung ab 20 Uhr (Berlin)

COMMIT_ALLE_MIN = 120           # Ergebnis höchstens alle 2 Std. ins Repo (außer bei Papier-Trades)
MAX_PUSH_PRO_LAUF = 3
ZEITZONE = "Europe/Berlin"
