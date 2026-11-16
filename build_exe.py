#!/usr/bin/env python
"""Graph Plotter für die Weitergabe bauen.

Standard (Ordner-Variante, empfohlen):
    python build_exe.py
    → dist/GraphPlotter/                      Programmordner (GraphPlotter.exe + Bibliotheken)
    → dist/GraphPlotter_v<Version>_portable.zip  zum Weitergeben ohne Installation
    → dist/GraphPlotter_v<Version>_Setup.exe     Installer (nur wenn Inno Setup 6 installiert ist)

Einzelne .exe (startet langsamer, wird häufiger von Virenscannern beanstandet):
    python build_exe.py --onefile

Die Ordner-Variante hält außerdem die LGPL von Qt einfach ein: Die Qt-Bibliotheken liegen als
eigene Dateien vor und können ausgetauscht werden.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from datetime import datetime
from importlib import metadata
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
MAIN_FILE = PROJECT / "Plotter.py"
DIST = PROJECT / "dist"
BUILD = PROJECT / "build"
APP_NAME = "GraphPlotter"
DISPLAY_NAME = "Graph Plotter"
# Laufzeit-Abhängigkeiten (Wurzeln); deren Abhängigkeiten werden für die Lizenztexte ermittelt
RUNTIME_PACKAGES = ["PySide6-Essentials", "matplotlib", "numpy", "pandas", "python-calamine", "openpyxl"]
# Qt-Teile, die PyInstaller über Erweiterungen mitnimmt, die das Programm aber nicht nutzt (~38 MB):
# Software-OpenGL, Qt Quick/QML (nur von der Bildschirmtastatur benötigt), PDF-Anzeige, Direct2D.
PRUNE = [
    "_internal/PySide6/opengl32sw.dll",
    "_internal/PySide6/Qt6Pdf.dll",
    "_internal/PySide6/Qt6Quick.dll",
    "_internal/PySide6/Qt6Qml*.dll",
    "_internal/PySide6/Qt6VirtualKeyboard.dll",
    "_internal/PySide6/plugins/imageformats/qpdf.dll",
    "_internal/PySide6/plugins/platforminputcontexts",
    "_internal/PySide6/plugins/platforms/qdirect2d.dll",
]


def prune(app_dir: Path) -> float:
    """Nicht benötigte Qt-Dateien entfernen; liefert die eingesparten MB."""
    saved = 0
    for pattern in PRUNE:
        for path in app_dir.glob(pattern):
            if path.is_dir():
                saved += sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                shutil.rmtree(path)
            elif path.is_file():
                saved += path.stat().st_size
                path.unlink()
    return saved / 2**20


def get_version() -> str:
    content = (PROJECT / "graph_plotter" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'VERSION\s*=\s*["\'](\d+\.\d+(?:\.\d+)?)["\']', content)
    return match.group(1) if match else "0.0"


# ---------------------------------------------------------------------------- Symbol

def make_icon(target: Path) -> Path:
    """Programmsymbol (.ico mit mehreren Größen) aus dem SVG-Symbol der Oberfläche erzeugen."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    sys.path.insert(0, str(PROJECT))
    from graph_plotter.ui.icons import APP_COLOR, svg

    _app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(QByteArray(svg("app", APP_COLOR).encode("utf-8")))
    images = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        images.append((size, bytes(buffer.data())))

    # ICO-Datei mit PNG-Einträgen (seit Windows Vista unterstützt)
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, payload = b"", b""
    for size, png in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(payload))
        payload += png
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(header + entries + payload)
    return target


# ---------------------------------------------------------------------------- Versionsinfo

def make_version_file(target: Path, version: str) -> Path:
    parts = [int(p) for p in version.split(".")] + [0, 0, 0]
    numbers = tuple(parts[:4])
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040704B0', [
      StringStruct('FileDescription', '{DISPLAY_NAME} – Messdaten darstellen'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', '{APP_NAME}'),
      StringStruct('OriginalFilename', '{APP_NAME}.exe'),
      StringStruct('ProductName', '{DISPLAY_NAME}'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1031, 1200])])
  ]
)
"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------- Lizenzen

def _dependency_closure(roots: list[str]) -> list[metadata.Distribution]:
    from packaging.markers import default_environment
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    env = default_environment()
    env["extra"] = ""
    seen: dict[str, metadata.Distribution] = {}
    queue = list(roots)
    while queue:
        name = canonicalize_name(queue.pop())
        if name in seen:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        seen[name] = dist
        for raw in dist.requires or []:
            req = Requirement(raw)
            if req.marker is None or req.marker.evaluate(env):
                queue.append(req.name)
    return sorted(seen.values(), key=lambda d: d.metadata["Name"].lower())


def _license_of(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    if meta.get("License-Expression"):
        return meta["License-Expression"]
    text = (meta.get("License") or "").strip()
    if text and len(text) < 80 and "\n" not in text:
        return text
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    return ", ".join(classifiers) or "siehe Lizenzdatei"


def write_licenses(target: Path) -> None:
    """Lizenztexte aller mitgelieferten Python-Pakete sammeln und eine Übersicht schreiben."""
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    lines = [f"{DISPLAY_NAME} – verwendete Software von Dritten", "=" * 60, "",
             "Dieses Programm enthält die folgenden Bibliotheken. Ihre Lizenztexte liegen in den",
             "gleichnamigen Unterordnern.", "",
             "Hinweis zu Qt/PySide6 (LGPL-3.0): Die Qt-Bibliotheken liegen als eigene Dateien im",
             "Programmordner (_internal/PySide6) und können gegen eine kompatible Version",
             "ausgetauscht werden. Quelltext: https://download.qt.io und https://code.qt.io/", "",
             f"{'Paket':<28}{'Version':<14}Lizenz", "-" * 60]
    for dist in _dependency_closure(RUNTIME_PACKAGES):
        name, version = dist.metadata["Name"], dist.version
        lines.append(f"{name:<28}{version:<14}{_license_of(dist)}")
        folder = target / name
        for file in dist.files or []:
            lower = str(file).lower()
            if any(key in Path(lower).name for key in ("licen", "copying", "notice")) or "/licenses/" in lower:
                source = Path(file.locate())
                if source.is_file():
                    folder.mkdir(exist_ok=True)
                    shutil.copy2(source, folder / source.name)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    lines.append(f"{'Python':<28}{sys.version.split()[0]:<14}PSF-2.0")
    if python_license.exists():
        (target / "Python").mkdir(exist_ok=True)
        shutil.copy2(python_license, target / "Python" / "LICENSE.txt")
    (target / "UEBERSICHT.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------- Installer

def find_iscc() -> Path | None:
    candidates = [Path(os.environ.get(v, "")) / "Inno Setup 6" / "ISCC.exe"
                  for v in ("ProgramFiles(x86)", "ProgramFiles")]
    candidates.append(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe")
    found = shutil.which("ISCC.exe")
    if found:
        candidates.insert(0, Path(found))
    return next((c for c in candidates if c.is_file()), None)


# ---------------------------------------------------------------------------- Build

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--onefile", action="store_true", help="einzelne .exe statt Programmordner")
    parser.add_argument("--no-installer", action="store_true", help="keinen Installer bauen")
    args = parser.parse_args()

    version = get_version()
    print("=" * 60)
    print(f"{DISPLAY_NAME} – Build v{version} ({'eine .exe' if args.onefile else 'Programmordner'})")
    print(f"Zeitstempel: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 60)

    icon = make_icon(BUILD / "graph_plotter.ico")
    version_file = make_version_file(BUILD / "version_info.txt", version)
    name = f"{APP_NAME}_v{version.replace('.', '')}" if args.onefile else APP_NAME

    command = [
        sys.executable, "-m", "PyInstaller",
        f"--name={name}",
        "--onefile" if args.onefile else "--onedir",
        "--windowed",
        f"--icon={icon}",
        f"--version-file={version_file}",
        # Nur PySide6 als Qt-Bindung; nicht benötigte Module weglassen
        "--exclude-module=PyQt5", "--exclude-module=PyQt6", "--exclude-module=PySide2",
        "--exclude-module=tkinter", "--exclude-module=pytest", "--exclude-module=IPython",
        "--hidden-import=PySide6.QtSvg",
        "--hidden-import=python_calamine",
        "--hidden-import=matplotlib.backends.backend_qtagg",
        "--hidden-import=matplotlib.backends.backend_pdf",
        "--hidden-import=matplotlib.backends.backend_svg",
        "--hidden-import=matplotlib.backends.backend_ps",
        "--noconfirm", "--clean",
        str(MAIN_FILE),
    ]
    print("\nStarte PyInstaller …")
    try:
        subprocess.run(command, check=True, cwd=str(PROJECT))
    except subprocess.CalledProcessError as exc:
        print(f"\n[FEHLER] PyInstaller ist fehlgeschlagen: {exc}")
        return 1

    if args.onefile:
        exe = DIST / f"{name}.exe"
        print(f"\n[OK] {exe} ({exe.stat().st_size / 2**20:.1f} MB)")
        return 0

    app_dir = DIST / APP_NAME
    print(f"\nNicht benötigte Qt-Teile entfernt: {prune(app_dir):.0f} MB")
    shutil.copy2(PROJECT / "README.md", app_dir / "LIESMICH.txt")
    write_licenses(app_dir / "Lizenzen")
    size = sum(f.stat().st_size for f in app_dir.rglob("*") if f.is_file())
    print(f"\n[OK] Programmordner: {app_dir} ({size / 2**20:.0f} MB)")

    archive = DIST / f"{APP_NAME}_v{version}_portable.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file in sorted(app_dir.rglob("*")):
            if file.is_file():
                zf.write(file, Path(APP_NAME) / file.relative_to(app_dir))
    print(f"[OK] Portables ZIP: {archive} ({archive.stat().st_size / 2**20:.0f} MB)")

    if args.no_installer:
        return 0
    iscc = find_iscc()
    if iscc is None:
        print("\n[HINWEIS] Inno Setup 6 nicht gefunden – kein Installer gebaut.\n"
              "          Installation z. B. mit: winget install JRSoftware.InnoSetup")
        return 0
    try:
        subprocess.run([str(iscc), f"/DAppVersion={version}", f"/DSourceDir={app_dir}",
                        f"/DOutputDir={DIST}", f"/DIconFile={icon}", str(PROJECT / "installer.iss")],
                       check=True, cwd=str(PROJECT))
    except subprocess.CalledProcessError as exc:
        print(f"\n[FEHLER] Inno Setup ist fehlgeschlagen: {exc}")
        return 1
    setup = DIST / f"{APP_NAME}_v{version}_Setup.exe"
    print(f"[OK] Installer: {setup} ({setup.stat().st_size / 2**20:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
