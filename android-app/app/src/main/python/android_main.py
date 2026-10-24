"""Point d'entrée Python de l'appli Android, lancé par ServerService via Chaquopy.

Démarre le même serveur que sur PC (app.py), mais seulement pour le téléphone
lui-même (127.0.0.1), et branche les services Android : indexation des
musiques dans la médiathèque et maintien du processeur éveillé pendant les
téléchargements.
"""
import os
import threading

PORT = 8765


def start(files_dir, static_dir):
    os.environ.update(
        MPD_APP="android",
        MPD_DATA_DIR=os.path.join(files_dir, "data"),
        MPD_STATIC_DIR=static_dir,
        PORT=str(PORT),
    )
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())

    import app
    from java import cast, jclass

    ctx = jclass("com.chaquo.python.Python").getPlatform().getApplication()
    scanner = jclass("android.media.MediaScannerConnection")
    # Sans ça, les lecteurs de musique ne voient les nouveaux fichiers qu'après un redémarrage
    app.ON_FILE_SAVED = lambda path: scanner.scanFile(ctx, [str(path)], None, None)

    power = cast(jclass("android.os.PowerManager"), ctx.getSystemService("power"))
    wake_lock = power.newWakeLock(1, "playlistdownloader:download")  # PARTIAL_WAKE_LOCK
    run_job = app.run_job

    def run_job_awake(job):
        wake_lock.acquire()
        try:
            run_job(job)
        finally:
            wake_lock.release()

    app.run_job = run_job_awake

    from waitress import serve
    threading.Thread(
        target=serve, args=(app.app,), kwargs={"host": "127.0.0.1", "port": PORT, "threads": 8}, daemon=True
    ).start()
