"""Round 595 : corps d'une pièce 3D (solides du STEP, morceaux d'un STL, volumes) — montrés, masqués,
couleur par corps ; mécanismes : contacts entre corps, liaisons (appui plan, glissière, pivot, pivot
glissant, encastrement), mouvement libre de chacun, animation dans la vue 3D."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round590 import cube_tris
from vectordrive.core import faces3d as F
from vectordrive.core import mechanics as M
from vectordrive.core import solids as SO
from vectordrive.io import model3d

app = QApplication.instance() or QApplication([])


def box_tris(x0, y0, z0, x1, y1, z1):
    """Pavé en 12 triangles, normales vers l'extérieur."""
    v = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)], dtype=float)
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    t = []
    for a, b, c, d in quads:
        t += [v[[a, b, c]], v[[a, c, d]]]
    return np.array(t)


def model_of(*parts):
    """Model3D de plusieurs pavés (un corps chacun)."""
    tris = np.concatenate(parts)
    body = np.concatenate([np.full(len(p), k) for k, p in enumerate(parts)])
    return model3d.Model3D(tris, np.ones((len(tris), 3)), np.zeros((0, 2, 3)), body_of=body,
                           body_names=[f'P{k}' for k in range(len(parts))])


def tube(r, z0, z1, n=48, inward=False):
    t = []
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        p0, p1 = (r * math.cos(a0), r * math.sin(a0)), (r * math.cos(a1), r * math.sin(a1))
        q = [(*p0, z0), (*p1, z0), (*p1, z1), (*p0, z1)]
        tri = [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
        if inward:
            tri = [x[::-1] for x in tri]
        t += tri
    return np.array(t, dtype=float)


class TestBodies(unittest.TestCase):
    def test_mesh_bodies(self):
        t = np.concatenate([cube_tris(), cube_tris(20.0)])
        b = F.bodies(t)
        self.assertEqual(b.tolist(), [0] * 12 + [1] * 12)
        seg = np.array([[t[0, 0], t[0, 1]], [t[20, 0], t[20, 1]], [[99, 99, 99], [0, 0, 0]]])
        self.assertEqual(F.segment_owner(t, b, seg).tolist(), [0, 1, -1])

    def test_model_bodies(self):
        m = model3d.Model3D(np.concatenate([cube_tris(), cube_tris(20.0)]), np.ones((24, 3)), np.zeros((0, 2, 3)))
        self.assertEqual(m.body_count(), 2)
        self.assertEqual(m.body_name(1), 'Corps 2')

    def test_step_bodies(self):
        from vectordrive.io.neostep import step3d

        class Fake:
            triangles = np.concatenate([cube_tris(), cube_tris(20.0)])
            couleurs = np.ones((24, 3))
            aretes = []
            notes = []
            n_instances = 1
            n_faces = 2
            face_de = np.array([0] * 12 + [1] * 12)
            faces = [{'genre': 'plan', 'index': 0, 'corps': 0}, {'genre': 'autre', 'index': 1, 'corps': 1}]
            corps = ['Noyau', 'Tiroir']
        old = step3d.lire_modele
        step3d.lire_modele = lambda *a, **k: Fake()
        try:
            m = model3d.from_step('x.stp')
        finally:
            step3d.lire_modele = old
        self.assertEqual(m.body_ids().tolist(), [0] * 12 + [1] * 12)
        self.assertEqual(m.body_name(1), 'Tiroir')

    def test_placed_kinds(self):
        from vectordrive.core import placement3d as P3
        m = model3d.Model3D(cube_tris(), np.ones((12, 3)), np.zeros((0, 2, 3)), face_kinds=[
            {'genre': 'cylindre', 'axe': [1.0, 0, 0], 'centre': [1.0, 0, 0], 'rayon': 2.0}])
        p = model3d.placed(m, P3.Placement('+Z', 90.0, 'libre', 10.0, 0.0))
        np.testing.assert_allclose(p.face_kinds[0]['axe'], [0, 1, 0], atol=1e-12)
        np.testing.assert_allclose(p.face_kinds[0]['centre'], [10, 1, 0], atol=1e-12)

    @unittest.skipUnless(SO.available(), 'manifold3d absent')
    def test_volumes_are_bodies(self):
        m = SO.to_model([SO.box(0, 0, 0, 1, 1, 1), SO.box(5, 0, 0, 1, 1, 1)])
        self.assertEqual(m.body_count(), 2)


class TestMechanics(unittest.TestCase):
    def test_stacked_is_planar_support(self):
        m = model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10))
        cs = M.contacts(m)
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0].kind, 'plan')
        self.assertAlmostEqual(cs[0].area, 100.0, 6)
        js = M.joints(m, found=cs)
        self.assertEqual(js[0].kind, 'appui')
        np.testing.assert_allclose(js[0].axis, [0, 0, 1], atol=1e-9)        # le corps du dessus se soulève
        mv = M.motions(m)
        self.assertEqual(len(mv), 1)
        self.assertEqual(mv[0].kind, 'translation')
        self.assertAlmostEqual(mv[0].amount, round(5 * 1.2 + 1, 1), 6)

    def test_flush_faces_are_not_contacts(self):
        m = model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(10.5, 0, 0, 20, 10, 5))   # côte à côte, 0,5 mm
        self.assertEqual(M.contacts(m), [])                                         # dessus affleurants : non
        self.assertEqual(M.motions(m), [])

    def test_gap_tolerance(self):
        m = model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5.2, 10, 10, 10))
        self.assertEqual(len(M.contacts(m, M.Settings(tol=0.3))), 1)
        self.assertEqual(M.contacts(m, M.Settings(tol=0.1)), [])

    def test_closed_slot_is_slide(self):
        # rail (corps 1) serré dans une glissière fermée (corps 0 en quatre pavés)
        frame = [box_tris(0, 0, 0, 30, 4, 10), box_tris(0, 4, 0, 30, 6, 2), box_tris(0, 4, 8, 30, 6, 10),
                 box_tris(0, 6, 0, 30, 10, 10)]
        frame = np.concatenate(frame)
        rail = box_tris(0, 4, 2, 30, 6, 8)
        m = model_of(frame, rail)
        m.body_of = np.concatenate([np.zeros(len(frame), int), np.ones(len(rail), int)])
        js = M.joints(m)
        self.assertEqual(len(js), 1)
        self.assertEqual(js[0].kind, 'glissiere')
        self.assertAlmostEqual(abs(js[0].axis[0]), 1.0, 9)                   # le long de X

    def test_pivot_and_free_direction(self):
        shaft, bore = tube(5.0, 0, 20), tube(5.0, 5, 15, inward=True)
        tris = np.concatenate([shaft, bore])
        n1, n2 = len(shaft), len(bore)
        m = model3d.Model3D(tris, np.ones((len(tris), 3)), np.zeros((0, 2, 3)),
                            face_of=np.concatenate([np.zeros(n1, int), np.ones(n2, int)]),
                            face_kinds=[{'genre': 'cylindre', 'axe': [0, 0, 1], 'centre': [0, 0, 0], 'rayon': 5.0},
                                        {'genre': 'cylindre', 'axe': [0, 0, 1], 'centre': [0, 0, 0], 'rayon': 5.0,
                                         'creux': True}],
                            body_of=np.concatenate([np.zeros(n1, int), np.ones(n2, int)]))
        js = M.joints(m)
        self.assertEqual(js[0].kind, 'pivot_glissant')
        self.assertIsNone(M.free_direction([np.array([1.0, 0, 0]), np.array([-1.0, 0, 0]),
                                            np.array([0, 1.0, 0]), np.array([0, -1.0, 0]),
                                            np.array([0, 0, 1.0]), np.array([0, 0, -1.0])]))
        d = M.free_direction([np.array([0, 0, 1.0]), np.array([0.3, 0, 0.95])])
        self.assertGreater(d[2], 0.9)                                        # dépouille : vers le haut

    def test_poses_follow_parent(self):
        mv = [M.Motion(1, 'translation', (0, 0, 1), (0, 0, 0), 10.0, 0),
              M.Motion(2, 'rotation', (0, 0, 1), (5, 0, 0), 90.0, 1)]
        p = M.poses(mv, 1.0)
        np.testing.assert_allclose(p[1][1], [0, 0, 10], atol=1e-12)
        R, t = p[2]
        np.testing.assert_allclose(R @ np.array([6.0, 0, 0]) + t, [5, 1, 10], atol=1e-9)   # tourne puis monte
        self.assertEqual(M.poses(mv, 0.0)[1][1].tolist(), [0, 0, 0])


class TestWindow(unittest.TestCase):
    def test_view_and_dialog(self):
        from vectordrive.ui.view3d import Panel3D
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = Panel3D(w)
            m = model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10))
            p.model = m
            p.view.set_model(m)
            p._fill_bodies_menu()
            acts = [a for a in p.bodies_menu.actions() if a.isCheckable()]
            self.assertEqual(len(acts), 3)                                   # 2 corps + couleur par corps
            acts[0].setChecked(False)
            self.assertEqual(p.view.hidden_bodies, {0})
            shown, keep = p.view.shown_model()
            self.assertEqual(len(shown.triangles), 12)
            p.show_all_bodies()
            dlg = p.mechanisms(show=False)
            self.assertEqual(dlg.joints_table.rowCount(), 1)
            self.assertEqual(dlg.joints_table.item(0, 2).text(), 'Appui plan')
            self.assertEqual(dlg.moves_table.rowCount(), 1)
            dlg.set_progress(1.0)
            self.assertIn(1, p.view.body_moves)
            self.assertAlmostEqual(float(p.view.body_moves[1][1][2]), 7.0, 6)
            shown, _k = p.view.shown_model()
            self.assertAlmostEqual(float(np.asarray(shown.triangles)[12:, :, 2].max()), 17.0, 4)
            dlg.moves_table.cellWidget(0, 4).setChecked(True)               # inverser
            self.assertAlmostEqual(float(p.view.body_moves[1][1][2]), -7.0, 6)
            dlg.moves_table.cellWidget(0, 0).setChecked(False)              # pas animé
            self.assertEqual(p.view.body_moves, {})
            dlg.done(0)
            self.assertEqual(p.view.body_moves, {})
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
