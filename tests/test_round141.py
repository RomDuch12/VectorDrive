"""Round 141 : projections de points du Mode Point de TypeEdit 13 —
verticale, horizontale, orthogonale — sur un repère (guide ou contour)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt

from vectordrive.core import geom
from vectordrive.core import nodes as N
from vectordrive.core.geom import Contour, Cubic, Line


class TestCore(unittest.TestCase):
    def test_lines(self):
        floor = Contour([Line((0, 0), (10, 0))], False)
        self.assertEqual(N.project_point(floor, (3, 5), 'v'), (3, 0))
        self.assertIsNone(N.project_point(floor, (13, 5), 'v'))          # la verticale ne le coupe pas
        self.assertIsNone(N.project_point(floor, (3, 5), 'h'))           # parallèle
        wall = Contour([Line((7, -5), (7, 5))], False)
        self.assertEqual(N.project_point(wall, (1, 2), 'h'), (7, 2))
        self.assertEqual(N.project_point(wall, (7, 9), 'v'), (7, 5))     # sur la droite : bout le plus proche
        slope = Contour([Line((0, 0), (10, 10))], False)
        q = N.project_point(slope, (0, 10), 'perp')
        self.assertAlmostEqual(q[0], 5, places=6)
        self.assertAlmostEqual(q[1], 5, places=6)

    def test_nearest_crossing(self):
        sq = geom.rect(0, 0, 10, 10)
        self.assertEqual(N.project_point(sq, (4, 2), 'v'), (4, 0))       # le bas, plus proche que le haut
        self.assertEqual(N.project_point(sq, (4, 8), 'v'), (4, 10))
        open_closing = Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 10))], True)  # fermeture implicite
        q = N.project_point(open_closing, (2, 7), 'h')
        self.assertEqual(q, (7, 7))                                       # sur la diagonale de fermeture

    def test_curves(self):
        c = Contour([Cubic((0, 0), (3, 8), (7, 8), (10, 0))], False)
        q = N.project_point(c, (4, 20), 'v')
        self.assertEqual(q[0], 4)
        _t, d = N.nearest_on_segment(c.segments[0], q)
        self.assertLess(d, 1e-6)                                         # précision de la vérification
        circ = geom.circle((0, 0), 5)
        q = N.project_point(circ, (10, 0), 'perp')
        self.assertAlmostEqual(q[0], 5, places=6)
        self.assertAlmostEqual(q[1], 0, places=6)
        q = N.project_point(circ, (3, 9), 'v')
        self.assertAlmostEqual(q[1], 4, places=9)                         # 3² + 4² = 5², côté du point

    def test_guides_and_nodes(self):
        self.assertEqual(N.project_on_guide('h', 20, (3, 5), 'v'), (3, 20))
        self.assertEqual(N.project_on_guide('h', 20, (3, 5), 'perp'), (3, 20))
        self.assertIsNone(N.project_on_guide('h', 20, (3, 5), 'h'))
        self.assertEqual(N.project_on_guide('v', -2, (3, 5), 'h'), (-2, 5))
        sq = geom.rect(0, 0, 10, 10)
        cs, n = N.project_nodes([sq], {(0, 0), (0, 1)}, lambda p: N.project_on_guide('h', 20, p, 'v'))
        self.assertEqual(n, 2)
        pts = {N.node_point(cs[0], k) for k in range(N.node_count(cs[0]))}
        moved = {N.node_point(sq, k) for k in (0, 1)}
        self.assertTrue(all((p[0], 20) in pts for p in moved))


class Ev:
    def modifiers(self):
        return Qt.KeyboardModifier.NoModifier


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1000, 700)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_mapping(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_RETOUCHE_PROJECTIONVERT'], 'node_project_v')
        self.assertEqual(TE_ACTIONS['ID_RETOUCHE_PROJECTIONHORIZ'], 'node_project_h')
        self.assertEqual(TE_ACTIONS['ID_RETOUCHE_PROJECTIONPERP'], 'node_project_perp')
        self.assertEqual(TE_ACTIONS['ID_RETOUCHE_ALIGNEVERTICAL'], 'node_align_v')     # inchangé

    def _node_mode(self):
        from vectordrive.core.document import Shape
        w = self.w
        sh = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        w.canvas.doc.add(sh)
        w.canvas.selection = [sh]
        w.set_tool('node')
        tool = w.canvas.tool_obj
        top = [k for k in range(4) if N.node_point(sh.path.contours[0], k)[1] == 10]
        tool.sel = {(0, k) for k in top}
        return w, tool, sh, top

    def test_project_on_guide_and_undo(self):
        w, tool, sh, top = self._node_mode()
        w.canvas.guides.append(['h', 25.0])
        w.node_project('v')
        self.assertEqual(tool.pending, 'v')
        sp = w.canvas.to_screen(5.0, 25.0)
        tool.press(sp, (5.0, 25.0), Ev())
        self.assertIsNone(tool.pending)
        c = tool.shape().path.contours[0]
        self.assertEqual(sorted(N.node_point(c, k)[1] for k in range(4)), [0, 0, 25, 25])
        w.undo()
        leaf = next(iter(w.canvas.doc.iter_leaves()))
        self.assertEqual(max(N.node_point(leaf.path.contours[0], k)[1] for k in range(4)), 10)

    def test_project_on_contour(self):
        from vectordrive.core.document import Shape
        w, tool, sh, top = self._node_mode()
        ref = Shape(path=geom.Path([Contour([Line((-20, 30), (40, 18))], False)]))   # pente douce
        w.canvas.doc.add(ref)
        w.node_project('perp')
        click = ref.path.contours[0].segments[0].point(0.5)
        tool.press(w.canvas.to_screen(*click), click, Ev())
        c = tool.shape().path.contours[0]
        line = ref.path.contours[0].segments[0]
        for k in top:
            _t, d = N.nearest_on_segment(line, N.node_point(c, k))
            self.assertLess(d, 1e-6)

    def test_needs_points(self):
        from PySide6.QtWidgets import QMessageBox
        w = self.w
        shown = []
        orig = QMessageBox.information
        QMessageBox.information = staticmethod(lambda *a, **k: shown.append(a))
        try:
            w.node_project('v')
        finally:
            QMessageBox.information = orig
        self.assertTrue(shown)


if __name__ == '__main__':
    unittest.main()
