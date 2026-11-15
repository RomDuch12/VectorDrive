"""Round 503 : anciennes polylignes 2D des DXF lues comme les LWPOLYLINE (arcs exacts, plus rapide) ;
vignettes gardées dans une mémoire bornée (F10 › Performances)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import ezdxf
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from vectordrive.io import dxf

app = QApplication.instance() or QApplication([])


class TestPolyline2D(unittest.TestCase):
    def test_same_as_lwpolyline(self):
        d = pathlib.Path(tempfile.mkdtemp())
        pts = [(0, 0, 0, 0, 0.5), (10, 0, 0, 0, 0), (10, 5, 0, 0, -1.0), (0, 5, 0, 0, 0)]
        a = ezdxf.new()
        a.modelspace().add_lwpolyline(pts, format='xyseb', close=True)
        a.saveas(d / 'lw.dxf')
        b = ezdxf.new()
        b.modelspace().add_polyline2d([(x, y) for x, y, *_r in pts], close=True)
        poly = next(iter(b.modelspace().query('POLYLINE')))
        for v, (_x, _y, _s, _e, bulge) in zip(poly.vertices, pts):
            v.dxf.bulge = bulge
        b.saveas(d / 'old.dxf')
        lw, old = dxf.read(d / 'lw.dxf'), dxf.read(d / 'old.dxf')
        (p1,), (p2,) = [[it.path for it in doc.iter_leaves()] for doc in (lw, old)]
        self.assertEqual(len(p2.contours), 1)
        self.assertTrue(p2.contours[0].closed)
        self.assertAlmostEqual(p1.contours[0].length(), p2.contours[0].length(), places=9)
        self.assertEqual([type(s).__name__ for s in p1.contours[0].segments],
                         [type(s).__name__ for s in p2.contours[0].segments])

    def test_fitted_polyline_left_to_ezdxf(self):
        doc = ezdxf.new()
        p = doc.modelspace().add_polyline2d([(0, 0), (5, 5), (10, 0)])
        p.dxf.flags |= 4                                        # spline ajustée : chemin générique
        self.assertFalse(dxf._plain_2d(p))


class TestImageCache(unittest.TestCase):
    def test_budget_lru(self):
        from vectordrive.ui.symbols import ImageCache
        c = ImageCache(16)                                      # 16 Mo
        img = QImage(1024, 1024, QImage.Format.Format_ARGB32)   # 4 Mo
        for k in range(6):
            c[k] = img
        self.assertLessEqual(c.used, 16 * 1024 * 1024)
        self.assertNotIn(0, c)                                  # les plus anciennes parties
        self.assertIn(5, c)
        c.get(2)                                                # vue : gardée
        c[6] = img
        self.assertIn(2, c)
        self.assertNotIn(3, c)
        c[7] = None                                             # échec de tracé gardé (petit)
        self.assertIsNone(c.get(7, 'absent'))
        c.clear()
        self.assertEqual((len(c), c.used), (0, 0))


if __name__ == '__main__':
    unittest.main()
