"""Round 590 : vue 3D — choisir des faces ou des contours fermés du modèle 3D au clic (Ctrl ou Maj :
plusieurs), surlignés ; faces d'un STEP gardées, faces des maillages (STL, volumes) retrouvées jusqu'aux
arêtes vives ; rayon de la caméra, contours d'un ensemble de faces."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from vectordrive.core import faces3d as F
from vectordrive.core import solids as SO
from vectordrive.io import model3d

app = QApplication.instance() or QApplication([])


def cube_tris(x0=0.0, y0=0.0, z0=0.0, a=10.0):
    """Cube en 12 triangles (comme un STL)."""
    v = np.array([[x0 + i * a, y0 + j * a, z0 + k * a] for i in (0, 1) for j in (0, 1) for k in (0, 1)])
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    t = []
    for a_, b, c, d in quads:
        t += [v[[a_, b, c]], v[[a_, c, d]]]
    return np.array(t, dtype=float)


def pocket_model():
    s = SO.boolean('subtract', [SO.box(0, 0, 0, 40, 20, 10), SO.box(10, 5, 5, 20, 10, 10)])
    return SO.to_model([s])


class TestFaces(unittest.TestCase):
    def test_segment_cube(self):
        f = F.segment(cube_tris())
        self.assertEqual(int(f.max()) + 1, 6)                   # 6 faces de 2 triangles
        self.assertEqual(sorted(np.bincount(f).tolist()), [2] * 6)
        self.assertEqual(f[0], 0)                               # numérotées dans l'ordre des triangles

    def test_smooth_cylinder_one_face(self):
        n = 48                                                  # côtés à 7,5° : une seule face latérale
        t = []
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            p0, p1 = (5 * math.cos(a0), 5 * math.sin(a0)), (5 * math.cos(a1), 5 * math.sin(a1))
            t += [[(*p0, 0), (*p1, 0), (*p1, 8)], [(*p0, 0), (*p1, 8), (*p0, 8)]]
        f = F.segment(np.array(t))
        self.assertEqual(int(f.max()) + 1, 1)

    def test_ray_hit(self):
        t = cube_tris()
        i, d = F.ray_hit(t, (5, 5, 30), (0, 0, -1))
        self.assertGreaterEqual(i, 0)
        self.assertAlmostEqual(d, 20.0, 9)                      # le dessus (Z 10), pas le dessous
        self.assertEqual(F.ray_hit(t, (50, 5, 30), (0, 0, -1))[0], -1)
        self.assertEqual(F.ray_hit(t, (5, 5, 30), (0, 0, 1))[0], -1)    # derrière l'origine : rien

    def test_boundary_loops(self):
        t = cube_tris()
        f = F.segment(t)
        top = F.face_triangles(f, [f[F.ray_hit(t, (5, 5, 30), (0, 0, -1))[0]]])
        loops = F.boundary_loops(t, top)
        self.assertEqual(len(loops), 1)
        L = loops[0]
        self.assertTrue(np.allclose(L[0], L[-1]))               # fermé
        self.assertEqual(len(L), 5)                             # carré
        self.assertTrue(np.allclose(L[:, 2], 10.0))
        self.assertEqual(F.boundary_loops(t), [])               # cube entier : pas de bord

    def test_describe(self):
        t = cube_tris()
        f = F.segment(t)
        top = F.face_triangles(f, [f[F.ray_hit(t, (5, 5, 30), (0, 0, -1))[0]]])
        d = F.describe(t[top])
        self.assertAlmostEqual(d['aire'], 100.0, 9)
        self.assertTrue(d['plat'])
        self.assertFalse(d['vertical'])
        side = F.face_triangles(f, [f[F.ray_hit(t, (-20, 5, 5), (1, 0, 0))[0]]])
        self.assertTrue(F.describe(t[side])['vertical'])

    def test_model_face_ids(self):
        m = model3d.Model3D(cube_tris(), np.ones((12, 3)), np.zeros((0, 2, 3)))
        self.assertIsNone(m.face_of)
        self.assertEqual(m.face_count(), 6)                     # calculées à la demande, gardées
        self.assertIsNotNone(m.face_of)
        from vectordrive.core import placement3d as P3
        moved = model3d.placed(m, P3.Placement('+Z', 90.0, 'libre', 5.0, 0.0))
        self.assertIs(moved.face_of, m.face_of)                 # même numérotation une fois posée

    def test_step_faces_kept(self):
        """Faces du STEP : celles du lecteur (une par face du fichier)."""
        from vectordrive.io.neostep import step3d

        class Fake:
            triangles = cube_tris()
            couleurs = np.ones((12, 3))
            aretes = []
            notes = []
            n_instances = 1
            n_faces = 2
            face_de = np.array([0] * 6 + [1] * 6)
            faces = [{'genre': 'plan', 'index': 0}, {'genre': 'cylindre', 'rayon': 3.0, 'creux': True, 'index': 1}]
        old = step3d.lire_modele
        step3d.lire_modele = lambda *a, **k: Fake()
        try:
            m = model3d.from_step('x.stp')
        finally:
            step3d.lire_modele = old
        self.assertEqual(m.face_count(), 2)
        self.assertEqual(m.face_kinds[1], {'genre': 'cylindre', 'rayon': 3.0, 'creux': True})


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestViewSelection(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.view3d import View3D
        self.v = View3D()
        self.v.resize(400, 300)
        self.m = pocket_model()
        self.v.set_model(self.m)
        self.v.set_view('dessus')
        self.changes = []
        self.v.selectionChanged.connect(lambda: self.changes.append(1))

    def test_faces(self):
        v = self.v
        v.select_mode = 'faces'
        f = v.select_at(QPointF(200, 150))                      # fond de la poche, au centre
        self.assertIsNotNone(f)
        self.assertEqual(v.sel_faces, {f})
        self.assertIn('200 mm²', v.selection_text())
        self.assertIn('horizontale', v.selection_text())
        g = v.select_at(QPointF(60, 150), add=True)             # Ctrl : le dessus en plus
        self.assertEqual(v.sel_faces, {f, g})
        self.assertIn('800 mm²', v.selection_text())
        v.select_at(QPointF(60, 150), add=True)                 # second Ctrl+clic : retirée
        self.assertEqual(v.sel_faces, {f})
        self.assertEqual(len(v.selected_triangles()), 2)
        v.select_at(QPointF(395, 5))                            # dans le vide : tout effacé
        self.assertEqual(v.sel_faces, set())
        self.assertGreaterEqual(len(self.changes), 4)

    def test_contours(self):
        v = self.v
        v.select_mode = 'contours'
        L = v.select_at(QPointF(200, 150))
        self.assertIsNotNone(L)
        self.assertEqual(len(v.sel_loops), 1)
        xs, ys = L[:, 0], L[:, 1]
        self.assertAlmostEqual(xs.min(), 10.0, 6)               # bord du fond de la poche
        self.assertAlmostEqual(ys.max(), 15.0, 6)
        self.assertIn('Z 5 à 5', v.selection_text())
        v.keyPressEvent(_key_escape())
        self.assertEqual(v.sel_loops, [])

    def test_highlight_arrays(self):
        from vectordrive.ui.view3d import PICKED_FACE, loop_lines, model_arrays
        tri, _e = model_arrays(self.m, np.array([0]))
        self.assertTrue(np.allclose(tri[0, 6:], PICKED_FACE))
        self.assertFalse(np.allclose(tri[3, 6:], PICKED_FACE))
        arr, ranges = loop_lines([np.zeros((5, 3)), np.ones((1, 3))])
        self.assertEqual(ranges, [(0, 5)])                      # un contour d'un point : ignoré

    def test_new_model_clears(self):
        v = self.v
        v.select_mode = 'faces'
        v.select_at(QPointF(200, 150))
        v.set_model(pocket_model())
        self.assertEqual(v.sel_faces, set())

    def test_ray_through_center(self):
        o, d = self.v.ray_at(QPointF(200, 150))
        self.assertAlmostEqual(float(np.linalg.norm(d)), 1.0, 9)
        self.assertLess(d[2], -0.99)                           # vue de dessus : vers le bas


def _key_escape():
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)


if __name__ == '__main__':
    unittest.main()
