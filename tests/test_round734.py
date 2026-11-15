"""Round 734 : Changer par un point (CHANGE, d'après CADCraft) — le bout le
plus proche de chaque trait droit amené au point, chaque cercle passant par
lui, un texte choisi seul posé dessus ; une seule annulation."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import cadtools as CT
from vectordrive.core.document import Group, Shape, Text
from vectordrive.core.geom import Affine, Path, arc, circle, polyline, rect


class TestChangePointCore(unittest.TestCase):
    def test_line_nearest_end(self):
        c = polyline([(0, 0), (10, 0), (10, 10)])
        n = CT.change_point(c, (12, 14))
        self.assertEqual((n.start, n.end), ((0, 0), (12, 14)))
        self.assertEqual(len(n.segments), 2)
        n = CT.change_point(c, (-3, 1))
        self.assertEqual((n.start, n.end), ((-3, 1), (10, 10)))
        self.assertEqual(n.segments[1], c.segments[1])          # le reste du tracé ne bouge pas

    def test_circle_keeps_centre_and_sense(self):
        for c in (circle((5, 5), 3), circle((5, 5), 3).reversed()):
            n = CT.change_point(c, (5, 13))
            centre, r = CT.circle_of(n)
            self.assertAlmostEqual(centre[0], 5, 6)
            self.assertAlmostEqual(centre[1], 5, 6)
            self.assertAlmostEqual(r, 8, 6)
            self.assertEqual(n.signed_area() > 0, c.signed_area() > 0)

    def test_ignored(self):
        self.assertIsNone(CT.change_point(rect(0, 0, 10, 5), (20, 20)))        # fermé, pas un cercle
        self.assertIsNone(CT.change_point(arc((0, 0), 5, 0, 90), (9, 9)))      # bout courbe
        self.assertIsNone(CT.change_point(polyline([(0, 0), (10, 0)]), (0, 0)))  # déjà là
        self.assertIsNone(CT.change_point(polyline([(0, 0), (1, 0), (1, 5)]), (1, 0)))  # le trait s'annulerait
        self.assertIsNone(CT.change_point(circle((0, 0), 2), (2, 0)))           # passe déjà par le point
        self.assertIsNone(CT.change_point(circle((0, 0), 2), (0, 0)))           # rayon nul


class TestChangePointUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1000, 700)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.w.canvas.doc.active_layer.items = []
        self.w._undo.clear()

    def test_lines_circle_group_one_undo(self):
        w, c = self.w, self.w.canvas
        L = c.doc.active_layer
        a = Shape(path=Path([polyline([(0, 0), (10, 0)])]), name='a')
        b = Shape(path=Path([polyline([(30, 0), (20, 5)]), circle((50, 0), 2)]), name='b')
        sq = Shape(path=Path([rect(0, 20, 5, 5)]), name='sq')
        inner = Shape(path=Path([polyline([(0, 40), (5, 40)])]), name='in')
        g = Group(children=[inner])
        L.items = [a, b, sq, g]
        c.select([a, b, sq, inner])
        new = w.cad_change((8, 8))
        self.assertEqual(sorted(it.name for it in new), ['a', 'b', 'in'])
        self.assertIn('3', w.statusBar().currentMessage())
        L = c.doc.active_layer
        a2, b2, sq2, g2 = L.items
        self.assertEqual(a2.path.contours[0].end, (8, 8))
        self.assertEqual(b2.path.contours[0].end, (8, 8))       # (20, 5) plus proche que (30, 0)
        self.assertAlmostEqual(CT.circle_of(b2.path.contours[1])[1], math.hypot(42, 8), 6)
        self.assertIs(sq2, sq)                                  # carré : écarté
        self.assertEqual(g2.children[0].path.contours[0].end, (8, 8))
        self.assertEqual({it.name for it in c.selection}, {'a', 'b', 'in'})
        w.undo()                                                # une seule annulation
        L = c.doc.active_layer
        self.assertEqual(L.items[0].path.contours[0].end, (10, 0))
        self.assertEqual(L.items[3].children[0].path.contours[0].end, (5, 40))

    def test_text_alone_and_refusals(self):
        w, c = self.w, self.w.canvas
        t = Text(text='AB', size=5, matrix=Affine.translation(3, 4), name='t')
        c.doc.active_layer.items = [t]
        c.select([t])
        new = w.cad_change((20, 30))
        self.assertEqual(new[0].matrix.apply((0.0, 0.0)), (20, 30))
        c.select([])
        self.assertEqual(w.cad_change((1, 1)), [])
        self.assertIn('Sélectionnez', w.statusBar().currentMessage())
        sq = Shape(path=Path([rect(0, 0, 5, 5)]))
        c.doc.active_layer.items = [sq]
        c.select([sq])
        n = len(w._undo)
        self.assertEqual(w.cad_change((9, 9)), [])
        self.assertIn('ignoré', w.statusBar().currentMessage())
        self.assertEqual(len(w._undo), n)                       # rien changé : pas d'annulation

    def test_pick_and_ribbon(self):
        w, c = self.w, self.w.canvas
        s = Shape(path=Path([polyline([(0, 0), (10, 0)])]))
        c.doc.active_layer.items = [s]
        c.select([s])
        self.assertEqual(w.cad_change(), [])                    # attend le clic
        self.assertEqual(c.tool, 'pick_point')
        c.tool_obj.callback((4, 6))                             # le clic accroché
        self.assertEqual(c.doc.active_layer.items[0].path.contours[0].start, (4, 6))   # (0, 0) plus proche
        from vectordrive.ui import icons
        self.assertIn('change_point', icons.ICONS)
        self.assertFalse(w.A['cad_change'].icon().isNull())
        self.assertTrue(w.A['cad_change'].toolTip())


if __name__ == '__main__':
    unittest.main()
