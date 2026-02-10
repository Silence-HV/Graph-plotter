#!/usr/bin/env python
"""
Build-Skript für Graph Plotter .exe
Erstellt eine standalone .exe-Datei mit allen Dependencies
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Versionsnummer
VERSION = "1.1"

# Pfade definieren
project_dir = Path(__file__).parent
main_file = project_dir / "Plotter.py"
dist_dir = project_dir / "dist"
build_dir = project_dir / "build"

print("=" * 60)
print(f"Graph Plotter - .exe Erstellung (v{VERSION})")
print(f"Zeitstempel: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# PyInstaller Befehl zusammenstellen
pyinstaller_cmd = [
    sys.executable, "-m", "PyInstaller",
    "--name=GraphPlotter",
    "--onefile",  # Einzelne .exe statt Ordner
    "--windowed",  # Keine Konsole
    "--icon=NONE",  # Kein Icon (optional)
    "--hidden-import=matplotlib.backends.backend_qt5agg",
    "--hidden-import=matplotlib.figure",
    "--hidden-import=matplotlib.ticker",
    "--hidden-import=PyQt5.sip",
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
    
    exe_path = dist_dir / "GraphPlotter.exe"
    
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
