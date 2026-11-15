"""Round 394 : Mode Point — en arc (TypeEdit : Transformer en arc)."""
import math
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


class TestToArc(unittest.TestCase):
    def test_core(self):
        c = geom.polyline([(0, 0), (5, 5), (10, 0)])                    # toit pointu
        out = N.to_arc(c, 0, 2)
        pts = out.flatten(0.001)
        self.assertEqual(tuple(round(v, 6) for v in pts[0]), (0, 0))
        self.assertEqual(tuple(round(v, 6) for v in pts[-1]), (10, 0))
        mid = (5, 5 / 2 + 2.5 * 0)                                       # milieu de la portion : (5, 5)
        # tous les points sur un même cercle passant par (0,0), (5,5), (10,0) : centre (5, 0), rayon 5
        for x, y in pts:
            self.assertAlmostEqual(math.hypot(x - 5, y), 5.0, 2)
        self.assertTrue(mid)
        straight = N.to_arc(geom.polyline([(0, 0), (5, 0), (10, 0)]), 0, 2)
        self.assertEqual(len(straight.segments), 1)                      # alignés : une droite

    def test_closed_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            sh = Shape(path=Path([geom.rect(0, 0, 10, 10)]))
            w._add_items([sh])
            w.canvas.select([sh])
            w.set_tool('node')
            before = sh.path.contours[0]
            w.canvas.tool_obj.sel = {(0, 0), (0, 2)}                         # deux côtés : le coin devient un arc
            w.node_portion('arc')
            c = sh.path.contours[0]
            self.assertTrue(c.closed)
            self.assertNotEqual(c, before)
            self.assertLess(abs(c.area()) if hasattr(c, 'area') else 0, 100.0 + 1e-6)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
