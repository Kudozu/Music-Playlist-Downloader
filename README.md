# 🎵 Music Playlist Downloader

Télécharge toutes les musiques d'une playlist **YouTube Music** dans le dossier de ton choix, depuis ton **PC** ou ton **téléphone**. Tout tourne en local, sans compte ni nom de domaine.

- Titre, artiste, album et pochette ajoutés aux fichiers
- Formats MP3, M4A ou Opus
- **Seulement les nouvelles musiques** : se souvient de ce qui a déjà été téléchargé pour chaque playlist et ne récupère que les nouveautés. Si l'option est désactivée, toute la playlist est retéléchargée.
- QR code pour ouvrir l'appli sur le téléphone en un scan

## ⬇️ Installation

### 💻 Windows

**[Télécharger MusicPlaylistDownloader.exe](https://github.com/0xim0/music-playlist-downloader/releases/latest/download/MusicPlaylistDownloader.exe)** puis double-clique dessus. C'est tout.

- Si Windows affiche « Windows a protégé votre ordinateur » : *Informations complémentaires → Exécuter quand même* (l'exe n'est pas signé).
- Si Windows demande l'accès réseau : coche **Réseaux privés** (nécessaire pour le téléphone).
- yt-dlp se met à jour tout seul à chaque lancement.

### 📱 Téléphone

**Avec le PC :** lance l'appli sur le PC et scanne le QR code en bas de la page (même Wi-Fi). Ensuite, menu ⋮ ou Partager → *Ajouter à l'écran d'accueil*. Le bouton *Tout en ZIP* enregistre les musiques sur le téléphone.

**Sans PC (Android) :** installe [Termux](https://f-droid.org/packages/com.termux/) (version F-Droid, pas Play Store), puis colle dans Termux :

```bash
curl -fsSL https://raw.githubusercontent.com/0xim0/music-playlist-downloader/main/android/install.sh | bash
```

Ensuite, tape `playlist` dans Termux pour lancer l'appli. Les musiques vont dans le dossier **Music** du téléphone.

### 🐍 Depuis le code source (Windows, macOS, Linux)

```bash
pip install -r requirements.txt imageio-ffmpeg
python app.py
```

Sous Windows, `Lancer.bat` fait tout ça automatiquement.

## Utilisation

1. Colle le lien de la playlist (`https://music.youtube.com/playlist?list=…`). Elle doit être publique ou non répertoriée.
2. Choisis le dossier de destination (bouton 📁).
3. Active ou non **Seulement les nouvelles musiques**, puis clique sur **Télécharger**.

La section *Playlists mémorisées* liste les playlists retenues. **Oublier** remet la mémoire d'une playlist à zéro. La mémoire est stockée dans `data/history.json`, à côté de l'exe.

## Publier une nouvelle version

```bash
git tag v1.0.1 && git push origin v1.0.1
```

GitHub Actions construit le `.exe` et crée la release automatiquement.

---

Pour un usage personnel. Respecte les droits d'auteur et les conditions d'utilisation de YouTube.
