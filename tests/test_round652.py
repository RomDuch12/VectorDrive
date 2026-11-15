"""Round 652 : relecture — la vue 3D compte le brut montré dans sa hauteur
(grille dessous, coupe sur toute sa hauteur) ; zones atteintes de chaque
prise calculées une fois pour les prises proposées et choisies."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round596 import two_boxes_stl
from vectordrive.cam import mill3d
from vectordrive.core import access3d as AC

app = QApplication.instance() or QApplication([])


class TestReachCache(unittest.TestCase):
    def test_shared(self):
        m = mill3d.raw_model(two_boxes_stl())
        cache = {}
        real = AC.reached
        with mock.patch.object(AC, 'reached', side_effect=real) as r:
            plan, left = AC.plan_sides(m, 0.5, cache=cache)
            n = r.call_count
            self.assertEqual(n, len(AC.SIDES))
            self.assertEqual(set(cache), set(AC.SIDES))
            self.assertAlmostEqual(AC.left_out(m, [s for s, _g in plan], 0.5, cache), left, 9)
            self.assertEqual(r.call_count, n)                                # rien de recalculé
        self.assertEqual(AC.plan_sides(m, 0.5), (plan, left))                # sans cache : pareil


class TestZRange(unittest.TestCase):
    def test_stock(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(two_boxes_stl())
            w._ensure_panel3d()
            v = w.panel3d.view
            self.assertTrue(w.panel3d.refresh())
            z0, z1 = v.model.bounds()[2], v.model.bounds()[5]
            v.stock_lines = np.zeros((2, 9), np.float32)
            v.stock_lines[:, 2] = (z0 - 3.0, z1 + 2.0)
            v.show_plate = True
            np.testing.assert_allclose(v.z_range(), (z0 - 3.0, z1 + 2.0), atol=1e-4)   # brut plus grand : sa hauteur
            v.set_clip(0.5)
            self.assertAlmostEqual(v.clip, (z0 - 3.0 + z1 + 2.0) / 2, 4)
            v.show_plate = False
            self.assertEqual(v.z_range(), (z0, z1))                          # brut caché : la pièce
            v.show_plate, v.stock_lines = True, None
            self.assertEqual(v.z_range(), (z0, z1))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
