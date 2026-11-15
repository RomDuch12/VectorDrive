"""Round 138 : commandes de TypeEdit 13 reliées — Affiner la courbe,
Transformer en segment / en angle (Mode Point), vues 2D YZ et ZX de la
pièce en 3D, base d'outils, couleurs d'usinage, réglages de vectorisation."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core import nodes as N
from vectordrive.core.geom import Contour, Cubic, Line


def close_paths(a: Contour, b: Contour, n: int = 200) -> float:
    pa = a.flatten(1e-4)
    from vectordrive.core.cleanup import _dist_to_polyline
    import numpy as np
    return float(_dist_to_polyline(np.asarray(pa, float), np.asarray(b.flatten(1e-4), float)).max())


class TestRefine(unittest.TestCase):
    def test_refine_keeps_path(self):
        for c in (geom.rect(0, 0, 10, 5), geom.circle((2, 3), 4),
                  Contour([Line((0, 0), (5, 0)), Cubic((5, 0), (7, 2), (7, 4), (5, 6))], False)):
            r = N.refine(c)
            self.assertEqual(len(r.segments), 2 * len(c.segments))
            self.assertEqual(N.node_count(r) - (0 if c.closed else 1), 2 * len(c.segments))
            self.assertLess(close_paths(r, c), 1e-6)
            self.assertAlmostEqual(r.length(), c.length(), delta=1e-5 * c.length())
            self.assertEqual(r.closed, c.closed)

    def test_midpoints(self):
        r = N.refine(geom.rect(0, 0, 10, 4))
        pts = {tuple(round(v, 9) for v in s.end) for s in r.segments}
        for m in ((5, 0), (10, 2), (5, 4), (0, 2)):
            self.assertIn(m, pts)


class TestPortion(unittest.TestCase):
    def square(self):
        return geom.rect(0, 0, 10, 10)                 # fermé, 4 droites

    def test_open(self):
        c = Contour([Line((0, 0), (1, 0)), Line((1, 0), (2, 1)), Line((2, 1), (3, 0)), Line((3, 0), (4, 0))], False)
        self.assertEqual(N.portion(c, 1, 3), [1, 2])
        self.assertEqual(N.portion(c, 3, 1), [1, 2])
        s = N.to_segment(c, 1, 3)
        self.assertEqual(len(s.segments), 3)
        self.assertEqual(s.segments[1], Line((1, 0), (3, 0)))
        self.assertFalse(s.closed)

    def test_closed_shorter_and_other(self):
        c = Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 1)), Line((10, 1), (0, 1)), Line((0, 1), (0, 0))], True)
        # nœud k = fin du segment k : nœud 0 = (10, 0), nœud 1 = (10, 1)
        self.assertEqual(N.portion(c, 0, 1), [1])                  # 1 mm plutôt que 21
        self.assertEqual(N.portion(c, 0, 1, other=True), [2, 3, 0])
        s = N.to_segment(c, 0, 1, other=True)                      # à cheval sur le départ
        self.assertTrue(s.closed)
        self.assertEqual(len(s.segments), 2)
        ends = {s.segments[0].start, s.segments[0].end}
        self.assertEqual(ends, {(10, 0), (10, 1)})

    def test_wrap_keeps_geometry(self):
        c = geom.circle((0, 0), 5)                                  # 4 quarts : nœuds (0,5) (-5,0) (0,-5) (5,0)
        self.assertEqual(len(c.segments), 4)
        self.assertEqual(N.portion(c, 0, 1), [1])
        self.assertEqual(N.portion(c, 0, 1, other=True), [2, 3, 0])  # à cheval sur le départ
        s = N.to_segment(c, 0, 1, other=True)
        self.assertTrue(s.closed)
        self.assertEqual(len(s.segments), 2)                        # un quart d'arc et sa corde
        self.assertIs(s.segments[0], c.segments[1])
        ln = s.segments[1]
        self.assertIsInstance(ln, Line)
        self.assertEqual((ln.p0, ln.p1), (c.segments[1].end, c.segments[1].start))
        self.assertAlmostEqual(s.signed_area(), math.pi * 25 / 4 - 12.5, delta=0.02)

    def test_angle_tangents(self):
        # arc de cercle d'un quart : tangentes en (5, 0) verticale et en (0, 5) horizontale → sommet (5, 5)
        arc = Contour(geom.arc_conics((0, 0), 5, 5, 0, 90), False)
        c = Contour([Line((5, -3), (5, 0))] + arc.segments + [Line((0, 5), (-3, 5))], False)
        k_end = len(c.segments) - 1
        r = N.to_angle(c, 1, k_end)
        apex = r.segments[1].end
        self.assertAlmostEqual(apex[0], 5, places=9)
        self.assertAlmostEqual(apex[1], 5, places=9)
        self.assertEqual(len(r.segments), 4)

    def test_angle_fallback_and_flat(self):
        # tangentes parallèles (demi-cercle) : sommet au point le plus éloigné de la corde
        half = Contour(geom.arc_conics((0, 0), 5, 5, 0, 180), False)
        r = N.to_angle(half, 0, N.node_count(half) - 1)
        apex = r.segments[0].end
        self.assertAlmostEqual(apex[1], 5, delta=0.05)
        self.assertAlmostEqual(apex[0], 0, delta=0.5)
        flat = Contour([Line((0, 0), (5, 0)), Line((5, 0), (10, 0))], False)
        self.assertIs(N.to_angle(flat, 0, 2), flat)                # déjà droit


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

    def test_actions_and_mapping(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        for cmd, key in (('ID_MODE_POINT_REFINE', 'node_refine'), ('ID_CONTOUR_RABOT', 'tool_portion_segment'),
                         ('ID_CONTOUR_SETANGLE', 'tool_portion_angle'), ('ID_AFFICHAGE_VUE2DYZ', 'view_yz'),
                         ('ID_AFFICHAGE_VUE2DZX', 'view_zx'), ('ID_MACHINING_TOOLSDATABASE', 'tool_library'),
                         ('ID_FILE_VECTORIZEPARAMETERS', 'trace'), ('ID_COLOR_USI', 'tools_table')):
            self.assertEqual(TE_ACTIONS[cmd], key)
            self.assertIn(key, self.w.A)

    def test_refine_selection_undo(self):
        from vectordrive.core.document import Shape
        w = self.w
        sh = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        w.canvas.doc.add(sh)
        w.canvas.selection = [sh]
        w.refine_curves()
        new = w.canvas.selection[0]
        self.assertEqual(len(new.path.contours[0].segments), 8)
        w.undo()
        leaves = list(w.canvas.doc.iter_leaves())
        self.assertEqual(len(leaves[0].path.contours[0].segments), 4)

    def test_node_portion(self):
        from vectordrive.core.document import Shape
        w = self.w
        c = Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 1)), Line((10, 1), (0, 1)), Line((0, 1), (0, 0))], True)
        sh = Shape(path=geom.Path([c]))
        w.canvas.doc.add(sh)
        w.canvas.selection = [sh]
        w.set_tool('node')
        tool = w.canvas.tool_obj
        self.assertEqual(type(tool).__name__, 'NodeTool')
        tool.sel = {(0, 3), (0, 1)}                                 # (0, 0) et (10, 1)
        w.node_portion('segment')
        segs = tool.shape().path.contours[0].segments
        self.assertEqual(len(segs), 3)
        self.assertIn(Line((10, 1), (0, 0)), segs + [s.reversed() for s in segs])

    def test_side_views(self):
        w = self.w
        w.set_3d_view('yz')
        self.assertEqual(w.view_mode(), '3d')
        self.assertEqual((w.panel3d.view.yaw, w.panel3d.view.pitch), (90.0, 0.0))
        w.A['view_zx'].trigger()
        self.assertEqual((w.panel3d.view.yaw, w.panel3d.view.pitch), (0.0, 0.0))
        w.set_view_mode('2d')


if __name__ == '__main__':
    unittest.main()
