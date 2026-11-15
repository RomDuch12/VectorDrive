"""Round 421 : volumes — coque, arrondi des arêtes, décalage, tirer / pousser, lissage."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core import solids as S
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestCore(unittest.TestCase):
    def test_shell_offset(self):
        b = S.box(0, 0, 0, 40, 30, 20)
        self.assertAlmostEqual(S.shell(b, 2).volume(), 24000 - 36 * 26 * 16, places=3)
        op = S.shell(b, 2, open_top=True)
        self.assertAlmostEqual(op.volume(), 24000 - 36 * 26 * 18, delta=1)
        with self.assertRaises(S.SolidError):
            S.shell(b, 20)
        self.assertEqual(tuple(round(v, 4) for v in S.offset(b, -2).bounds()), (2, 2, 2, 38, 28, 18))
        self.assertEqual(tuple(round(v, 4) for v in S.offset(b, 2).bounds()), (-2, -2, -2, 42, 32, 22))

    def test_round_presspull_smooth(self):
        b = S.box(0, 0, 0, 40, 30, 20)
        r = S.round_edges(b, 3)
        self.assertEqual(tuple(round(v, 4) for v in r.bounds()), (0, 0, 0, 40, 30, 20))
        self.assertLess(r.volume(), b.volume())
        self.assertGreater(r.volume(), b.volume() - 1000)
        hole = S.presspull(b, geom.Path([geom.circle((20, 15), 5)]), -5)
        self.assertAlmostEqual(hole.volume(), 24000 - math.pi * 25 * 5, delta=3)
        boss = S.presspull(b, geom.Path([geom.circle((20, 15), 5)]), 5)
        self.assertAlmostEqual(boss.bounds()[5], 25)
        sm = S.smooth(S.box(0, 0, 0, 10, 10, 10), 3)
        self.assertGreater(len(sm.tris), 12)
        self.assertLess(sm.volume(), 1000)


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestCommands(unittest.TestCase):
    def test_commands(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            a = S.make_shape(S.box(0, 0, 0, 40, 30, 20))
            c.doc.add(a)
            c.select([a])
            got = w.solid_shell(params={'thickness': 2.0, 'open_top': True})
            self.assertAlmostEqual(S.of_item(got[0]).volume(), 24000 - 36 * 26 * 18, delta=1)
            w.undo()
            a = c.doc.layers[0].items[0]
            circ = Shape(path=geom.Path([geom.circle((20, 15), 5)]))
            c.doc.add(circ)
            c.select([a, circ])
            got = w.solid_presspull(params={'height': -5.0, 'top': True, 'z0': 0.0})
            self.assertEqual(len(got), 1)
            self.assertEqual(len(c.doc.layers[0].items), 1)                    # la forme est consommée
            self.assertAlmostEqual(S.of_item(got[0]).volume(), 24000 - math.pi * 25 * 5, delta=3)
            c.select(got)
            self.assertEqual(len(w.solid_round(params={'radius': 1.0, 'concave': False})), 1)
            c.select(c.doc.layers[0].items)
            self.assertEqual(len(w.solid_offset(params={'distance': 1.0})), 1)
            c.select(c.doc.layers[0].items)
            self.assertEqual(len(w.solid_smooth(params={'steps': 2, 'sharp': 52.5})), 1)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
