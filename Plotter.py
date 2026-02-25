import sys
import csv
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QSpinBox, QDoubleSpinBox,
    QCheckBox, QMessageBox, QGroupBox, QComboBox, QListWidget, QListWidgetItem,
    QScrollArea
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QMimeData
import matplotlib

# Versionsnummer
VERSION = "1.3"
matplotlib.use('Qt5Agg')  # Stelle sicher, dass Qt5 Backend verwendet wird
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import numpy as np


class DropableFileList(QListWidget):
    """QListWidget mit Drag & Drop Unterstützung für CSV-Dateien"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.parent_window = None
    
    def dragEnterEvent(self, event):
        """Wird aufgerufen, wenn etwas über das Widget gezogen wird"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Wird aufgerufen, wenn etwas über das Widget bewegt wird"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """Wird aufgerufen, wenn etwas auf das Widget gedroppt wird"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
            # Extrahiere Dateipfade
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                # Nur CSV-Dateien laden
                if file_path.lower().endswith('.csv'):
                    if self.parent_window:
                        self.parent_window.load_file(file_path)
        else:
            event.ignore()


class GraphPlotter(QMainWindow):
    # SI-Präfixe und ihre Faktoren
    SI_PREFIXES = {
        'p (pico)': 1e-12,
        'n (nano)': 1e-9,
        'µ (micro)': 1e-6,
        'm (milli)': 1e-3,
        '1': 1,
        'k (kilo)': 1e3,
        'M (mega)': 1e6,
        'G (giga)': 1e9
    }
    
    # Farben für mehrere Graphen
    COLORS = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Graph Plotter - CSV Visualisierung (v{VERSION})")
        self.setGeometry(100, 100, 1400, 800)
        
        # Mehrere Datensätze speichern
        self.datasets = []  # Liste mit {'path': ..., 'time': [...], 'values': [...], 'label': ...}
        self.file_path = None
        
        # Achsenzuordnungen für Datensätze (Index -> 'y1' oder 'y2')
        self.axis_assignments = {}
        
        # UI erstellen
        self.init_ui()
        
    def init_ui(self):
        """Erstelle die grafische Oberfläche"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QHBoxLayout()
        
        # Linke Seite - Kontrollpanel
        left_panel = self.create_control_panel()
        main_layout.addWidget(left_panel)
        
        # Rechte Seite - Plot
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        main_layout.addWidget(self.canvas, 1)
        
        main_widget.setLayout(main_layout)
        
    def create_control_panel(self):
        """Erstelle das Kontrollpanel auf der linken Seite"""
        group = QGroupBox("Einstellungen")
        layout = QVBoxLayout()
        
        # Statistik-Modus
        self.statistics_mode = QCheckBox("Statistik-Modus (Mittelwert + Std.Abw.)")
        self.statistics_mode.setToolTip(
            "Wenn aktiviert, werden mehrere Y-Spalten einer CSV-Datei\n"
            "als Messwiederholungen interpretiert. Es werden Mittelwert\n"
            "und Standardabweichung berechnet und dargestellt."
        )
        layout.addWidget(self.statistics_mode)
        
        # Datei laden
        layout.addWidget(QLabel("CSV-Dateien:"))
        file_layout = QHBoxLayout()
        self.file_button = QPushButton("CSV Datei laden")
        self.file_button.clicked.connect(lambda: self.load_file())
        file_layout.addWidget(self.file_button)
        layout.addLayout(file_layout)
        
        # Liste geladener Dateien
        self.file_list = DropableFileList()
        self.file_list.setMaximumHeight(100)
        self.file_list.parent_window = self
        layout.addWidget(self.file_list)
        
        # Button zum Entfernen
        remove_button = QPushButton("Datei entfernen")
        remove_button.clicked.connect(self.remove_file)
        layout.addWidget(remove_button)
        
        # Legende - Benutzerdefinierte Labels
        layout.addWidget(QLabel("Legende (optional):"))
        self.legend_scroll = QScrollArea()
        self.legend_scroll.setWidgetResizable(True)
        self.legend_scroll.setMaximumHeight(120)
        self.legend_scroll_widget = QWidget()
        self.legend_layout = QVBoxLayout(self.legend_scroll_widget)
        self.legend_layout.setContentsMargins(5, 5, 5, 5)
        self.legend_scroll.setWidget(self.legend_scroll_widget)
        layout.addWidget(self.legend_scroll)
        
        # Dictionary zum Speichern der Custom-Labels
        self.custom_labels = {}  # {index: QLineEdit}
        
        # X-Achsen Grenzen
        layout.addWidget(QLabel("X-Achse (Zeit):"))
        
        x_min_layout = QHBoxLayout()
        x_min_layout.addWidget(QLabel("Min:"))
        self.x_min_input = QLineEdit()
        self.x_min_input.setPlaceholderText("Auto")
        x_min_layout.addWidget(self.x_min_input)
        layout.addLayout(x_min_layout)
        
        x_max_layout = QHBoxLayout()
        x_max_layout.addWidget(QLabel("Max:"))
        self.x_max_input = QLineEdit()
        self.x_max_input.setPlaceholderText("Auto")
        x_max_layout.addWidget(self.x_max_input)
        layout.addLayout(x_max_layout)
        
        # Y-Achsen Grenzen
        layout.addWidget(QLabel("Y-Achse:"))
        
        y_min_layout = QHBoxLayout()
        y_min_layout.addWidget(QLabel("Min:"))
        self.y_min_input = QLineEdit()
        self.y_min_input.setPlaceholderText("Auto")
        y_min_layout.addWidget(self.y_min_input)
        layout.addLayout(y_min_layout)
        
        y_max_layout = QHBoxLayout()
        y_max_layout.addWidget(QLabel("Max:"))
        self.y_max_input = QLineEdit()
        self.y_max_input.setPlaceholderText("Auto")
        y_max_layout.addWidget(self.y_max_input)
        layout.addLayout(y_max_layout)
        
        # X-Achsen Label und Skalierung
        layout.addWidget(QLabel("X-Achsen Label:"))
        self.x_label_input = QLineEdit()
        self.x_label_input.setPlaceholderText("z.B. Zeit")
        layout.addWidget(self.x_label_input)
        
        x_scale_layout = QHBoxLayout()
        x_scale_layout.addWidget(QLabel("Skalierung:"))
        self.x_scale_combo = QComboBox()
        self.x_scale_combo.addItems(list(self.SI_PREFIXES.keys()))
        self.x_scale_combo.setCurrentText('1')
        x_scale_layout.addWidget(self.x_scale_combo)
        layout.addLayout(x_scale_layout)
        
        # Y-Achsen Label und Einheit
        layout.addWidget(QLabel("Y-Achsen Label:"))
        self.y_label_input = QLineEdit()
        self.y_label_input.setPlaceholderText("z.B. Amplitude")
        layout.addWidget(self.y_label_input)
        
        layout.addWidget(QLabel("Y-Achsen Einheit:"))
        self.y_unit_input = QLineEdit()
        self.y_unit_input.setPlaceholderText("z.B. mV, m/s²")
        layout.addWidget(self.y_unit_input)
        
        # Skalierungsfaktor Y-Achse
        y_scale_layout = QHBoxLayout()
        y_scale_layout.addWidget(QLabel("Skalierung:"))
        self.y_scale_combo = QComboBox()
        self.y_scale_combo.addItems(list(self.SI_PREFIXES.keys()))
        self.y_scale_combo.setCurrentText('1')
        y_scale_layout.addWidget(self.y_scale_combo)
        layout.addLayout(y_scale_layout)
        
        # Y-Tick für primäre Achse
        y_tick_layout = QHBoxLayout()
        y_tick_layout.addWidget(QLabel("Y-Tick Abstand:"))
        self.y_tick_input = QLineEdit()
        self.y_tick_input.setPlaceholderText("Auto")
        y_tick_layout.addWidget(self.y_tick_input)
        layout.addLayout(y_tick_layout)
        
        # === Sekundäre Y-Achse (Y2) ===
        self.y2_enabled = QCheckBox("Sekundäre Y-Achse (Y2) aktivieren")
        self.y2_enabled.setToolTip("Aktiviert eine zweite Y-Achse auf der rechten Seite.")
        self.y2_enabled.stateChanged.connect(self.toggle_y2_settings)
        layout.addWidget(self.y2_enabled)
        
        # Y2-Achsen Einstellungen (anfangs versteckt)
        self.y2_group = QGroupBox("Y2-Achse Einstellungen")
        y2_layout = QVBoxLayout()
        
        # Y2 Min/Max
        y2_min_layout = QHBoxLayout()
        y2_min_layout.addWidget(QLabel("Y2 Min:"))
        self.y2_min_input = QLineEdit()
        self.y2_min_input.setPlaceholderText("Auto")
        y2_min_layout.addWidget(self.y2_min_input)
        y2_layout.addLayout(y2_min_layout)
        
        y2_max_layout = QHBoxLayout()
        y2_max_layout.addWidget(QLabel("Y2 Max:"))
        self.y2_max_input = QLineEdit()
        self.y2_max_input.setPlaceholderText("Auto")
        y2_max_layout.addWidget(self.y2_max_input)
        y2_layout.addLayout(y2_max_layout)
        
        # Y2 Label und Einheit
        y2_layout.addWidget(QLabel("Y2-Achsen Label:"))
        self.y2_label_input = QLineEdit()
        self.y2_label_input.setPlaceholderText("z.B. Temperatur")
        y2_layout.addWidget(self.y2_label_input)
        
        y2_layout.addWidget(QLabel("Y2-Achsen Einheit:"))
        self.y2_unit_input = QLineEdit()
        self.y2_unit_input.setPlaceholderText("z.B. °C, K")
        y2_layout.addWidget(self.y2_unit_input)
        
        # Y2 Skalierung
        y2_scale_layout = QHBoxLayout()
        y2_scale_layout.addWidget(QLabel("Y2 Skalierung:"))
        self.y2_scale_combo = QComboBox()
        self.y2_scale_combo.addItems(list(self.SI_PREFIXES.keys()))
        self.y2_scale_combo.setCurrentText('1')
        y2_scale_layout.addWidget(self.y2_scale_combo)
        y2_layout.addLayout(y2_scale_layout)
        
        # Y2 Tick
        y2_tick_layout = QHBoxLayout()
        y2_tick_layout.addWidget(QLabel("Y2-Tick Abstand:"))
        self.y2_tick_input = QLineEdit()
        self.y2_tick_input.setPlaceholderText("Auto")
        y2_tick_layout.addWidget(self.y2_tick_input)
        y2_layout.addLayout(y2_tick_layout)
        
        self.y2_group.setLayout(y2_layout)
        self.y2_group.setVisible(False)
        layout.addWidget(self.y2_group)
        
        # Tick-Rate Einstellungen
        layout.addWidget(QLabel("Tick-Rate (Markierungen):"))
        
        x_tick_layout = QHBoxLayout()
        x_tick_layout.addWidget(QLabel("X-Tick Abstand:"))
        self.x_tick_input = QLineEdit()
        self.x_tick_input.setPlaceholderText("Auto")
        x_tick_layout.addWidget(self.x_tick_input)
        layout.addLayout(x_tick_layout)
        
        # Schriftgröße Einstellungen
        layout.addWidget(QLabel("Schriftgrößen:"))
        
        label_size_layout = QHBoxLayout()
        label_size_layout.addWidget(QLabel("Achsen-Label (pt):"))
        self.label_size_input = QLineEdit()
        self.label_size_input.setText("12")
        self.label_size_input.setMaximumWidth(60)
        label_size_layout.addWidget(self.label_size_input)
        label_size_layout.addStretch()
        layout.addLayout(label_size_layout)
        
        tick_size_layout = QHBoxLayout()
        tick_size_layout.addWidget(QLabel("Achsen-Ticks (pt):"))
        self.tick_size_input = QLineEdit()
        self.tick_size_input.setText("10")
        self.tick_size_input.setMaximumWidth(60)
        tick_size_layout.addWidget(self.tick_size_input)
        tick_size_layout.addStretch()
        layout.addLayout(tick_size_layout)
        # Plot Button
        plot_button = QPushButton("Plot erstellen")
        plot_button.setFont(QFont("Arial", 12, QFont.Bold))
        plot_button.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        plot_button.clicked.connect(self.plot_data)
        layout.addWidget(plot_button)
        
        # Export Button
        export_button = QPushButton("Plot exportieren")
        export_button.setFont(QFont("Arial", 12, QFont.Bold))
        export_button.setStyleSheet("background-color: #2196F3; color: white; padding: 10px;")
        export_button.clicked.connect(self.export_plot)
        layout.addWidget(export_button)
        
        layout.addStretch()
        group.setLayout(layout)
        
        return group
    
    def load_file(self, file_path=None):
        """Lade eine CSV-Datei (mit mehreren Y-Spalten)
        
        Args:
            file_path: Optionaler Dateipfad. Wenn None, wird ein Dialog angezeigt.
        """
        # Wenn kein Dateipfad gegeben, Dialog öffnen
        if file_path is None:
            dialog = QFileDialog(self)
            dialog.setWindowTitle("CSV Datei laden")
            dialog.setFileMode(QFileDialog.ExistingFile)
            dialog.setDefaultSuffix("csv")
            dialog.setNameFilters(["CSV Dateien (*.csv)", "Alle Dateien (*)"])
            
            if dialog.exec_() == QFileDialog.Accepted:
                files = dialog.selectedFiles()
                if files and len(files) > 0:
                    file_path = files[0]
                else:
                    return
            else:
                return
        
        # Überprüfe, dass file_path gültig ist
        if not file_path:
            return
        
        # Prüfe ob Statistik-Modus aktiv ist
        if self.statistics_mode.isChecked():
            self.load_file_statistics(file_path)
            return
        
        try:
            time_data = []
            y_columns = {}  # {'Spaltenname': [Werte]}
            headers = []
            
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                # Lese Header-Zeile
                headers = next(reader)
                
                # Initialisiere Listen für alle Y-Spalten (ab Spalte 2)
                for i in range(1, len(headers)):
                    y_columns[headers[i]] = []
                
                # Lese Datenpunkte
                for row in reader:
                    if len(row) >= 2:
                        try:
                            time_val = float(row[0])
                            time_data.append(time_val)
                            
                            # Lese alle Y-Werte
                            for i in range(1, len(headers)):
                                if i < len(row):
                                    try:
                                        y_val = float(row[i])
                                        y_columns[headers[i]].append(y_val)
                                    except ValueError:
                                        y_columns[headers[i]].append(None)
                                else:
                                    y_columns[headers[i]].append(None)
                        except ValueError:
                            continue
            
            # Erstelle für jede Y-Spalte einen separaten Datensatz
            if time_data and y_columns:
                csv_name = Path(file_path).stem
                
                for col_name, y_values in y_columns.items():
                    # Filtere None-Werte heraus
                    valid_pairs = [(t, y) for t, y in zip(time_data, y_values) if y is not None]
                    
                    if valid_pairs:
                        valid_time = [pair[0] for pair in valid_pairs]
                        valid_values = [pair[1] for pair in valid_pairs]
                        
                        dataset = {
                            'path': file_path,
                            'time': valid_time,
                            'values': valid_values,
                            'label': f"{csv_name} - {col_name}"
                        }
                        self.datasets.append(dataset)
                        
                        # Zur Liste hinzufügen
                        self.file_list.addItem(QListWidgetItem(
                            f"{csv_name} - {col_name} ({len(valid_time)} Punkte)"
                        ))
                
                # Legendenfelder aktualisieren
                self.update_legend_fields()
                
                # Auto-Grenzen anzeigen
                all_time = []
                all_values = []
                for dataset in self.datasets:
                    all_time.extend(dataset['time'])
                    all_values.extend(dataset['values'])
                
                if all_time and all_values:
                    x_min, x_max = min(all_time), max(all_time)
                    y_min, y_max = min(all_values), max(all_values)
                    
                    self.x_min_input.setPlaceholderText(f"Auto: {x_min:.2f}")
                    self.x_max_input.setPlaceholderText(f"Auto: {x_max:.2f}")
                    self.y_min_input.setPlaceholderText(f"Auto: {y_min:.2f}")
                    self.y_max_input.setPlaceholderText(f"Auto: {y_max:.2f}")
            else:
                QMessageBox.warning(self, "Fehler", "Datei enthält keine gültigen Zahlendaten!")
                
        except FileNotFoundError:
            QMessageBox.critical(self, "Fehler", f"Datei nicht gefunden: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Laden", f"Fehler: {str(e)}")
    
    def remove_file(self):
        """Entferne die aktuell ausgewählte Datei"""
        current_row = self.file_list.currentRow()
        if current_row >= 0:
            self.file_list.takeItem(current_row)
            del self.datasets[current_row]
            # Achsenzuordnung entfernen
            if current_row in self.axis_assignments:
                del self.axis_assignments[current_row]
            # Achsenzuordnungen neu nummerieren
            new_assignments = {}
            for old_idx, axis in list(self.axis_assignments.items()):
                if old_idx > current_row:
                    new_assignments[old_idx - 1] = axis
                else:
                    new_assignments[old_idx] = axis
            self.axis_assignments = new_assignments
            # Legendenfelder aktualisieren
            self.update_legend_fields()
    
    def toggle_y2_settings(self, state):
        """Ein-/Ausblenden der sekundären Y-Achsen-Einstellungen"""
        self.y2_group.setVisible(state == Qt.Checked)
        # Legendenfelder aktualisieren um Achsenzuordnung anzuzeigen/verstecken
        self.update_legend_fields()
    
    def load_file_statistics(self, file_path):
        """Lade eine CSV-Datei im Statistik-Modus.
        
        Alle Y-Spalten werden als Messwiederholungen interpretiert.
        Es werden Mittelwert und Standardabweichung berechnet.
        
        Args:
            file_path: Pfad zur CSV-Datei
        """
        try:
            time_data = []
            y_columns = []  # Liste von Listen für alle Y-Spalten
            headers = []
            
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                # Lese Header-Zeile
                headers = next(reader)
                
                # Initialisiere Listen für alle Y-Spalten (ab Spalte 2)
                num_y_columns = len(headers) - 1
                y_columns = [[] for _ in range(num_y_columns)]
                
                # Lese Datenpunkte
                for row in reader:
                    if len(row) >= 2:
                        try:
                            time_val = float(row[0])
                            time_data.append(time_val)
                            
                            # Lese alle Y-Werte
                            for i in range(num_y_columns):
                                if i + 1 < len(row):
                                    try:
                                        y_val = float(row[i + 1])
                                        y_columns[i].append(y_val)
                                    except ValueError:
                                        y_columns[i].append(np.nan)
                                else:
                                    y_columns[i].append(np.nan)
                        except ValueError:
                            continue
            
            if time_data and y_columns:
                csv_name = Path(file_path).stem
                
                # Konvertiere zu numpy Arrays für statistische Berechnungen
                y_array = np.array(y_columns)  # Shape: (num_columns, num_points)
                
                # Berechne Mittelwert und Standardabweichung über alle Spalten
                mean_values = np.nanmean(y_array, axis=0)
                std_values = np.nanstd(y_array, axis=0)
                
                # Erstelle Datensatz mit Statistik
                dataset = {
                    'path': file_path,
                    'time': time_data,
                    'values': mean_values.tolist(),
                    'std': std_values.tolist(),
                    'label': f"{csv_name} (n={num_y_columns})",
                    'is_statistics': True
                }
                self.datasets.append(dataset)
                
                # Zur Liste hinzufügen
                self.file_list.addItem(QListWidgetItem(
                    f"{csv_name} (Statistik: {num_y_columns} Messungen, {len(time_data)} Punkte)"
                ))
                
                # Legendenfelder aktualisieren
                self.update_legend_fields()
                
                # Auto-Grenzen anzeigen
                self.update_auto_limits()
                
            else:
                QMessageBox.warning(self, "Fehler", "Datei enthält keine gültigen Zahlendaten!")
                
        except FileNotFoundError:
            QMessageBox.critical(self, "Fehler", f"Datei nicht gefunden: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Laden", f"Fehler: {str(e)}")
    
    def update_auto_limits(self):
        """Aktualisiere die Auto-Grenzen basierend auf allen geladenen Datensätzen"""
        if not self.datasets:
            return
        
        all_time = []
        all_values = []
        for dataset in self.datasets:
            all_time.extend(dataset['time'])
            all_values.extend(dataset['values'])
            # Bei Statistik-Daten auch die Standardabweichung berücksichtigen
            if dataset.get('is_statistics') and 'std' in dataset:
                values = np.array(dataset['values'])
                std = np.array(dataset['std'])
                all_values.extend((values - std).tolist())
                all_values.extend((values + std).tolist())
        
        if all_time and all_values:
            x_min, x_max = min(all_time), max(all_time)
            y_min, y_max = min(all_values), max(all_values)
            
            self.x_min_input.setPlaceholderText(f"Auto: {x_min:.2f}")
            self.x_max_input.setPlaceholderText(f"Auto: {x_max:.2f}")
            self.y_min_input.setPlaceholderText(f"Auto: {y_min:.2f}")
            self.y_max_input.setPlaceholderText(f"Auto: {y_max:.2f}")
    
    def update_legend_fields(self):
        """Aktualisiere die Legendeneingabefelder basierend auf geladenen Datensätzen"""
        # Alte Widgets entfernen
        while self.legend_layout.count() > 0:
            child = self.legend_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                # Auch verschachtelte Layouts löschen
                while child.layout().count() > 0:
                    subchild = child.layout().takeAt(0)
                    if subchild.widget():
                        subchild.widget().deleteLater()
        
        # Custom Labels zurücksetzen
        self.custom_labels = {}
        
        # Achsenzuordnung-Combos zurücksetzten
        self.axis_combos = {}
        
        # Neue Eingabefelder für jeden Datensatz erstellen
        for idx, dataset in enumerate(self.datasets):
            label_layout = QHBoxLayout()
            label_layout.setContentsMargins(0, 0, 0, 0)
            
            # Label mit Datensatznummer
            label = QLabel(f"G{idx + 1}:")
            label.setMaximumWidth(30)
            label_layout.addWidget(label)
            
            # Eingabefeld mit Platzhalter (Original-Label)
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(dataset['label'])
            self.custom_labels[idx] = line_edit
            label_layout.addWidget(line_edit)
            
            # Achsenzuordnung nur wenn Y2 aktiviert
            if self.y2_enabled.isChecked():
                axis_combo = QComboBox()
                axis_combo.addItems(['Y1', 'Y2'])
                axis_combo.setMaximumWidth(45)
                # Vorherige Auswahl wiederherstellen
                if idx in self.axis_assignments:
                    axis_combo.setCurrentText(self.axis_assignments[idx])
                else:
                    self.axis_assignments[idx] = 'Y1'
                axis_combo.currentTextChanged.connect(lambda text, i=idx: self.on_axis_changed(i, text))
                self.axis_combos[idx] = axis_combo
                label_layout.addWidget(axis_combo)
            
            self.legend_layout.addLayout(label_layout)
        
        # Stretch am Ende hinzufügen, um die Felder nach oben zu drücken
        self.legend_layout.addStretch()
    
    def on_axis_changed(self, idx, axis):
        """Speichere die Achsenzuordnung wenn geändert"""
        self.axis_assignments[idx] = axis
    
    def get_axis_limits(self):
        """Ermittle die Achsen-Grenzen (in der gewählten Skalierung)"""
        if not self.datasets:
            raise ValueError("Keine Daten geladen!")
        
        # Skalierungsfaktoren abrufen
        x_scale_factor = 1.0 / self.SI_PREFIXES[self.x_scale_combo.currentText()]
        y_scale_factor = 1.0 / self.SI_PREFIXES[self.y_scale_combo.currentText()]
        
        # Alle Daten sammeln um Auto-Grenzen zu berechnen
        all_time = []
        all_values = []
        for dataset in self.datasets:
            all_time.extend(dataset['time'])
            all_values.extend(dataset['values'])
            # Bei Statistik-Daten auch die Standardabweichung berücksichtigen
            if dataset.get('is_statistics') and 'std' in dataset:
                values = np.array(dataset['values'])
                std = np.array(dataset['std'])
                all_values.extend((values - std).tolist())
                all_values.extend((values + std).tolist())
        
        # Skalierte Grenzen der Rohdaten
        x_min_auto = min(all_time) * x_scale_factor
        x_max_auto = max(all_time) * x_scale_factor
        y_min_auto = min(all_values) * y_scale_factor
        y_max_auto = max(all_values) * y_scale_factor
        
        # X-Achse (Grenzen in der gewählten Skalierung)
        try:
            x_min = float(self.x_min_input.text()) if self.x_min_input.text() else None
        except ValueError:
            x_min = None
            
        try:
            x_max = float(self.x_max_input.text()) if self.x_max_input.text() else None
        except ValueError:
            x_max = None
        
        if x_min is None:
            x_min = x_min_auto
        if x_max is None:
            x_max = x_max_auto
        
        # Y-Achse (Grenzen in der gewählten Skalierung)
        try:
            y_min = float(self.y_min_input.text()) if self.y_min_input.text() else None
        except ValueError:
            y_min = None
            
        try:
            y_max = float(self.y_max_input.text()) if self.y_max_input.text() else None
        except ValueError:
            y_max = None
        
        if y_min is None:
            y_min = y_min_auto
        if y_max is None:
            y_max = y_max_auto
        
        return x_min, x_max, y_min, y_max
    
    def plot_data(self):
        """Erstelle den Plot mit mehreren Datensätzen"""
        try:
            if not self.datasets:
                QMessageBox.warning(self, "Fehler", "Bitte laden Sie zunächst eine CSV-Datei!")
                return
            
            x_min, x_max, y_min, y_max = self.get_axis_limits()
            
            # Skalierungsfaktoren abrufen (Kehrwert, da Konvertierung nach der Einheit)
            x_scale_factor = 1.0 / self.SI_PREFIXES[self.x_scale_combo.currentText()]
            y_scale_factor = 1.0 / self.SI_PREFIXES[self.y_scale_combo.currentText()]
            
            # Y2-Skalierungsfaktor und Grenzen
            y2_enabled = self.y2_enabled.isChecked()
            y2_scale_factor = 1.0 / self.SI_PREFIXES[self.y2_scale_combo.currentText()] if y2_enabled else 1.0
            
            # Plot erstellen
            self.fig.clear()
            ax = self.fig.add_subplot(111)
            ax2 = None
            
            # Zweite Y-Achse erstellen wenn aktiviert
            if y2_enabled:
                ax2 = ax.twinx()
            
            # Alle Datensätze zeichnen
            any_data_plotted = False
            lines_ax1 = []
            labels_ax1 = []
            lines_ax2 = []
            labels_ax2 = []
            
            # Transparenz basierend auf Anzahl der Graphen
            num_datasets = len(self.datasets)
            line_alpha = 0.7 if num_datasets > 1 else 1.0
            marker_alpha = line_alpha  # Gleiche Transparenz für Marker
            
            for idx, dataset in enumerate(self.datasets):
                # Bestimme welche Achse verwendet wird
                use_y2 = y2_enabled and self.axis_assignments.get(idx, 'Y1') == 'Y2'
                current_ax = ax2 if use_y2 else ax
                current_scale = y2_scale_factor if use_y2 else y_scale_factor
                
                # Skaliere die Daten
                scaled_time = np.array([t * x_scale_factor for t in dataset['time']])
                scaled_values = np.array([v * current_scale for v in dataset['values']])
                
                # Benutzerdefinierten Label verwenden, falls vorhanden
                custom_label = ""
                if idx in self.custom_labels:
                    custom_label = self.custom_labels[idx].text().strip()
                
                # Label: Custom oder Original
                label = custom_label if custom_label else dataset['label']
                
                # Farbe basierend auf Index
                color = self.COLORS[idx % len(self.COLORS)]
                
                # Prüfe ob Statistik-Datensatz (mit Standardabweichung)
                if dataset.get('is_statistics') and 'std' in dataset:
                    # Statistik-Modus: Zeichne Mittelwert mit Fehlerband
                    scaled_std = np.array([s * current_scale for s in dataset['std']])
                    
                    # Filter nach X-Grenzen (Y-Grenzen werden durch ylim gehandhabt)
                    mask = (scaled_time >= x_min) & (scaled_time <= x_max)
                    filtered_time = scaled_time[mask]
                    filtered_values = scaled_values[mask]
                    filtered_std = scaled_std[mask]
                    
                    if len(filtered_time) > 0:
                        # Fehlerband (Standardabweichung) zeichnen
                        current_ax.fill_between(filtered_time, 
                                        filtered_values - filtered_std,
                                        filtered_values + filtered_std, 
                                        alpha=0.3 * marker_alpha, color=color)
                        
                        # Mittelwert-Linie zeichnen
                        line, = current_ax.plot(filtered_time, filtered_values, color=color, 
                                linewidth=2, marker='', alpha=line_alpha)
                        
                        # Für Legende sammeln
                        if use_y2:
                            lines_ax2.append(line)
                            labels_ax2.append(f'{label} (Y2)')
                        else:
                            lines_ax1.append(line)
                            labels_ax1.append(f'{label} (Mittelwert)')
                        any_data_plotted = True
                else:
                    # Standard-Modus: Normale Darstellung
                    # Filtere Datenpunkte nach X-Grenzen
                    mask = (scaled_time >= x_min) & (scaled_time <= x_max)
                    filtered_time = scaled_time[mask]
                    filtered_values = scaled_values[mask]
                    
                    if len(filtered_time) > 0:
                        # Plot mit Transparenz für Linie UND Marker
                        line, = current_ax.plot(filtered_time, filtered_values, color=color, marker='o', 
                                linewidth=2, markersize=4, alpha=line_alpha,
                                markerfacecolor=(*matplotlib.colors.to_rgb(color), marker_alpha),
                                markeredgecolor=(*matplotlib.colors.to_rgb(color), marker_alpha))
                        
                        # Für Legende sammeln
                        if use_y2:
                            lines_ax2.append(line)
                            labels_ax2.append(f'{label} (Y2)')
                        else:
                            lines_ax1.append(line)
                            labels_ax1.append(label)
                        any_data_plotted = True
            
            if not any_data_plotted:
                QMessageBox.warning(self, "Warnung", "Keine Datenpunkte innerhalb der gesetzten Grenzen!")
                return
            
            # Schriftgrößen abrufen
            try:
                label_fontsize = int(self.label_size_input.text())
            except ValueError:
                label_fontsize = 12
            
            try:
                tick_fontsize = int(self.tick_size_input.text())
            except ValueError:
                tick_fontsize = 10
            
            # X-Label
            x_label = self.x_label_input.text() or "Zeit"
            ax.set_xlabel(x_label, fontsize=label_fontsize, fontweight='bold')
            
            # Y-Label mit Einheit (primäre Achse)
            y_label = self.y_label_input.text() or "Wert"
            y_unit = self.y_unit_input.text()
            
            if y_unit:
                y_label = f"{y_label} ({y_unit})"
            
            ax.set_ylabel(y_label, fontsize=label_fontsize, fontweight='bold')
            
            # Y2-Label mit Einheit (sekundäre Achse)
            if y2_enabled and ax2:
                y2_label = self.y2_label_input.text() or "Wert 2"
                y2_unit = self.y2_unit_input.text()
                
                if y2_unit:
                    y2_label = f"{y2_label} ({y2_unit})"
                
                ax2.set_ylabel(y2_label, fontsize=label_fontsize, fontweight='bold')
                ax2.tick_params(axis='y', which='major', labelsize=tick_fontsize)
            
            # Schriftgröße der Tick-Label setzen
            ax.tick_params(axis='both', which='major', labelsize=tick_fontsize)
            
            ax.set_xlim(x_min, x_max)
            ax.set_ylim(y_min, y_max)
            ax.grid(True, alpha=0.3)
            
            # Y2-Grenzen setzen
            if y2_enabled and ax2:
                try:
                    y2_min = float(self.y2_min_input.text()) if self.y2_min_input.text() else None
                except ValueError:
                    y2_min = None
                try:
                    y2_max = float(self.y2_max_input.text()) if self.y2_max_input.text() else None
                except ValueError:
                    y2_max = None
                
                if y2_min is not None or y2_max is not None:
                    current_y2_min, current_y2_max = ax2.get_ylim()
                    ax2.set_ylim(y2_min if y2_min is not None else current_y2_min,
                                 y2_max if y2_max is not None else current_y2_max)
            
            # Tick-Locator setzen
            from matplotlib.ticker import MultipleLocator, AutoMinorLocator
            
            try:
                x_tick = float(self.x_tick_input.text()) if self.x_tick_input.text() else None
            except ValueError:
                x_tick = None
            
            try:
                y_tick = float(self.y_tick_input.text()) if self.y_tick_input.text() else None
            except ValueError:
                y_tick = None
            
            # Die Daten sind bereits skaliert (mit x_scale_factor, y_scale_factor)
            # Der Nutzer gibt Tick-Abstände in der angezeigten/skalierten Einheit ein
            # Diese werden direkt an Matplotlib übergeben
            if x_tick is not None and x_tick > 0:
                ax.xaxis.set_major_locator(MultipleLocator(x_tick))
            
            if y_tick is not None and y_tick > 0:
                ax.yaxis.set_major_locator(MultipleLocator(y_tick))
            
            # Y2-Tick setzen
            if y2_enabled and ax2:
                try:
                    y2_tick = float(self.y2_tick_input.text()) if self.y2_tick_input.text() else None
                except ValueError:
                    y2_tick = None
                
                if y2_tick is not None and y2_tick > 0:
                    ax2.yaxis.set_major_locator(MultipleLocator(y2_tick))
            
            # Legende hinzufügen wenn mehrere Datensätze oder Statistik-Modus
            has_statistics = any(d.get('is_statistics') for d in self.datasets)
            if len(self.datasets) > 1 or has_statistics or y2_enabled:
                # Kombiniere Legenden von beiden Achsen
                all_lines = lines_ax1 + lines_ax2
                all_labels = labels_ax1 + labels_ax2
                if all_lines:
                    ax.legend(all_lines, all_labels, loc='best', fontsize=label_fontsize-2)
            
            self.fig.tight_layout()
            self.canvas.draw()
            
            # Info anzeigen
            total_points = sum(len(d['time']) for d in self.datasets)
            info_text = f"{len(self.datasets)} Datensätze geladen ({total_points} Punkte gesamt)"
            
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Fehler beim Erstellen des Plots: {str(e)}")
    
    def export_plot(self):
        """Exportiere den Plot in eine Bilddatei"""
        try:
            if not hasattr(self, 'fig') or self.fig is None:
                QMessageBox.warning(self, "Fehler", "Bitte erstellen Sie zunächst einen Plot!")
                return
            
            # Dateiformat-Optionen
            file_filters = (
                "PNG - Hochauflösendes Raster (*.png);;"
                "PDF - Rasterisiert (*.pdf);;"
                "JPEG - Komprimiertes Raster (*.jpg);;"
                "Alle Dateien (*)"
            )
            
            file_path, selected_filter = QFileDialog.getSaveFileName(
                self,
                "Plot exportieren",
                "",
                file_filters
            )
            
            if not file_path:
                return
            
            # Dateiformat bestimmen
            if not file_path.lower().endswith(('.pdf', '.png', '.jpg')):
                # Dateiendung basierend auf Filter hinzufügen
                if 'PNG' in selected_filter:
                    file_path += '.png'
                elif 'PDF' in selected_filter:
                    file_path += '.pdf'
                elif 'JPEG' in selected_filter:
                    file_path += '.jpg'
            
            # Optimierte Speicheroptionen für verschiedene Formate
            file_ext = file_path.lower().split('.')[-1]
            
            if file_ext == 'png':
                # PNG mit hoher Auflösung und maximaler Komprimierung (PIL)
                self.fig.savefig(file_path, format='png', dpi=300, bbox_inches='tight',
                                 pil_kwargs={'optimize': True, 'compress_level': 9})
            elif file_ext == 'pdf':
                # PDF vollständig rasterisiert für große Datensätze
                # Verhindert Überlastung von PDF-Readern bei vielen Datenpunkten
                self.fig.savefig(file_path, format='pdf', dpi=300, bbox_inches='tight')
            elif file_ext == 'jpg' or file_ext == 'jpeg':
                # JPEG mit guter Qualität und Komprimierung
                self.fig.savefig(file_path, format='jpeg', dpi=300, bbox_inches='tight',
                                 pil_kwargs={'optimize': True, 'quality': 95})
            else:
                self.fig.savefig(file_path, bbox_inches='tight')
            
            QMessageBox.information(
                self,
                "Erfolg",
                f"Plot erfolgreich exportiert zu:\n{file_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Export", f"Fehler: {str(e)}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    plotter = GraphPlotter()
    plotter.show()
    print("Fenster sollte jetzt sichtbar sein...")
    sys.exit(app.exec_())
