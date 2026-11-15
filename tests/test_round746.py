"""Round 746 : Extrusion d'un côté, symétrique ou des deux côtés, à travers
les volumes choisis, et réunie, soustraite ou en commun avec eux (SolidCraft :
étendue et opération de l'extrusion)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core import solids as S

app = QApplication.instance() or QApplication([])


def rb(b):
    return tuple(round(v, 3) + 0.0 for v in b)


def square(x, y, a):
    return geom.Path([geom.rect(x, y, a, a)])


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestExtent(unittest.TestCase):
    def test_sides(self):
        self.assertEqual(S.extent_sides('plus', 10), (0, 10))
        self.assertEqual(S.extent_sides('plus', -4), (-4, 0))
        self.assertEqual(S.extent_sides('sym', 10), (-5, 5))
        self.assertEqual(S.extent_sides('deux', 10, 3), (-3, 10))
        self.assertEqual(S.extent_sides('deux', -10, 3), (-10, 3))      # l'autre côté : à l'opposé du premier
        b = S.box(0, 0, 2, 10, 10, 8)
        self.assertAlmostEqual(S.through_all_distance([b], 0), 10 * 1.02 + 1)
        with self.assertRaises(S.SolidError):
            S.through_all_distance([], 0)

    def test_between(self):
        s = S.extrude_between(square(0, 0, 10), -3, 7, 1)
        self.assertEqual(rb(s.bounds()), (0, 0, -2, 10, 10, 8))
        t = S.extrude_between(square(0, 0, 10), -6, 0, 0, 10)              # dépouille vers le bas
        self.assertEqual(rb(t.bounds())[2::3], (-6, 0))
        self.assertLess(t.volume(), 600)
        with self.assertRaises(S.SolidError):
            S.extrude_between(square(0, 0, 10), -3, 3, 0, 5)              # dépouille des deux côtés
        with self.assertRaises(S.SolidError):
            S.extrude_between(square(0, 0, 10), 2, 2)

    def test_window(self):
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            base = dict(height=10.0, taper=0.0, z0=0.0, delete=True)
            sq = Shape(path=square(0, 0, 10))
            w._add_items([sq])
            c.select([sq])
            new = w.solid_extrude(params=dict(base, direction='sym'))
            self.assertEqual(rb(S.of_item(new[0]).bounds()), (0, 0, -5, 10, 10, 5))
            w.undo()
            c.select([it for it in c.doc.iter_items()])
            new = w.solid_extrude(params=dict(base, direction='deux', height2=2.0))
            self.assertEqual(rb(S.of_item(new[0]).bounds()), (0, 0, -2, 10, 10, 10))
            w.undo()
            # un bloc et un carré au milieu : à travers tout, soustrait → un trou débouchant
            block = S.make_shape(S.box(-10, -10, 0, 30, 30, 20), 0)
            w._add_items([block])
            sq = next(it for it in c.doc.iter_items() if not S.is_solid(it))
            c.select([block, sq])
            out = w.solid_extrude(params=dict(base, through=True, z0=20.0, height=-1.0,
                                              operation='subtract'))
            self.assertEqual(len(out), 1)
            r = S.of_item(out[0])
            self.assertAlmostEqual(r.volume(), 30 * 30 * 20 - 10 * 10 * 20, places=2)
            self.assertNotIn(sq, list(c.doc.iter_items()))                   # la forme remplacée
            w.undo()
            sq = next(it for it in c.doc.iter_items() if not S.is_solid(it))
            block = next(it for it in c.doc.iter_items() if S.is_solid(it))
            c.select([block, sq])
            out = w.solid_extrude(params=dict(base, z0=15.0, operation='union', delete=False))
            self.assertEqual(rb(S.of_item(out[0]).bounds()), (-10, -10, 0, 20, 20, 25))
            self.assertIn(sq, list(c.doc.iter_items()))
            w.undo()
            c.select([next(it for it in c.doc.iter_items() if S.is_solid(it)),
                      next(it for it in c.doc.iter_items() if not S.is_solid(it))])
            out = w.solid_extrude(params=dict(base, z0=15.0, operation='intersect'))
            self.assertAlmostEqual(S.of_item(out[0]).volume(), 10 * 10 * 5, places=2)
            w.undo()
            c.select([next(it for it in c.doc.iter_items() if not S.is_solid(it))])
            self.assertEqual(w.solid_extrude(params=dict(base, operation='subtract')), [])  # aucun volume choisi
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
