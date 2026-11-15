"""Round 66 : miroir sur axe."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Shape, Text
from vectordrive.core.geom import Affine, Contour, Line, Path


class TestReflection(unittest.TestCase):
    def test_matrix(self):
        m = Affine.reflection((0, 0), (1, 1))
        for p, q in (((1, 0), (0, 1)), ((3, 3), (3, 3)), ((-2, 5), (5, -2))):
            r = m.apply(p)
            self.assertAlmostEqual(r[0], q[0], places=12)
            self.assertAlmostEqual(r[1], q[1], places=12)
        mm = m @ m
        self.assertAlmostEqual(mm.a, 1, places=12)
        self.assertAlmostEqual(mm.b, 0, places=12)
        v = Affine.reflection((5, 0), (5, 10))
        self.assertEqual(tuple(round(x, 12) for x in v.apply((7, 3))), (3, 3))
        with self.assertRaises(ValueError):
            Affine.reflection((1, 1), (1, 1))

    def test_arcs_stay_exact(self):
        c = Path([geom.circle((10, 0), 3)]).transformed(Affine.reflection((0, -5), (0, 5)))
        for q in c.contours[0].flatten(1e-4):
            self.assertAlmostEqual(math.hypot(q[0] + 10, q[1]), 3, places=9)


class TestBlend(unittest.TestCase):
    def test_lines(self):
        from vectordrive.core import blend as BL
        L = math.pi
        cases = [  # (a, b, r, longueur attendue)
            (((0, 0), (10, 0)), ((10, 0), (10, 10)), 2, 8 + 8 + L),       # se touchent
            (((0, 0), (6, 0)), ((10, 4), (10, 10)), 2, 8 + 8 + L),        # à prolonger
            (((0, 0), (14, 0)), ((10, -4), (10, 10)), 1, 9 + 9 + L / 2),  # à couper
            (((0, 0), (14, 0)), ((10, -4), (10, 10)), 0, 10 + 10),        # coin vif
            (((10, 0), (0, 0)), ((10, 10), (10, 0)), 2, 8 + 8 + L),       # sens quelconques
        ]
        for a, b, r, exp in cases:
            c = BL.blend(Contour([Line(*a)], False), Contour([Line(*b)], False), r)
            self.assertIsNotNone(c, (a, b, r))
            self.assertAlmostEqual(c.length(), exp, places=9)
            for s1, s2 in zip(c.segments, c.segments[1:]):
                self.assertLess(geom.dist(s1.end, s2.start), 1e-9)

    def test_tangency_on_arc(self):
        from vectordrive.core import blend as BL
        arc = Contour(geom.arc_conics((0, 0), 10, 10, 180, 150), False)   # de (−10, 0) à (8,66, −5)
        ln = Contour([Line((5, -20), (5, 20))], False)                     # coupe l'arc en (5, −8,66)
        c = BL.blend(arc, ln, 1)
        fillet = [s for s in c.segments if isinstance(s, geom.Conic) and abs(s.circle_params()[1] - 1) < 1e-6]
        self.assertIn(len(fillet), (1, 2))                                # arc coupé en coniques de 90° au plus
        cx, cy = fillet[0].circle_params()[0]
        self.assertAlmostEqual(geom.dist((cx, cy), fillet[-1].circle_params()[0]), 0, places=9)
        self.assertAlmostEqual(math.hypot(cx, cy), 9, places=6)           # tangent intérieurement au cercle r 10
        self.assertAlmostEqual(cx, 4, places=6)                           # tangent à la droite x = 5
        self.assertEqual(c.end, (5, 20))                                  # bouts gardés : (−10, 0) et (5, 20)
        self.assertAlmostEqual(geom.dist(c.start, (-10, 0)), 0, places=9)

    def test_closed_refused(self):
        from vectordrive.core import blend as BL
        self.assertIsNone(BL.blend(geom.circle((0, 0), 1), Contour([Line((0, 0), (1, 0))], False), 1))


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_mirror_axis(self):
        from vectordrive.core import text as TX
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            sq = Shape(path=Path([geom.rect(2, 0, 3, 3)]))
            t = Text(text='F', font='Arial', size=5)
            t.outline = TX.outline_for(t)
            axis = Shape(path=Path([Contour([Line((0, -10), (0, 10))], False)]))
            w._add_items([sq, t, axis])
            w.canvas.select([sq, t, axis])
            from unittest import mock
            with mock.patch.object(type(w), '_ctrl_held', staticmethod(lambda: True)):    # Ctrl : les originaux restent
                w.mirror_axis()
            items = list(w.canvas.doc.iter_items())
            self.assertEqual(len(items), 5)                                   # originaux gardés + 2 copies
            copy_sq = next(i for i in items if isinstance(i, Shape) and i is not sq and i is not axis)
            self.assertEqual(tuple(round(v, 9) for v in copy_sq.bbox()), (-5, 0, -2, 3))
            copy_t = next(i for i in items if isinstance(i, Text) and i is not t)
            self.assertLess(copy_t.bbox()[2], 0)
            self.assertIsNone(w._axis_of(Shape(path=Path([geom.circle((0, 0), 1)]))))   # pas un axe
            bent = Shape(path=Path([Contour([Line((0, 0), (1, 0)), Line((1, 0), (1, 1))], False)]))
            self.assertIsNone(w._axis_of(bent))
            # raccordement
            from dataclasses import dataclass
            from vectordrive.ui import dialogs
            h = Shape(path=Path([Contour([Line((0, 20), (10, 20))], False)]))
            v = Shape(path=Path([Contour([Line((10, 20), (10, 30))], False)]))
            w._add_items([h, v])
            w.canvas.select([h, v])

            @dataclass
            class R:
                radius: float = 2.0

            class Fake:
                def __init__(self, *a, **k):
                    pass

                def exec(self):
                    return True

                def result_params(self):
                    return R()
            old = dialogs.ParamsDialog
            dialogs.ParamsDialog = Fake
            try:
                n0 = len(list(w.canvas.doc.iter_items()))
                w.blend_dialog()
            finally:
                dialogs.ParamsDialog = old
            self.assertEqual(len(list(w.canvas.doc.iter_items())), n0 - 1)
            self.assertAlmostEqual(w.canvas.selection[0].path.length(), 16 + math.pi, places=9)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
