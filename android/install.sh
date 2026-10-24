#!/data/data/com.termux/files/usr/bin/bash
# Installe Music Playlist Downloader sur Android (dans Termux), sans PC.
# Usage, dans Termux :
#   curl -fsSL https://raw.githubusercontent.com/Kudozu/music-playlist-downloader/main/android/install.sh | bash
set -e
REPO="https://github.com/Kudozu/music-playlist-downloader"
DIR="$HOME/music-playlist-downloader"

echo "== Installation des paquets (python, ffmpeg, git)…"
pkg update -y
pkg install -y python ffmpeg git

if [ ! -d "$HOME/storage" ]; then
  echo "== Autorise l'accès au stockage dans la fenêtre qui s'ouvre"
  termux-setup-storage
  sleep 3
fi

if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone --depth 1 "$REPO" "$DIR"
fi
pip install -q -r "$DIR/requirements.txt"

# Commande "playlist" pour lancer l'appli
cat > "$PREFIX/bin/playlist" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
cd "$DIR"
git pull -q --ff-only 2>/dev/null || true
pip install -q -U yt-dlp 2>/dev/null || true
termux-wake-lock 2>/dev/null || true
(sleep 2 && termux-open-url http://localhost:5000) &
NO_BROWSER=1 python app.py
EOF
chmod +x "$PREFIX/bin/playlist"

echo
echo "== C'est installé !"
echo "   Pour lancer l'appli : tape   playlist   dans Termux."
echo "   Les musiques vont par défaut dans le dossier Music du téléphone."
