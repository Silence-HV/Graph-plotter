# Graph Plotter – Analyse und Verbesserungsplan

Stand: 13.11.2026, Basis: v1.8 (Commit `6f911a1`)

Dieses Dokument fasst die Code-Analyse des Graph Plotters zusammen, listet die gefundenen Fehler und
alle Verbesserungsvorschläge auf und hält fest, welche davon umgesetzt sind.

Legende Status: ✅ umgesetzt · ⏳ offen

---

## 1. Ausgangslage (v1.8)

- PyQt5-Desktop-Anwendung mit Matplotlib-Backend, gesamter Code in einer Datei `Plotter.py` (~1430 Zeilen, eine Klasse).
- Import von CSV (Komma-getrennt, UTF-8) und Excel (`openpyxl`, deutsche Zahlenformatierung).
- Spalte 1 = X-Werte, jede weitere Spalte = eigener Datensatz; im Statistik-Modus werden alle Y-Spalten
  zu Mittelwert ± Standardabweichung zusammengefasst.
- Funktionen: SI-Präfix-Skalierung, Achsengrenzen, Tick-Abstände, Schriftgrößen, eigene Legenden-Labels
  und Farben, sekundäre Y-Achse, Export (PNG, PDF, JPG, SVG, SVGZ, TIFF, WebP).
- Build einer einzelnen `.exe` per PyInstaller (`build_exe.py`).

---

## 2. Gefundene Fehler

| # | Fehler | Auswirkung | Status |
|---|--------|------------|--------|
| F1 | `.xls` wird im Dialog und per Drag & Drop angeboten, `openpyxl` kann aber nur `.xlsx` lesen | Fehlermeldung beim Laden | ✅ `xlrd` für `.xls` |
| F2 | NaN-Mittelwerte (Zeilen ohne gültige Y-Werte) fließen in die Achsengrenzen ein | Falsche Grenzen oder Abbruch bei `set_ylim` | ✅ |
| F3 | Automatische Y1-Grenze berücksichtigt auch Datensätze der Y2-Achse | Y1-Kurven werden gestaucht | ✅ Autoskalierung je Achse |
| F4 | Beim Entfernen eines Datensatzes werden eigene Farben nicht neu zugeordnet | Farben springen auf falsche Graphen | ✅ Farbe gehört zum Datensatz |
| F5 | Eigene Legenden-Texte werden bei jedem Laden/Entfernen/Y2-Umschalten gelöscht | Eingaben gehen verloren | ✅ Label gehört zum Datensatz |
| F6 | Platzhalter „Auto: …“ zeigen unskalierte Werte, Eingaben werden aber skaliert interpretiert; CSV-Laden ignoriert die Std.-Abw. | Verwirrende Grenzen | ✅ Platzhalter zeigen die tatsächlichen Plot-Grenzen |
| F7 | Export ohne vorherigen Plot erzeugt ein leeres Bild | Leere Datei | ✅ |
| F8 | „PDF – Rasterisiert“ war tatsächlich Vektor; beim SVG wurden Fehlerbalken nicht gerastert | Falsche Beschriftung, große Dateien | ✅ |

### Fachliche und Bedien-Fehler

| # | Fehler | Status |
|---|--------|--------|
| A1 | Standardabweichung mit `ddof=0` (Population) statt `ddof=1` (Stichprobe) – unterschätzt die Streuung bei wenigen Wiederholungen | ✅ SD (ddof=1), SEM, 95-%-KI wählbar |
| A2 | Dezimalkomma in Eingabefeldern („0,5“) wird stillschweigend ignoriert | ✅ deutsche Zahlen erlaubt, ungültige Felder rot markiert |
| A3 | SI-Präfix fehlt in der Achsenbeschriftung (Werte in mV, Label zeigt „[V]“); X-Achse ohne Einheitenfeld | ✅ |
| A4 | Exportgröße hängt von der Fenstergröße ab | ✅ Exportgröße in cm und DPI wählbar |
| A5 | Sehr kleiner Tick-Abstand erzeugt Millionen Ticks (Programm hängt) | ✅ Prüfung mit Warnung |
| A6 | CSV ohne Kopfzeile: erste Messzeile wird als Header verschluckt | ✅ automatische Erkennung |
| A7 | Unsortierte X-Werte erzeugen Zickzack-Linien | ✅ Option „nach X sortieren“ |
| A8 | Unbehandelte Fehler verschwinden in der `.exe` (kein Konsolenfenster) | ✅ globaler Fehlerdialog + Logdatei |

---

## 3. Verbesserungsvorschläge

### B. Datenimport

| # | Vorschlag | Status |
|---|-----------|--------|
| B9 | Excel-Tabellenblatt wählen | ✅ (Importdialog) |
| B10 | Kopfzeilen/Metadaten überspringen | ✅ (Importdialog, automatisch erkannt) |
| B11 | Importdialog mit Vorschau, Wahl der X-Spalte und der Y-Spalten | ✅ |
| B12 | Datum/Uhrzeit als X-Werte | ✅ (als Sekunden ab erstem Wert) |
| B13 | Mehrere Dateien auf einmal öffnen, Drag & Drop auf das ganze Fenster | ✅ |
| B14 | Warnung beim doppelten Laden einer Datei | ⏳ |
| – | CSV mit Semikolon/Tab, Dezimalkomma, Windows-Kodierung (cp1252) | ✅ |

### C. Bedienung

| # | Vorschlag | Status |
|---|-----------|--------|
| C15 | Einstellungsbereich scrollbar (kleine Bildschirme) | ✅ |
| C16 | Einstellungen zwischen Programmstarts merken (`QSettings`) | ⏳ |
| C17 | Projektdatei (JSON) mit Dateien und allen Plot-Einstellungen | ✅ |
| C18 | Datensätze ein-/ausblenden, Reihenfolge ändern, „Alle entfernen“, Mehrfachauswahl | ✅ |
| C19 | Automatisches Neuzeichnen bei Änderungen | ⏳ |
| C20 | Messwert-Cursor (X/Y am Mauszeiger, ΔX/ΔY) | ⏳ |
| C21 | High-DPI-Unterstützung | ✅ |

### D. Darstellung

| # | Vorschlag | Status |
|---|-----------|--------|
| D22 | Linie/Marker/beides, Linienstil, -breite, Markertyp je Datensatz | ✅ |
| D23 | Logarithmische Achsen (X, Y, Y2) | ✅ |
| D24 | Titel, Raster an/aus, Nebenticks, Legende außerhalb | ✅ |
| D25 | Statistik als Fehlerbalken oder Band | ✅ |
| D26 | Farbenblind-taugliche Standardpalette (`tab10`) | ✅ |
| D27 | Legendenfehler bei Y2 + Toolbar-Bearbeitung beheben statt nur warnen | ⏳ |

### E. Auswertung

| # | Vorschlag | Status |
|---|-----------|--------|
| E28 | Kurvenanpassung (linear, Polynom 2/3, exponentiell) mit Gleichung und R² in der Legende | ✅ |
| E29 | Vorverarbeitung: Offset, Normierung, Glättung, Ableitung | ⏳ |
| E30 | Kennwerte je Datensatz (Min, Max, Mittelwert, Spitze-Spitze, Integral) | ⏳ |
| E31 | Export der (berechneten) Daten als CSV/Excel | ⏳ |

### F. Technik und Wartbarkeit

| # | Vorschlag | Status |
|---|-----------|--------|
| F32 | Aufteilung in Module (Laden, Statistik, Fit, Plotten, Oberfläche) | ✅ |
| F33 | Automatische Tests mit `pytest` | ✅ |
| F34 | `requirements.txt` mit Versionen, Icon und Versionsinfo für die `.exe` | ✅ requirements / ⏳ Icon |
| F35 | Aufräumen (`BACKUP/`, alte `.spec`-Dateien, ungenutzte Imports) | ⏳ (ungenutzte Imports ✅) |

---

## 4. Umsetzungsplan

1. **Schritt 1 – Korrektheit:** F1–F8 und A1–A8. ✅
2. **Schritt 2 – Grundlage:** Aufteilung in Module (F32) und Tests (F33). ✅
3. **Schritt 3 – Funktionen:** Importdialog (B9–B13), Projektdatei (C17), Darstellung pro Datensatz und
   Log-Achsen (D22–D26), Kurvenanpassung (E28). ✅

Offene Punkte für eine spätere Version: B14, C16, C19, C20, D27, E29–E31, F34 (Icon), F35.

---

## 5. Neue Projektstruktur (v2.0)

```
Plotter.py                 Startpunkt (wird auch von build_exe.py verwendet)
graph_plotter/
  __init__.py              VERSION
  numparse.py              Zahlen-Parser (deutsch/englisch, E-Notation)
  loaders.py               CSV/Excel einlesen, Kopfzeilen-Erkennung, ImportSpec
  model.py                 Datensatz (Daten + Darstellungsoptionen)
  stats.py                 Mittelwert, SD/SEM/95-%-KI
  fitting.py               Kurvenanpassung
  plotting.py              Zeichnen (ohne Qt, testbar)
  project.py               Projektdatei speichern/laden
  ui/                      Hauptfenster, Importdialog, Stil- und Exportdialog
tests/                     pytest-Tests
requirements.txt           Laufzeit-Abhängigkeiten
requirements-dev.txt       Zusätzlich für Tests und Build
```

Tests ausführen: `.venv\Scripts\python -m pytest` (46 Tests, inkl. Oberflächen-Rauchtests ohne Fenster)
Abhängigkeiten installieren: `.venv\Scripts\python -m pip install -r requirements-dev.txt`
`.exe` bauen: `.venv\Scripts\python build_exe.py` → `dist\GraphPlotter_v20.exe`

---

## 6. Bedienung in v2.0 – was sich geändert hat

- **Ein Button „Dateien laden…“** für CSV/Text und Excel (Mehrfachauswahl). Drag & Drop funktioniert im
  ganzen Fenster, auch für Projektdateien (`.gplot`). Dateien können auch per „Öffnen mit“ bzw. als
  Kommandozeilenargument übergeben werden.
- **Importdialog:** Tabellenblatt, Kopfzeile, Datenbeginn, X-Spalte, Y-Spalten, Statistik-Modus und
  Sortierung; Vorschau der ersten 60 Zeilen. Abschaltbar über „Importdialog mit Vorschau anzeigen“ –
  dann wird automatisch erkannt (Spalte 1 = X).
- **Datensatz-Tabelle** ersetzt Dateiliste und Legendenfelder: Sichtbarkeit, Farbe, Legendentext, Achse
  (Y1/Y2) und über „…“ Linie, Marker und Kurvenanpassung. Auswahl über die Zeilennummer (G1, G2, …),
  Entf-Taste entfernt die Auswahl.
- **Statistik-Modus:** Das Fehlermaß (SD/SEM/95 %-KI) und die Darstellung (Fehlerbalken/Band) lassen sich
  nachträglich umschalten, ohne neu zu laden.
- **Eingabefelder** akzeptieren „0,5“ und „0.5“; ungültige Eingaben werden rot markiert und verhindern
  den Plot mit einer Meldung. Die Platzhalter zeigen nach dem Plotten die tatsächlich verwendeten Grenzen.
- **Export:** Nach der Dateiauswahl folgt ein Dialog für Größe (cm), Auflösung und – bei PDF/SVG –
  das Rastern der Datenlinien (voreingestellt ab 5000 Punkten).
- **Tastenkürzel:** Strg+O laden, Strg+R plotten, Strg+E exportieren, Strg+S Projekt speichern.
- **Unerwartete Fehler** werden angezeigt und protokolliert in `%APPDATA%\GraphPlotter\graphplotter.log`.

### Bekannte Einschränkungen

- Die Kurvenbearbeitung über die Matplotlib-Toolbar baut die Legende bei aktiver Y2-Achse ohne die
  Y2-Einträge neu auf (D27). Danach einfach erneut „Plot erstellen“.
- Einstellungen werden nur über Projektdateien gespeichert, nicht automatisch zwischen Programmstarts (C16).
- Die automatische Kopfzeilen-Erkennung verlangt zwei aufeinanderfolgende Zahlenzeilen; steht direkt
  nach der ersten Messzeile eine fehlerhafte Zeile, den Datenbeginn im Importdialog korrigieren.
- Zahlen mit genau einem Trennzeichen gelten als Dezimalzahl: „1.000“ wird als 1,0 gelesen, nicht als 1000.
