# -*- coding: utf-8 -*-
"""Einstellungen des Bitcoin-Radars (Langfrist-Bewertung). Reine Analyse – keine Orders."""
import os

BASIS = os.path.dirname(os.path.abspath(__file__))
REPO_WURZEL = os.path.dirname(BASIS)
JOURNAL = os.path.join(REPO_WURZEL, "speicher", "bitcoin.enc")
JOURNAL_KLAR = os.path.join(REPO_WURZEL, "speicher", "bitcoin.json")
SEITE = os.path.join(REPO_WURZEL, "docs", "bitcoin", "index.html")
PASSWORT = os.environ.get("RADAR_PASSWORT", "")
NTFY_THEMA = os.environ.get("NTFY_THEMA", "")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")
ZEITZONE = "Europe/Berlin"

COINMETRICS = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
CM_METRIKEN = "PriceUSD,CapMrktCurUSD,CapMVRVCur,SplyCur,IssTotUSD,HashRate,AdrActCnt"
FNG = "https://api.alternative.me/fng/?limit=0&format=json"
BGEO = "https://bitcoin-data.com/v1/"
BGEO_ENDPUNKTE = {"sth-realized-price": "sthRealizedPrice", "lth-realized-price": "lthRealizedPrice", "sopr": "sopr", "sth-mvrv": "sthMvrv"}

GENESIS = "2009-01-03"
HALVINGS = ["2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20", "2028-04-15"]  # letztes = Schätzung
LERN_START = "2014-01-01"        # ab hier wird walk-forward bewertet (vorher nur Lernen)
MIN_HISTORIE_TAGE = 730          # Perzentile erst ab 2 Jahren Historie
HORIZONT = 365                   # Ziel: Rendite der nächsten 12 Monate

# Zonen nach Gesamt-Score (0 = sehr teuer, 100 = sehr günstig)
ZONEN = [(80, "Strong Buy"), (60, "Akkumulieren"), (40, "Halten"), (20, "Reduzieren"), (0, "Strong Sell")]
ANTEIL_JE_ZONE = {"Strong Buy": 1.0, "Akkumulieren": 1.0, "Halten": 1.0, "Reduzieren": 0.5, "Strong Sell": 0.0}  # „Halten“ heißt halten
SPARPLAN_FAKTOR = {"Strong Buy": 2.0, "Akkumulieren": 1.5, "Halten": 1.0, "Reduzieren": 0.5, "Strong Sell": 0.0}
MAX_GEWICHT = 0.30               # kein Indikator mehr als 30 % der Gesamtbewertung
GEBUEHR = 0.002                  # Backtest: 0,2 % je Umschichtung
