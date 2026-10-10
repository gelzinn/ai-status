"""Build the Windows executable icon from the project's favicon artwork."""
from pathlib import Path
import struct

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

root = Path(__file__).resolve().parents[3]
app = QGuiApplication([])
svg = QSvgRenderer(str(root / "apps/web/public/favicon.svg"))
assert svg.isValid(), "Invalid application icon"
images = []
for size in (16, 24, 32, 48, 64, 128, 256):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    svg.render(painter)
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert pixmap.save(buffer, "PNG")
    images.append((size, bytes(data)))
offset = 6 + 16 * len(images)
entries = []
for size, payload in images:
    entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(payload), offset))
    offset += len(payload)
target = root / "build/windows-app.ico"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + b"".join(payload for _, payload in images))
