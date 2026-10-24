"""Mise à jour de yt-dlp pour la version .exe.

L'exe embarque une version figée de yt-dlp, que YouTube finit toujours par casser.
Au démarrage on récupère la dernière version (une wheel, importable telle quelle
comme un zip) et on la fait passer avant celle embarquée. En cas de souci on
retombe sur la version embarquée.
"""
import importlib.abc
import importlib.machinery
import json
import sys
import urllib.request
from pathlib import Path


class _WheelFirst(importlib.abc.MetaPathFinder):
    def __init__(self, wheel):
        self.wheel = wheel

    def find_spec(self, name, path, target=None):
        if name == "yt_dlp" or name.startswith("yt_dlp."):
            return importlib.machinery.PathFinder.find_spec(name, path or [self.wheel])
        return None


def _download_latest(folder: Path):
    meta = json.load(urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=10))
    version = meta["info"]["version"]
    url = next(u["url"] for u in meta["urls"] if u["packagetype"] == "bdist_wheel")
    wheel = folder / f"yt_dlp-{version}.whl"
    if not wheel.exists():
        print(f"  Mise à jour de yt-dlp vers {version}…")
        folder.mkdir(parents=True, exist_ok=True)
        part = wheel.with_suffix(".part")
        urllib.request.urlretrieve(url, part)
        part.replace(wheel)
        for old in folder.glob("*.whl"):
            if old != wheel:
                old.unlink(missing_ok=True)


def use_latest(folder: Path):
    try:
        _download_latest(folder)
    except Exception:
        pass  # pas de réseau : on garde ce qu'on a
    wheels = sorted(folder.glob("*.whl"))
    if not wheels:
        return
    finder = _WheelFirst(str(wheels[-1]))
    sys.meta_path.insert(0, finder)
    try:
        import yt_dlp  # noqa: F401
    except Exception:
        sys.meta_path.remove(finder)
        for mod in [m for m in sys.modules if m == "yt_dlp" or m.startswith("yt_dlp.")]:
            del sys.modules[mod]
        wheels[-1].unlink(missing_ok=True)
