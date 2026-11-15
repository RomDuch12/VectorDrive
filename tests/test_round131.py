"""Round 131 : performances — ouverture des VND (lectures de l'archive
précompilées, points des contours en C, coordonnées vérifiées par numpy,
conversion des contours, placement des textes sans contours), premier
rendu (arcs en cubiques sans recherche adaptative), zoom des gros dessins
(aperçu mis à l'échelle, rendu net après une pause)."""
import math
import os
import struct
import tempfile
import unittest

import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts as F
from vectordrive.core import geom
from vectordrive.core import text as TX
from vectordrive.core.document import Shape
from vectordrive.core.geom import Conic
from vectordrive.io import vnd
from vectordrive.io.mfc import Archive, ArchiveError, MfcClass, MfcObject
from vectordrive.ui.canvas import conic_cubics_fast


def arc(r, ang_deg, sx=1.0, sy=1.0):
    th = math.radians(ang_deg)
    p0, p2 = (r, 0.0), (r * math.cos(th), r * math.sin(th))
    t = r / math.cos(th / 2)
    p1 = (t * math.cos(th / 2), t * math.sin(th / 2))
    return Conic((p0[0] * sx, p0[1] * sy), (p1[0] * sx, p1[1] * sy), (p2[0] * sx, p2[1] * sy), math.cos(th / 2))


def cubic_points(c, n=300):
    t = np.linspace(0, 1, n)[:, None]
    P = [np.array(v) for v in c]
    return (1 - t) ** 3 * P[0] + 3 * (1 - t) ** 2 * t * P[1] + 3 * (1 - t) * t * t * P[2] + t ** 3 * P[3]


class TestConics(unittest.TestCase):
    def test_within_a_micron(self):
        for r in (0.5, 5, 50, 500, 5000):
            for ang in (10, 90, 179):
                for sx, sy in ((1, 1), (1, 0.3), (2.5, 1)):
                    cubics = conic_cubics_fast(arc(r, ang, sx, sy), 1e-3)
                    pts = np.vstack([cubic_points(c) for c in cubics]) / np.array([sx, sy])
                    dev = np.abs(np.linalg.norm(pts, axis=1) - r).max() * max(sx, sy)
                    self.assertLess(dev, 1e-3, (r, ang, sx, sy))
                    self.assertEqual(cubics[0][0], arc(r, ang, sx, sy).p0)          # extrémités exactes
                    self.assertEqual(cubics[-1][3], arc(r, ang, sx, sy).p2)

    def test_small_arc_one_piece(self):
        self.assertEqual(len(conic_cubics_fast(arc(2, 90), 1e-3)), 1)          # erreur estimée 0,54 µm
        self.assertEqual(len(conic_cubics_fast(arc(5, 90), 1e-3)), 2)

    def test_other_weights_fall_back(self):
        c = Conic((0, 0), (5, 5), (10, 0), 1.0)                       # parabole
        self.assertTrue(conic_cubics_fast(c, 1e-3))


class TestReading(unittest.TestCase):
    def test_archive_end_of_file(self):
        ar = Archive(b'\x01\x00', 0)
        self.assertEqual(ar.u16(), 1)
        with self.assertRaises(ArchiveError):
            ar.u32()
        ar = Archive(struct.pack('<Id', 7, 2.5), 0)
        self.assertEqual((ar.u32(), ar.f64(), ar.pos), (7, 2.5, 12))
        self.assertEqual(Archive(struct.pack('<3d', 1, 2, 3), 0).f64s(3), (1.0, 2.0, 3.0))

    def test_contour_points_and_finite_flag(self):
        from vectordrive.io import vnd_write as W
        pts = [(0.001, 0.0, 0.0, 1.0, 13), (0.002, 0.001, 0.0, 0.7, 12), (0.003, 0.0, 0.0, 1.0, 13)]
        o = MfcObject(MfcClass('CContour', 1))
        o.fields = W._obdao_fields((0,) * 6)
        o.fields.update(type=0, points=pts)
        w = W.MfcWriter()
        W.WRITERS['CContour'](w, o)
        back = MfcObject(MfcClass('CContour', 1))
        vnd.read_contour(Archive(bytes(w.buf), 0, vnd.READERS), back)
        self.assertEqual(back.fields['points'], pts)
        self.assertTrue(back.fields['finite'])
        o.fields['points'] = [(float('nan'), 0.0, 0.0, 1.0, 13)] + pts[1:]
        w = W.MfcWriter()
        W.WRITERS['CContour'](w, o)
        back = MfcObject(MfcClass('CContour', 1))
        vnd.read_contour(Archive(bytes(w.buf), 0, vnd.READERS), back)
        self.assertFalse(back.fields['finite'])
        self.assertFalse(vnd.points_finite(back.fields))
        self.assertTrue(vnd.points_finite({'points': pts}))                    # sans drapeau : calculé

    def test_contour_segments(self):
        k = 1000.0
        pts = [(0, 0, 0, 1, 13), (0.01, 0, 0, 1, 13), (0.01, 0.01, 0, 1, 13), (0, 0.01, 0, 1, 13)]
        segs = vnd.contour_segments(pts, closed=True)
        self.assertEqual(len(segs), 4)                                          # refermé
        self.assertEqual(segs[0].p0, (0.0, 0.01 * k))                            # commence au dernier nœud
        conic = vnd.contour_segments([(0, 0, 0, 1, 13), (0.005 * 0.7, 0.005 * 0.7, 0, 0.7, 12),
                                      (0.01, 0, 0, 1, 13)], closed=False)
        self.assertEqual(type(conic[0]).__name__, 'Conic')
        self.assertAlmostEqual(conic[0].w, 0.7)
        self.assertEqual(conic[0].p1, (5.0, 5.0))


@unittest.skipUnless(F.find_font('Arial'), 'Arial absente')
class TestTextBox(unittest.TestCase):
    def test_layout_bbox_matches(self):
        for text, kw in (('BFM Machines', {}), ('Centré\nsur deux', {'align': 'center'}),
                         ('AVATAR Wy', {'width_ratio': 0.8, 'spacing': 0.3, 'align': 'right'})):
            a = TX.layout(text, 'Arial', 5, **kw).bbox()
            b = TX.layout_bbox(text, 'Arial', 5, **kw)
            self.assertTrue(all(abs(x - y) < 1e-9 for x, y in zip(a, b)), (text, a, b))
        self.assertIsNone(TX.layout_bbox('', 'Arial', 5))


class TestZoomPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_slow_scene_zooms_by_preview_then_refines(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.resize(900, 700)
            c = w.canvas
            for i in range(40):
                c.doc.add(Shape(path=geom.Path([geom.circle((i * 5.0, 10.0), 2.0)])))
            c.invalidate()
            c.grab()
            first = c._scene_k
            c._render_ms = 500.0                                   # dessin « lent »
            c.zoom_at(1.25, QPointF(400, 300))
            self.assertFalse(c._scene_dirty)                       # la vue a changé, pas le dessin
            c.grab()
            self.assertEqual(c._scene_k, first)                    # aperçu : scène non refaite
            self.assertTrue(c._refine.isActive())
            c._refine.stop()
            c._refine_now()
            c.grab()
            self.assertNotEqual(c._scene_k, first)                 # rendu net à la nouvelle vue
            self.assertLess(c._render_ms, 500.0)
            # dessin rapide : rendu direct à chaque zoom
            c._render_ms = 1.0
            k = c._scene_k
            c.zoom_at(1.25, QPointF(400, 300))
            c.grab()
            self.assertNotEqual(c._scene_k, k)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
