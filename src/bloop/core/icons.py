from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from bloop.ui.theme import C


def launcher_pixmap(size: int = 128) -> QPixmap:
    """Filled rounded mark for the dock / taskbar / .desktop icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    margin = size * 0.06
    well = QPainterPath()
    well.addRoundedRect(QRectF(margin, margin, size - 2 * margin, size - 2 * margin), size * 0.22, size * 0.22)
    painter.fillPath(well, QColor("#1a1a1a"))
    painter.setPen(QPen(QColor("#2f2f2f"), max(1, size // 48)))
    painter.drawPath(well)

    box = QRectF(size * 0.2, size * 0.28, size * 0.6, size * 0.44)
    mid = box.center()
    wave = QPainterPath()
    wave.moveTo(box.left(), mid.y())
    wave.cubicTo(
        box.left() + box.width() * 0.18, box.top(),
        box.left() + box.width() * 0.32, box.bottom(),
        mid.x(), mid.y(),
    )
    wave.cubicTo(
        box.left() + box.width() * 0.68, box.top(),
        box.left() + box.width() * 0.82, box.bottom(),
        box.right(), mid.y(),
    )
    painter.setPen(QPen(QColor(C.accent), max(2, size // 12), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(wave)
    painter.end()
    return pm


def icon_pixmap(kind: str, size: int = 72, color: str | None = None) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    accent = QColor(color or C.accent)
    painter.setPen(QPen(accent, max(2, size // 22)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    m = size * 0.18
    box = QRectF(m, m, size - 2 * m, size - 2 * m)
    k = (kind or "wave").lower()

    if k in {"wave", "pad", "sound"}:
        mid = box.center()
        path = QPainterPath()
        path.moveTo(box.left(), mid.y())
        width = box.width()
        path.cubicTo(
            box.left() + width * 0.18, box.top() + box.height() * 0.05,
            box.left() + width * 0.32, box.bottom() - box.height() * 0.05,
            mid.x(), mid.y(),
        )
        path.cubicTo(
            box.left() + width * 0.68, box.top() + box.height() * 0.08,
            box.left() + width * 0.82, box.bottom() - box.height() * 0.08,
            box.right(), mid.y(),
        )
        painter.drawPath(path)
        painter.drawLine(box.left(), mid.y(), box.right(), mid.y())
    elif k == "cable":
        painter.drawRoundedRect(box.adjusted(box.width() * 0.08, box.height() * 0.28, -box.width() * 0.08, -box.height() * 0.28), 8, 8)
        painter.drawEllipse(QRectF(box.left() + box.width() * 0.18, box.center().y() - box.height() * 0.12, box.width() * 0.22, box.height() * 0.24))
        painter.drawEllipse(QRectF(box.right() - box.width() * 0.4, box.center().y() - box.height() * 0.12, box.width() * 0.22, box.height() * 0.24))
    elif k == "stop":
        painter.setBrush(accent)
        painter.drawRoundedRect(box.adjusted(box.width() * 0.18, box.height() * 0.18, -box.width() * 0.18, -box.height() * 0.18), 4, 4)
    elif k == "folder":
        painter.drawRoundedRect(box.adjusted(0, box.height() * 0.18, 0, 0), 4, 4)
        painter.drawRoundedRect(QRectF(box.left(), box.top() + 2, box.width() * 0.42, box.height() * 0.28), 3, 3)
    else:
        painter.drawEllipse(box)

    painter.end()
    return pm


def application_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 22, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(launcher_pixmap(size))
    return icon


def tray_icon() -> QIcon:
    return application_icon()
