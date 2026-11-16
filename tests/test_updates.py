"""Tests der Update-Prüfung und des Downloads (lokaler HTTP-Server, kein Internet nötig)."""

import hashlib
import http.server
import json
import threading
from functools import partial

import pytest

from graph_plotter import updates
from graph_plotter.updates import ReleaseInfo, UpdateError, download, fetch_latest, is_newer, parse_release, parse_version


@pytest.fixture
def server(tmp_path):
    """Kleiner HTTP-Server, der Dateien aus tmp_path ausliefert."""
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp_path
    httpd.shutdown()


def release_json(base, setup_name, data, digest=True):
    return {
        "tag_name": "v9.1.0",
        "html_url": "https://example.invalid/releases/v9.1.0",
        "body": "Neu: alles",
        "assets": [
            {"name": setup_name, "size": len(data), "browser_download_url": f"{base}/{setup_name}",
             "digest": f"sha256:{hashlib.sha256(data).hexdigest()}" if digest else None},
            {"name": "GraphPlotter_v9.1_portable.zip", "size": 1, "browser_download_url": f"{base}/p.zip"},
        ],
    }


def test_parse_version_and_compare():
    assert parse_version("v3.2.1") == (3, 2, 1)
    assert parse_version("3.2.0") == parse_version("v3.2") == (3, 2)
    assert is_newer((3, 2, 1), (3, 2)) and is_newer((3, 10), (3, 9, 9))
    assert not is_newer((3, 2), (3, 2)) and not is_newer((3, 1, 9), (3, 2))
    with pytest.raises(ValueError):
        parse_version("latest")


def test_parse_release_picks_assets():
    info = parse_release(release_json("http://x", "GraphPlotter_v9.1_Setup.exe", b"abc"))
    assert info.version == (9, 1) and info.version_text == "9.1"
    assert info.setup_url.endswith("_Setup.exe") and info.setup_size == 3
    assert info.setup_sha256 == hashlib.sha256(b"abc").hexdigest()
    assert info.portable_url.endswith("p.zip")


def test_fetch_and_download_over_http(server):
    base, folder = server
    data = b"installer" * 50_000
    (folder / "GraphPlotter_v9.1_Setup.exe").write_bytes(data)
    (folder / "latest.json").write_text(json.dumps(release_json(base, "GraphPlotter_v9.1_Setup.exe", data)))

    info = fetch_latest(f"{base}/latest.json")
    assert info.tag == "v9.1.0"
    seen = []
    (folder / "dl").mkdir()
    path = download(info, folder / "dl", progress=lambda d, t: seen.append((d, t)))
    assert path.read_bytes() == data
    assert seen[-1] == (len(data), len(data))


def test_download_rejects_wrong_checksum_and_cancel(server):
    base, folder = server
    (folder / "GraphPlotter_v9.1_Setup.exe").write_bytes(b"echt")
    info = parse_release(release_json(base, "GraphPlotter_v9.1_Setup.exe", b"echt"))
    info.setup_sha256 = "0" * 64
    (folder / "dl").mkdir()
    with pytest.raises(UpdateError, match="Prüfsumme"):
        download(info, folder / "dl")
    assert not any((folder / "dl").iterdir())  # verworfene Datei gelöscht

    info = parse_release(release_json(base, "GraphPlotter_v9.1_Setup.exe", b"echt"))
    with pytest.raises(UpdateError, match="abgebrochen"):
        download(info, folder / "dl", cancelled=lambda: True)


def test_fetch_errors_are_user_friendly(server):
    base, _ = server
    with pytest.raises(UpdateError, match="Keine veröffentlichte Version"):
        fetch_latest(f"{base}/gibt-es-nicht.json")
    with pytest.raises(UpdateError, match="Keine Verbindung"):
        fetch_latest("http://127.0.0.1:9/latest")


def test_install_kind_from_source():
    assert updates.install_kind() == "source"
