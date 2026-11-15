"""
Draws the Wield icon and writes assets/icons/wield.png (512px),
assets/icons/wield.ico (16-256px, for the .exe and taskbar), and the
website's images/icon.png (256px) and favicon.png (64px).

    python -m tools.make_icon

The mark: two "peace sign" Vs, one lilac and one peach, overlapping to
form a W on a deep night-violet rounded square. A Wield gesture is the
letter itself. Small light dots mark the fingertips.
"""

import os
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)

BG_TOP = "#2A2150"
BG_BOTTOM = "#15112B"
LILAC = "#B7A6FF"
PEACH = "#FFB38A"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "icons")
WEB_DIR = os.path.join(ROOT, "website")

# The two Vs, in a 512-unit box: (left tip, bottom, right tip).
LEFT_V = ((98, 150), (182, 372), (266, 150))
RIGHT_V = ((246, 150), (330, 372), (414, 150))
STROKE = 58
TIP_DOT = 13


def _v_path(points, k):
    path = QPainterPath(QPointF(points[0][0] * k, points[0][1] * k))
    for x, y in points[1:]:
        path.lineTo(QPointF(x * k, y * k))
    return path


def draw_icon(size):

    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)

    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)

    s = float(size)
    k = s / 512.0

    background = QLinearGradient(0, 0, s, s)
    background.setColorAt(0, QColor(BG_TOP))
    background.setColorAt(1, QColor(BG_BOTTOM))
    p.setPen(Qt.NoPen)
    p.setBrush(background)
    p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.23, s * 0.23)

    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(LILAC), STROKE * k, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(_v_path(LEFT_V, k))

    # Screen blending lightens where the two fingers cross.
    p.setCompositionMode(QPainter.CompositionMode_Screen)
    p.setPen(QPen(QColor(PEACH), STROKE * k, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(_v_path(RIGHT_V, k))
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)

    # Fingertip dots, left out at tiny sizes where they would only blur.
    if size >= 48:
        tip = QColor("#FFFFFF")
        tip.setAlphaF(0.7)
        p.setPen(Qt.NoPen)
        p.setBrush(tip)
        for x, y in (LEFT_V[0], LEFT_V[2], RIGHT_V[0], RIGHT_V[2]):
            p.drawEllipse(QPointF(x * k, y * k), TIP_DOT * k, TIP_DOT * k)

    p.end()
    return image


def main():

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    os.makedirs(OUT_DIR, exist_ok=True)

    png = os.path.join(OUT_DIR, "wield.png")
    draw_icon(512).save(png)

    # Each .ico size is drawn on its own so small sizes stay crisp.
    from PIL import Image
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = []
    for size in sizes:
        tmp = os.path.join(OUT_DIR, f"_icon_{size}.png")
        draw_icon(size).save(tmp)
        frames.append(Image.open(tmp).convert("RGBA"))
    frames[-1].save(
        os.path.join(OUT_DIR, "wield.ico"),
        sizes=[(n, n) for n in sizes],
        append_images=frames[:-1],
    )
    for size in sizes:
        os.remove(os.path.join(OUT_DIR, f"_icon_{size}.png"))

    if os.path.isdir(WEB_DIR):
        draw_icon(256).save(os.path.join(WEB_DIR, "images", "icon.png"))
        draw_icon(64).save(os.path.join(WEB_DIR, "favicon.png"))

    print("Wrote", png, "wield.ico and the website icons")


if __name__ == "__main__":
    main()
