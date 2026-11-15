"""Round 140 : Aligner et centrer (les deux axes), Déplacer un contour d'un
objet sans le décombiner (TypeEdit 13)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QPointF, Qt

from vectordrive.core import geom


class Ev:
    def __init__(self, mods=Qt.KeyboardModifier.NoModifier):
        self.mods = mods

    def modifiers(self):
        return self.mods


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.canvas.doc.plate = None                    # référence : le premier objet sélectionné

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_mapping(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_MANIPULER_ZONE_ALIGNER'], 'align_center')
        self.assertEqual(TE_ACTIONS['ID_CONTOUR_MOVE'], 'tool_contour_move')
        for k in ('align_center', 'tool_contour_move'):
            self.assertIn(k, self.w.A)

    def test_align_center(self):
        from vectordrive.core.document import Shape
        w = self.w
        a = Shape(path=geom.Path([geom.rect(0, 0, 40, 20)]))
        b = Shape(path=geom.Path([geom.circle((100, 70), 5)]))
        w.canvas.doc.add(a)
        w.canvas.doc.add(b)
        w.canvas.selection = [a, b]
        w.A['align_center'].trigger()
        bb = [it for L in w.canvas.doc.layers for it in L.items if it.id == b.id][0].bbox()
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 20, places=9)
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, 10, places=9)
        w.undo()
        bb = [it for L in w.canvas.doc.layers for it in L.items if it.id == b.id][0].bbox()
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 100, places=9)

    def test_move_one_contour(self):
        from vectordrive.core.document import Shape
        w = self.w
        sh = Shape(path=geom.Path([geom.rect(0, 0, 40, 30), geom.circle((10, 10), 4)]))
        w.canvas.doc.add(sh)
        w.canvas.selection = [sh]
        w.A['tool_contour_move'].trigger()
        tool = w.canvas.tool_obj
        self.assertEqual(type(tool).__name__, 'ContourMoveTool')
        grab = (14.0, 10.0)                                # sur le cercle
        self.assertEqual(tool.find(QPointF(), grab)[1], 1)
        tool.press(QPointF(), grab, Ev())
        tool.move(QPointF(), (19.0, 12.0), Ev())
        w.canvas.grab()                                    # aperçu
        tool.release(QPointF(), (19.0, 12.0), Ev())
        rect, circ = sh.path.contours
        self.assertEqual(rect, geom.rect(0, 0, 40, 30))    # l'autre contour n'a pas bougé
        cb = circ.bbox()
        self.assertAlmostEqual((cb[0] + cb[2]) / 2, 15, places=9)
        self.assertAlmostEqual((cb[1] + cb[3]) / 2, 12, places=9)
        self.assertEqual(len(sh.path.contours), 2)         # toujours un seul objet
        w.undo()
        leaf = next(iter(w.canvas.doc.iter_leaves()))
        cb = leaf.path.contours[1].bbox()
        self.assertAlmostEqual((cb[0] + cb[2]) / 2, 10, places=9)

    def test_ctrl_45_and_miss(self):
        from vectordrive.core.document import Shape
        w = self.w
        sh = Shape(path=geom.Path([geom.rect(0, 0, 40, 30), geom.circle((10, 10), 4)]))
        w.canvas.doc.add(sh)
        w.canvas.selection = [sh]
        w.A['tool_contour_move'].trigger()
        tool = w.canvas.tool_obj
        tool.press(QPointF(), (20.0, 20.0), Ev())           # dans le vide
        self.assertIsNone(tool.hit)
        tool.press(QPointF(), (14.0, 10.0), Ev())
        ctrl = Ev(Qt.KeyboardModifier.ControlModifier)
        tool.release(QPointF(), (24.0, 11.0), ctrl)          # presque horizontal → horizontal
        cb = sh.path.contours[1].bbox()
        self.assertAlmostEqual((cb[1] + cb[3]) / 2, 10, places=6)
        self.assertGreater((cb[0] + cb[2]) / 2, 19)


if __name__ == '__main__':
    unittest.main()
