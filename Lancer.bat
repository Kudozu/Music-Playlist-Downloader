@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Music Playlist Downloader

if exist ".venv\Scripts\python.exe" goto deps

rem Trouve Python (sans tomber sur le faux python.exe du Microsoft Store), sinon l'installe
set "PY="
for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
if not defined PY for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
if not defined PY (
    echo Python n'est pas installe : installation automatique...
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not exist "%PY%" (
    echo Impossible d'installer Python. Installe-le depuis https://www.python.org puis relance.
    pause
    exit /b 1
)
echo Premiere installation, patiente un peu...
"%PY%" -m venv .venv

:deps
echo Mise a jour des dependances (yt-dlp change souvent)...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -U -r requirements.txt
rem ffmpeg (pour MP3/Opus) est optionnel : sans lui on telecharge en M4A
where ffmpeg >nul 2>nul || ".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check imageio-ffmpeg 2>nul || echo (ffmpeg indisponible : seul le format M4A sera propose)

".venv\Scripts\python.exe" app.py
pause
