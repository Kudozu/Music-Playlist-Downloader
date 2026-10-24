## 💻 Sur ordinateur (Windows)

**Option 1 : l'exe (le plus simple)**
1. Télécharge **`MusicPlaylistDownloader.exe`** ci-dessous et double-clique dessus.
2. Si Windows affiche « Windows a protégé votre ordinateur » : **Informations complémentaires → Exécuter quand même** (l'exe n'est pas signé).
3. La page s'ouvre dans le navigateur. Si Windows demande l'accès réseau, coche **Réseaux privés** (c'est ce qui permet au téléphone de se connecter).

Tout est inclus (Python, yt-dlp, ffmpeg), et yt-dlp se met à jour tout seul.

**Option 2 : si l'exe est bloqué** (« Une stratégie de contrôle d'application a bloqué ce fichier », c'est le Contrôle intelligent des applications de Windows 11)
1. Télécharge **`MusicPlaylistDownloader-Windows.zip`**, clic droit → **Extraire tout**.
2. Double-clique sur **`Lancer.bat`**. Python s'installe tout seul s'il manque. Le premier lancement prend quelques minutes, les suivants sont rapides.

## 📱 Sur téléphone

**Le plus simple (avec le PC allumé) :** lance l'appli sur le PC, puis scanne le **QR code** affiché en bas de la page avec l'appareil photo du téléphone (même Wi-Fi). Dans le navigateur du téléphone : menu ⋮ ou Partager → **« Ajouter à l'écran d'accueil »** pour l'avoir comme une appli.
Les musiques arrivent dans le dossier choisi sur le PC ; le bouton **« Tout en ZIP »** les enregistre aussi sur le téléphone.

**Sans PC (Android uniquement) :**
1. Installe **Termux** depuis [F-Droid](https://f-droid.org/packages/com.termux/) ou [GitHub](https://github.com/termux/termux-app/releases) (pas la version du Play Store, elle est obsolète).
2. Ouvre Termux et colle :
   ```
   curl -fsSL https://raw.githubusercontent.com/0xim0/music-playlist-downloader/main/android/install.sh | bash
   ```
3. Ensuite, pour lancer l'appli : tape `playlist` dans Termux. Les musiques vont dans le dossier **Music** du téléphone.
