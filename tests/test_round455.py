"""Round 455 : 3D — clic sur une trajectoire : coordonnées du point le plus proche ; second clic :
distance ; troisième : on recommence ; Échap : effacés."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from vectordrive.cam.model import Move, Toolpath
from vectordrive.ui import view3d as V

app = QApplication.instance() or QApplication([])


def screen_of(v, p):
    m = np.array(v.camera().data(), dtype=np.float64).reshape(4, 4)
    h = np.array([p[0], p[1], p[2], 1.0]) @ m
    return QPointF((h[0] / h[3] + 1) * 0.5 * v.width(), (1 - h[1] / h[3]) * 0.5 * v.height())


class TestPick(unittest.TestCase):
    def test_points_and_distance(self):
        from vectordrive.cam import relief as RL
        from vectordrive.core.document import Document
        tp = Toolpath(op_id='', tool_id='', name='a')
        tp.moves = [Move('rapid', 0, 0, 5), Move('plunge', 0, 0, -1), Move('feed', 30, 0, -1),
                    Move('feed', 30, 40, -1)]
        v = V.View3D()
        v.resize(600, 400)
        v.set_relief(RL.from_paths(Document(), [tp], cut=False))
        v.set_exag(2.0)                                                           # profondeurs exagérées à l'écran
        self.assertIsNone(v.pick_at(QPointF(-500, -500)))                         # loin de tout : rien
        a = v.pick_at(screen_of(v, (0, 0, -2.0)))
        self.assertEqual(tuple(round(c, 6) for c in a), (0.0, 0.0, -1.0))         # Z vrai, pas exagéré
        b = v.pick_at(screen_of(v, (30, 40, -2.0)))
        self.assertEqual(tuple(round(c, 6) for c in b), (30.0, 40.0, -1.0))
        lines = v.pick_lines()
        self.assertEqual(len(lines), 3)
        self.assertIn('Distance 50 mm', lines[2])
        self.assertIn('Distance 50 mm', [t for t, _c in v.overlay_lines()][-1])
        v.pick_at(screen_of(v, (30, 0, -2.0)))                                    # troisième : on recommence
        self.assertEqual(len(v.picks), 1)
        v.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(v.picks, [])
        self.assertTrue(math.isfinite(v.zoom))
        v.deleteLater()


if __name__ == '__main__':
    unittest.main()
