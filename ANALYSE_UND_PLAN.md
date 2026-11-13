# Graph Plotter – Analyse und Verbesserungsplan

Stand: 13.11.2026, Basis: v1.8 (Commit `6f911a1`), aktueller Stand: v3.0

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
| B14 | Warnung beim doppelten Laden einer Datei | ✅ (v3.0, Hinweis) |
| – | CSV mit Semikolon/Tab, Dezimalkomma, Windows-Kodierung (cp1252) | ✅ |

### C. Bedienung

| # | Vorschlag | Status |
|---|-----------|--------|
| C15 | Einstellungsbereich scrollbar (kleine Bildschirme) | ✅ |
| C16 | Einstellungen zwischen Programmstarts merken (`QSettings`) | ✅ teilweise (v3.0: Fenster, Farbschema, letzter Ordner, zuletzt geöffnet, Importdialog; Plot-Einstellungen über Projektdatei) |
| C17 | Projektdatei (JSON) mit Dateien und allen Plot-Einstellungen | ✅ |
| C18 | Datensätze ein-/ausblenden, Reihenfolge ändern, „Alle entfernen“, Mehrfachauswahl | ✅ |
| C19 | Automatisches Neuzeichnen bei Änderungen | ✅ (v3.0, Live-Vorschau) |
| C20 | Messwert-Cursor (X/Y am Mauszeiger, ΔX/ΔY) | ✅ (v3.0) |
| C21 | High-DPI-Unterstützung | ✅ |

### D. Darstellung

| # | Vorschlag | Status |
|---|-----------|--------|
| D22 | Linie/Marker/beides, Linienstil, -breite, Markertyp je Datensatz | ✅ |
| D23 | Logarithmische Achsen (X, Y, Y2) | ✅ |
| D24 | Titel, Raster an/aus, Nebenticks, Legende außerhalb | ✅ |
| D25 | Statistik als Fehlerbalken oder Band | ✅ |
| D26 | Farbenblind-taugliche Standardpalette (`tab10`) | ✅ |
| D27 | Legendenfehler bei Y2 + Toolbar-Bearbeitung beheben statt nur warnen | ✅ (v3.0: fehleranfälliger Toolbar-Dialog entfällt, alles über die Eigenschaften-Tabs) |

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

4. **Schritt 4 – Vektorexport (v2.1):** siehe Abschnitt 7. ✅
5. **Schritt 5 – Neue Oberfläche (v3.0):** siehe Abschnitt 8. ✅

Noch offen: E29–E31, F34 (Icon), F35, Plot-Einstellungen ohne Projektdatei merken (Rest von C16),
Dezimalkomma in den Achsenbeschriftungen des Plots, Drag & Drop zum Umsortieren der Datenliste.

---

## 5. Projektstruktur (v3.0)

```
Plotter.py                 Startpunkt (wird auch von build_exe.py verwendet)
graph_plotter/
  __init__.py              VERSION
  app.py                   Programmstart, Fehlerdialog, Logdatei
  numparse.py              Zahlen-Parser (deutsch/englisch, E-Notation)
  loaders.py               CSV/Excel einlesen, Kopfzeilen-Erkennung
  model.py                 ImportSpec und Datensatz (Daten + Darstellungsoptionen)
  stats.py                 Mittelwert, SD/SEM/95-%-KI
  fitting.py               Kurvenanpassung
  reduction.py             Datenreduktion für den Export (Min/Max, Marker ausdünnen)
  plotting.py              Zeichnen und alle Plot-/Export-Einstellungen (ohne Qt, testbar)
  exporting.py             Export in Dateien und Bytes (Zwischenablage)
  presets.py               Vorlagen (Bildschirm, Paper, Abschlussarbeit, Präsentation)
  project.py               Projektdatei speichern/laden
  ui/                      Oberfläche (PySide6)
    main_window.py         Hauptfenster, Live-Vorschau, Laden/Speichern/Export
    dataset_list.py        Datenliste links (Modell + gezeichnete Zeilen)
    panels.py              Tabs rechts: Datensatz, Achsen, Darstellung, Export
    plot_view.py           Plot, Navigation, Seitenansicht, Messfunktion
    import_dialog.py       Importdialog mit Vorschau
    widgets.py             Eingabefelder, Farbknopf, einklappbare Abschnitte
    theme.py, icons.py     Farbschema (hell/dunkel) und Symbole
tests/                     pytest-Tests (Kern, Export, Oberfläche)
requirements.txt           Laufzeit-Abhängigkeiten
requirements-dev.txt       Zusätzlich für Tests und Build
```

Tests ausführen: `.venv\Scripts\python -m pytest` (74 Tests, Oberflächentests laufen ohne Fenster)
Abhängigkeiten installieren: `.venv\Scripts\python -m pip install -r requirements-dev.txt`
`.exe` bauen: `.venv\Scripts\python build_exe.py` → `dist\GraphPlotter_v30.exe`

---

## 6. Bedienung in v2.0 (durch v3.0 teilweise ersetzt, siehe Abschnitt 8)

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

---

## 7. Vektorexport (v2.1)

### Ursache der unbrauchbaren Vektorgrafiken

In SVG und PDF wird **jeder Marker und jeder Fehlerbalken als eigenes Objekt** gespeichert. Linien
vereinfacht Matplotlib selbst, Marker nicht. Bei 3 × 200.000 Messpunkten entstanden so 600.000 Kreise
(bzw. 1,8 Mio. Fehlerbalken-Teile), an denen Word, Inkscape und PDF-Viewer scheitern.

### Lösung

| Maßnahme | Wirkung |
|----------|---------|
| Min/Max-Reduktion je Pixelspalte (M4-Verfahren) | Linien und Fehlerbänder: optisch identisch, Spitzen und Ausreißer bleiben erhalten |
| Linie + Marker: Marker/Fehlerbalken nur an jedem n-ten Punkt (Standard max. 250 je Datensatz) | Marker dienen der Erkennbarkeit; die Linie zeigt weiterhin alle Daten |
| Nur Marker: deckungsgleiche Marker zusammenfassen (Raster = halber Markerdurchmesser) | Punktwolken sehen gleich aus, bestehen aber aus wenigen tausend Objekten |
| Text als echte Schrift (SVG: `<text>`, PDF: eingebettetes TrueType) in Arial | Beschriftungen in Inkscape/Illustrator/PowerPoint bearbeitbar; abschaltbar („Text als Pfade“) |
| Neues Format EPS | für LaTeX und ältere Programme |

Die Bildschirmansicht bleibt unreduziert, damit beim Zoomen alle Punkte sichtbar sind. Nach dem Export
zeigt eine Meldung Dateigröße und was reduziert wurde.

### Messung (3 Messreihen à 200.000 Punkte, 16 × 10 cm, 300 dpi)

| Fall | Format | vorher | nachher |
|------|--------|-------:|--------:|
| Linie + Marker | SVG | 89,2 MB | 0,50 MB |
| Linie + Marker | PDF | 4,8 MB | 0,18 MB |
| Nur Marker | SVG | 88,4 MB | 1,38 MB |
| Nur Linie | SVG | 0,77 MB | 0,39 MB |
| Statistik mit Fehlerbalken | SVG | 393,6 MB | 0,89 MB |
| Statistik mit Fehlerbalken | PDF | 23,4 MB | 0,22 MB |

Export-Dauer jeweils unter 0,5 s.

---

## 8. Neue Oberfläche (v3.0)

Technische Basis ist jetzt **Qt 6 über PySide6** statt PyQt5. Gründe: bessere Unterstützung für
hochauflösende Bildschirme und den Windows-Dunkelmodus, und die LGPL-Lizenz ist bei der Weitergabe der
`.exe` unkomplizierter als die GPL von PyQt5. Die `.exe` ist zudem kleiner (74 statt 92 MB).

### Aufbau

```
┌ Öffnen ▾ │ Speichern ▾ │ Exportieren │ Kopieren │ Vorlage [Paper ▾]          Farbschema ▾ ┐
├ DATEN  + − ˄ ˅ ┬ ⌂ ‹ › ✥ 🔍 ⌖ │ ▯          Export: 16 × 10 cm ┬ Datensatz│Achsen│Darstellung│Export ┤
│ 👁 ● Kanal 1    │                                            │ einklappbare Abschnitte         │
│ 👁 ● Kanal 2    │               Plot (live)                  │                                 │
├────────────────┴────────────────────────────────────────────┴─────────────────────────────────┤
│ 3 von 3 Datensätzen · 1.200 Punkte      ⚠ Hinweise                    x = 1,25  y = 0,93       │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Was neu ist

- **Live-Vorschau:** Jede Änderung zeichnet nach 0,25 s neu, der Button „Plot erstellen“ entfällt.
  Hinweise (z. B. ignorierte Grenzen) erscheinen in der Statusleiste statt als Dialog.
- **Datenliste links:** Auge-Symbol zum Ein-/Ausblenden, Klick auf den Farbpunkt ändert die Farbe,
  Infozeile mit Punktzahl, Wiederholungen, Y2 und Fit. Entf entfernt, Strg+↑/↓ verschiebt.
- **Eigenschaften rechts in Tabs:** Datensatz, Achsen, Darstellung und Export, mit einklappbaren
  Abschnitten. Änderungen im Tab „Datensatz“ gelten für **alle ausgewählten** Datensätze.
- **Vorlagen** in der Werkzeugleiste: Bildschirm, Paper einspaltig (8,5 cm) und zweispaltig (17 cm),
  Abschlussarbeit (15 cm), Präsentation 16:9. Sie setzen Schriftgrößen und Exportgröße.
  Neue Standardschrift: 14/12/12 pt statt 30/24/30 pt.
- **Seitenansicht** (Blatt-Symbol über dem Plot): zeigt den Plot in Exportgröße, also mit den echten
  Größenverhältnissen von Schrift und Linien.
- **Export ohne Zwischendialog:** Größe, Auflösung und Vektor-Optionen stehen im Tab „Export“ und werden
  im Projekt gespeichert.
- **Kopieren** (Strg+Umschalt+C): legt den Plot als PNG und SVG in die Zwischenablage, zum direkten
  Einfügen in Word oder PowerPoint.
- **Messen:** Fadenkreuz-Symbol, dann Messpunkte anklicken. Zwei Punkte ergeben Δx und Δy; Esc löscht.
  Die Koordinaten unter dem Mauszeiger stehen immer rechts in der Statusleiste.
- **Farbschema** hell, dunkel oder wie Windows; der Plot selbst bleibt wie im Export weiß.
- **Gemerkt werden:** Fenstergröße und Aufteilung, Farbschema, letzter Ordner, zuletzt geöffnete Dateien
  und Projekte (Menü am „Öffnen“-Knopf), Importdialog an/aus.
- **Projekt speichern** merkt sich den Dateinamen (Strg+S speichert direkt, „Speichern unter…“ im Menü).
- Der Bearbeitungsdialog der Matplotlib-Toolbar ist entfallen und damit auch der Legendenfehler bei Y2 (D27).

### Tastenkürzel

| Kürzel | Funktion |
|--------|----------|
| Strg+O | Dateien laden |
| Strg+Umschalt+O | Projekt öffnen |
| Strg+S / Strg+Umschalt+S | Projekt speichern / speichern unter |
| Strg+E | Exportieren |
| Strg+Umschalt+C | Plot kopieren |
| Entf, Strg+↑/↓ | Datensatz entfernen / verschieben (in der Datenliste) |
| Esc | Messung löschen (im Plot) |

### Bekannte Einschränkungen

- Beim Ändern einer Einstellung wird neu gezeichnet; ein vorher eingestellter Zoom wird dabei
  zurückgesetzt.
- Die Datenliste lässt sich (noch) nicht per Drag & Drop umsortieren, sondern über ˄/˅ bzw. Strg+↑/↓.
- Zahlen im Plot (Achsen, Fit-Gleichung) verwenden den Dezimalpunkt.
- Die automatische Kopfzeilen-Erkennung verlangt zwei aufeinanderfolgende Zahlenzeilen; steht direkt
  nach der ersten Messzeile eine fehlerhafte Zeile, den Datenbeginn im Importdialog korrigieren.
- Zahlen mit genau einem Trennzeichen gelten als Dezimalzahl: „1.000“ wird als 1,0 gelesen, nicht als 1000.
