"""Round 712 : Cote de longueur d'arc (comme DIMARC en DAO, d'après CADCraft) —
longueur développée, arc passant par le point choisi (plus de 180°, sens
horaire), symbole d'arc, symétrie, outil (arc en morceaux réuni, cercle
entier refusé), Tab, ruban."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import dims as D
from vectordrive.core import geom
from vectordrive.core.geom import Affine, Contour, Path


class TestCore(unittest.TestCase):
    def test_value_and_sweep(self):
        top = D.Dim('arc', [(10, 0), (0, 0), (-10, 0), (0, 10)], 14.0)
        self.assertAlmostEqual(top.value(), 10 * math.pi)
        self.assertAlmostEqual(D.arc_sweep(top.points)[3], 180.0)
        bottom = D.Dim('arc', [(10, 0), (0, 0), (-10, 0), (0, -10)], 14.0)
        self.assertAlmostEqual(D.arc_sweep(bottom.points)[3], -180.0)            # par le bas : sens horaire
        big = D.Dim('arc', [(10, 0), (0, 0), (0, 10), (0, -10)], 14.0)
        self.assertAlmostEqual(D.arc_sweep(big.points)[3], -270.0)               # plus de 180°
        self.assertAlmostEqual(big.value(), 15 * math.pi)
        short = D.Dim('arc', [(10, 0), (0, 0), (0, 10)], 14.0)                   # sans point : le petit arc
        self.assertAlmostEqual(short.value(), 5 * math.pi)
        self.assertEqual(big.label(), '47,12')
        self.assertIn('arc', D.KINDS)

    def test_build_dict_mirror(self):
        d = D.Dim('arc', [(10, 0), (0, 0), (0, 10), (0, -10)], 16.0)
        lines, filled, txt = D.build(d)
        self.assertEqual(len(filled.contours), 2)                                 # deux flèches pleines
        self.assertTrue(txt.contours)
        bb = lines.bbox()
        self.assertGreater(bb[3], 16.0)                                           # symbole au-dessus du texte
        ext = [c for c in lines.contours if len(c.segments) == 1 and isinstance(c.segments[0], geom.Line)]
        self.assertTrue(any(abs(math.dist(c.segments[0].start, (0, 0)) - 11.0) < 1e-9 for c in ext))   # écart 1 mm
        back = D.from_dict(D.to_dict(d))
        self.assertAlmostEqual(back.value(), d.value())
        m = D.from_dict(D.transformed(D.to_dict(d), Affine.mirror_y(0.0)))
        self.assertAlmostEqual(m.value(), d.value())                              # le symétrique garde son arc
        self.assertAlmostEqual(D.arc_sweep(m.points)[3], 270.0)
        inner = D.Dim('arc', [(10, 0), (0, 0), (-10, 0), (0, 10)], 6.0, D.DimStyle(orientation='horizontale'))
        ti = D.build(inner)[2].bbox()
        self.assertLess(ti[3], 6.0)                                               # arc de cote dedans : texte vers le centre
        self.assertEqual(D.build(D.Dim('arc', [(0, 0), (0, 0), (0, 0)], 5.0)), [])


class Ev:
    def modifiers(self):
        from PySide6.QtCore import Qt
        return Qt.KeyboardModifier.NoModifier


class TestTool(unittest.TestCase):
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
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage, QKeyEvent, QPainter
        from vectordrive.core.document import Shape
        from vectordrive.ui.tools import DimensionTool
        w, c = self.w, self.w.canvas
        arc = Contour(geom.arc_conics((100, 0), 20, 20, 0, 200), False)           # en trois morceaux
        self.assertGreater(len(arc.segments), 1)
        c.doc.add(Shape(path=Path([arc])))
        c.doc.add(Shape(path=Path([geom.circle((200, 0), 10)])))
        c.fit((60, -40, 220, 40))
        w.set_tool('dim_arc')
        t = c.tool_obj
        self.assertIsInstance(t, DimensionTool)
        self.assertEqual(t.mode, 'arc')
        self.click(210, 0)                                                        # cercle entier : refusé
        self.assertEqual(t.pts, [])
        self.click(100, 20)
        self.assertEqual(len(t.pts), 1)
        t.move(c.to_screen(100, 30), (100, 30), Ev())
        img = QImage(300, 200, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        t.paint(p)                                                                # aperçu
        p.end()
        self.click(100, 30)
        g = c.selection[0]
        d = D.dim_of(g)
        self.assertEqual(d.kind, 'arc')
        self.assertAlmostEqual(d.value(), 20 * math.radians(200), places=6)      # morceaux réunis
        self.assertAlmostEqual(d.offset, 30.0)
        w.undo()
        self.assertNotIn(g, c.doc.active_layer.items)
        t.mode = 'radiale'
        t.key(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(t.mode, 'arc')                                           # Tab : après la radiale
        w.set_tool('select')

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('dim_arc', icons.ICONS)
        a = self.w.A['tool_dim_arc']
        self.assertFalse(a.icon().isNull())
        self.assertTrue(a.toolTip())


if __name__ == '__main__':
    unittest.main()
