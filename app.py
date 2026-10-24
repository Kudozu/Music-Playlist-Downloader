"""Music Playlist Downloader - serveur local (PC + téléphone sur le même Wi-Fi)."""
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import webbrowser
import zipfile
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)  # lancé depuis le .exe
RES_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))  # fichiers embarqués
BASE_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "history.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
PORT = int(os.environ.get("PORT", 5000))
TERMUX = "com.termux" in os.environ.get("PREFIX", "")
ANDROID_STORAGE = Path("/storage/emulated/0")
DEFAULT_FOLDER = str((ANDROID_STORAGE if TERMUX else Path.home()) / "Music")

if FROZEN:
    import ytdlp_update
    ytdlp_update.use_latest(DATA_DIR / "yt-dlp")

import qrcode  # noqa: E402
import qrcode.image.svg  # noqa: E402
import yt_dlp  # noqa: E402
from flask import Flask, abort, jsonify, request, send_file, send_from_directory  # noqa: E402
from mutagen.mp4 import MP4, MP4Cover  # noqa: E402


def find_ffmpeg():
    candidates = [shutil.which("ffmpeg")]
    try:
        import imageio_ffmpeg
        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    for exe in filter(None, candidates):
        try:  # il peut exister mais être bloqué (ex. Contrôle intelligent des applications)
            subprocess.run([exe, "-version"], capture_output=True, timeout=15, check=True)
            return exe
        except Exception:
            continue
    return None


# Sans ffmpeg on télécharge le M4A natif de YouTube (pas de conversion possible)
FFMPEG = find_ffmpeg()
FORMATS = ("mp3", "m4a", "opus") if FFMPEG else ("m4a",)

DATA_DIR.mkdir(exist_ok=True)
app = Flask(__name__, static_folder=str(RES_DIR / "static"))

history_lock = threading.Lock()
jobs = {}


# ---------------------------------------------------------------- stockage

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def mark_downloaded(playlist_id, playlist_title, video_id):
    with history_lock:
        history = load_json(HISTORY_FILE, {})
        entry = history.setdefault(playlist_id, {"title": playlist_title, "ids": []})
        entry["title"] = playlist_title
        if video_id not in entry["ids"]:
            entry["ids"].append(video_id)
        entry["updated"] = time.strftime("%Y-%m-%d %H:%M")
        save_json(HISTORY_FILE, history)


def downloaded_ids(playlist_id):
    with history_lock:
        return set(load_json(HISTORY_FILE, {}).get(playlist_id, {}).get("ids", []))


# ---------------------------------------------------------------- téléchargement

class Job:
    def __init__(self, url, folder, only_new, audio_format):
        self.id = uuid.uuid4().hex[:10]
        self.url = url
        self.folder = Path(folder)
        self.only_new = only_new
        self.audio_format = audio_format
        self.status = "running"  # running | done | error | cancelled
        self.playlist_title = ""
        self.total = 0
        self.index = 0
        self.skipped = 0
        self.current = ""
        self.current_pct = 0.0
        self.files = []
        self.failed = []
        self.log = []
        self.cancel = False

    def add_log(self, msg):
        self.log.append(time.strftime("%H:%M:%S ") + msg)
        self.log = self.log[-300:]

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "playlist_title": self.playlist_title,
            "total": self.total,
            "index": self.index,
            "skipped": self.skipped,
            "current": self.current,
            "current_pct": round(self.current_pct, 1),
            "files": [p.name for p in self.files],
            "failed": self.failed,
            "log": self.log[-60:],
            "folder": str(self.folder),
        }


class Cancelled(Exception):
    pass


def tag_m4a(path, info):
    """Ajoute titre/artiste/album/pochette quand ffmpeg n'est pas là pour le faire."""
    audio = MP4(path)
    audio["\xa9nam"] = info.get("track") or info.get("title") or ""
    audio["\xa9ART"] = info.get("artist") or info.get("uploader") or ""
    if info.get("album"):
        audio["\xa9alb"] = info["album"]
    if info.get("release_year"):
        audio["\xa9day"] = str(info["release_year"])
    thumbs = [t["url"] for t in info.get("thumbnails") or [] if t.get("url", "").split("?")[0].endswith(".jpg")]
    for url in reversed(thumbs):  # de la meilleure à la plus petite, certaines n'existent pas
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                audio["covr"] = [MP4Cover(r.read(), imageformat=MP4Cover.FORMAT_JPEG)]
            break
        except OSError:
            continue
    audio.save()


def run_job(job: Job):
    try:
        job.folder.mkdir(parents=True, exist_ok=True)
        job.add_log("Lecture de la playlist…")
        with yt_dlp.YoutubeDL({"extract_flat": "in_playlist", "quiet": True, "ignoreerrors": True}) as ydl:
            info = ydl.extract_info(job.url, download=False)
        if not info:
            raise RuntimeError("Impossible de lire cette playlist (lien invalide ou privée ?)")

        raw = info.get("entries") if info.get("_type") == "playlist" else [info]
        entries = [e for e in raw or [] if e and e.get("id")]
        playlist_id = info.get("id") or job.url
        job.playlist_title = info.get("title") or playlist_id
        job.add_log(f"Playlist « {job.playlist_title} » : {len(entries)} musiques")

        if job.only_new:
            already = downloaded_ids(playlist_id)
            todo = [e for e in entries if e["id"] not in already]
            job.skipped = len(entries) - len(todo)
            if job.skipped:
                job.add_log(f"{job.skipped} déjà téléchargées, ignorées")
        else:
            todo = entries
        job.total = len(todo)
        if not todo:
            job.add_log("Rien de nouveau à télécharger 🎉")

        def hook(d):
            if job.cancel:
                raise Cancelled()
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                job.current_pct = d.get("downloaded_bytes", 0) * 100 / total if total else 0
            elif d["status"] == "finished":
                job.current_pct = 100

        opts = {
            "outtmpl": str(job.folder / "%(artist,uploader)s - %(title)s.%(ext)s"),
            "windowsfilenames": True,
            "trim_file_name": 120,  # Windows refuse les chemins de plus de 260 caractères
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [hook],
            "retries": 10,
            "fragment_retries": 10,
            "extractor_retries": 3,
        }
        if FFMPEG:
            postprocessors = [
                {"key": "FFmpegExtractAudio", "preferredcodec": job.audio_format, "preferredquality": "0"},
                {"key": "FFmpegMetadata", "add_metadata": True},
            ]
            if job.audio_format in ("mp3", "m4a"):
                postprocessors.append({"key": "EmbedThumbnail"})
            opts.update({
                "format": "bestaudio/best",
                "ffmpeg_location": FFMPEG,
                "postprocessors": postprocessors,
                "writethumbnail": job.audio_format in ("mp3", "m4a"),
                "convert_thumbnails": "jpg",
                "postprocessor_args": {"thumbnailsconvertor+ffmpeg_o": ["-c:v", "mjpeg", "-vf", "crop=ih:ih"]},
            })
        else:
            opts["format"] = "bestaudio[ext=m4a]/bestaudio"

        with yt_dlp.YoutubeDL(opts) as ydl:
            for i, entry in enumerate(todo, 1):
                if job.cancel:
                    raise Cancelled()
                job.index = i
                job.current = entry.get("title") or entry["id"]
                job.current_pct = 0
                video_url = f"https://music.youtube.com/watch?v={entry['id']}"
                try:
                    for attempt in range(3):  # coupures réseau passagères
                        try:
                            result = ydl.extract_info(video_url, download=True)
                            break
                        except yt_dlp.utils.DownloadError as exc:
                            if attempt == 2 or "unavailable" in str(exc).lower():
                                raise
                            job.add_log(f"… nouvelle tentative pour {job.current}")
                            time.sleep(3)
                    path = Path(ydl.prepare_filename(result))
                    if FFMPEG:
                        path = path.with_suffix("." + job.audio_format)
                    elif path.suffix == ".m4a":
                        tag_m4a(path, result)
                    job.files.append(path)
                    mark_downloaded(playlist_id, job.playlist_title, entry["id"])
                    job.add_log(f"✔ {path.name}")
                except Cancelled:
                    raise
                except Exception as exc:  # une musique indisponible ne bloque pas les autres
                    msg = str(exc).replace("ERROR: ", "")[:200]
                    job.failed.append(job.current)
                    job.add_log(f"✘ {job.current} : {msg}")

        job.current = ""
        job.status = "done"
        job.add_log(f"Terminé : {len(job.files)} téléchargées, {len(job.failed)} échecs")
    except Cancelled:
        job.status = "cancelled"
        job.add_log("Annulé")
    except Exception as exc:
        job.status = "error"
        job.add_log(f"Erreur : {exc}")


# ---------------------------------------------------------------- routes

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/settings")
def get_settings():
    return jsonify({"default_folder": DEFAULT_FOLDER, "formats": FORMATS, **load_json(SETTINGS_FILE, {})})


@app.post("/api/download")
def start_download():
    body = request.get_json(force=True)
    url = (body.get("url") or "").strip()
    folder = (body.get("folder") or DEFAULT_FOLDER).strip()
    audio_format = body.get("format") if body.get("format") in FORMATS else FORMATS[0]
    if not url.startswith("http"):
        return jsonify({"error": "Colle un lien de playlist YouTube Music"}), 400
    folder = os.path.expanduser(folder)
    if not os.path.isabs(folder):
        folder = os.path.join(DEFAULT_FOLDER, folder)

    save_json(SETTINGS_FILE, {"folder": folder, "only_new": bool(body.get("only_new")), "format": audio_format})
    job = Job(url, folder, bool(body.get("only_new")), audio_format)
    jobs[job.id] = job
    threading.Thread(target=run_job, args=(job,), daemon=True).start()
    return jsonify({"id": job.id})


@app.get("/api/jobs")
def list_jobs():
    return jsonify([j.to_dict() for j in jobs.values()][::-1])


@app.get("/api/jobs/<job_id>")
def get_job(job_id):
    job = jobs.get(job_id) or abort(404)
    return jsonify(job.to_dict())


@app.post("/api/jobs/<job_id>/cancel")
def cancel_job(job_id):
    job = jobs.get(job_id) or abort(404)
    job.cancel = True
    return jsonify({"ok": True})


@app.get("/api/jobs/<job_id>/file/<int:n>")
def job_file(job_id, n):
    job = jobs.get(job_id) or abort(404)
    if n >= len(job.files) or not job.files[n].exists():
        abort(404)
    return send_file(job.files[n], as_attachment=True)


@app.get("/api/jobs/<job_id>/zip")
def job_zip(job_id):
    job = jobs.get(job_id) or abort(404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for p in job.files:
            if p.exists():
                zf.write(p, p.name)
    buf.seek(0)
    name = "".join(c for c in (job.playlist_title or "playlist") if c not in '\\/:*?"<>|')
    return send_file(buf, as_attachment=True, download_name=f"{name}.zip", mimetype="application/zip")


@app.get("/api/history")
def get_history():
    history = load_json(HISTORY_FILE, {})
    return jsonify([
        {"id": pid, "title": h.get("title", pid), "count": len(h.get("ids", [])), "updated": h.get("updated", "")}
        for pid, h in history.items()
    ])


@app.delete("/api/history/<playlist_id>")
def delete_history(playlist_id):
    with history_lock:
        history = load_json(HISTORY_FILE, {})
        history.pop(playlist_id, None)
        save_json(HISTORY_FILE, history)
    return jsonify({"ok": True})


@app.get("/api/browse")
def browse():
    """Liste les sous-dossiers du PC pour choisir le dossier de destination."""
    path = request.args.get("path") or ""
    if not path:  # racine : dossiers utiles + lecteurs Windows / stockage Android
        home = ANDROID_STORAGE if TERMUX else Path.home()
        roots = [str(home / d) for d in ("Music", "Download", "Downloads", "Desktop") if (home / d).is_dir()]
        roots.insert(0, str(home))
        if os.name == "nt":
            roots += [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
        elif not TERMUX:
            roots.append("/")
        return jsonify({"path": "", "parent": None, "dirs": [{"name": r, "path": r} for r in roots]})
    p = Path(path)
    if not p.is_dir():
        return jsonify({"error": "Dossier introuvable"}), 404
    try:
        dirs = sorted(
            (c for c in p.iterdir() if c.is_dir() and not c.name.startswith((".", "$"))),
            key=lambda c: c.name.lower(),
        )
    except PermissionError:
        dirs = []
    parent = str(p.parent) if p.parent != p else ""
    return jsonify({"path": str(p), "parent": parent, "dirs": [{"name": c.name, "path": str(c)} for c in dirs]})


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


@app.get("/api/phone")
def phone():
    """Adresse à ouvrir sur le téléphone + QR code à scanner."""
    url = f"http://{lan_ip()}:{PORT}"
    svg = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=2).to_string(encoding="unicode")
    return jsonify({"url": url, "svg": svg})


def port_in_use():
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


if __name__ == "__main__":
    local = f"http://localhost:{PORT}"
    if port_in_use():  # déjà lancé (double-clic en trop) : on rouvre juste la page
        webbrowser.open(local)
        sys.exit()
    print("\n  Music Playlist Downloader")
    print(f"  Sur cet appareil : {local}")
    print(f"  Sur le téléphone : http://{lan_ip()}:{PORT}   (même Wi-Fi, ou scanne le QR code dans la page)")
    print("  Laisse cette fenêtre ouverte. Ferme-la pour arrêter.\n")
    if os.environ.get("NO_BROWSER") != "1":
        threading.Timer(1.0, webbrowser.open, args=(local,)).start()
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT, threads=8)
