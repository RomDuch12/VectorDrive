"""Round 445 : image claire sur fond transparent reconnue (affichée sur fond sombre, vectorisée
d'après sa forme) ; vectorisation : longueur des segments, courbure continue (lissage C∞)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from vectordrive.core import trace as TR

app = QApplication.instance() or QApplication([])


def ring(white: bool, size: int = 120) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor('white' if white else 'black'))
    p.drawEllipse(QRectF(10, 10, size - 20, size - 20))
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    p.drawEllipse(QRectF(size * 0.35, size * 0.35, size * 0.3, size * 0.3))
    p.end()
    return img


class TestLightImage(unittest.TestCase):
    def test_detect_and_gray(self):
        from vectordrive.ui.dialogs import light_on_transparent, qimage_gray
        self.assertTrue(light_on_transparent(ring(True)))
        self.assertFalse(light_on_transparent(ring(False)))
        for white in (True, False):                       # même forme, blanche ou noire : mêmes contours
            g = qimage_gray(ring(white))
            self.assertLess(g[60, 15], 0.3)                # anneau : encre
            self.assertGreater(g[60, 60], 0.7)             # trou : fond
            self.assertEqual(len(TR.trace(g, TR.TraceSpec())), 2)

    def test_canvas_backdrop(self):
        from PySide6.QtCore import QBuffer, QIODevice
        from vectordrive.core.document import Image
        from vectordrive.core.geom import Affine
        from vectordrive.ui.main_window import MainWindow
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        ring(True).save(buf, 'PNG')
        w = MainWindow()
        try:
            im = Image(data=bytes(buf.data()), fmt='png', matrix=Affine(40, 0, 0, -40, 0, 40))
            w.canvas.doc.add(im)
            w.canvas.resize(300, 300)
            w.canvas.fit((0, 0, 40, 40))
            shot = w.canvas.grab().toImage()
            pt = w.canvas.to_screen(20, 20)                # centre de l'anneau (trou) : fond sombre visible
            self.assertLess(QColor(shot.pixel(int(pt.x()), int(pt.y()))).lightness(), 120)
        finally:
            w.modified = False
            w.close()


def disk(n: int = 60) -> np.ndarray:
    y, x = np.mgrid[0:n, 0:n]
    return np.where((x - n / 2 + 0.5) ** 2 + (y - n / 2 + 0.5) ** 2 < (n / 3) ** 2, 0.0, 1.0)


def max_turn(c) -> float:
    pts = c.flatten(0.01)
    turns = []
    for a, b, d in zip(pts, pts[1:], pts[2:]):
        u = (b[0] - a[0], b[1] - a[1])
        v = (d[0] - b[0], d[1] - b[1])
        nu, nv = math.hypot(*u), math.hypot(*v)
        if nu > 1e-9 and nv > 1e-9:
            turns.append(math.degrees(math.acos(max(-1, min(1, (u[0] * v[0] + u[1] * v[1]) / (nu * nv))))))
    return max(turns)


class TestSegments(unittest.TestCase):
    def test_segment_length(self):
        g = disk()
        c = TR.trace(g, TR.TraceSpec(segment=8.0))[0]
        lengths = [math.dist(s.point(0.0), s.point(1.0)) for s in c.segments]
        self.assertAlmostEqual(sum(lengths) / len(lengths), 8.0, delta=1.0)

    def test_curvature_smoother(self):
        g = disk()
        plain = TR.trace(g, TR.TraceSpec(smooth=False))[0]
        fair = TR.trace(g, TR.TraceSpec(curvature=True, smoothing=2.0, segment=4.0, corner_angle=170))[0]
        self.assertLess(max_turn(fair), max_turn(plain))
        r = [math.dist(s.point(0.0), (30.0, 30.0)) for s in fair.segments]
        self.assertLess(max(r) - min(r), 1.2)              # reste un cercle


if __name__ == '__main__':
    unittest.main()
