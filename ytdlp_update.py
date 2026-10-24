"""Mise à jour de yt-dlp pour la version .exe.

L'exe embarque une version figée de yt-dlp, que YouTube finit toujours par casser.
On garde la dernière version publiée (une wheel, importable telle quelle comme un
zip) dans data/yt-dlp et on la fait passer avant celle embarquée. Le téléchargement
se fait en arrière-plan pour ne jamais ralentir le démarrage : la nouvelle version
sert au lancement suivant. En cas de souci on retombe sur la version embarquée.
"""
import importlib.abc
import importlib.machinery
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path


class _WheelFirst(importlib.abc.MetaPathFinder):
    def __init__(self, wheel):
        self.wheel = wheel

    def find_spec(self, name, path, target=None):
        if name == "yt_dlp" or name.startswith("yt_dlp."):
            return importlib.machinery.PathFinder.find_spec(name, path or [self.wheel])
        return None


def _version(wheel: Path):
    return tuple(int(x) for x in wheel.stem.split("-")[1].split(".") if x.isdigit())


def _download_latest(folder: Path, deadline=600):
    meta = json.load(urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=15))
    version = meta["info"]["version"]
    url = next(u["url"] for u in meta["urls"] if u["packagetype"] == "bdist_wheel")
    wheel = folder / f"yt_dlp-{version}.whl"
    if wheel.exists():
        return
    folder.mkdir(parents=True, exist_ok=True)
    part = wheel.with_suffix(".part")
    start = time.monotonic()
    with urllib.request.urlopen(url, timeout=20) as r, open(part, "wb") as f:
        while chunk := r.read(65536):
            if time.monotonic() - start > deadline:
                raise TimeoutError
            f.write(chunk)
    part.replace(wheel)


def _update_in_background(folder: Path):
    try:
        _download_latest(folder)
    except Exception:
        pass  # pas de réseau : on réessaiera au prochain lancement
    finally:
        for p in folder.glob("*.part"):
            p.unlink(missing_ok=True)


def use_latest(folder: Path):
    wheels = sorted(folder.glob("yt_dlp-*.whl"), key=_version)
    for old in wheels[:-1]:
        old.unlink(missing_ok=True)
    if wheels:
        finder = _WheelFirst(str(wheels[-1]))
        sys.meta_path.insert(0, finder)
        try:
            import yt_dlp  # noqa: F401
        except Exception:
            sys.meta_path.remove(finder)
            for mod in [m for m in sys.modules if m == "yt_dlp" or m.startswith("yt_dlp.")]:
                del sys.modules[mod]
            wheels[-1].unlink(missing_ok=True)
    threading.Thread(target=_update_in_background, args=(folder,), daemon=True).start()
