"""Round 54 : ombrage."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom, pathops
from vectordrive.core import shadow as S
from vectordrive.core.document import Shape
from vectordrive.core.geom import Affine, Cubic, Path


class TestShadow(unittest.TestCase):
    def test_square_solid_and_drop(self):
        sq = Path([geom.rect(0, 0, 10, 10)])
        d = 2 * math.sqrt(2)
        self.assertAlmostEqual(pathops.area(S.shadow_path(sq, S.ShadowSpec('pleine', -45, d))), 40, places=6)
        self.assertAlmostEqual(pathops.area(S.shadow_path(sq, S.ShadowSpec('portee', -45, d))), 36, places=6)

    def test_disc_is_exact_on_curves(self):
        sp = S.shadow_path(Path([geom.circle((0, 0), 10)]), S.ShadowSpec(distance=5, angle=-30))
        self.assertAlmostEqual(pathops.area(sp), 2 * 10 * 5, delta=0.02)
        self.assertTrue(any(not isinstance(s, geom.Line) for c in sp.contours for s in c.segments))

    def test_ring_hole_partly_filled(self):
        r, d = 10, 5
        lens = 2 * r * r * math.acos(d / (2 * r)) - d / 2 * math.sqrt(4 * r * r - d * d)
        expected = math.pi * 400 + 2 * 20 * d - lens - math.pi * 300
        ring = Path([geom.circle((0, 0), 20), geom.circle((0, 0), 10)])
        self.assertAlmostEqual(pathops.area(S.shadow_path(ring, S.ShadowSpec(distance=d, angle=0))), expected, delta=0.05)

    def test_monotone_split(self):
        c = Cubic((0, 0), (0, 10), (10, 10), (10, 0))       # arche : tangente horizontale au sommet
        pieces = S._monotone_pieces(c, (1, 0))
        self.assertEqual(len(pieces), 2)
        self.assertAlmostEqual(pieces[0].end[1], 7.5)

    def test_gap_and_rebuild(self):
        sq = Shape(path=Path([geom.rect(0, 0, 10, 10)]))
        g = S.build([sq], S.ShadowSpec('portee', 0, 3, gap=1, keep=False))
        self.assertFalse(g.children[0].visible)
        self.assertAlmostEqual(pathops.area(g.children[1].path), 20, delta=0.01)    # 3 − 1 de large sur 10
        g2 = S.rebuild(g.transformed(Affine.translation(0, 20)), S.ShadowSpec('portee', 0, 3))
        self.assertAlmostEqual(g2.children[1].path.bbox()[1], 20, places=6)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_choices(self):
        from vectordrive.ui.dialogs import ParamsDialog
        dlg = ParamsDialog(None, 'x', S.ShadowSpec(kind='portee'), {'kind': 'Ombre'},
                           choices={'kind': [('pleine', 'P'), ('portee', 'D')]})
        self.assertEqual(dlg.fields['kind'].currentData(), 'portee')
        dlg.fields['kind'].setCurrentIndex(0)
        self.assertEqual(dlg.result_params().kind, 'pleine')

    def test_new_and_edit(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w._add_items([Shape(path=Path([geom.rect(0, 0, 10, 10)]))])
            w._shadow_dialog = lambda spec: S.ShadowSpec(distance=2, angle=0)
            w.new_shadow()
            g = w.canvas.selection[0]
            self.assertIn('shadow', g.extra)
            w._shadow_dialog = lambda spec: S.ShadowSpec(kind='portee', distance=4, angle=90)
            w._item_double_clicked(g)
            self.assertEqual(w.canvas.selection[0].extra['shadow']['distance'], 4)
            w.undo()
            gs = [it for it in w.canvas.doc.iter_items() if 'shadow' in it.extra]
            self.assertEqual([g.extra['shadow']['distance'] for g in gs], [2])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
