#!/usr/bin/env bash
# Test de l'APK sur l'émulateur de la CI : installation, lancement, serveur qui répond,
# puis essai de téléchargement d'un titre (non bloquant : YouTube filtre souvent les IP de datacenter).
set -u
PKG=com.kudozu.playlistdownloader
APK=${1:-PlaylistDownloader.apk}

adb install -r "$APK" || exit 1
adb shell appops set $PKG MANAGE_EXTERNAL_STORAGE allow
adb shell pm grant $PKG android.permission.POST_NOTIFICATIONS || true
adb shell am start -n $PKG/.MainActivity
adb forward tcp:8765 tcp:8765

for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8765/api/settings; then echo; up=1; break; fi
  sleep 3
done
if [ -z "${up:-}" ]; then
  echo "Le serveur ne répond pas"; adb logcat -d | grep -iE "python|chaquopy|playlist|AndroidRuntime" | tail -80; exit 1
fi
curl -sf http://127.0.0.1:8765/ | grep -q "Playlist Downloader" || { echo "Page introuvable"; exit 1; }
adb exec-out screencap -p > screenshot.png

id=$(curl -sf -X POST http://127.0.0.1:8765/api/download -H 'Content-Type: application/json' \
  -d '{"url":"https://music.youtube.com/watch?v=K4DyBUG242c","folder":"/storage/emulated/0/Music/test","format":"m4a","only_new":false}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
for i in $(seq 1 60); do
  job=$(curl -sf http://127.0.0.1:8765/api/jobs/$id)
  echo "$job" | grep -q '"status":"running"' || break
  sleep 3
done
echo "$job" | python3 -c 'import sys,json;j=json.load(sys.stdin);print(j["status"]);print("\n".join(j["log"]))'
adb shell ls -la /storage/emulated/0/Music/test || true
echo "OK : l'APK démarre et le serveur répond"
