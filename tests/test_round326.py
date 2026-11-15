"""Round 326 : parcours en dessin (TypeEdit : éditer la géométrie du
parcours) — trajectoire du centre de l'outil en traits, passes de Z en
double retirées, arcs aplatis, calque « Parcours »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model as M
from vectordrive.cam.model import Move
from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestDrawing(unittest.TestCase):
    def test_polylines(self):
        tp = M.Toolpath(op_id='x', tool_id='t', moves=[Move('rapid', 0, 0, 5), Move('plunge', 0, 0, -1), Move('feed', 5, 0, -1),
                                          Move('feed', 10, 0, -1), Move('feed', 10, 10, -1),
                                          Move('arc_ccw', 0, 10, -1, cx=5, cy=10),
                                          Move('rapid', 0, 10, 5), Move('rapid', 20, 0, 5), Move('plunge', 20, 0, -1),
                                          Move('feed', 30, 0, -1)])
        d = tp.drawing()
        self.assertEqual(len(d), 2)
        self.assertEqual(d[0][:3], [(0, 0), (10, 0), (10, 10)])           # point aligné (5, 0) retiré
        self.assertGreater(len(d[0]), 6)                                   # demi-cercle aplati
        self.assertEqual(d[1], [(20, 0), (30, 0)])

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            c.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0))
            s = w.cam_panel.setup()
            t = M.CamTool(name='F2', diameter=2)
            s.tools = [t]
            s.operations = [M.Operation(kind='contour', side='exterieur', depth=2, step_down=1, tool_id=t.id)]
            w.cam_panel.save(s)
            shapes = w.cam_to_drawing()
            self.assertEqual(len(shapes), 1)
            self.assertEqual(len(shapes[0].path.contours), 1)                 # 2 passes, un seul tracé
            b = shapes[0].path.bbox()
            self.assertAlmostEqual(b[0], -1, 3)
            self.assertIn('Parcours', [L.name for L in c.doc.layers])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
