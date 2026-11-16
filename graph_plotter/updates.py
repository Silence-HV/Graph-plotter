"""Nach neuen Versionen suchen und den Installer herunterladen (ohne Qt, dadurch testbar).

Quelle sind die GitHub-Releases des Projekts. Abgefragt wird nur die öffentliche Release-Seite; es
werden keine Daten über den Nutzer oder seine Dateien übertragen.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import VERSION

REPOSITORY = "Silence-HV/Graph-plotter"
RELEASES_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
# Für Tests (oder eine andere Quelle) überschreibbar
UPDATE_URL_ENV = "GRAPHPLOTTER_UPDATE_URL"
TIMEOUT = 10


class UpdateError(Exception):
    """Update-Prüfung oder Download fehlgeschlagen (Meldung ist für Nutzer formuliert)."""


@dataclass
class ReleaseInfo:
    version: tuple[int, ...]
    tag: str
    page_url: str
    notes: str = ""
    setup_url: str = ""
    setup_name: str = ""
    setup_size: int = 0
    setup_sha256: str = ""
    portable_url: str = ""

    @property
    def version_text(self) -> str:
        return ".".join(str(p) for p in self.version)


def parse_version(text: str) -> tuple[int, ...]:
    """„v3.2.1“ → (3, 2, 1). Raises ValueError, wenn keine Versionsnummer enthalten ist."""
    match = re.search(r"(\d+(?:\.\d+)*)", text or "")
    if not match:
        raise ValueError(f"Keine Versionsnummer in „{text}“")
    parts = [int(p) for p in match.group(1).split(".")]
    while len(parts) > 1 and parts[-1] == 0:  # 3.2.0 == 3.2
        parts.pop()
    return tuple(parts)


def is_newer(remote: tuple[int, ...], local: tuple[int, ...] | None = None) -> bool:
    return remote > (local if local is not None else parse_version(VERSION))


def parse_release(data: dict) -> ReleaseInfo:
    tag = data.get("tag_name") or ""
    info = ReleaseInfo(version=parse_version(tag), tag=tag, page_url=data.get("html_url") or "",
                       notes=data.get("body") or "")
    for asset in data.get("assets") or []:
        name = asset.get("name") or ""
        url = asset.get("browser_download_url") or ""
        if name.lower().endswith("_setup.exe"):
            digest = asset.get("digest") or ""
            info.setup_url, info.setup_name = url, name
            info.setup_size = int(asset.get("size") or 0)
            info.setup_sha256 = digest.split(":", 1)[1] if digest.startswith("sha256:") else ""
        elif name.lower().endswith("_portable.zip"):
            info.portable_url = url
    return info


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"GraphPlotter/{VERSION}",
    })


def fetch_latest(url: Optional[str] = None) -> ReleaseInfo:
    """Neuestes Release abfragen. Raises UpdateError bei Netzwerk- oder Formatfehlern."""
    url = url or os.environ.get(UPDATE_URL_ENV) or RELEASES_API
    try:
        with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("Keine veröffentlichte Version gefunden (Projekt nicht öffentlich "
                              "oder noch kein Release).") from exc
        raise UpdateError(f"Update-Server antwortet mit Fehler {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError("Keine Verbindung zum Update-Server (Internet?).") from exc
    except ValueError as exc:
        raise UpdateError("Unerwartete Antwort vom Update-Server.") from exc
    try:
        return parse_release(data)
    except ValueError as exc:
        raise UpdateError(f"Unerwartete Antwort vom Update-Server: {exc}") from exc


def download(info: ReleaseInfo, target_dir: Optional[Path] = None,
             progress: Optional[Callable[[int, int], None]] = None,
             cancelled: Optional[Callable[[], bool]] = None) -> Path:
    """Installer herunterladen und Größe/Prüfsumme kontrollieren.

    Returns:
        Pfad der heruntergeladenen Datei.

    Raises:
        UpdateError: bei Abbruch, Netzwerkfehler, unvollständigem Download oder falscher Prüfsumme
            (die Teildatei wird dann gelöscht).
    """
    if not info.setup_url:
        raise UpdateError("Diese Version enthält keinen Installer.")
    target_dir = Path(target_dir or tempfile.mkdtemp(prefix="graphplotter_update_"))
    target = target_dir / (info.setup_name or "GraphPlotter_Setup.exe")
    sha = hashlib.sha256()
    done = 0
    try:
        with urllib.request.urlopen(_request(info.setup_url), timeout=TIMEOUT) as response, \
                open(target, "wb") as out:
            total = int(response.headers.get("Content-Length") or info.setup_size or 0)
            while True:
                if cancelled is not None and cancelled():
                    raise UpdateError("Download abgebrochen.")
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, total)
    except UpdateError:
        target.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        target.unlink(missing_ok=True)
        raise UpdateError(f"Download fehlgeschlagen: {exc}") from exc

    if info.setup_size and done != info.setup_size:
        target.unlink(missing_ok=True)
        raise UpdateError("Download unvollständig – bitte erneut versuchen.")
    if info.setup_sha256 and sha.hexdigest().lower() != info.setup_sha256.lower():
        target.unlink(missing_ok=True)
        raise UpdateError("Prüfsumme des Downloads stimmt nicht – Datei wurde verworfen.")
    return target


def install_kind() -> str:
    """„installed“ (über den Installer), „portable“ (entpackter Ordner) oder „source“ (Python)."""
    if not getattr(sys, "frozen", False):
        return "source"
    folder = Path(sys.executable).resolve().parent
    return "installed" if any(folder.glob("unins*.exe")) else "portable"


def launch_installer(path: Path) -> subprocess.Popen:
    """Installer im „stillen“ Modus starten: zeigt nur den Fortschritt, schließt das laufende Programm
    und startet es danach neu (siehe installer.iss)."""
    return subprocess.Popen([str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                            close_fds=True)
