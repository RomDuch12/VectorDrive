"""Round 467 : 3D — mesure au clic sur les arêtes d'un modèle 3D."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from vectordrive.io.model3d import Model3D
from vectordrive.ui import view3d as V

app = QApplication.instance() or QApplication([])


def screen_of(v, p):
    m = np.array(v.camera().data(), dtype=np.float64).reshape(4, 4)
    h = np.array([p[0], p[1], p[2], 1.0]) @ m
    return QPointF((h[0] / h[3] + 1) * 0.5 * v.width(), (1 - h[1] / h[3]) * 0.5 * v.height())


class TestModelPick(unittest.TestCase):
    def test_edges(self):
        tri = np.array([[[0, 0, 0], [40, 0, 0], [40, 30, 0]]], dtype=float)
        seg = np.array([[[0, 0, 0], [40, 0, 0]], [[40, 0, 0], [40, 30, 0]]], dtype=float)
        model = Model3D(triangles=tri, colors=np.array([[0.5, 0.5, 0.5]]), segments=seg)
        v = V.View3D()
        v.resize(500, 400)
        v.set_model(model)
        a = v.pick_at(screen_of(v, (0, 0, 0)))
        b = v.pick_at(screen_of(v, (40, 30, 0)))
        self.assertEqual(tuple(round(c, 4) for c in a), (0.0, 0.0, 0.0))
        self.assertEqual(tuple(round(c, 4) for c in b), (40.0, 30.0, 0.0))
        self.assertIn('Distance 50 mm', v.pick_lines()[-1])
        v.deleteLater()


if __name__ == '__main__':
    unittest.main()
