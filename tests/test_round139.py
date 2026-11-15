"""Round 139 : Aligner suivant un axe vertical / horizontal (TypeEdit) —
redresser un objet en le faisant tourner autour d'un point pour qu'un autre
point soit à sa verticale ou à son horizontale."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QPointF

from vectordrive.core import geom
from vectordrive.core.geom import Affine


class TestAngle(unittest.TestCase):
    def test_smallest_rotation(self):
        from vectordrive.ui.tools import AxisAlignTool as T
        self.assertAlmostEqual(T.angle((0, 0), (1, 10), 'v'), math.degrees(math.atan2(1, 10)))  # presque vertical
        self.assertAlmostEqual(T.angle((0, 0), (10, 1), 'h'), -math.degrees(math.atan2(1, 10)))
        self.assertAlmostEqual(T.angle((0, 0), (-10, 1), 'h'), math.degrees(math.atan2(1, 10)))   # vers la gauche
        self.assertAlmostEqual(T.angle((0, 0), (1, -10), 'v'), -math.degrees(math.atan2(1, 10)))  # vers le bas
        for q in ((3, 7), (-4, 2), (5, -6), (-1, -9), (8, 0.5)):
            for axis in 'vh':
                a = T.angle((2, 1), q, axis)
                self.assertLessEqual(abs(a), 90 + 1e-9)
                x, y = Affine.rotation(a, (2, 1)).apply(q)
                if axis == 'v':
                    self.assertAlmostEqual(x, 2, places=9)
                else:
                    self.assertAlmostEqual(y, 1, places=9)


class Ev:
    def modifiers(self):
        from PySide6.QtCore import Qt
        return Qt.KeyboardModifier.NoModifier


class TestTool(unittest.TestCase):
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

    def test_straighten_and_undo(self):
        from vectordrive.core.document import Shape
        from vectordrive.ui.shortcuts import TE_ACTIONS
        w = self.w
        self.assertEqual(TE_ACTIONS['ID_COMPO_ALIGNER_ALIGNEROTVERTI'], 'tool_axis_v')
        self.assertEqual(TE_ACTIONS['ID_COMPO_ALIGNER_ALIGNEROTHORIZ'], 'tool_axis_h')
        tilted = geom.rect(0, 0, 20, 10).transformed(Affine.rotation(7, (0, 0)))
        sh = Shape(path=geom.Path([tilted]))
        w.canvas.doc.add(sh)
        w.canvas.selection = [sh]
        w.A['tool_axis_h'].trigger()
        tool = w.canvas.tool_obj
        self.assertEqual(type(tool).__name__, 'AxisAlignTool')
        p0 = tilted.segments[0].start                  # coin (0, 0)
        p1 = tilted.segments[0].end                    # coin (20, 0) tourné de 7°
        tool.press(QPointF(), p0, Ev())
        tool.move(QPointF(), p1, Ev())
        w.canvas.grab()                                 # dessine l'aperçu
        tool.press(QPointF(), p1, Ev())
        new = w.canvas.selection[0]
        c = new.path.contours[0]
        a, b = c.segments[0].start, c.segments[0].end
        self.assertAlmostEqual(b[1], a[1], places=9)    # bord du bas redevenu horizontal
        self.assertAlmostEqual(a[0], p0[0], places=9)   # pivot immobile
        self.assertEqual(w.canvas.tool, 'select')       # outil terminé
        w.undo()
        leaf = next(iter(w.canvas.doc.iter_leaves()))
        self.assertAlmostEqual(leaf.path.contours[0].segments[0].end[1], p1[1], places=9)

    def test_needs_selection(self):
        w = self.w
        w.A['tool_axis_v'].trigger()
        msgs = []
        w.canvas.measured.connect(msgs.append)
        w.canvas.tool_obj.press(QPointF(), (0, 0), Ev())
        self.assertIsNone(w.canvas.tool_obj.pivot)
        self.assertTrue(msgs)


if __name__ == '__main__':
    unittest.main()
