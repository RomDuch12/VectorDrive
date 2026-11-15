"""Round 31 : raccord automatique des contours ouverts."""
import math
import os
import pathlib
import random
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import chain as CH
from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.geom import Contour, Cubic, Line, Path
from tests.corpus import corpus


def pieces(contour, rnd, gap=0.0):
    """Contour éclaté en contours d'un segment, sens et ordre au hasard."""
    out = []
    for s in contour.segments:
        c = Contour([s], False)
        out.append(c.reversed() if rnd.random() < 0.5 else c)
    if gap:
        s = out[0].segments[0]
        out[0] = Contour([Line((s.start[0] + gap, s.start[1]), s.end)] if isinstance(s, Line) else [s], False)
    rnd.shuffle(out)
    return out


class TestChain(unittest.TestCase):
    def test_square_with_gap(self):
        rnd = random.Random(3)
        sq = geom.rect(0, 0, 10, 10)
        out, j, k = CH.chain(pieces(sq, rnd, gap=0.004), 0.01)
        self.assertEqual((j, k, len(out)), (3, 1, 1))
        c = out[0]
        self.assertTrue(c.closed)
        self.assertAlmostEqual(c.length(), 40, delta=0.01)
        for a, b in zip(c.segments, c.segments[1:] + c.segments[:1]):
            self.assertEqual(a.end, b.start)                      # recalé, sans micro-segment

    def test_curves_and_far_pieces(self):
        rnd = random.Random(5)
        circle = geom.circle((50, 50), 7)
        far = Contour([Line((0, 100), (10, 100))], False)
        bez = Contour([Cubic((0, 0), (5, 10), (15, 10), (20, 0))], False)
        tail = Contour([Line((20.005, 0), (30, 0))], False)
        out, j, k = CH.chain(pieces(circle, rnd) + [far, bez, tail], 0.01)
        closed = [c for c in out if c.closed]
        self.assertEqual(len(closed), 1)
        self.assertAlmostEqual(closed[0].length(), 2 * math.pi * 7, places=6)
        joined = [c for c in out if not c.closed and len(c.segments) == 2]
        self.assertEqual(len(joined), 1)
        self.assertEqual(joined[0].segments[0].end, joined[0].segments[1].start)
        self.assertIsInstance(joined[0].segments[0], Cubic)

    def test_closed_kept_and_tolerance(self):
        sq = geom.rect(0, 0, 5, 5)
        a = Contour([Line((10, 0), (20, 0))], False)
        b = Contour([Line((20.5, 0), (30, 0))], False)
        out, j, k = CH.chain([sq, a, b], 0.01)
        self.assertEqual((j, k), (0, 0))
        self.assertIs(out[0], sq)
        out, j, k = CH.chain([a, b], 1.0)
        self.assertEqual(j, 1)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_chain_command_and_undo(self):
        w = self.w
        rnd = random.Random(1)
        parts = [Shape(path=Path([c])) for c in pieces(geom.rect(0, 0, 30, 20), rnd)]
        keep = Shape(path=Path([geom.circle((100, 100), 5)]))
        w._add_items(parts + [keep])
        w.canvas.select([])
        self.assertEqual(w.chain_contours(0.01), (3, 1))
        items = list(w.canvas.doc.iter_items())
        self.assertEqual(len(items), 2)
        self.assertTrue(all(c.closed for it in items for c in it.path.contours))
        w.undo()
        self.assertEqual(len(list(w.canvas.doc.iter_items())), 5)

    def test_real_dxf(self):
        f = corpus('dxf_reel_1') if corpus('dxf_reel_1').exists() else None
        if f is None:
            self.skipTest('DXF de l\'atelier absent')
        import tempfile
        from PySide6.QtCore import QSettings
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.w.settings = QSettings(str(pathlib.Path(tmp.name) / 'essai.ini'), QSettings.Format.IniFormat)
        self.w.settings.setValue('import/raccord_dxf', False)
        self.w.open_path(str(f))
        self.assertEqual(self.w.chain_contours(0.01), (799, 88))
        # option active (par défaut) : déjà raccordé à l'ouverture (round 35)
        self.w.settings.setValue('import/raccord_dxf', True)
        self.w.open_path(str(f))
        self.assertIn('799 raccord(s), 88 contour(s) fermé(s)', self.w.canvas.doc.report)
        self.assertEqual(self.w.chain_contours(0.01), (0, 0))


if __name__ == '__main__':
    unittest.main()
