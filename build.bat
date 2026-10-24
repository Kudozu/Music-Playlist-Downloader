@echo off
rem Construit dist\MusicPlaylistDownloader.exe (utilise aussi par GitHub Actions)
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onefile ^
  --name MusicPlaylistDownloader ^
  --icon icon.ico ^
  --add-data "static;static" ^
  --collect-all imageio_ffmpeg ^
  --hidden-import ytdlp_update ^
  app.py
