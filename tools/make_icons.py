"""Génère le logo et toutes les icônes à partir d'une seule définition vectorielle.

    python tools/make_icons.py

Sorties : static/logo.svg, static/icon-*.png, static/apple-touch-icon.png, icon.ico
et les drawables Android (android-app/app/src/main/res/drawable/ic_*.xml).
Aucune dépendance : le rendu PNG est fait ici (suréchantillonnage 4x4).
"""
import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "android-app" / "app" / "src" / "main" / "res" / "drawable"

# ---------------------------------------------------------------- géométrie (repère 512 x 512)
C1, C2 = (0xFF, 0x3B, 0x5C), (0xFF, 0x8A, 0x3D)  # dégradé haut-gauche -> bas-droite
DARK = (0x14, 0x14, 0x14)
WHITE = (0xFF, 0xFF, 0xFF)
RADIUS = 116  # coins du carré arrondi

# Notes (doubles croches), dessinées dans leur propre repère puis réduites/décalées
NOTE_SCALE, NOTE_DX, NOTE_DY = 0.86, -34, -30
STEMS = [(196, 150, 228, 352), (356, 120, 388, 320)]  # x0, y0, x1, y1
BEAM = [(196, 136), (388, 104), (388, 164), (196, 196)]
HEADS = [(176, 352), (336, 320)]  # centres
HEAD_RX, HEAD_RY, HEAD_ROT = 58, 44, -22

# Pastille de téléchargement
BADGE = (388, 388)
BADGE_CUT, BADGE_R = 104, 86
SHAFT = (376, 336, 400, 392)
ARROW_HEAD = [(340, 382), (436, 382), (388, 436)]


def hexc(c):
    return "#%02X%02X%02X" % c


# ---------------------------------------------------------------- tests de contenance (rendu PNG)
def in_poly(x, y, pts):
    sign = 0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        d = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if d:
            if sign and (d > 0) != (sign > 0):
                return False
            sign = d
    return True


def in_rect(x, y, r):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def in_ellipse(x, y, c, rx, ry, rot):
    a = math.radians(rot)
    dx, dy = x - c[0], y - c[1]
    u = dx * math.cos(a) + dy * math.sin(a)
    v = -dx * math.sin(a) + dy * math.cos(a)
    return (u / rx) ** 2 + (v / ry) ** 2 <= 1


def in_notes(x, y):
    # repère des notes : on applique la transformation inverse
    x = 256 + (x - NOTE_DX - 256) / NOTE_SCALE
    y = 256 + (y - NOTE_DY - 256) / NOTE_SCALE
    return (any(in_rect(x, y, s) for s in STEMS) or in_poly(x, y, BEAM)
            or any(in_ellipse(x, y, h, HEAD_RX, HEAD_RY, HEAD_ROT) for h in HEADS))


def in_round_rect(x, y, r):
    cx = min(max(x, r), 512 - r)
    cy = min(max(y, r), 512 - r)
    return 0 <= x <= 512 and 0 <= y <= 512 and (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def gradient(x, y):
    t = min(max((x + y) / 1024, 0), 1)
    return tuple(round(a + (b - a) * t) for a, b in zip(C1, C2))


def sample(x, y, full_bleed):
    if not (full_bleed or in_round_rect(x, y, RADIUS)):
        return None
    d2 = (x - BADGE[0]) ** 2 + (y - BADGE[1]) ** 2
    if d2 <= BADGE_R ** 2:
        return WHITE if in_rect(x, y, SHAFT) or in_poly(x, y, ARROW_HEAD) else DARK
    if d2 > BADGE_CUT ** 2 and in_notes(x, y):
        return WHITE
    return gradient(x, y)


def render_png(size, full_bleed=False, n=4):
    rows = []
    k = 512 / size
    for j in range(size):
        row = bytearray([0])
        for i in range(size):
            acc = [0, 0, 0, 0]
            for a in range(n):
                for b in range(n):
                    c = sample((i + (a + 0.5) / n) * k, (j + (b + 0.5) / n) * k, full_bleed)
                    if c:
                        acc[0] += c[0]; acc[1] += c[1]; acc[2] += c[2]; acc[3] += 255
            cov = acc[3] / 255
            row += bytes([round(acc[0] / cov) if cov else 0, round(acc[1] / cov) if cov else 0,
                          round(acc[2] / cov) if cov else 0, round(acc[3] / (n * n))])
        rows.append(bytes(row))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


def write_ico(path, sizes):
    imgs = [(s, render_png(s)) for s in sizes]
    out = struct.pack("<HHH", 0, 1, len(imgs))
    offset = 6 + 16 * len(imgs)
    for s, data in imgs:
        out += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(out + b"".join(d for _, d in imgs))


# ---------------------------------------------------------------- chemins vectoriels (SVG + Android)
def f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def rect_path(r):
    return f"M{r[0]},{r[1]}H{r[2]}V{r[3]}H{r[0]}Z"


def poly_path(pts):
    return "M" + "L".join(f"{f(x)},{f(y)}" for x, y in pts) + "Z"


def ellipse_path(c, rx, ry, rot):
    a = math.radians(rot)
    p1 = (c[0] + rx * math.cos(a), c[1] + rx * math.sin(a))
    p2 = (c[0] - rx * math.cos(a), c[1] - rx * math.sin(a))
    arc = f"A{rx},{ry} {rot} 1 0 "
    return f"M{f(p1[0])},{f(p1[1])}{arc}{f(p2[0])},{f(p2[1])}{arc}{f(p1[0])},{f(p1[1])}Z"


def circle_path(c, r):
    return f"M{c[0] - r},{c[1]}A{r},{r} 0 1 0 {c[0] + r},{c[1]}A{r},{r} 0 1 0 {c[0] - r},{c[1]}Z"


NOTES_PATH = "".join([*(rect_path(s) for s in STEMS), poly_path(BEAM),
                      *(ellipse_path(h, HEAD_RX, HEAD_RY, HEAD_ROT) for h in HEADS)])
ARROW_PATH = rect_path(SHAFT) + poly_path(ARROW_HEAD)
NOTE_TRANSFORM = f"translate({f(256 - 256 * NOTE_SCALE + NOTE_DX)} {f(256 - 256 * NOTE_SCALE + NOTE_DY)}) scale({NOTE_SCALE})"


def svg_logo():
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="512" y2="512" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{hexc(C1)}"/><stop offset="1" stop-color="{hexc(C2)}"/>
    </linearGradient>
    <mask id="cut"><rect width="512" height="512" fill="#fff"/><circle cx="{BADGE[0]}" cy="{BADGE[1]}" r="{BADGE_CUT}"/></mask>
  </defs>
  <rect width="512" height="512" rx="{RADIUS}" fill="url(#g)"/>
  <g mask="url(#cut)"><path transform="{NOTE_TRANSFORM}" fill="#fff" d="{NOTES_PATH}"/></g>
  <circle cx="{BADGE[0]}" cy="{BADGE[1]}" r="{BADGE_R}" fill="{hexc(DARK)}"/>
  <path fill="#fff" d="{ARROW_PATH}"/>
</svg>
"""


def android_gradient(x1, y1, x2, y2):
    return f"""<aapt:attr name="android:fillColor">
        <gradient android:type="linear" android:startX="{f(x1)}" android:startY="{f(y1)}" android:endX="{f(x2)}" android:endY="{f(y2)}">
          <item android:offset="0" android:color="#FF{hexc(C1)[1:]}"/>
          <item android:offset="1" android:color="#FF{hexc(C2)[1:]}"/>
        </gradient>
      </aapt:attr>"""


def vector(size_dp, body):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!-- Généré par tools/make_icons.py -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:aapt="http://schemas.android.com/aapt"
    android:width="{size_dp}dp" android:height="{size_dp}dp"
    android:viewportWidth="512" android:viewportHeight="512">
{body}
</vector>
"""


def notes_group(extra=""):
    return f"""  <group android:pivotX="256" android:pivotY="256" android:scaleX="{NOTE_SCALE}" android:scaleY="{NOTE_SCALE}"
      android:translateX="{NOTE_DX}" android:translateY="{NOTE_DY}">
    <path android:fillColor="#FFFFFFFF" android:pathData="{NOTES_PATH}"/>
  </group>{extra}"""


def android_icons():
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "ic_launcher_background.xml").write_text(vector(108, f"""  <path android:pathData="M0,0H512V512H0Z">
      {android_gradient(0, 0, 512, 512)}
  </path>"""), encoding="utf-8")

    # Avant-plan : le dessin est réduit pour tenir dans la zone sûre des icônes adaptatives
    s = 0.6
    g0, g1 = 256 - 256 / s, 256 + 256 / s  # dégradé de la découpe aligné sur le fond
    (RES / "ic_launcher_foreground.xml").write_text(vector(108, f"""  <group android:pivotX="256" android:pivotY="256" android:scaleX="{s}" android:scaleY="{s}">
{notes_group()}
    <path android:pathData="{circle_path(BADGE, BADGE_CUT)}">
      {android_gradient(g0, g0, g1, g1)}
    </path>
    <path android:fillColor="#FF{hexc(DARK)[1:]}" android:pathData="{circle_path(BADGE, BADGE_R)}"/>
    <path android:fillColor="#FFFFFFFF" android:pathData="{ARROW_PATH}"/>
  </group>"""), encoding="utf-8")

    (RES / "ic_launcher_monochrome.xml").write_text(vector(108, f"""  <group android:pivotX="256" android:pivotY="256" android:scaleX="{s}" android:scaleY="{s}">
{notes_group()}
  </group>"""), encoding="utf-8")

    (RES / "ic_stat.xml").write_text(vector(24, f"""  <group android:pivotX="256" android:pivotY="256" android:scaleX="1.25" android:scaleY="1.25" android:translateX="40" android:translateY="40">
{notes_group()}
  </group>"""), encoding="utf-8")


if __name__ == "__main__":
    (ROOT / "static" / "logo.svg").write_text(svg_logo(), encoding="utf-8")
    (ROOT / "static" / "icon-192.png").write_bytes(render_png(192))
    (ROOT / "static" / "icon-512.png").write_bytes(render_png(512))
    (ROOT / "static" / "apple-touch-icon.png").write_bytes(render_png(180, full_bleed=True))
    write_ico(ROOT / "icon.ico", (16, 32, 48, 256))
    android_icons()
    print("Icônes générées.")
