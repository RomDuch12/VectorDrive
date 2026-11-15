"""Round 316 : outil spécial (TypeEdit) — outil de forme d'après un profil de
révolution dessiné et l'axe donné par deux marqueurs ; rayon de coupe,
forme pour la compensation 3D et la simulation."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.cam import advanced as A, model as M
from vectordrive.core import forms as F, geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def cone_tool():
    # profil d'un cône de 90° : r = h, jusqu'à r = 3
    return M.CamTool(kind='profil', diameter=6, profile=[[0, 0], [3, 3], [3, 8]])


class TestSpecialTool(unittest.TestCase):
    def test_shape(self):
        t = cone_tool()
        self.assertAlmostEqual(t.radius_at(1.5), 1.5)
        self.assertAlmostEqual(t.radius_at(5), 3.0)
        h = A.tool_profile(t, np.array([0.0, 1.0, 2.9, 3.5]))
        self.assertAlmostEqual(h[0], 0.0, 2)
        self.assertAlmostEqual(h[1], 1.0, 1)
        self.assertAlmostEqual(h[2], 2.9, 1)
        self.assertTrue(math.isinf(h[3]))
        back = M.CamTool.from_dict(t.to_dict())
        self.assertEqual(back.profile, t.profile)

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            prof = Shape(path=geom.Path([geom.polyline([(10, 0), (12, 2), (12, 10)])]))      # axe en x = 10
            m1, m2 = F.make(F.Marker(cx=10, cy=12)), F.make(F.Marker(cx=10, cy=-1))
            for it in (prof, m1, m2):
                c.doc.add(it)
            c.select([prof, m1, m2])
            t = w.special_tool('Fraise à congé')
            self.assertEqual(t.kind, 'profil')
            self.assertAlmostEqual(t.diameter, 4.0)
            self.assertAlmostEqual(t.cut_length, 10.0)
            self.assertAlmostEqual(t.radius_at(1.0), 1.0, 3)
            s = w.cam_panel.setup()
            self.assertIn(t.id, [x.id for x in s.tools])
            c.select([prof])
            self.assertIsNone(w.special_tool())                         # sans marqueur : rien
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
