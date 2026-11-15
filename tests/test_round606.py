"""Round 606 : trous d'une pièce 3D (STEP) → cercles du dessin et perçages — cylindres creux à axe vertical,
cercle complet (faces d'un même trou réunies), profondeur sous le haut de la pièce, débouchant ou non ; au
foret du bon diamètre s'il y en a un, sinon à la fraise en hélice."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round595 import box_tris
from vectordrive.cam import model as CM
from vectordrive.core import holes3d as H
from vectordrive.io import model3d

app = QApplication.instance() or QApplication([])


def arc(cx, cy, r, z0, z1, a0=0.0, a1=360.0, n=36, axis='z'):
    t = []
    for k in range(n):
        u0 = math.radians(a0 + (a1 - a0) * k / n)
        u1 = math.radians(a0 + (a1 - a0) * (k + 1) / n)
        p0, p1 = (cx + r * math.cos(u0), cy + r * math.sin(u0)), (cx + r * math.cos(u1), cy + r * math.sin(u1))
        q = [(*p0, z0), (*p1, z0), (*p1, z1), (*p0, z1)]
        t += [[q[0], q[2], q[1]], [q[0], q[3], q[2]]]
    a = np.array(t, dtype=float)
    if axis == 'x':
        a = a[..., [2, 1, 0]]
    return a


def part():
    """Bloc 40 × 20 × 10 : un trou Ø4 débouchant en deux demi-faces, un trou Ø3 de 6 mm, un congé (quart de
    cylindre), un trou horizontal."""
    pieces = [box_tris(0, 0, 0, 40, 20, 10), arc(10, 10, 2, 0, 10, 0, 180), arc(10, 10, 2, 0, 10, 180, 360),
              arc(25, 10, 1.5, 4, 10), arc(35, 5, 1.0, 0, 10, 0, 90), arc(5, 10, 1.0, 20, 30, axis='x')]
    kinds = [{'genre': 'plan'}, {'genre': 'cylindre', 'axe': [0, 0, 1], 'centre': [10, 10, 0], 'rayon': 2.0, 'creux': True},
             {'genre': 'cylindre', 'axe': [0, 0, -1], 'centre': [10, 10, 5], 'rayon': 2.0, 'creux': True},
             {'genre': 'cylindre', 'axe': [0, 0, 1], 'centre': [25, 10, 4], 'rayon': 1.5, 'creux': True},
             {'genre': 'cylindre', 'axe': [0, 0, 1], 'centre': [35, 5, 0], 'rayon': 1.0, 'creux': True},
             {'genre': 'cylindre', 'axe': [1, 0, 0], 'centre': [0, 10, 5], 'rayon': 1.0, 'creux': True}]
    tris = np.concatenate(pieces)
    fo = np.concatenate([np.full(len(p), k) for k, p in enumerate(pieces)])
    return model3d.Model3D(tris, np.ones((len(tris), 3)), np.zeros((0, 2, 3)), face_of=fo, face_kinds=kinds)


class TestHoles(unittest.TestCase):
    def test_find(self):
        hs = H.find(part())
        self.assertEqual([(h.x, h.y, h.diameter) for h in hs], [(10.0, 10.0, 4.0), (25.0, 10.0, 3.0)])
        a, b = hs
        self.assertEqual(sorted(a.faces), [1, 2])                         # deux demi-faces : un trou
        self.assertTrue(a.through)
        self.assertAlmostEqual(a.depth, 10.0, 6)
        self.assertFalse(b.through)
        self.assertAlmostEqual(b.depth, 6.0, 6)
        self.assertGreaterEqual(a.coverage, H.FULL_DEG)
        self.assertEqual(H.find(model3d.Model3D(box_tris(0, 0, 0, 1, 1, 1), np.ones((12, 3)),
                                                np.zeros((0, 2, 3)))), [])        # STL : rien de connu


class TestPanel(unittest.TestCase):
    def test_drilling(self):
        from vectordrive.ui.view3d import Panel3D
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            s = w.cam_panel.setup()
            s.tools.append(CM.CamTool(name='Foret 3', kind='foret', diameter=3.0, number=7))
            w.cam_panel.save(s)
            p = Panel3D(w)
            m = part()
            p.model = m
            p.view.set_model(m)
            circles, ops = p.holes_to_drilling()
            self.assertEqual(len(circles), 2)
            self.assertEqual(circles[0].extra['trou3d']['diametre'], 4.0)
            by_kind = {o.kind: o for o in ops}
            self.assertAlmostEqual(by_kind['percage_fraise'].depth, 10.5, 6)      # débouchant : 0,5 de plus
            self.assertEqual(by_kind['percage_fraise'].hole_diameter, 4.0)
            self.assertAlmostEqual(by_kind['percage'].depth, 6.0, 6)              # foret Ø3 du document
            self.assertEqual(w.cam_panel.setup().tool(by_kind['percage'].tool_id).name, 'Foret 3')
            self.assertEqual(len(by_kind['percage'].items), 1)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
