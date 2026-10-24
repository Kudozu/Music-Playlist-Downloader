@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Music Playlist Downloader

if not exist ".venv\Scripts\python.exe" (
    echo Premiere installation, patiente un peu...
    python -m venv .venv || (echo Python est introuvable. Installe-le depuis python.org & pause & exit /b 1)
)
echo Mise a jour des dependances (yt-dlp change souvent)...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -U -r requirements.txt
rem ffmpeg (pour MP3/Opus) est optionnel : sans lui on telecharge en M4A
where ffmpeg >nul 2>nul || ".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check imageio-ffmpeg 2>nul || echo (ffmpeg indisponible : seul le format M4A sera propose)


".venv\Scripts\python.exe" app.py
pause
