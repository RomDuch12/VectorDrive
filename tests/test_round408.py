"""Round 408 : Ctrl+flèche en mode point — pas demandé, puis les points avancent."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, nodes
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def key(k, mods=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QEvent.Type.KeyPress, k, mods)


class TestNodeCtrlArrow(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        c = self.w.canvas
        self.s = Shape(path=geom.Path([geom.rect(0, 0, 10, 4)]))
        c.doc.add(self.s)
        c.select([self.s])
        self.w.set_tool('node')
        self.t = c.tool_obj

    def tearDown(self):
        self.w.step_answer = None
        self.w.canvas.arrow_step = None
        self.w.set_tool('select')
        self.w.modified = False
        self.w.close()

    def pt(self, k):
        return tuple(round(v, 6) for v in nodes.node_point(self.s.path.contours[0], k))

    def test_ctrl_arrow_asks_and_moves(self):
        p0 = self.pt(0)
        self.t.sel = {(0, 0)}
        self.w.step_answer = 3.0
        self.assertTrue(self.t.key(key(Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)))
        self.assertEqual(self.pt(0), (p0[0] + 3, p0[1]))
        self.assertEqual(self.w.canvas.arrow_step, 3.0)
        self.w.step_answer = None
        self.t.key(key(Qt.Key.Key_Up))                          # flèche simple : le pas saisi
        self.assertEqual(self.pt(0), (p0[0] + 3, p0[1] + 3))
        self.t.key(key(Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier))      # Maj : dix pas
        self.assertEqual(self.pt(0), (p0[0] + 3, p0[1] - 27))
        self.w.undo()
        self.s = self.w.canvas.doc.layers[0].items[0]           # l'annulation remet une copie
        self.assertEqual(self.pt(0), (p0[0] + 3, p0[1] + 3))

    def test_zero_resets(self):
        self.t.sel = {(0, 0)}
        self.w.canvas.arrow_step = 5.0
        self.w.step_answer = 0.0
        p0 = self.pt(0)
        self.t.key(key(Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier))
        self.assertIsNone(self.w.canvas.arrow_step)
        self.assertEqual(self.pt(0), p0)                         # 0 : ne bouge pas

    def test_extent_proposal(self):
        self.t.sel = {(0, k) for k in range(nodes.node_count(self.s.path.contours[0]))}
        gap = self.w.canvas.step_gap_mm
        self.assertAlmostEqual(self.t._extent_step(True), 10 + gap)
        self.assertAlmostEqual(self.t._extent_step(False), 4 + gap)
        self.t.sel = {(0, 0)}
        self.assertIsNone(self.t._extent_step(True))


if __name__ == '__main__':
    unittest.main()
