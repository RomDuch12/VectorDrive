"""Round 387 : Mode Point — Moyenne (points réunis à leur point moyen)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, nodes as N
from vectordrive.core.document import Shape
from vectordrive.core.geom import Path

app = QApplication.instance() or QApplication([])


class TestAverage(unittest.TestCase):
    def test_core(self):
        a = geom.polyline([(0, 0), (10, 0)])
        b = geom.polyline([(12, 4), (20, 4)])
        out = N.align_nodes([a, b], {(0, 1), (1, 0)}, 'both')
        self.assertEqual(N.node_point(out[0], 1), (11.0, 2.0))
        self.assertEqual(N.node_point(out[1], 0), (11.0, 2.0))
        self.assertEqual(N.node_point(out[0], 0), (0, 0))                      # les autres ne bougent pas
        self.assertIsNotNone(N.join(out[0], out[1]))                           # puis Joindre soude les bouts

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            sh = Shape(path=Path([geom.rect(0, 0, 10, 10)]))
            w._add_items([sh])
            w.canvas.select([sh])
            w.set_tool('node')
            w.canvas.tool_obj.sel = {(0, 0), (0, 2)}
            w.node_edit('node_average')
            pts = {N.node_point(sh.path.contours[0], k) for k in (0, 2)}
            self.assertEqual(len(pts), 1)
            self.assertEqual(pts.pop(), (5.0, 5.0))
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
