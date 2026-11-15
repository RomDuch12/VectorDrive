"""Round 245 : trajectoires calculées dans un calque « Trajectoires » —
2.5D (teinte selon la profondeur) et 3D, par-dessus un modèle STEP aussi ;
la case du calque les montre ou les cache partout."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def toolpath():
    from vectordrive.cam.model import Move, Toolpath
    tp = Toolpath('op', 't', name='Essai')
    tp.moves = [Move('rapid', 0, 0, 5), Move('feed', 0, 0, 0), Move('feed', 10, 0, 0),
                Move('feed', 10, 0, -1), Move('feed', 20, 0, -1), Move('feed', 20, 0, -4), Move('feed', 30, 0, -4),
                Move('rapid', 30, 0, 5)]
    return tp


class TestTrajectoryLayer(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.set_toolpaths_visible(True)
        self.w.modified = False
        self.w.close()

    def _traj_row(self):
        from vectordrive.ui.layers import TRAJ
        t = self.w.layers_panel.tree
        return next((t.topLevelItem(i) for i in range(t.topLevelItemCount())
                     if t.topLevelItem(i).data(1, Qt.ItemDataRole.UserRole) == TRAJ), None)

    def test_row_and_visibility(self):
        w = self.w
        self.assertIsNone(self._traj_row())                       # rien de calculé : pas de ligne
        w.cam_panel.display([toolpath()])
        row = self._traj_row()
        self.assertIsNotNone(row)
        self.assertEqual(row.text(1), 'Trajectoires')
        self.assertEqual(len(w.canvas.toolpaths), 1)
        self.assertEqual(row.checkState(0), Qt.CheckState.Checked)
        row.setCheckState(0, Qt.CheckState.Unchecked)             # la case du calque
        QApplication.processEvents()                              # appliquée au tour suivant
        self.assertFalse(w.canvas.toolpaths_visible)
        self.assertIn(w.settings.value('vue/calque_trajectoires'), (False, 'false'))
        self.assertEqual(len(w.canvas.doc.layers), 1)             # pas un calque du dessin
        w.set_toolpaths_visible(True)
        self.assertEqual(self._traj_row().checkState(0), Qt.CheckState.Checked)

    def test_depth_bands(self):
        c = self.w.canvas
        tp = toolpath()
        c.set_toolpaths([(tp, '#1971c2')])
        bands, rapid = c._toolpath_bands(tp)
        counts = [b.elementCount() for b in bands]
        self.assertGreater(counts[0], 0)                          # en surface
        self.assertGreater(counts[-1], 0)                         # au fond (−4)
        self.assertGreater(rapid.elementCount(), 0)
        feed, _r = c._toolpath_paths(tp)
        self.assertEqual(feed.elementCount(), sum(counts))
        c.grab()                                                  # dessin sans erreur

    def test_paths_over_model(self):
        import numpy as np
        from vectordrive.io.model3d import Model3D
        from vectordrive.ui.view3d import View3D
        v = View3D()
        tris = np.array([[[0, 0, 0], [30, 0, 0], [0, 10, 0]]], np.float32) + np.array([0, 0, 8], np.float32)
        m = Model3D(tris, np.ones((1, 3), np.float32), np.zeros((0, 2, 3), np.float32))
        v.set_model(m)
        v.model_paths, v.model_dz = [toolpath()], m.bounds()[5]
        self.assertEqual(v.model_dz, 8.0)                         # haut de la pièce : Z = 0 de la FAO
        v.deleteLater()


if __name__ == '__main__':
    unittest.main()
