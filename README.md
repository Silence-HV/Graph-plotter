# Graph Plotter

Messdaten aus CSV-, Text- und Excel-Dateien als Diagramm darstellen und für Berichte,
Abschlussarbeiten und Präsentationen exportieren.

## Installation

Es gibt zwei Varianten:

- **Installer** (`GraphPlotter_v…_Setup.exe`): ausführen und den Schritten folgen. Administratorrechte
  sind nicht nötig.
- **Portable Version** (`GraphPlotter_v…_portable.zip`): entpacken und `GraphPlotter.exe` im Ordner
  starten. Nichts wird installiert; zum Entfernen den Ordner löschen.

Läuft unter Windows 10 (ab Version 1809) und Windows 11, jeweils 64 Bit.

**Warnung „Der Computer wurde durch Windows geschützt“:** Das Programm ist nicht digital signiert.
Windows warnt deshalb beim ersten Start. Auf „Weitere Informationen“ und dann „Trotzdem ausführen“
klicken.

## Updates

Das Programm prüft beim Start im Hintergrund, ob es eine neuere Version gibt. Dabei wird nur die
Release-Seite des Projekts auf GitHub abgefragt; Daten über dich oder deine Dateien werden nicht
übertragen.

- Gibt es ein Update, erscheint oben im Fenster ein Hinweis. **„Jetzt aktualisieren“** lädt den
  Installer, prüft ihn, schließt das Programm, installiert die neue Version und startet sie wieder.
  Einstellungen und Projekte bleiben erhalten; deinstallieren ist nicht nötig.
- Bei der **portablen Version** öffnet derselbe Knopf die Download-Seite. Den alten Ordner durch den
  neuen ersetzen.
- Manuell suchen und die automatische Prüfung abschalten: Menü **„Programm“** oben rechts.

Ein Update von Hand geht genauso: die neue `…_Setup.exe` ausführen, die alte Version bleibt nicht
zurück.

## Kurzanleitung

1. **Daten laden:** Dateien ins Fenster ziehen oder „Öffnen“ wählen. Im Importdialog Kopfzeile,
   Datenbeginn sowie X- und Y-Spalten prüfen und „Importieren“ klicken.
2. **Datensätze** erscheinen links. Das Auge blendet ein und aus, ein Klick auf den Farbpunkt ändert
   die Farbe. Mehrere Datensätze auswählen mit Strg- oder Umschalt-Klick.
3. **Einstellungen** stehen rechts in den Tabs. Der Plot aktualisiert sich bei jeder Änderung.
   - *Datensatz:* Legende, Farbe, Y-Achse, Linie, Marker, Kurvenanpassung
   - *Achsen:* Beschriftung, Einheit mit Präfix (z. B. mV), Grenzen, Tick-Abstand, logarithmisch,
     zweite Y-Achse
   - *Darstellung:* Titel, Schriftgrößen, Legende, Fehlermaß für Messwiederholungen
   - *Export:* Größe in cm, Auflösung, Optionen für Vektorgrafiken
4. **Exportieren** speichert den Plot als PDF, SVG, EPS, PNG, JPEG, TIFF oder WebP.
   **Kopieren** legt ihn in die Zwischenablage, zum Einfügen in Word oder PowerPoint mit Strg+V.
5. **Projekt speichern** sichert Dateien und alle Einstellungen in einer `.gplot`-Datei.

**Vorlagen** (oben in der Werkzeugleiste) setzen Schriftgrößen und Exportgröße passend für
Bildschirm, Paper (einspaltig/zweispaltig), Abschlussarbeit oder Präsentation. Die **Seitenansicht**
(Blatt-Symbol über dem Plot) zeigt den Plot in Exportgröße.

### Weitere Funktionen

- **Zoomen und Ausschnitt exportieren:** Mit Lupe oder Verschieben-Werkzeug zoomen, dann über den Pfeil
  an „Exportieren“ bzw. „Kopieren“ nur den Ausschnitt ausgeben. Das Zuschneiden-Symbol übernimmt den
  Ausschnitt dauerhaft in die Achsengrenzen.
- **Messen:** Fadenkreuz-Symbol wählen und Messpunkte anklicken. Zwei Punkte ergeben Δx und Δy;
  Esc löscht die Messung.
- **Messwiederholungen:**
  - Stehen die Wiederholungen als Spalten in einer Datei: beim Laden „Y-Spalten als
    Messwiederholungen zusammenfassen“ ankreuzen.
  - Liegt eine Datei je Messung vor: die Datensätze links auswählen und „Zusammenfassen“ wählen
    (Symbol oben in der Datenliste oder Rechtsklick).

  Angezeigt wird der Mittelwert mit Standardabweichung, Standardfehler oder 95-%-Konfidenzintervall.
- **Kurvenanpassung:** linear, Polynom 2./3. Grades, exponentiell; Gleichung und R² stehen in der Legende.

### Tastenkürzel

| Kürzel | Funktion |
|---|---|
| Strg+O | Dateien laden |
| Strg+Umschalt+O | Projekt öffnen |
| Strg+S | Projekt speichern |
| Strg+E | Exportieren |
| Strg+Umschalt+E | Ausschnitt exportieren |
| Strg+Umschalt+C | Plot kopieren |
| Entf, Strg+↑/↓ | Datensatz entfernen / verschieben (in der Datenliste) |

## Unterstützte Dateien

| Art | Endungen | Hinweise |
|---|---|---|
| Text | `.csv` `.txt` `.tsv` `.dat` `.asc` `.prn` | Trennzeichen Semikolon, Tab, Komma oder Leerzeichen; Kodierung UTF-8, UTF-16 oder Windows-1252 |
| Tabellen | `.xlsx` `.xlsm` `.xls` `.xlsb` `.ods` | Tabellenblatt im Importdialog wählbar |

- **Zahlen:** Dezimalkomma oder Dezimalpunkt, Tausendertrenner („1.000,5“), E-Notation („1,5E-3“).
  Zellen mit Einheiten („12,5 V“) werden als fehlender Wert behandelt.
- **Datum und Uhrzeit** als X-Werte, z. B. „16.11.2026 12:00:01,5“, „2026-11-16T12:00:01“ oder
  „12:00:01“. Sie werden als Sekunden ab dem ersten Wert dargestellt; ein Sprung über Mitternacht
  wird erkannt.
- **Aufbau:** Eine X-Spalte und beliebig viele Y-Spalten. Zeilen mit Geräteangaben vor der Tabelle
  werden automatisch übersprungen.

### Grenzen

- Für unterschiedliche X-Spalten je Messreihe (z. B. X1, Y1, X2, Y2) die Datei mehrfach laden und
  jeweils andere Spalten wählen.
- Mehrere Tabellen untereinander in einer Datei werden zu einer Reihe zusammengefasst.
- Die Excel-Formeln einer Datei liefern nur Werte, wenn die Datei zuletzt in Excel gespeichert wurde.
- Alle Daten liegen im Arbeitsspeicher. 1 Mio. Zeilen laden in etwa 1 s und brauchen rund 220 MB.
  Das Neuzeichnen von mehreren Millionen Punkten dauert jeweils 1–2 s.

## Probleme melden

Bei einem unerwarteten Fehler zeigt das Programm eine Meldung und schreibt Details in
`%APPDATA%\GraphPlotter\graphplotter.log`. Diese Datei hilft bei der Fehlersuche.

## Lizenz

Graph Plotter steht unter der [MIT-Lizenz](LICENSE): Nutzung, Weitergabe und Änderung sind frei,
solange der Lizenzhinweis erhalten bleibt; es gibt keine Gewährleistung. Die mitgelieferten
Bibliotheken haben eigene Lizenzen (Ordner `Lizenzen` im Programmordner).

---

## Für Entwickler

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python Plotter.py          # starten
.venv\Scripts\python -m pytest           # Tests
.venv\Scripts\python build_exe.py        # Programmordner, ZIP und (mit Inno Setup 6) Installer
```

Aufbau, Messungen und Entwicklungsstand: siehe `ANALYSE_UND_PLAN.md`.
