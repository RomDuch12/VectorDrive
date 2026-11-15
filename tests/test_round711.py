"""Round 711 : Ligne d'axe (comme CENTERLINE en DAO, d'après CADCraft) — axe
de deux traits droits, débord, trait mixte qui finit sur des tirets longs,
outil à deux clics qui reste actif, réglages F10, ruban."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import cadtools as C
from vectordrive.core.geom import Contour, Line, Path


def _pt(p, q, places=6):
    return all(abs(a - b) < 10 ** -places for a, b in zip(p, q))


class TestCore(unittest.TestCase):
    def test_center_line(self):
        a, b = C.center_line(((0, 0), (10, 0)), ((10, 4), (0, 4)))          # sens opposés : remis ensemble
        self.assertTrue(_pt(a, (-2, 2)) and _pt(b, (12, 2)))
        a, b = C.center_line(((0, 0), (10, 5)), ((0, 0), (10, -5)), 0.0)    # en V : la bissectrice
        self.assertTrue(_pt(a, (0, 0)) and _pt(b, (10, 0)))
        a, b = C.center_line(((0, 0), (20, 0)), ((5, 6), (15, 6)), 1.0)     # longueurs différentes
        self.assertTrue(_pt(a, (1.5, 3)) and _pt(b, (18.5, 3)))
        self.assertIsNone(C.center_line(((1, 1), (1, 1)), ((1, 1), (1, 1))))

    def test_axis_path(self):
        p = C.axis_path((0, 0), (0, 14))
        self.assertEqual(len(p.contours), 1)
        self.assertFalse(p.contours[0].closed)
        p = C.axis_path((0, 0), (100, 0), dashed=True)
        cs = p.contours
        self.assertEqual(len(cs), 15)                                        # 7 motifs + un tiret long
        self.assertTrue(_pt(cs[0].segments[0].start, (0, 0)))
        self.assertTrue(_pt(cs[-1].segments[-1].end, (100, 0)))
        first = math.dist(cs[0].segments[0].start, cs[0].segments[-1].end)
        last = math.dist(cs[-1].segments[0].start, cs[-1].segments[-1].end)
        self.assertAlmostEqual(first, last, places=6)                        # tirets longs aux deux bouts
        self.assertGreater(first, 4 * math.dist(cs[1].segments[0].start, cs[1].segments[-1].end))
        self.assertEqual(len(C.axis_path((0, 0), (5, 0), dashed=True).contours), 1)   # court : un seul tiret


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
        cls.msgs = []
        cls.w.canvas.measured.connect(cls.msgs.append)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def click(self, x, y):
        self.w.canvas.tool_obj.press(self.w.canvas.to_screen(x, y), (x, y), Ev())

    def test_two_clicks(self):
        from PySide6.QtGui import QImage, QPainter
        from vectordrive.core.document import Shape
        from vectordrive.ui.tools import CenterLineTool
        w, c = self.w, self.w.canvas
        w.settings.setValue('axe/tirets', False)
        w.settings.setValue('axe/debord', 3.0)
        c.doc.add(Shape(path=Path([Contour([Line((100, 0), (160, 0))], False)])))
        c.doc.add(Shape(path=Path([Contour([Line((160, 10), (100, 10))], False)])))
        c.fit((90, -20, 170, 30))
        w.set_tool('center_line')
        t = c.tool_obj
        self.assertIsInstance(t, CenterLineTool)
        self.assertEqual((t.extend, t.dashed), (3.0, False))
        self.click(130, 25)                                                  # à côté : rien
        self.assertIsNone(t.first)
        self.click(130, 0)
        self.assertIsNotNone(t.first)
        self.click(130, 0)                                                   # le même trait : refusé
        self.assertIn('autre', self.msgs[-1])
        t.move(c.to_screen(120, 10), (120, 10), Ev())
        self.assertTrue(_pt(t.hover[0], (97, 5)))                            # aperçu sous le curseur
        img = QImage(300, 200, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        t.paint(p)
        p.end()
        n = len(c.doc.active_layer.items)
        self.click(120, 10)
        sh = c.selection[0]
        seg = sh.path.contours[0].segments[0]
        self.assertTrue(_pt(seg.start, (97, 5)) and _pt(seg.end, (163, 5)))
        self.assertIs(c.tool_obj, t)                                         # l'outil reste actif
        self.assertIsNone(t.first)
        self.assertIn('66.000 mm', self.msgs[-1])
        self.assertEqual(len(c.doc.active_layer.items), n + 1)
        w.undo()
        self.assertEqual(len(c.doc.active_layer.items), n)
        w.settings.setValue('axe/tirets', True)
        w.set_tool('select')
        w.set_tool('center_line')
        self.assertTrue(c.tool_obj.dashed)
        self.click(130, 0)
        self.click(130, 10)
        self.assertGreater(len(c.selection[0].path.contours), 1)            # en trait mixte
        w.settings.setValue('axe/tirets', False)
        c.tool_obj.cancel()
        w.set_tool('select')

    def test_ribbon_options_icon(self):
        from vectordrive.ui import icons, options
        self.assertIn('center_line', icons.ICONS)
        a = self.w.A['tool_center_line']
        self.assertFalse(a.icon().isNull())
        self.assertTrue(a.toolTip())
        for k in ('axe/debord', 'axe/tirets', 'axe/echelle'):
            self.assertIn(k, options.BY_KEY)


if __name__ == '__main__':
    unittest.main()
