# Radar

Ein Musterdepot, das sich jeden Abend selbst aktualisiert. Es scannt rund 650 Aktien (S&P 500, Nasdaq 100,
DAX, MDAX) und die Insider-Meldungen der SEC. Nur wenn **viel zusammenkommt**, gibt es **eine** Empfehlung:
welche Aktie, wie viel Prozent des Portfolios, wo der Stopp liegt und wie lange gehalten wird.
Jede Empfehlung landet im Verlauf, und du siehst, wie sie ausgegangen ist.

Der Radar handelt nicht selbst. Ordern musst du bei deinem Broker.

## Wie eine Empfehlung entsteht

Jede Aktie bekommt täglich einen Score von 0 bis 100:

| Baustein | Punkte | Bedingung |
|---|---|---|
| Kurssprung nach Zahlen (PEAD) | bis 40 | +5 % mit Gap und 3-fachem Volumen, Niveau gehalten. Live wird geprüft, ob am Sprungtag Quartalszahlen kamen |
| Insider-Cluster | bis 40 | mehrere Vorstände kaufen mit eigenem Geld (SEC Form 4, keine Sparpläne nach 10b5-1) |
| Momentum | bis 30 | Aufwärtstrend und Stärke im Vergleich zu allen Aktien |

- **Momentum allein reicht nie.** Es braucht einen Auslöser (Zahlen oder Insider).
- **Kauf ab Score 55.** Liegt der S&P 500 unter seiner 200-Tage-Linie, erst ab 70.
- **Höchstens 1 neue Empfehlung pro Tag und 5 Positionen.** Mal kommt eine pro Woche, mal mehrere – je nachdem, was der Markt hergibt.
- **Größe 12–35 %** des Portfolios, je höher der Score, desto mehr. Gedeckelt so, dass ein Stopp höchstens 3 % des Portfolios kostet.
- **Ausstieg:** Nachzieh-Stopp (höchster Schluss − 3 × ATR) oder spätestens nach 40 Handelstagen.
- **Freies Geld arbeitet mit:** Was gerade in keiner Empfehlung steckt, liegt im S&P-500-ETF, solange der Markt über seiner 200-Tage-Linie liegt, sonst im Geldmarkt. Die Empfehlungen müssen also den Markt schlagen, nicht das Sparbuch.

## Lernmodul

Etwa alle 20 Handelstage spielt der Radar die letzten ~400 Tage mit 96 Varianten seiner Einstellungen durch: Schwelle, Haltedauer, Stopp und Gewichtung der Signale. Gewählt wird anhand der ersten zwei Drittel (Lernteil). Übernommen wird eine Variante nur, wenn sie auch im zeitlich danach liegenden Drittel (Prüfteil) klar besser ist. Die neuen Regeln gelten nur für künftige Empfehlungen, offene Positionen behalten ihre Regeln. Jede Änderung steht im Reiter *Lernen*.

## Das Dashboard

| Reiter | Inhalt |
|---|---|
| Heute | Empfehlung mit Anteil, Limit, Stopp und Gründen, weitere Aufgaben, Kennzahlen, Kurve gegen den S&P 500 |
| Portfolio | Aufteilung, jede Position mit Mini-Chart, Stopp, Haltedauer und Gründen |
| Verlauf | alle Empfehlungen mit Filter (Live, Rückblick, Gewinner …), je Trade Kursverlauf, Ergebnis und Vergleich zum S&P 500 |
| Insider | aktuelle Insider-Käufe (SEC) und Status des Datenabrufs |
| Scanner | die 15 stärksten Aktien, aufgeschlüsselt nach Momentum, Zahlen und Insider |
| Statistik | Radar gegen S&P 500 und „nur Kern“, Kennzahlen, Ergebnis nach Auslöser, Monatsrenditen |
| Lernen | aktuelle Einstellungen, letzte Prüfung, Änderungshistorie |

Beim ersten Start spielt der Radar die letzten 250 Handelstage mit genau diesen Regeln durch (Rückblick).
Danach läuft er live, und jede neue Empfehlung wird festgeschrieben.

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
