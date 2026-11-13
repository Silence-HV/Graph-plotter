"""Graph Plotter – Startpunkt.

Der Programmcode liegt im Paket ``graph_plotter``. Diese Datei bleibt als Einstiegspunkt
für den direkten Start (``python Plotter.py``) und für den PyInstaller-Build erhalten.
"""

import sys

from graph_plotter.app import main

if __name__ == "__main__":
    sys.exit(main())
