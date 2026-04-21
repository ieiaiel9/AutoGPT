"""
RAZ Core - Icon Generator
Generates the RAZ wing icon as a PNG using QPainter.
Black background, angled wing design, white/gold highlights.
Run once to produce assets/raz_icon.png
"""

import os
import sys
import math

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ICON_PATH = os.path.join(ASSETS_DIR, "raz_icon.png")

def generate_icon():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import (
        QPainter, QPixmap, QColor, QPen, QBrush,
        QLinearGradient, QPainterPath, QPolygonF
    )
    from PySide6.QtCore import Qt, QPointF, QRectF

    app = QApplication.instance() or QApplication(sys.argv)

    SIZE = 256
    pix = QPixmap(SIZE, SIZE)
    pix.fill(QColor(0, 0, 0, 0))  # transparent background

    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)

    cx, cy = SIZE // 2, SIZE // 2

    # ── Black circle background ───────────────────────────────────────────
    bg_grad = QLinearGradient(0, 0, SIZE, SIZE)
    bg_grad.setColorAt(0.0, QColor("#0a0a0a"))
    bg_grad.setColorAt(1.0, QColor("#000000"))
    p.setBrush(QBrush(bg_grad))
    p.setPen(Qt.NoPen)
    p.drawEllipse(4, 4, SIZE - 8, SIZE - 8)

    # ── Outer gold ring ───────────────────────────────────────────────────
    ring_pen = QPen(QColor("#c9a84c"), 3)
    p.setPen(ring_pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(6, 6, SIZE - 12, SIZE - 12)

    # ── Inner subtle white ring ───────────────────────────────────────────
    inner_pen = QPen(QColor(255, 255, 255, 30), 1)
    p.setPen(inner_pen)
    p.drawEllipse(14, 14, SIZE - 28, SIZE - 28)

    # ── Wing shape (single angled wing, right-facing) ─────────────────────
    # Main wing body - sweeping from center-left to upper-right
    wing = QPainterPath()
    wing.moveTo(cx - 70, cy + 30)       # root trailing edge
    wing.cubicTo(
        cx - 20, cy - 10,               # inner curve up
        cx + 40, cy - 55,               # sweep toward tip
        cx + 80, cy - 45                # wingtip
    )
    wing.cubicTo(
        cx + 55, cy - 20,               # tip trailing
        cx + 10,  cy + 10,              # mid sweep back
        cx - 70, cy + 30                # back to root
    )
    wing.closeSubpath()

    wing_grad = QLinearGradient(cx - 70, cy + 30, cx + 80, cy - 55)
    wing_grad.setColorAt(0.0,  QColor(255, 255, 255, 220))  # bright white root
    wing_grad.setColorAt(0.35, QColor("#e8d48a"))            # gold mid
    wing_grad.setColorAt(0.7,  QColor("#c9a84c"))            # deep gold
    wing_grad.setColorAt(1.0,  QColor(180, 150, 60, 160))   # faded tip
    p.setBrush(QBrush(wing_grad))
    p.setPen(Qt.NoPen)
    p.drawPath(wing)

    # ── Wing feather lines ─────────────────────────────────────────────────
    feather_pen = QPen(QColor(0, 0, 0, 160), 1.5)
    p.setPen(feather_pen)
    feather_lines = [
        (cx - 40, cy + 22, cx + 10,  cy - 42),
        (cx - 15, cy + 12,  cx + 35,  cy - 52),
        (cx + 10,  cy,      cx + 60,  cy - 50),
        (cx + 30,  cy - 12, cx + 75,  cy - 46),
    ]
    for x1, y1, x2, y2 in feather_lines:
        p.drawLine(int(x1), int(y1), int(x2), int(y2))

    # ── Lower secondary wing (shadow/depth) ──────────────────────────────
    shadow_wing = QPainterPath()
    shadow_wing.moveTo(cx - 65, cy + 45)
    shadow_wing.cubicTo(
        cx - 10, cy + 25,
        cx + 30, cy - 5,
        cx + 72, cy - 10
    )
    shadow_wing.cubicTo(
        cx + 50, cy + 15,
        cx,      cy + 40,
        cx - 65, cy + 45
    )
    shadow_wing.closeSubpath()

    shadow_grad = QLinearGradient(cx - 65, cy + 45, cx + 72, cy - 10)
    shadow_grad.setColorAt(0.0, QColor(200, 200, 200, 120))
    shadow_grad.setColorAt(0.5, QColor("#a08030"))
    shadow_grad.setColorAt(1.0, QColor(120, 90, 30, 80))
    p.setBrush(QBrush(shadow_grad))
    p.setPen(Qt.NoPen)
    p.drawPath(shadow_wing)

    # ── "R" lettermark at center-left ────────────────────────────────────
    from PySide6.QtGui import QFont
    font = QFont("Consolas", 28, QFont.Bold)
    p.setFont(font)
    p.setPen(QPen(QColor("#000000"), 1))
    p.drawText(QRectF(cx - 88, cy - 18, 36, 36), Qt.AlignCenter, "R")
    p.setPen(QPen(QColor("#ffffff"), 1))
    p.drawText(QRectF(cx - 90, cy - 20, 36, 36), Qt.AlignCenter, "R")

    p.end()

    os.makedirs(ASSETS_DIR, exist_ok=True)
    pix.save(ICON_PATH, "PNG")
    print(f"[ICON] Generated: {ICON_PATH}")
    return ICON_PATH


if __name__ == "__main__":
    generate_icon()
