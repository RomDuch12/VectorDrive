"""Round 803 : dépouille d'un volume déjà fait."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import numpy as np
from PySide6.QtWidgets import QApplication, QDialog

from vectordrive.core import draft3d as DR
from vectordrive.core import history3d as HI
from vectordrive.core import solids as SO

app = QApplication.instance() or QApplication([])


def box():
    return SO.box(0, 0, 0, 20, 20, 20)


def wall_pick(solid, normal):
    """La face dont la normale est celle-ci."""
    faces = DR._faces(solid)
    tris, face_of, nrm = faces
    k = np.flatnonzero(nrm @ np.array(normal, dtype=float) > 0.999)[0]
    return DR.pick_of(solid, int(face_of[k]), faces)


def plate_with_pocket():
    return SO._solid(SO.box(-30, -30, 0, 60, 60, 20).manifold() - SO.box(-10, -10, 10, 20, 20, 20).manifold(), 'p')


def is_flat(solid, normal, tol=1e-4):
    """Tous les sommets de la face de cette normale sont dans un même plan."""
    faces = DR._faces(solid)
    tris, _f, nrm = faces
    k = nrm @ np.array(normal, dtype=float) > 0.999
    h = tris[k].reshape(-1, 3) @ np.array(normal, dtype=float)
    return bool(k.any()) and float(h.max() - h.min()) <= tol


class Kernel(unittest.TestCase):
    def test_one_wall(self):
        s = box()
        out = DR.apply(s, {'angle': 5.0, 'neutral': 0.0, 'pull': 'z+', 'picks': [wall_pick(s, (1, 0, 0))]})
        drop = 20.0 * math.tan(math.radians(5.0))
        top = out.verts[np.isclose(out.verts[:, 2], 20.0, atol=1e-5)]
        self.assertAlmostEqual(top[:, 0].max(), 20.0 - drop, places=4)
        bottom = out.verts[np.isclose(out.verts[:, 2], 0.0, atol=1e-5)]
        self.assertAlmostEqual(bottom[:, 0].max(), 20.0, places=5)
        self.assertAlmostEqual(out.volume(), 8000.0 - 0.5 * 20 * drop * 20, places=2)

    def test_the_other_faces_stay_in_their_planes(self):
        s = box()
        out = DR.apply(s, {'angle': 5.0, 'neutral': 0.0, 'pull': 'z+', 'picks': [wall_pick(s, (1, 0, 0))]})
        self.assertAlmostEqual(out.verts[:, 1].min(), 0.0, places=5)
        self.assertAlmostEqual(out.verts[:, 1].max(), 20.0, places=5)
        self.assertAlmostEqual(out.verts[:, 0].min(), 0.0, places=5)
        self.assertAlmostEqual(out.verts[:, 2].max(), 20.0, places=5)
        for n in ((0, 1, 0), (0, -1, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)):
            self.assertTrue(is_flat(out, n), n)

    def test_all_walls_make_a_frustum(self):
        s = box()
        faces = DR._faces(s)
        picks = [DR.pick_of(s, f, faces) for f in DR.walls(faces)]
        self.assertEqual(len(picks), 4)
        out = DR.apply(s, {'angle': 5.0, 'neutral': 0.0, 'pull': 'z+', 'picks': picks})
        top = 20.0 - 2 * 20.0 * math.tan(math.radians(5.0))
        want = 20.0 / 3.0 * (400.0 + top ** 2 + 20.0 * top)
        self.assertAlmostEqual(out.volume(), want, places=2)

    def test_neutral_plane_in_the_middle(self):
        s = box()
        out = DR.apply(s, {'angle': 5.0, 'neutral': 10.0, 'pull': 'z+', 'picks': [wall_pick(s, (1, 0, 0))]})
        d = 10.0 * math.tan(math.radians(5.0))
        self.assertAlmostEqual(out.verts[:, 0].max(), 20.0 + d, places=4)
        self.assertAlmostEqual(out.verts[np.isclose(out.verts[:, 2], 20.0, atol=1e-5)][:, 0].max(), 20.0 - d, places=4)
        self.assertAlmostEqual(out.volume(), 8000.0, places=2)

    def test_negative_angle_is_an_undercut(self):
        s = box()
        out = DR.apply(s, {'angle': -5.0, 'neutral': 0.0, 'pull': 'z+', 'picks': [wall_pick(s, (1, 0, 0))]})
        self.assertGreater(out.volume(), 8000.0)
        self.assertGreater(out.verts[:, 0].max(), 20.0)

    def test_pull_down_turns_it_round(self):
        s = box()
        out = DR.apply(s, {'angle': 5.0, 'neutral': -20.0, 'pull': 'z-', 'picks': [wall_pick(s, (1, 0, 0))]})
        self.assertAlmostEqual(out.verts[np.isclose(out.verts[:, 2], 20.0, atol=1e-5)][:, 0].max(), 20.0, places=4)
        self.assertLess(out.verts[np.isclose(out.verts[:, 2], 0.0, atol=1e-5)][:, 0].max(), 18.5)

    def test_other_pull_directions(self):
        s = box()
        out = DR.apply(s, {'angle': 5.0, 'neutral': 0.0, 'pull': 'x+', 'picks': [wall_pick(s, (0, 1, 0))]})
        self.assertLess(out.verts[np.isclose(out.verts[:, 0], 20.0, atol=1e-5)][:, 1].max(), 18.5)
        self.assertAlmostEqual(out.verts[np.isclose(out.verts[:, 0], 0.0, atol=1e-5)][:, 1].max(), 20.0, places=4)

    def test_cylinder_becomes_a_cone(self):
        s = SO.cylinder(0, 0, 0, 10, 20)
        faces = DR._faces(s)
        picks = [DR.pick_of(s, f, faces) for f in DR.walls(faces)]
        self.assertEqual(len(picks), 1)
        out = DR.apply(s, {'angle': 5.0, 'neutral': 0.0, 'pull': 'z+', 'picks': picks})
        top = 10.0 - 20.0 * math.tan(math.radians(5.0))
        r = np.hypot(out.verts[:, 0], out.verts[:, 1])
        tops = np.isclose(out.verts[:, 2], 20.0, atol=1e-5)
        np.testing.assert_allclose(r[tops], top, atol=0.01)
        np.testing.assert_allclose(r[~tops], 10.0, atol=0.01)

    def test_pocket_opens_upwards(self):
        s = plate_with_pocket()
        faces = DR._faces(s)
        tris, face_of, nrm = faces
        inner = []
        for f in DR.walls(faces):
            c = tris[face_of == f].reshape(-1, 3)
            if np.abs(c[:, :2]).max() < 11:
                inner.append(DR.pick_of(s, f, faces))
        self.assertEqual(len(inner), 4)
        out = DR.apply(s, {'angle': 5.0, 'neutral': 10.0, 'pull': 'z+', 'picks': inner})
        self.assertGreater(s.volume(), out.volume())
        d = 10.0 * math.tan(math.radians(5.0))
        top = out.verts[np.isclose(out.verts[:, 2], 20.0, atol=1e-5) & (np.abs(out.verts[:, 0]) < 15)]
        self.assertAlmostEqual(np.abs(top[:, 0]).max(), 10.0 + d, places=3)
        floor = out.verts[np.isclose(out.verts[:, 2], 10.0, atol=1e-5)]
        self.assertAlmostEqual(np.abs(floor[:, 0]).max(), 10.0, places=3)
        self.assertEqual(out.manifold().status(), SO._m().Error.NoError)

    def test_outer_wall_of_the_plate_stays(self):
        s = plate_with_pocket()
        out = DR.apply(s, {'angle': 3.0, 'neutral': 0.0, 'pull': 'z+', 'picks': [wall_pick(s, (1, 0, 0))]})
        self.assertEqual(out.manifold().status(), SO._m().Error.NoError)
        top = out.verts[np.isclose(out.verts[:, 2], 20.0, atol=1e-5)]
        self.assertAlmostEqual(top[:, 0].max(), 30.0 - 20.0 * math.tan(math.radians(3.0)), places=4)
        inner = np.abs(out.verts[:, 0]) < 15
        self.assertAlmostEqual(np.abs(out.verts[inner][:, 0]).max(), 10.0, places=5)
        self.assertAlmostEqual(out.verts[:, 0].min(), -30.0, places=5)

    def test_flat_face_is_refused(self):
        s = box()
        with self.assertRaises(DR.DraftError) as ctx:
            DR.apply(s, {'angle': 5.0, 'pull': 'z+', 'picks': [wall_pick(s, (0, 0, 1))]})
        self.assertIn('parois', str(ctx.exception))

    def test_refusals(self):
        s = box()
        q = wall_pick(s, (1, 0, 0))
        for values in ({'angle': 0.0, 'picks': [q]}, {'angle': 60.0, 'picks': [q]}, {'angle': 5.0, 'picks': []},
                       {'angle': 5.0, 'pull': 'w', 'picks': [q]}, {'angle': 5.0, 'picks': [[500, 0, 0, 1, 0, 0]]}):
            with self.assertRaises(DR.DraftError):
                DR.apply(s, values)
        self.assertTrue(issubclass(DR.DraftError, SO.SolidError))

    def test_neutral_default(self):
        s = SO.box(0, 0, 5, 20, 20, 20)
        self.assertEqual(DR.neutral_default(s, 'z+'), 5.0)
        self.assertEqual(DR.neutral_default(s, 'z-'), -25.0)
        out = DR.apply(s, {'angle': 5.0, 'pull': 'z+', 'picks': [wall_pick(s, (1, 0, 0))]})
        self.assertAlmostEqual(out.verts[:, 0].max(), 20.0, places=5)

    def test_a_face_is_found_by_its_side(self):
        s = box()
        faces = DR._faces(s)
        q = wall_pick(s, (1, 0, 0))
        self.assertEqual(DR.find(faces, q), DR.find(faces, [20.2, 10, 10, 1, 0, 0]))
        with self.assertRaises(DR.DraftError):                    # le bon endroit, mais tournée à l'opposé
            DR.find(faces, [20, 10, 10, -1, 0, 0])

    def test_color_and_name_stay(self):
        s = box()
        s.color, s.name = (0.1, 0.2, 0.3), 'pièce'
        out = DR.apply(s, {'angle': 2.0, 'picks': [wall_pick(s, (1, 0, 0))]})
        self.assertEqual(out.color, (0.1, 0.2, 0.3))
        self.assertEqual(out.name, 'pièce')

    def test_a_large_angle_that_folds_is_refused(self):
        s = SO.box(0, 0, 0, 5, 20, 40)
        faces = DR._faces(s)
        picks = [DR.pick_of(s, f, faces) for f in DR.walls(faces)]
        with self.assertRaises(DR.DraftError):
            DR.apply(s, {'angle': 40.0, 'neutral': 0.0, 'pull': 'z+', 'picks': picks})

    def test_a_pocket_that_reaches_the_outer_wall_is_refused(self):
        s = SO._solid(SO.box(-11, -11, 0, 22, 22, 20).manifold() - SO.box(-10, -10, 10, 20, 20, 20).manifold(), 'p')
        faces = DR._faces(s)
        tris, face_of, _n = faces
        inner = [DR.pick_of(s, f, faces) for f in DR.walls(faces)
                 if np.abs(tris[face_of == f].reshape(-1, 3)[:, :2]).max() < 10.5]
        self.assertEqual(len(inner), 4)
        self.assertLess(DR.apply(s, {'angle': 5.0, 'neutral': 10.0, 'pull': 'z+', 'picks': inner}).volume(), s.volume())
        with self.assertRaises(DR.DraftError) as ctx:
            DR.apply(s, {'angle': 10.0, 'neutral': 10.0, 'pull': 'z+', 'picks': inner})
        self.assertIn('croisent', str(ctx.exception))

    def test_a_rounded_top_asks_to_draft_first(self):
        from vectordrive.core import edge_blend as EB
        s = box()
        chains = EB.sharp_chains(s)
        top = [list(map(float, c.middle())) for c in chains if abs(c.middle()[2] - 20.0) < 1e-6]
        self.assertEqual(len(top), 4)
        out = EB.apply(s, {'kind': 'fillet', 'radius': 3.0, 'radius_end': 3.0, 'picks': top})
        faces = DR._faces(out)
        self.assertEqual(DR.walls(faces), [])                     # le bouton ne la propose pas
        tris, face_of, nrm = faces
        k = int(np.flatnonzero(nrm @ np.array([1.0, 0, 0]) > 0.999)[0])
        with self.assertRaises(DR.DraftError) as ctx:
            DR.apply(out, {'angle': 3.0, 'neutral': 0.0, 'pull': 'z+', 'picks': [DR.pick_of(out, int(face_of[k]), faces)]})
        self.assertIn('avant d’arrondir', str(ctx.exception))

    def test_a_slanted_wall_turns_about_the_neutral_line(self):
        v = np.array([[0.0, 0, 0], [20, 0, 0], [20, 20, 0], [0, 20, 0], [0, 0, 20], [10, 0, 20], [10, 20, 20], [0, 20, 20]])
        t = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                      [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
        s = SO.Solid(v, t, 'p', None)
        n = np.array([2.0, 0, 1]) / math.sqrt(5.0)
        before = math.degrees(math.atan2(10.0, 20.0))
        out = DR.apply(s, {'angle': 5.0, 'neutral': 0.0, 'pull': 'z+', 'picks': [wall_pick(s, n)]})
        top = out.verts[np.isclose(out.verts[:, 2], 20.0, atol=1e-5)][:, 0].max()
        bottom = out.verts[np.isclose(out.verts[:, 2], 0.0, atol=1e-5)][:, 0].max()
        self.assertAlmostEqual(bottom, 20.0, places=5)
        self.assertAlmostEqual(math.degrees(math.atan2(bottom - top, 20.0)), before + 5.0, places=3)

    def part(self):
        man = SO.box(-40, -30, 0, 80, 60, 25).manifold()
        man = man - SO.box(-30, -20, 10, 30, 40, 20).manifold()
        man = man - SO.cylinder(22, 0, 10, 10, 20).manifold()
        return SO._solid(man, 'pièce')

    def test_a_round_pocket_cuts_its_top_face_again(self):
        # Le dessus garde sa forme valable, mais un de ses triangles fins se retournait : un refus à tort
        s = self.part()
        faces = DR._faces(s)
        tan = math.tan(math.radians(3.0))
        out = DR.apply(s, {'angle': 3.0, 'neutral': 0.0, 'pull': 'z+', 'picks': [DR.pick_of(s, f, faces) for f in DR.walls(faces)]})
        self.assertEqual(out.manifold().status(), SO._m().Error.NoError)

        def frustum(a, b, h, d0, d1):
            a0, b0, a1, b1 = a + 2 * d0, b + 2 * d0, a + 2 * d1, b + 2 * d1
            return h / 3.0 * (a0 * b0 + a1 * b1 + math.sqrt(a0 * b0 * a1 * b1))

        tris = s.triangles()
        ring = tris[np.isclose(tris[:, :, 2], 10.0, atol=1e-5).all(axis=1)]
        ring = ring[np.hypot(ring[:, :, 0] - 22, ring[:, :, 1]).max(axis=1) < 10.5]
        k = 1.0
        round_area = float(DR._areas(ring).sum()) / (math.pi * 100.0)
        cone = 15.0 * math.pi * round_area / 3.0 * ((10 + 10 * tan) ** 2 + (10 + 25 * tan) ** 2 + (10 + 10 * tan) * (10 + 25 * tan))
        want = frustum(80, 60, 25, 0.0, -25 * tan) - frustum(30, 40, 15, 10 * tan, 25 * tan) - cone
        self.assertAlmostEqual(out.volume() / want, k, delta=0.002)
        got = DR._faces(out)
        top = np.isclose(got[0][:, :, 2], 25.0, atol=1e-5).all(axis=1) & (DR._areas(got[0]) > 1e-9)
        self.assertTrue((got[2][top, 2] > 0.99).all())

    def test_a_flat_face_cut_again_keeps_its_area(self):
        s = self.part()
        faces = DR._faces(s)
        out = DR.apply(s, {'angle': 3.0, 'neutral': 0.0, 'pull': 'z+', 'picks': [DR.pick_of(s, f, faces) for f in DR.walls(faces)]})
        tris = out.triangles()
        top = np.isclose(tris[:, :, 2], 25.0, atol=1e-5).all(axis=1)
        tan = math.tan(math.radians(3.0))
        side = 80 - 50 * tan, 60 - 50 * tan
        pocket = (30 + 50 * tan) * (40 + 50 * tan)
        ring = 10 + 25 * tan
        self.assertAlmostEqual(float(DR._areas(tris[top]).sum()), side[0] * side[1] - pocket - math.pi * ring ** 2, delta=2.0)

    def test_loops_of_a_flat_face(self):
        t = np.array([[0, 1, 2], [0, 2, 3]])
        self.assertEqual(sorted(len(x) for x in DR._loops(t)), [4])
        with_hole = SO._solid(SO.box(0, 0, 0, 20, 20, 5).manifold() - SO.box(5, 5, -1, 10, 10, 10).manifold(), 'p')
        tris, face_of, nrm = DR._faces(with_hole)
        f = int(face_of[np.flatnonzero(nrm[:, 2] > 0.999)[0]])
        self.assertEqual(sorted(len(x) for x in DR._loops(np.asarray(with_hole.tris)[face_of == f])), [4, 4])

    def test_crossing(self):
        square = np.array([[0.0, 0], [10, 0], [10, 10], [0, 10]])
        self.assertFalse(DR._crossing([square]))
        self.assertTrue(DR._crossing([np.array([[0.0, 0], [10, 10], [10, 0], [0, 10]])]))
        self.assertFalse(DR._crossing([square, square[::-1] / 5.0 + 3.0]))
        self.assertTrue(DR._crossing([square, square[::-1] + 5.0]))

    def test_a_side_turned_over_is_seen(self):
        s = box()
        tris, face_of, _n = DR._faces(s)
        v = np.asarray(s.verts, dtype=np.float64)
        self.assertFalse(DR._side_turned_over(v, v * 2.0, np.asarray(s.tris), face_of))
        self.assertTrue(DR._side_turned_over(v, v * -1.0, np.asarray(s.tris), face_of))

    def bosses(self):
        man = SO.box(-30, -20, 0, 60, 40, 5).manifold() + SO.box(-14, -5, 5, 10, 10, 30).manifold()
        return SO._solid(man + SO.box(4, -5, 5, 10, 10, 30).manifold(), 'p')

    def test_bosses_that_lean_into_each_other_are_refused(self):
        s = self.bosses()
        inner = [wall_pick(s, (1, 0, 0)), None]
        faces = DR._faces(s)
        tris, face_of, nrm = faces
        k = np.flatnonzero(nrm @ np.array([1.0, 0, 0]) > 0.999)
        k = k[np.abs(tris[k].mean(axis=1)[:, 0] + 4) < 1e-6]
        inner[0] = DR.pick_of(s, int(face_of[k[0]]), faces)
        k = np.flatnonzero(nrm @ np.array([-1.0, 0, 0]) > 0.999)
        k = k[np.abs(tris[k].mean(axis=1)[:, 0] - 4) < 1e-6]
        inner[1] = DR.pick_of(s, int(face_of[k[0]]), faces)
        done = DR.apply(s, {'angle': -3.0, 'neutral': 5.0, 'pull': 'z+', 'picks': inner})
        self.assertGreater(done.volume(), s.volume())
        with self.assertRaises(DR.DraftError) as ctx:          # 8 de vide, 30 de haut : 4 chacune à 7,6°
            DR.apply(s, {'angle': -9.0, 'neutral': 5.0, 'pull': 'z+', 'picks': inner})
        self.assertIn('croisent', str(ctx.exception))

    def test_self_crossing(self):
        v = np.array([[0.0, 0, 0], [10, 0, 0], [0, 10, 0], [2, 2, -1], [2, 2, 1], [8, 8, 1], [20.0, 20, 5], [21, 20, 5], [20, 21, 5]])
        t = np.array([[0, 1, 2], [3, 4, 5], [6, 7, 8]])
        real = np.ones(3, dtype=bool)
        moved = np.zeros((3, 3), dtype=bool)
        faces = np.arange(3)
        self.assertFalse(DR.self_crossing(v, t, moved, real, faces))        # rien ne bouge : rien à chercher
        moved[1] = True
        self.assertTrue(DR.self_crossing(v, t, moved, real, faces))
        self.assertFalse(DR.self_crossing(v, t, moved, real, np.zeros(3, dtype=int)))   # dans une même face : pas ici
        moved[:] = False
        moved[2] = True
        self.assertFalse(DR.self_crossing(v, t, moved, real, faces))        # loin de tout
        t2 = np.array([[0, 1, 2], [0, 4, 5]])                        # un sommet commun ne compte pas
        moved = np.zeros((2, 3), dtype=bool)
        moved[1] = True
        self.assertFalse(DR.self_crossing(v, t2, moved, np.ones(2, dtype=bool), np.arange(2)))

    def test_self_crossing_sees_a_contact(self):
        v = np.array([[0.0, 0, 0], [10, 0, 0], [0, 10, 0], [2, 2, 0], [2, 2, 3], [4, 2, 3]])
        t = np.array([[0, 1, 2], [3, 4, 5]])
        moved = np.zeros((2, 3), dtype=bool)
        moved[1] = True
        self.assertTrue(DR.self_crossing(v, t, moved, np.ones(2, dtype=bool), np.arange(2)))

    def test_distances(self):
        t = np.array([[[0.0, 0, 0], [10, 0, 0], [0, 10, 0]]])
        self.assertAlmostEqual(DR._distances(np.array([1.0, 1, 3]), t)[0], 3.0)
        self.assertAlmostEqual(DR._distances(np.array([-3.0, 0, 4]), t)[0], 5.0)


class Dialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def dialog(self, solid=None, last=None):
        from vectordrive.ui.draft3d_dialog import DraftDialog
        d = DraftDialog(self.win, solid or box(), last)
        self.addCleanup(d.deleteLater)
        return d

    def test_walls_button(self):
        d = self.dialog()
        d.walls_button.click()
        self.assertEqual(len(d.view.sel_faces), 4)
        self.assertIn('4', d.status.text())
        d.pull.setCurrentIndex(d.pull.findData('x+'))
        d.walls_button.click()
        self.assertEqual(len(d.view.sel_faces), 4)
        d.none_button.click()
        self.assertEqual(d.view.sel_faces, set())

    def test_values(self):
        d = self.dialog(SO.box(0, 0, 3, 20, 20, 20))
        self.assertEqual(d.neutral.value(), 3.0)
        d.angle.setValue(2.0)
        d.walls_button.click()
        v = d.values()
        self.assertEqual(v['angle'], 2.0)
        self.assertEqual(v['pull'], 'z+')
        self.assertEqual(len(v['picks']), 4)

    def test_neutral_follows_the_pull(self):
        d = self.dialog(SO.box(0, 0, 3, 20, 20, 20))
        d.pull.setCurrentIndex(d.pull.findData('z-'))
        self.assertEqual(d.neutral.value(), -23.0)

    def test_comes_back_with_its_faces(self):
        s = box()
        q = wall_pick(s, (1, 0, 0))
        d = self.dialog(s, {'angle': 7.0, 'pull': 'z+', 'neutral': 2.0, 'picks': [q]})
        self.assertEqual(d.angle.value(), 7.0)
        self.assertEqual(d.neutral.value(), 2.0)
        self.assertEqual(len(d.view.sel_faces), 1)

    def test_lost_faces_are_dropped(self):
        d = self.dialog(last={'picks': [[500, 0, 0, 1, 0, 0]]})
        self.assertEqual(d.view.sel_faces, set())

    def test_stays_open_on_an_error(self):
        d = self.dialog()
        d.accept()
        self.assertEqual(d.result(), 0)
        self.assertIn('aucune', d.status.text())
        d.choose(DR.walls(d.faces))
        d.accept()
        self.assertEqual(d.result(), int(QDialog.DialogCode.Accepted))

    def test_preview_comes_back(self):
        d = self.dialog()
        d.walls_button.click()
        before = d.view.model
        chosen = set(d.view.sel_faces)
        d.preview_button.setChecked(True)
        self.assertIsNot(d.view.model, before)
        self.assertEqual(d.view.select_mode, 'off')
        d.preview_button.setChecked(False)
        self.assertIs(d.view.model, before)
        self.assertEqual(d.view.sel_faces, chosen)
        self.assertEqual(d.view.select_mode, 'faces')

    def test_preview_that_fails_says_why(self):
        d = self.dialog()
        d.preview_button.setChecked(True)
        self.assertFalse(d.preview_button.isChecked())
        self.assertIn('aucune', d.status.text())

    def test_accept_from_the_preview(self):
        d = self.dialog()
        d.walls_button.click()
        d.preview_button.setChecked(True)
        d.accept()
        self.assertEqual(d.result(), int(QDialog.DialogCode.Accepted))
        self.assertEqual(len(d.values()['picks']), 4)


class Command(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.c = self.win.canvas
        self.doc = self.c.doc
        self.doc.layers[0].items = []
        self.c.selection = []
        self.win._undo.clear()
        self.win.settings.remove('cad/solide_depouille')
        self.addCleanup(self.win.settings.remove, 'cad/solide_depouille')

    def add(self, s=None):
        it = SO.make_shape(s or box())
        self.doc.add(it)
        self.c.select([it])
        return it

    def only(self):
        items = [it for it in self.doc.layers[0].items if SO.is_solid(it)]
        self.assertEqual(len(items), 1)
        return items[0], SO.of_item(items[0])

    def values(self, **kw):
        return dict({'angle': 5.0, 'neutral': 0.0, 'pull': 'z+', 'picks': [wall_pick(box(), (1, 0, 0))]}, **kw)

    def test_with_given_values(self):
        self.add()
        out = self.win.solid_draft(params=self.values())
        self.assertEqual(len(out), 1)
        self.assertLess(self.only()[1].volume(), 8000.0)

    def test_nothing_selected(self):
        self.assertEqual(self.win.solid_draft(params=self.values()), [])

    def test_one_volume_at_a_time(self):
        a, b = SO.make_shape(box()), SO.make_shape(SO.box(50, 0, 0, 5, 5, 5))
        self.doc.add(a)
        self.doc.add(b)
        self.c.select([a, b])
        self.assertEqual(self.win.solid_draft(params=self.values()), [])
        self.assertIn('seul', self.win.statusBar().currentMessage())

    def test_error_shows_in_the_status_bar(self):
        it = self.add()
        self.assertEqual(self.win.solid_draft(params=self.values(angle=0.0)), [])
        self.assertIn('nul', self.win.statusBar().currentMessage())
        self.assertIs(self.only()[0], it)

    def test_undo(self):
        self.add()
        self.win.solid_draft(params=self.values())
        self.win.undo()
        self.assertAlmostEqual(self.only()[1].volume(), 8000.0)

    def test_dialog_path(self):
        self.add()
        from vectordrive.ui import draft3d_dialog as DD

        def fake(dlg):
            dlg.walls_button.click()
            dlg.angle.setValue(2.0)
            return 1
        with mock.patch.object(DD.DraftDialog, 'exec', fake):
            out = self.win.solid_draft()
        self.assertEqual(len(out), 1)
        kept = self.win.settings.value('cad/solide_depouille')
        self.assertEqual(kept, {'angle': 2.0, 'pull': 'z+'})

    def test_dialog_cancelled(self):
        it = self.add()
        from vectordrive.ui import draft3d_dialog as DD
        with mock.patch.object(DD.DraftDialog, 'exec', lambda dlg: 0):
            self.assertEqual(self.win.solid_draft(), [])
        self.assertIs(self.only()[0], it)

    def test_history(self):
        self.assertIn('solid_draft', HI.RECORDED)
        self.add()
        it = self.win.solid_draft(params=self.values())[0]
        hist = HI.history_of(it)
        self.assertEqual(hist['steps'][-1]['cmd'], 'solid_draft')
        self.assertEqual(hist['steps'][-1]['params']['angle'], 5.0)
        self.assertEqual(hist['steps'][-1]['params']['picks'], self.values()['picks'])

    def test_history_with_another_angle(self):
        self.add()
        it = self.win.solid_draft(params=self.values())[0]
        v5 = self.only()[1].volume()
        ref = len(HI.history_of(it)['steps']) - 1
        self.assertIsNotNone(self.win.history_set_params(it, ref, {'angle': 10.0}))
        self.assertLess(self.only()[1].volume(), v5)

    def test_history_edit_opens_the_window_with_its_faces(self):
        self.add()
        it = self.win.solid_draft(params=self.values())[0]
        from vectordrive.ui import draft3d_dialog as DD
        seen = {}

        def fake(dlg):
            seen['faces'] = len(dlg.view.sel_faces)
            seen['angle'] = dlg.angle.value()
            dlg.angle.setValue(1.0)
            return 1
        with mock.patch.object(DD.DraftDialog, 'exec', fake):
            new = self.win.history_edit_params(it, len(HI.history_of(it)['steps']) - 1)
        self.assertEqual(seen, {'faces': 1, 'angle': 5.0})
        self.assertIsNotNone(new)

    def test_ribbon(self):
        action = self.win.A['solid_draft']
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups()
                 for b in g.buttons() if b.defaultAction() is action]
        self.assertEqual(len(found), 1)


if __name__ == '__main__':
    unittest.main()
