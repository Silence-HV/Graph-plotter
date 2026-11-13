#!/usr/bin/env python
"""
Build-Skript für Graph Plotter .exe
Erstellt eine standalone .exe-Datei mit allen Dependencies
"""

import os
import sys
import subprocess
import re
from pathlib import Path
from datetime import datetime

# Pfade definieren
project_dir = Path(__file__).parent
main_file = project_dir / "Plotter.py"
dist_dir = project_dir / "dist"
build_dir = project_dir / "build"

# Version aus graph_plotter/__init__.py auslesen
def get_version():
    with open(project_dir / "graph_plotter" / "__init__.py", 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r'VERSION\s*=\s*["\'](\d+\.\d+)["\']', content)
    if match:
        return match.group(1)
    return "1.0"

VERSION = get_version()
VERSION_SHORT = VERSION.replace(".", "")  # 1.4 -> 14

print("=" * 60)
print(f"Graph Plotter - .exe Erstellung (v{VERSION})")
print(f"Zeitstempel: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# Dateiname mit Versionsnummer
exe_name = f"GraphPlotter_v{VERSION_SHORT}"

# PyInstaller Befehl zusammenstellen
pyinstaller_cmd = [
    sys.executable, "-m", "PyInstaller",
    f"--name={exe_name}",
    "--onefile",  # Einzelne .exe statt Ordner
    "--windowed",  # Keine Konsole
    "--icon=NONE",  # Kein Icon (optional)
    "--collect-all=PyQt5",  # Alle PyQt5-Module und Binaries sammeln
    "--collect-all=PyQt5.sip",  # sip-Modul sammeln
    "--hidden-import=PyQt5.sip",
    "--hidden-import=sip",
    "--hidden-import=matplotlib.backends.backend_qt5agg",
    "--hidden-import=matplotlib.backends.backend_pdf",
    "--hidden-import=matplotlib.backends.backend_svg",
    "--hidden-import=matplotlib.figure",
    "--hidden-import=matplotlib.ticker",
    "--hidden-import=xlrd",  # .xls-Unterstützung (wird nur bei Bedarf importiert)
    "--noconfirm",  # Alte Builds überschreiben ohne Nachfrage
    "--clean",  # Alten Build löschen
    str(main_file)
]

print("\nStarte PyInstaller...")
print(f"Befehl: {' '.join(pyinstaller_cmd)}\n")

try:
    # PyInstaller ausführen
    result = subprocess.run(pyinstaller_cmd, check=True, cwd=str(project_dir))
    
    print("\n" + "=" * 60)
    print("[OK] Erstellung erfolgreich!")
    print("=" * 60)
    
    exe_path = dist_dir / f"{exe_name}.exe"
    
    if exe_path.exists():
        file_size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\nDatei: {exe_path}")
        print(f"Groesse: {file_size_mb:.2f} MB")
        print("\nDie .exe-Datei kann jetzt direkt ausgeführt werden!")
        print(f"Pfad: {exe_path}")
    else:
        print("\nWarnung: .exe-Datei nicht gefunden!")
        
except subprocess.CalledProcessError as e:
    print(f"\n[FEHLER] Fehler bei der Erstellung: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n[FEHLER] Fehler: {e}")
    sys.exit(1)
