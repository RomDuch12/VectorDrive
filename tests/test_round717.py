"""Round 717 : cote radiale à ressaut (comme DIMJOGGED : la ligne part d'un
centre déporté et rejoint le rayon par un ressaut) et ressaut de ligne de
cote (comme DIMJOGLINE), d'après CADCraft."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import dims as D
from vectordrive.core import geom
from vectordrive.core.geom import Path


def _pts(contour):
    return [contour.segments[0].start] + [s.end for s in contour.segments]


class TestJogged(unittest.TestCase):
    c, r = (0.0, 0.0), 100.0

    def radial(self, o, **style):
        st = D.DimStyle()
        for k, v in style.items():
            setattr(st, k, v)
        return D.Dim('radiale', [self.c, (60.0, 80.0), o], 5.0, st)

    def test_jogged(self):
        u, n = (0.6, 0.8), (-0.8, 0.6)
        o = (u[0] * 50 + n[0] * 10, u[1] * 50 + n[1] * 10)
        d = self.radial(o)
        self.assertEqual(d.value(), 100.0)
        self.assertEqual(d.label(), 'R100,00')
        line = D.build(d)[0].contours[0]
        pts = _pts(line)
        self.assertEqual(len(pts), 5)                                            # départ, ressaut (2), arc, texte
        for (x, y), (ex, ey) in ((pts[0], o), (pts[3], (60.0, 80.0))):
            self.assertAlmostEqual(x, ex)
            self.assertAlmostEqual(y, ey)
        a, b, j1 = pts[0], pts[1], pts[2]
        self.assertAlmostEqual((b[0] - a[0]) * n[0] + (b[1] - a[1]) * n[1], 0.0)    # parallèle au rayon
        self.assertAlmostEqual(j1[0] * n[0] + j1[1] * n[1], 0.0)                    # puis sur le rayon
        dj = (j1[0] - b[0], j1[1] - b[1])
        self.assertAlmostEqual(abs(dj[0] * u[0] + dj[1] * u[1]), abs(dj[0] * n[0] + dj[1] * n[1]))   # à 45°
        self.assertTrue(0 < (j1[0] * u[0] + j1[1] * u[1]) < 100.0)

    def test_fallbacks(self):
        straight = _pts(D.build(self.radial((30.0, 40.0)))[0].contours[0])
        self.assertEqual(len(straight), 3)                                       # sur le rayon : raccourcie
        self.assertAlmostEqual(straight[0][0], 30.0)
        plain = _pts(D.build(self.radial((90.0, 120.0)))[0].contours[0])
        self.assertEqual(plain[0], self.c)                                       # hors du cercle : depuis le centre
        steep = _pts(D.build(self.radial((0.6 * 90 - 0.8 * 30, 0.8 * 90 + 0.6 * 30)))[0].contours[0])
        self.assertEqual(len(steep), 5)                                          # ressaut plus raide, reste dedans
        dia = D.build(self.radial((30.0, 0.0), diameter=True))[0].contours[0]
        self.assertAlmostEqual(_pts(dia)[0][0], -60.0)                           # diamètre : pas de ressaut
        g = D.group(self.radial((20.0, 10.0)))
        self.assertEqual(len(D.dim_of(g.transformed(geom.Affine.rotation(90.0))).points), 3)


class TestJogLine(unittest.TestCase):
    def test_jog_line(self):
        plain = D.build(D.Dim('libre', [(0, 0), (60, 0)], 8.0))[0]
        lines = D.build(D.Dim('libre', [(0, 0), (60, 0), (15, 0)], 8.0))[0]
        self.assertEqual(len(lines.contours), len(plain.contours) + 2)           # ligne en deux, zigzag
        zig = [c for c in lines.contours if len(c.segments) == 3]
        self.assertEqual(len(zig), 1)
        h = 1.5 * D.DimStyle().text_height
        zx0, zy0, zx1, zy1 = zig[0].bbox()
        self.assertAlmostEqual((zx0 + zx1) / 2, 15.0)
        self.assertAlmostEqual(zy1 - zy0, h)
        on_line = [c for c in lines.contours if c.bbox()[1] == c.bbox()[3] == 8.0 and len(c.segments) == 1]
        self.assertEqual(sorted(round(c.bbox()[0], 6) for c in on_line), [0.0, round(15 + h / 2, 6)])
        cut = D.build(D.Dim('libre', [(0, 0), (60, 0), (10, 0)], 8.0, D.DimStyle(text_offset=0.0)))[0]
        self.assertEqual(len([c for c in cut.contours if c.bbox()[1] == c.bbox()[3] == 8.0]), 3)   # texte et ressaut
        mid = D.build(D.Dim('libre', [(0, 0), (60, 0), (30, 0)], 8.0, D.DimStyle(text_offset=0.0)))[0]
        self.assertFalse([c for c in mid.contours if len(c.segments) == 3])      # sur le texte : pas de ressaut
        short = D.build(D.Dim('libre', [(0, 0), (4, 0), (2, 0)], 8.0))[0]
        self.assertFalse([c for c in short.contours if len(c.segments) == 3])
        far = D.build(D.Dim('horizontale', [(0, 0), (60, 5), (500, -40)], 8.0))[0]
        z = [c for c in far.contours if len(c.segments) == 3][0]
        self.assertAlmostEqual(z.bbox()[2], 60.0)                                # ramené sur la ligne


class Ev:
    def modifiers(self):
        from PySide6.QtCore import Qt
        return Qt.KeyboardModifier.NoModifier


class TestUi(unittest.TestCase):
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

    def click(self, x, y):
        self.w.canvas.tool_obj.press(self.w.canvas.to_screen(x, y), (x, y), Ev())

    def test_tool(self):
        from PySide6.QtGui import QImage, QPainter
        from vectordrive.core.document import Shape
        w, c = self.w, self.w.canvas
        c.doc.add(Shape(path=Path([geom.circle((0, 0), 100)])))
        c.fit((-120, -120, 120, 120))
        w.set_tool('dim_jogged')
        t = c.tool_obj
        self.assertEqual(t.mode, 'rayon_ressaut')
        self.click(60, 80)
        self.click(66, 88)
        self.assertEqual(len(t.pts), 2)
        t.move(c.to_screen(20, 40), (20, 40), Ev())
        img = QImage(300, 200, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        t.paint(p)                                                                # aperçu avec le ressaut
        p.end()
        self.click(20, 40)
        d = D.dim_of(c.selection[0])
        self.assertEqual((d.kind, len(d.points)), ('radiale', 3))
        self.assertAlmostEqual(d.value(), 100.0)
        self.assertEqual(tuple(d.points[2]), (20, 40))
        self.assertEqual(t.pts, [])
        w.set_tool('select')

    def test_jog_line_action(self):
        w, c = self.w, self.w.canvas
        g = D.group(D.Dim('libre', [(0, 0), (80, 0)], 8.0))
        c.doc.add(g)
        c.select([g])
        self.assertEqual(w.dim_jog_line({'position': 25.0}), 1)
        self.assertEqual(D.dim_of(g).points[2], (20.0, 0.0))
        w.dim_jog_line({'position': 0.0})
        self.assertEqual(len(D.dim_of(g).points), 2)                             # retiré
        w.undo()
        g = next(it for it in c.doc.active_layer.items if (d := D.dim_of(it)) and d.points[1][0] == 80)
        self.assertEqual(len(D.dim_of(g).points), 3)
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as mb:
            c.select([])
            self.assertEqual(w.dim_jog_line({'position': 25.0}), 0)
            self.assertTrue(mb.called)

    def test_ribbon_icons(self):
        from vectordrive.ui import icons
        for k, a in (('dim_jogged', 'tool_dim_jogged'), ('dim_jog_line', 'dim_jog_line')):
            self.assertIn(k, icons.ICONS)
            self.assertFalse(self.w.A[a].icon().isNull())
            self.assertTrue(self.w.A[a].toolTip())


if __name__ == '__main__':
    unittest.main()
