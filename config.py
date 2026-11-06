# -*- coding: utf-8 -*-
"""
Einstellungen für den Strategie-Radar. Alles hier darfst du anpassen.
Das Dashboard rechnet in % des Strategie-Portfolios – dein Kapital braucht der
Radar nur, um dir Stückzahlen zu nennen.
"""
import os

# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------
KAPITAL_EUR = float(os.environ.get("KAPITAL_EUR") or 10_000)  # nur für Stückzahl-Angaben
# Euro-Beträge im Dashboard zeigen? Bei öffentlichem Dashboard (GitHub Pages) besser aus: nur %.
ZEIGE_EURO = (os.environ.get("ZEIGE_EURO") or "1") == "1"

SCHWELLE = 55              # Mindest-Score (0–100) für eine Kaufempfehlung
SCHWELLE_RISK_OFF = 70     # höhere Hürde, wenn der S&P 500 unter seiner 200-Tage-Linie liegt
MAX_POSITIONEN = 5         # höchstens so viele Aktien gleichzeitig
MAX_NEU_PRO_TAG = 1        # höchstens eine neue Empfehlung pro Tag
MAX_JE_BRANCHE = 1         # Klumpenrisiko: höchstens 1 Aktie je Branche (z. B. nicht zwei Krankenversicherer)
MAX_JE_SEKTOR = 2          # und höchstens 2 je Sektor (z. B. Gesundheit)

# Positionsgröße wächst mit der Überzeugung: Score an der Schwelle -> GEWICHT_MIN,
# Score 90+ -> GEWICHT_MAX (aggressiv, aber begrenzt)
GEWICHT_MIN = 0.12
GEWICHT_MAX = 0.35
MAX_VERLUST_PRO_TRADE = 0.03   # Stopp-Abstand x Gewicht darf max. 3 % des Portfolios kosten
MIN_CASH_FUER_KAUF = 0.08      # unter 8 % freiem Cash keine neuen Käufe

# Ausstieg
STOPP_ATR_START = 2.5      # Anfangs-Stopp: Einstieg minus 2,5 x ATR(20)
STOPP_ATR_NACHZIEH = 3.0   # Nachzieh-Stopp: höchster Schlusskurs minus 3 x ATR(20)
HALTEDAUER = 40            # Zeitstopp in Handelstagen (Effekte wirken meist in den ersten Wochen)
MAX_GAP_EINSTIEG = 0.04    # Eröffnet die Aktie > 4 % über dem Signal-Schluss: Einstieg auslassen
KOSTEN = 0.001             # 0,1 % je Kauf/Verkauf (Gebühr + Spread), für das Musterdepot

RUECKBLICK_TAGE = 750      # beim ersten Start: ~3 Jahre rückwirkend simulieren (mehr Trades = belastbarere Statistik)

# Kern: Geld, das gerade in keiner Empfehlung steckt, liegt im S&P-500-ETF (Markt über 200-Tage-Linie)
# bzw. im Geldmarkt (Markt darunter). So arbeitet auch das freie Geld.
KERN_AKTIV = True
GELDMARKT_ZINS = 0.02      # angenommener Geldmarktzins p.a. für Phasen außerhalb des Marktes

# ---------------------------------------------------------------------------
# Lernmodul: prüft regelmäßig, ob andere Einstellungen zuletzt besser funktioniert hätten
# ---------------------------------------------------------------------------
LERNEN_AKTIV = True
LERN_INTERVALL = 20        # alle 20 Handelstage (ca. monatlich) neu prüfen
LERN_FENSTER = 750         # auf den letzten ~3 Jahren testen (zu kurze Fenster lernen nur Zufall)
LERN_MARGE = 0.15          # nur wechseln, wenn eine Variante klar (15 %) besser ist – gegen Zufallstreffer
LERN_MIN_TRADES = 12

# ---------------------------------------------------------------------------
# Signale und ihr Gewicht im Score (0–100)
# ---------------------------------------------------------------------------
GEWICHT_MOMENTUM = 0.30    # Stärke der letzten 6–12 Monate, nur im Aufwärtstrend
GEWICHT_PEAD = 0.40        # Kurssprung auf Quartalszahlen, der gehalten wird
GEWICHT_INSIDER = 0.40     # mehrere Vorstände kaufen mit eigenem Geld
GEWICHT_HOCH = 0.15        # Ausbruch auf neues 52-Wochen-Hoch mit Volumen
# Momentum + 52W-Hoch allein (max. 45) erreichen nie die Schwelle – es braucht Zahlen oder Insider.

HOCH_VOLUMEN_FAKTOR = 1.5  # Ausbruchstag mit mind. 1,5-fachem Volumen
HOCH_FENSTER = 5           # Signal gilt 5 Handelstage nach dem Ausbruch

# Warnsignal: negativer Kurssprung (Gap und Tagesminus mit Volumen, Schwellen wie beim PEAD)
EXIT_NEG_SPRUNG = True     # gehaltene Aktie am nächsten Tag verkaufen
NEG_SPERRE = 20            # danach 20 Handelstage keine Käufe in dieser Aktie

FILTER = []                # wird vom Lernmodul gefüllt (z. B. "Schwankung p.a. höchstens 60 %")

PEAD_GAP_MIN = 0.03
PEAD_TAGESPLUS_MIN = 0.05
PEAD_VOLUMEN_FAKTOR = 3.0
PEAD_FRISCH = 5            # volle Punkte bis 5 Tage nach dem Sprung, danach weniger
PEAD_MAX_ALTER = 15

INSIDER_AKTIV = True
INSIDER_FENSTER = 10       # Käufe der letzten 10 Handelstage (nach Meldedatum)
INSIDER_MIN_KAUF = 25_000  # kleinere Einzelkäufe ignorieren (USD bzw. EUR)
# Nur echte Anomalien zählen: Bewertung 0–100 aus Cluster, Rolle, Bestandsplus, Größe, Erstkauf und Kursrückgang.
# Beispiel: CEO kauft für 50 Tsd. bei 50 Mio. Bestand (+0,1 %) -> ca. 30 Punkte = normal, kein Signal.
INSIDER_MIN_AUFFAELLIG = 50
INSIDER_HISTORIE_TAGE = 260   # zusätzliche Vorgeschichte, um Erst- und Routinekäufe zu erkennen
INSIDER_LAENDER = ("USA", "DE")   # USA: SEC Form 4 · DE: BaFin Directors' Dealings (Art. 19 MAR)
INSIDER_FEED_TAGE = 45     # so viele Tage zeigt der Insider-Reiter
INSIDER_FEED_MIN_VERKAUF = 250_000   # Verkäufe erst ab dieser Größe anzeigen (es gibt sehr viele kleine)

# Groß + mittel + klein: In mittleren und kleinen Werten wirken Insider- und Zahlen-Effekte am stärksten.
UNIVERSEN = ["sp500", "nasdaq100", "sp400", "sp600", "dax", "mdax", "sdax"]
ZUSATZ_TICKER = []
MIN_PREIS = 5.0
MIN_UMSATZ = 5_000_000     # Ø Tagesumsatz in Kurswährung

# ---------------------------------------------------------------------------
# Vergleichsindizes im Dashboard (Name, Yahoo-Ticker) – im Dashboard ein-/ausschaltbar
# ---------------------------------------------------------------------------
BENCHMARKS = [
    ("S&P 500", "SPY"),
    ("Nasdaq 100", "QQQ"),
    ("MSCI World", "URTH"),
    ("DAX", "^GDAXI"),
]

# ---------------------------------------------------------------------------
# Odd-Lot-Tender (Sonderchancen, separat vom Portfolio)
# ---------------------------------------------------------------------------
ODDLOT_AKTIV = True
ODDLOT_TAGE = 30

# ---------------------------------------------------------------------------
# Zugänge & Benachrichtigung (in GitHub als "Secrets" hinterlegen)
# ---------------------------------------------------------------------------
# Die SEC verlangt Name + E-Mail im User-Agent, sonst Fehler 403.
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT") or "StrategieRadar privat bitte-eigene-email@beispiel.de"
# Push aufs Handy über die kostenlose App "ntfy": dort ein Thema abonnieren
# (z. B. "radar-leon-x7k2") und denselben Namen hier eintragen. Leer = aus.
NTFY_THEMA = os.environ.get("NTFY_THEMA") or ""
DASHBOARD_URL = os.environ.get("DASHBOARD_URL") or ""   # Link, der in der Push-Nachricht mitgeschickt wird
# Passwort für Journal und Dashboard. Gesetzt = alles verschlüsselt (Pflicht bei öffentlichem Repository).
RADAR_PASSWORT = os.environ.get("RADAR_PASSWORT") or ""

# ---------------------------------------------------------------------------
# Dateien
# ---------------------------------------------------------------------------
JOURNAL_DATEI = "speicher/journal.json"          # ohne Passwort (nur lokal)
JOURNAL_DATEI_GESCHUETZT = "speicher/journal.enc"  # mit Passwort (für GitHub)
DASHBOARD_DATEI = "docs/index.html"
