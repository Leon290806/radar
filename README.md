# Radar

Ein Musterdepot, das sich jeden Abend selbst aktualisiert. Es scannt rund 650 Aktien (S&P 500, Nasdaq 100,
DAX, MDAX) und die Insider-Meldungen der SEC. Nur wenn **viel zusammenkommt**, gibt es **eine** Empfehlung:
welche Aktie, wie viel Prozent des Portfolios, wo der Stopp liegt und wie lange gehalten wird.
Jede Empfehlung landet im Verlauf, und du siehst, wie sie ausgegangen ist.

Der Radar handelt nicht selbst. Ordern musst du bei deinem Broker.

## Wie eine Empfehlung entsteht

Jede Aktie bekommt täglich einen Score von 0 bis 100 aus vier Bausteinen:

| Baustein | Punkte | Bedingung |
|---|---|---|
| Kurssprung nach Zahlen (PEAD) | bis 40 | +5 % mit Gap und 3-fachem Volumen, Niveau gehalten. Live wird geprüft, ob am Sprungtag Quartalszahlen kamen |
| Insider-Cluster | bis 40 | Vorstände/Direktoren kaufen mit eigenem Geld (USA: SEC Form 4, DE: BaFin Directors' Dealings; keine Sparpläne) |
| Momentum | bis 30 | Aufwärtstrend und Stärke im Vergleich zu allen Aktien |
| 52-Wochen-Hoch | bis 15 | Ausbruch auf ein neues Jahreshoch mit erhöhtem Volumen |

- **Ohne Auslöser kein Kauf:** Es braucht immer einen Kurssprung nach Zahlen oder Insider-Käufe. Momentum und 52W-Hoch allein reichen nie, auch nicht nach dem Lernen.
- **Warnsignal:** Rutscht eine Aktie mit Volumen ab (negativer Kurssprung), wird sie verkauft und 20 Tage gesperrt.
- **Kauf ab Score 55.** Im Abwärtstrend (S&P 500 unter seiner 200-Tage-Linie) erst ab 70.
- **Höchstens 1 neue Empfehlung pro Tag und 5 Positionen.** Größe 12–35 % je nach Score, ein Stopp kostet höchstens 3 % des Portfolios.
- **Ausstieg:** Nachzieh-Stopp oder Zeitstopp. **Freies Geld** liegt im S&P-500-ETF bzw. im Abwärtstrend im Geldmarkt.

## Lernmodul

Etwa alle 20 Handelstage passiert Folgendes:
1. **Fehleranalyse:** Was hatten die Verlierer gemeinsam? Daraus entstehen Filter-Ideen.
2. **~180 Varianten:** Gewichtung, Schwelle, Haltedauer und Stopp werden durchgespielt.
3. **Robustheit:** Eine Variante zählt nur, wenn auch leicht veränderte Einstellungen gut sind.
4. **Filter-Tests:** Jede Filter-Idee wird erneut simuliert.
5. **Bestätigung:** Gewählt wird auf dem älteren Teil, übernommen nur, was auch im neueren Teil klar besser ist.

Alles, was der Radar dabei „denkt“, steht im Reiter *Lernen*.

## Dashboard

Die Reiter heißen Übersicht · Portfolio · Verlauf · Insider · Scanner · Statistik · Lernen. Ein Klick auf einen Ticker öffnet die Detailansicht mit Chart, Ereignissen, Score-Aufschlüsselung und Insider-Transaktionen.

## Variante A: automatisch in der Cloud (empfohlen, kein PC nötig)

Läuft kostenlos über GitHub, jeden Werktag nach US-Börsenschluss. Das Dashboard ist eine passwortgeschützte
Webseite fürs Handy. Bei neuen Empfehlungen kommt eine Push-Nachricht.

**Privat trotz öffentlichem Repository:** Journal und Dashboard werden mit deinem Passwort verschlüsselt
(AES-256). Im Repository und auf der Webseite liegt ohne Passwort nur Zeichensalat. Sichtbar ist nur der Code.
Ändern oder in deinem Konto ausführen kann ihn niemand außer dir.

1. **Repository anlegen:** auf github.com oben rechts **+ → New repository**. Name `radar`, **Public**, ohne README → *Create repository*.
2. **Dateien hochladen:** auf der leeren Seite auf *uploading an existing file* klicken. Die ZIP entpacken und den **Inhalt** des Ordners `strategie-radar` ins Fenster ziehen, inklusive des Ordners `.github`. Auf dem Mac blendest du ihn im Finder mit **Cmd + Shift + .** ein. Dann *Commit changes*.
3. **Geheimnisse hinterlegen:** *Settings → Secrets and variables → Actions → New repository secret*:
   - `RADAR_PASSWORT`: dein Passwort für das Dashboard (lang und neu, nicht wiederverwenden)
   - `SEC_USER_AGENT`: `Vorname Nachname deine@email.de` (die SEC verlangt eine Kontaktangabe)
   - `NTFY_THEMA` (optional): ein ausgedachter, schwer zu erratender Name für die Push-Nachrichten, z. B. `radar-k7q2m9x4`
4. **Webseite einschalten:** *Settings → Pages → Source: „GitHub Actions“*.
5. **Starten:** *Actions* → Workflows erlauben → *Radar* → **Run workflow**. Der erste Lauf dauert 30–60 Minuten (Insider-Historie), danach nur wenige Minuten.
6. **Aufs Handy:** `https://DEINNAME.github.io/radar/` öffnen, Passwort eingeben, „Zum Home-Bildschirm“ wählen.
7. **Push:** die App **ntfy** installieren und dein Thema abonnieren.

Die Push-Nachricht selbst ist nicht verschlüsselt. Deshalb sollte der Themen-Name schwer zu erraten sein.

## Variante B: auf dem eigenen PC

```
pip install -r requirements.txt
python radar.py --demo        # Probelauf mit erfundenen Daten
python radar.py               # echter Lauf, öffnet das Dashboard
```
Für den täglichen Lauf: unter Windows über die Aufgabenplanung (Mo–Fr 23:30 Uhr, Programm `python`,
Argument `radar.py --kein-browser`, „Starten in“ = dieser Ordner); unter Mac/Linux per cron.
Der PC muss dafür an sein.

## Nützliche Befehle

- `python radar.py --neu` startet das Journal neu, mit Rückblick.
- `python radar.py --neu --rueckblick 500` macht einen längeren Rückblick (lädt mehr Daten).
- Alle Regeln findest du in `config.py`.

## Ehrlich

- PEAD, Insider-Käufe und Momentum sind wissenschaftlich belegt, aber bekannt und schwächer als früher. Eine neuere Studie (2022–2026) fand den Insider-Effekt vor allem in den ersten Tagen nach der Meldung, über 1–3 Monate war er nicht mehr sicher nachweisbar. Deshalb zählt Insider hier nur mit anderen Signalen zusammen.
- Der Rückblick nutzt die **heutigen** Indexmitglieder. Firmen, die inzwischen pleite oder aus dem Index gefallen sind, fehlen. Das Ergebnis ist deshalb geschönt. Zählen tun die Live-Trades.
- Konzentriert heißt schwankungsreich: 5 Aktien mit bis zu 35 % Gewicht können deutlich stärker fallen als ein ETF.
- Erst ein paar Monate nur mitlesen, dann mit kleinem Geld starten.
- Gewinne sind steuerpflichtig. Kein Anlagerat.
