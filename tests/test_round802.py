"""Round 802 : congés et chanfreins sur les arêtes choisies."""
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
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QDialog

from vectordrive.core import edge_blend as EB
from vectordrive.core import history3d as HI
from vectordrive.core import solids as SO

app = QApplication.instance() or QApplication([])

A = 1.0 - math.pi / 4.0                  # aire retirée par un congé de rayon 1 sur un angle droit
RING = 0.2234                            # distance du centre de cette aire à l'arête, pour un rayon 1


def box():
    return SO.box(0, 0, 0, 20, 20, 20)


def edge(chains, *where):
    """L'arête dont tous les points vérifient where : (axe, valeur)."""
    for c in chains:
        if all(np.allclose(c.points[:, axis], value, atol=1e-6) for axis, value in where):
            return c
    raise AssertionError(where)


def step():
    return SO._solid(SO.box(0, 0, 0, 40, 20, 10).manifold() + SO.box(20, 0, 0, 20, 20, 30).manifold(), 'L')


def plate_with_hole():
    return SO._solid(SO.box(-30, -30, 0, 60, 60, 10).manifold() - SO.cylinder(0, 0, -1.0, 8.0, 13.0).manifold(), 'p')


def plate_with_boss():
    return SO._solid(SO.box(-30, -30, 0, 60, 60, 10).manifold() + SO.cylinder(0, 0, 5.0, 8.0, 20.0).manifold(), 'b')


class Chains(unittest.TestCase):
    def test_box(self):
        c = EB.sharp_chains(box())
        self.assertEqual(len(c), 12)
        self.assertTrue(all(k.convex and not k.closed for k in c))
        self.assertTrue(all(abs(k.length() - 20.0) < 1e-6 for k in c))
        self.assertTrue(all(abs(k.angle - 90.0) < 1e-6 for k in c))

    def test_cylinder_has_two_closed_edges(self):
        c = EB.sharp_chains(SO.cylinder(0, 0, 0, 10, 20))
        self.assertEqual(len(c), 2)
        self.assertTrue(all(k.closed and k.convex for k in c))
        for k in c:
            np.testing.assert_allclose(k.points[0], k.points[-1])

    def test_sphere_has_none(self):
        self.assertEqual(EB.sharp_chains(SO.sphere(0, 0, 0, 10)), [])

    def test_empty(self):
        self.assertEqual(EB.sharp_chains(SO.Solid(np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64))), [])

    def test_step_has_one_inner_edge(self):
        c = EB.sharp_chains(step())
        inner = [k for k in c if not k.convex]
        self.assertEqual(len(inner), 1)
        np.testing.assert_allclose(inner[0].points[:, 0], 20.0)
        np.testing.assert_allclose(inner[0].points[:, 2], 10.0)
        self.assertAlmostEqual(inner[0].length(), 20.0)

    def test_boss_foot_is_inner_and_closed(self):
        inner = [k for k in EB.sharp_chains(plate_with_boss()) if not k.convex]
        self.assertEqual(len(inner), 1)
        self.assertTrue(inner[0].closed)

    def test_hole_rim_is_outer(self):
        rims = [k for k in EB.sharp_chains(plate_with_hole()) if k.closed]
        self.assertEqual(len(rims), 2)
        self.assertTrue(all(k.convex for k in rims))

    def test_a_corner_stops_the_chain(self):
        # sans arête verticale, un contour resterait d'un seul tenant ; ici chaque côté est à part
        c = EB.sharp_chains(box())
        self.assertTrue(all(len(k.points) == 2 for k in c))

    def test_left_and_right_sides(self):
        c = edge(EB.sharp_chains(box()), (1, 0.0), (2, 20.0))
        go = c.points[-1] - c.points[0]
        if go[0] > 0:
            np.testing.assert_allclose(c.left[0], (0, 0, 1), atol=1e-6)
            np.testing.assert_allclose(c.right[0], (0, -1, 0), atol=1e-6)
        else:
            np.testing.assert_allclose(c.left[0], (0, -1, 0), atol=1e-6)
            np.testing.assert_allclose(c.right[0], (0, 0, 1), atol=1e-6)

    def test_middle_is_on_the_edge(self):
        c = edge(EB.sharp_chains(box()), (1, 0.0), (2, 20.0))
        np.testing.assert_allclose(c.middle(), (10, 0, 20), atol=1e-6)
        self.assertLess(c.distance(c.middle()), 1e-9)
        for k in EB.sharp_chains(SO.cylinder(0, 0, 0, 10, 20)):
            self.assertLess(k.distance(k.middle()), 1e-6)

    def test_find(self):
        c = EB.sharp_chains(box())
        k = EB.find(c, [10.1, 0.1, 20.1])
        self.assertLess(c[k].distance([10, 0, 20]), 1e-9)
        with self.assertRaises(EB.EdgeBlendError):
            EB.find(c, [10, 10, 10])
        with self.assertRaises(EB.EdgeBlendError):
            EB.find([], [0, 0, 0])


class Blends(unittest.TestCase):
    def assertWhole(self, s):
        man = s.manifold()
        self.assertEqual(man.status(), SO._m().Error.NoError)

    def test_fillet_takes_the_right_volume(self):
        s = box()
        c = edge(EB.sharp_chains(s), (1, 0.0), (2, 20.0))
        out = EB.apply(s, {'radius': 2.0, 'picks': [c.middle()]})
        self.assertAlmostEqual((s.volume() - out.volume()) / (A * 4 * 20), 1.0, delta=0.04)
        self.assertWhole(out)

    def test_the_rest_does_not_move(self):
        s = box()
        c = edge(EB.sharp_chains(s), (1, 0.0), (2, 20.0))
        out = EB.apply(s, {'radius': 2.0, 'picks': [c.middle()]})
        np.testing.assert_allclose(out.verts.min(axis=0), (0, 0, 0), atol=1e-6)
        np.testing.assert_allclose(out.verts.max(axis=0), (20, 20, 20), atol=1e-6)
        # sept arêtes restent ; à chaque bout du congé, le profil relie les deux qui y arrivaient en une seule
        lengths = sorted(k.length() for k in EB.sharp_chains(out))
        self.assertEqual(len(lengths), 9)
        self.assertEqual(sum(1 for n in lengths if abs(n - 20.0) < 1e-6), 7)
        self.assertAlmostEqual(lengths[-1], 18.0 + 18.0 + math.pi, delta=0.01)

    def test_arc_is_tangent_and_right(self):
        s = box()
        c = edge(EB.sharp_chains(s), (1, 0.0), (2, 20.0))
        out = EB.apply(s, {'radius': 5.0, 'picks': [c.middle()]})
        v = out.verts[(out.verts[:, 1] < 5 - 1e-6) & (out.verts[:, 2] > 15 + 1e-6)]
        self.assertGreater(len(v), 8)
        d = np.hypot(v[:, 1] - 5.0, v[:, 2] - 15.0)
        np.testing.assert_allclose(d, 5.0, atol=1e-3)

    def test_chamfer(self):
        s = box()
        c = edge(EB.sharp_chains(s), (1, 0.0), (2, 20.0))
        out = EB.apply(s, {'kind': 'chamfer', 'radius': 2.0, 'picks': [c.middle()]})
        self.assertAlmostEqual(s.volume() - out.volume(), 40.0, places=2)
        self.assertWhole(out)

    def test_acute_angle(self):
        # un coin aigu : le raccord est plus loin de l'arête qu'à angle droit
        from vectordrive.core import geom
        s = SO.extrude(geom.Path([geom.polyline([(0, 0), (40, 0), (0, 20)], True)]), 10.0)
        tip = [c for c in EB.sharp_chains(s) if np.allclose(c.points[:, :2], (40, 0), atol=1e-6)][0]
        out = EB.apply(s, {'radius': 1.0, 'picks': [tip.middle()]})
        phi = math.atan2(20, 40)
        removed = (1.0 / math.tan(phi / 2) - (math.pi - phi) / 2) * 10.0
        self.assertAlmostEqual((s.volume() - out.volume()) / removed, 1.0, delta=0.05)
        self.assertWhole(out)

    def test_obtuse_angle(self):
        from vectordrive.core import geom
        s = SO.extrude(geom.Path([geom.polyline([(0, 0), (30, 0), (45, 15), (45, 40), (0, 40)], True)]), 10.0)
        c = [k for k in EB.sharp_chains(s) if np.allclose(k.points[:, :2], (30, 0), atol=1e-6)][0]
        self.assertAlmostEqual(c.angle, 45.0, places=4)
        out = EB.apply(s, {'radius': 3.0, 'picks': [c.middle()]})
        phi = math.radians(135.0)
        removed = 9.0 * (1.0 / math.tan(phi / 2) - (math.pi - phi) / 2) * 10.0
        self.assertAlmostEqual((s.volume() - out.volume()) / removed, 1.0, delta=0.1)

    def test_variable_radius(self):
        s = box()
        c = edge(EB.sharp_chains(s), (1, 0.0), (2, 20.0))
        out = EB.apply(s, {'radius': 2.0, 'radius_end': 4.0, 'picks': [c.middle()]})
        lost = s.volume() - out.volume()
        self.assertGreater(lost, A * 4 * 20)
        self.assertLess(lost, A * 16 * 20)
        self.assertAlmostEqual(lost / (A * (4 + 8 + 16) / 3 * 20), 1.0, delta=0.12)
        ends = out.verts[np.isclose(out.verts[:, 1], 0.0, atol=1e-6)]
        top = ends[:, 2].max()
        self.assertAlmostEqual(top, 18.0 if c.points[0][0] < 1 else 16.0, delta=2.01)
        self.assertWhole(out)

    def test_variable_chamfer(self):
        s = box()
        c = edge(EB.sharp_chains(s), (1, 0.0), (2, 20.0))
        out = EB.apply(s, {'kind': 'chamfer', 'radius': 1.0, 'radius_end': 3.0, 'picks': [c.middle()]})
        self.assertAlmostEqual((s.volume() - out.volume()) / (0.5 * (1 + 3 + 9) / 3 * 20), 1.0, delta=0.05)

    def test_inner_edge_adds_material(self):
        s = step()
        c = [k for k in EB.sharp_chains(s) if not k.convex][0]
        out = EB.apply(s, {'radius': 2.0, 'picks': [c.middle()]})
        self.assertAlmostEqual((out.volume() - s.volume()) / (A * 4 * 20), 1.0, delta=0.04)
        np.testing.assert_allclose(out.verts.min(axis=0), (0, 0, 0), atol=1e-5)
        np.testing.assert_allclose(out.verts.max(axis=0), (40, 20, 30), atol=1e-5)
        self.assertWhole(out)

    def test_inner_chamfer(self):
        s = step()
        c = [k for k in EB.sharp_chains(s) if not k.convex][0]
        out = EB.apply(s, {'kind': 'chamfer', 'radius': 2.0, 'picks': [c.middle()]})
        self.assertAlmostEqual(out.volume() - s.volume(), 40.0, places=2)

    def test_edge_stopped_by_a_wall_leaves_the_wall(self):
        s = step()
        c = edge(EB.sharp_chains(s), (1, 0.0), (2, 10.0))
        self.assertAlmostEqual(c.length(), 20.0)
        out = EB.apply(s, {'radius': 2.0, 'picks': [c.middle()]})
        self.assertAlmostEqual((s.volume() - out.volume()) / (A * 4 * 20), 1.0, delta=0.04)
        # le profil du congé s'arrête sur la paroi, qui garde son haut
        for q in ((20, 0, 8), (20, 2, 10), (20, 0, 30)):
            self.assertTrue(np.any(np.all(np.isclose(out.verts, q, atol=1e-4), axis=1)), q)
        self.assertWhole(out)

    def test_cylinder_rim(self):
        s = SO.cylinder(0, 0, 0, 10, 20)
        rim = max(EB.sharp_chains(s), key=lambda k: k.points[:, 2].max())
        out = EB.apply(s, {'radius': 2.0, 'picks': [rim.middle()]})
        want = 2 * math.pi * (10 - RING * 2) * A * 4
        self.assertAlmostEqual((s.volume() - out.volume()) / want, 1.0, delta=0.05)
        self.assertWhole(out)
        self.assertAlmostEqual(np.hypot(*out.verts[np.isclose(out.verts[:, 2], 20.0, atol=1e-6)][:, :2].T).max(), 8.0, delta=0.02)

    def test_hole_rim_keeps_the_hole(self):
        s = plate_with_hole()
        rim = [k for k in EB.sharp_chains(s) if k.closed and k.points[:, 2].max() > 9][0]
        out = EB.apply(s, {'radius': 2.0, 'picks': [rim.middle()]})
        want = 2 * math.pi * (8 + RING * 2) * A * 4
        self.assertAlmostEqual((s.volume() - out.volume()) / want, 1.0, delta=0.05)
        self.assertEqual(out.manifold().genus(), 1)

    def test_boss_foot(self):
        s = plate_with_boss()
        foot = [k for k in EB.sharp_chains(s) if not k.convex][0]
        out = EB.apply(s, {'radius': 2.0, 'picks': [foot.middle()]})
        want = 2 * math.pi * (8 + RING * 2) * A * 4
        self.assertAlmostEqual((out.volume() - s.volume()) / want, 1.0, delta=0.05)
        self.assertWhole(out)

    def test_corner_of_three_is_a_ball(self):
        s = box()
        at = np.array([20.0, 20.0, 20.0])
        three = [c for c in EB.sharp_chains(s) if min(np.linalg.norm(c.points[0] - at), np.linalg.norm(c.points[-1] - at)) < 1e-6]
        self.assertEqual(len(three), 3)
        out = EB.apply(s, {'radius': 3.0, 'picks': [c.middle() for c in three]})
        centre = at - 3.0
        v = out.verts[np.all(out.verts >= centre - 1e-6, axis=1)]
        self.assertGreater(len(v), 20)
        d = np.linalg.norm(v - centre, axis=1)
        self.assertLess(d.max(), 3.0 + 1e-3)
        self.assertGreater(d.min(), 3.0 - 0.02)
        self.assertWhole(out)

    def test_every_edge_of_a_box_is_a_rounded_box(self):
        s = box()
        out = EB.apply(s, {'radius': 3.0, 'picks': [c.middle() for c in EB.sharp_chains(s)]})
        a, r = 14.0, 3.0
        want = a ** 3 + 3 * a ** 2 * 2 * r + 3 * a * math.pi * r ** 2 + 4.0 / 3.0 * math.pi * r ** 3
        self.assertAlmostEqual(out.volume() / want, 1.0, delta=0.005)
        self.assertEqual(out.manifold().genus(), 0)
        self.assertEqual(EB.sharp_chains(out, 45.0), [])

    def test_two_edges_meeting_on_an_edge_left_sharp(self):
        s = box()
        c1 = edge(EB.sharp_chains(s), (1, 0.0), (2, 20.0))
        c2 = edge(EB.sharp_chains(s), (0, 0.0), (2, 20.0))
        out = EB.apply(s, {'radius': 2.0, 'picks': [c1.middle(), c2.middle()]})
        self.assertAlmostEqual((s.volume() - out.volume()) / (2 * A * 4 * 20), 1.0, delta=0.04)
        self.assertWhole(out)

    def test_same_edge_twice_counts_once(self):
        s = box()
        c = edge(EB.sharp_chains(s), (1, 0.0), (2, 20.0))
        one = EB.apply(s, {'radius': 2.0, 'picks': [c.middle()]})
        two = EB.apply(s, {'radius': 2.0, 'picks': [c.middle(), [5, 0, 20]]})
        self.assertAlmostEqual(one.volume(), two.volume())

    def test_too_big_is_refused_with_the_limit(self):
        s = SO.box(0, 0, 0, 20, 20, 4)
        c = edge(EB.sharp_chains(s), (1, 0.0), (2, 4.0))
        with self.assertRaises(EB.EdgeBlendError) as ctx:
            EB.apply(s, {'radius': 5.0, 'picks': [c.middle()]})
        self.assertIn('au plus', str(ctx.exception))
        top = EB.largest(c, s)
        self.assertGreater(top, 3.5)
        self.assertLess(top, 4.6)
        EB.apply(s, {'radius': 3.9, 'picks': [c.middle()]})

    def test_too_big_chamfer_on_a_narrow_face(self):
        s = SO.box(0, 0, 0, 20, 3, 20)
        c = edge(EB.sharp_chains(s), (1, 0.0), (2, 20.0))
        with self.assertRaises(EB.EdgeBlendError):
            EB.apply(s, {'kind': 'chamfer', 'radius': 4.0, 'picks': [c.middle()]})

    def test_refusals(self):
        s = box()
        with self.assertRaises(EB.EdgeBlendError):
            EB.apply(s, {'radius': 1.0, 'picks': []})
        with self.assertRaises(EB.EdgeBlendError):
            EB.apply(s, {'radius': 0.0, 'picks': [[10, 0, 20]]})
        with self.assertRaises(EB.EdgeBlendError):
            EB.apply(s, {'radius': 1.0, 'picks': [[10, 10, 10]]})
        self.assertTrue(issubclass(EB.EdgeBlendError, SO.SolidError))

    def test_color_and_name_stay(self):
        s = box()
        s.color, s.name = (0.1, 0.2, 0.3), 'pièce'
        out = EB.apply(s, {'radius': 1.0, 'picks': [[10, 0, 20]]})
        self.assertEqual(out.color, (0.1, 0.2, 0.3))
        self.assertEqual(out.name, 'pièce')

    def test_a_turned_part(self):
        m = np.eye(4)
        m[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
        m[:3, 3] = (5, 6, 7)
        s = box().transformed(m)
        c = EB.sharp_chains(s)
        out = EB.apply(s, {'radius': 2.0, 'picks': [c[0].middle()]})
        self.assertAlmostEqual((s.volume() - out.volume()) / (A * 4 * 20), 1.0, delta=0.04)

    def test_arc_sides(self):
        self.assertEqual(EB._arc_sides(0.001), 3)
        self.assertLessEqual(EB._arc_sides(1000.0), EB.MAX_SEGMENTS)
        self.assertGreater(EB._arc_sides(10.0), EB._arc_sides(1.0))


class View(unittest.TestCase):
    def view(self, solid):
        from vectordrive.ui.view3d import View3D
        v = View3D()
        v.resize(800, 600)
        v.set_model(SO.to_model([solid]))
        v.select_mode = 'aretes'
        chains = EB.sharp_chains(solid)
        v.set_edge_chains([c.points for c in chains])
        return v, chains

    def screen(self, v, q):
        m = np.array(v.camera().data(), dtype=np.float64).reshape(4, 4)
        h = np.r_[q, 1.0] @ m
        return QPointF((h[0] / h[3] + 1) * 0.5 * v.width(), (1 - h[1] / h[3]) * 0.5 * v.height())

    def seen(self, v, chains):
        """Une arête vue dans cette vue : dessus de la pièce, côté caméra."""
        for k, c in enumerate(chains):
            if v.edge_at(self.screen(v, c.middle())) == k:
                return k
        raise AssertionError('aucune arête cliquable')

    def test_a_click_takes_an_edge(self):
        v, chains = self.view(box())
        k = self.seen(v, chains)
        self.assertEqual(v.select_at(self.screen(v, chains[k].middle())), k)
        self.assertEqual(v.sel_edges, {k})
        self.assertEqual(len(v.sel_loops), 1)
        np.testing.assert_allclose(v.sel_loops[0], chains[k].points)

    def test_a_second_click_gives_it_back(self):
        v, chains = self.view(box())
        k = self.seen(v, chains)
        at = self.screen(v, chains[k].middle())
        v.select_at(at)
        v.select_at(at)
        self.assertEqual(v.sel_edges, set())
        self.assertEqual(v.sel_loops, [])

    def test_clicks_add_up(self):
        v, chains = self.view(box())
        hit = []
        for k, c in enumerate(chains):
            if v.edge_at(self.screen(v, c.middle())) == k:
                v.select_at(self.screen(v, c.middle()))
                hit.append(k)
        self.assertGreater(len(hit), 3)
        self.assertEqual(v.sel_edges, set(hit))

    def test_click_in_the_void_changes_nothing(self):
        v, chains = self.view(box())
        k = self.seen(v, chains)
        v.select_at(self.screen(v, chains[k].middle()))
        self.assertIsNone(v.select_at(QPointF(2, 2)))
        self.assertEqual(v.sel_edges, {k})

    def test_seen_edge_before_hidden_edge(self):
        # vue de dessus : les arêtes du dessus et celles du dessous se projettent presque au même endroit
        v, chains = self.view(box())
        v.set_ortho(True)
        v.yaw, v.pitch = 0.0, 89.0
        for k, c in enumerate(chains):
            if abs(c.points[:, 2] - 20).max() < 1e-6:
                got = v.edge_at(self.screen(v, c.middle()))
                self.assertLess(abs(chains[got].points[:, 2] - 20).max(), 1e-6)

    def test_no_edges_no_pick(self):
        from vectordrive.ui.view3d import View3D
        v = View3D()
        v.resize(100, 100)
        self.assertIsNone(v.edge_at(QPointF(5, 5)))

    def test_set_edge_selection_keeps_to_known_ranks(self):
        v, chains = self.view(box())
        v.set_edge_selection([0, 1, 99, -1])
        self.assertEqual(v.sel_edges, {0, 1})

    def test_new_chains_clear_the_selection(self):
        v, chains = self.view(box())
        v.set_edge_selection([0])
        v.set_edge_chains([c.points for c in chains])
        self.assertEqual(v.sel_edges, set())


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
        from vectordrive.ui.edges3d_dialog import EdgesDialog
        d = EdgesDialog(self.win, solid or box(), last)
        self.addCleanup(d.deleteLater)
        return d

    def test_buttons(self):
        d = self.dialog(step())
        n = len(d.chains)
        d.all_button.click()
        self.assertEqual(len(d.view.sel_edges), n)
        self.assertIn(str(n), d.status.text())
        d.in_button.click()
        self.assertEqual(len(d.view.sel_edges), 1)
        d.out_button.click()
        self.assertEqual(len(d.view.sel_edges), n - 1)
        d.none_button.click()
        self.assertEqual(d.view.sel_edges, set())

    def test_values(self):
        d = self.dialog()
        d.radius.setValue(1.5)
        d.kind.setCurrentIndex(1)
        d.choose([0])
        v = d.values()
        self.assertEqual(v['kind'], 'chamfer')
        self.assertEqual(v['radius'], 1.5)
        self.assertEqual(v['radius_end'], 0.0)
        self.assertEqual(v['picks'], [d.chains[0].middle()])
        d.variable.setChecked(True)
        d.end.setValue(3.0)
        self.assertEqual(d.values()['radius_end'], 3.0)

    def test_keeps_its_settings(self):
        d = self.dialog(last={'kind': 'chamfer', 'radius': 4.0, 'radius_end': 6.0, 'picks': [[10, 0, 20]]})
        self.assertEqual(d.values()['kind'], 'chamfer')
        self.assertEqual(d.radius.value(), 4.0)
        self.assertTrue(d.variable.isChecked())
        self.assertEqual(d.end.value(), 6.0)
        self.assertEqual(len(d.view.sel_edges), 1)

    def test_lost_edges_are_dropped_on_opening(self):
        d = self.dialog(last={'picks': [[500, 500, 500]]})
        self.assertEqual(d.view.sel_edges, set())

    def test_no_edge_is_told(self):
        d = self.dialog(SO.sphere(0, 0, 0, 10))
        self.assertIn('arête vive', d.status.text())

    def test_stays_open_on_an_error(self):
        d = self.dialog()
        d.accept()                                       # rien de choisi
        self.assertEqual(d.result(), 0)
        self.assertIn('aucune', d.status.text())
        d.choose([0])
        d.radius.setValue(500.0)
        d.accept()
        self.assertEqual(d.result(), 0)
        self.assertIn('au plus', d.status.text())
        self.assertEqual(len(d.view.sel_edges), 1)
        d.radius.setValue(1.0)
        d.accept()
        self.assertEqual(d.result(), int(QDialog.DialogCode.Accepted))

    def test_preview_comes_back(self):
        d = self.dialog()
        d.choose([0, 1])
        before = d.view.model
        d.preview_button.setChecked(True)
        self.assertIsNot(d.view.model, before)
        self.assertEqual(d.view.edge_chains, [])
        d.preview_button.setChecked(False)
        self.assertIs(d.view.model, before)
        self.assertEqual(d.view.sel_edges, {0, 1})
        self.assertEqual(len(d.view.sel_loops), 2)
        self.assertEqual(len(d.view.edge_chains), len(d.chains))

    def test_preview_that_fails_says_why(self):
        d = self.dialog()
        d.choose([0])
        d.radius.setValue(500.0)
        d.preview_button.setChecked(True)
        self.assertFalse(d.preview_button.isChecked())
        self.assertIn('au plus', d.status.text())

    def test_accept_from_the_preview(self):
        d = self.dialog()
        d.choose([0])
        d.preview_button.setChecked(True)
        d.accept()
        self.assertEqual(d.result(), int(QDialog.DialogCode.Accepted))
        self.assertEqual(len(d.values()['picks']), 1)


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
        self.win.settings.remove('cad/solide_aretes')
        self.addCleanup(self.win.settings.remove, 'cad/solide_aretes')

    def add(self, s=None):
        it = SO.make_shape(s or box())
        self.doc.add(it)
        self.c.select([it])
        return it

    def only(self):
        items = [it for it in self.doc.layers[0].items if SO.is_solid(it)]
        self.assertEqual(len(items), 1)
        return items[0], SO.of_item(items[0])

    def test_with_given_values(self):
        self.add()
        out = self.win.solid_edges(params={'radius': 2.0, 'picks': [[10, 0, 20]]})
        self.assertEqual(len(out), 1)
        s = self.only()[1]
        self.assertAlmostEqual((8000 - s.volume()) / (A * 4 * 20), 1.0, delta=0.04)

    def test_nothing_selected(self):
        self.assertEqual(self.win.solid_edges(params={'radius': 2.0, 'picks': [[10, 0, 20]]}), [])
        self.assertIn('volumes', self.win.statusBar().currentMessage())

    def test_one_volume_at_a_time(self):
        a, b = SO.make_shape(box()), SO.make_shape(SO.box(50, 0, 0, 5, 5, 5))
        self.doc.add(a)
        self.doc.add(b)
        self.c.select([a, b])
        self.assertEqual(self.win.solid_edges(params={'radius': 1.0, 'picks': [[10, 0, 20]]}), [])
        self.assertIn('seul', self.win.statusBar().currentMessage())

    def test_error_shows_in_the_status_bar(self):
        it = self.add()
        self.assertEqual(self.win.solid_edges(params={'radius': 500.0, 'picks': [[10, 0, 20]]}), [])
        self.assertIn('au plus', self.win.statusBar().currentMessage())
        self.assertIs(self.only()[0], it)

    def test_undo(self):
        self.add()
        self.win.solid_edges(params={'radius': 2.0, 'picks': [[10, 0, 20]]})
        self.win.undo()
        self.assertAlmostEqual(self.only()[1].volume(), 8000.0)

    def test_dialog_path(self):
        self.add()
        from vectordrive.ui import edges3d_dialog as ED

        def fake(dlg):
            dlg.choose([0])
            dlg.radius.setValue(1.5)
            return 1
        with mock.patch.object(ED.EdgesDialog, 'exec', fake):
            out = self.win.solid_edges()
        self.assertEqual(len(out), 1)
        kept = self.win.settings.value('cad/solide_aretes')
        self.assertEqual(kept['radius'], 1.5)
        self.assertNotIn('picks', kept)

    def test_dialog_cancelled(self):
        it = self.add()
        from vectordrive.ui import edges3d_dialog as ED
        with mock.patch.object(ED.EdgesDialog, 'exec', lambda dlg: 0):
            self.assertEqual(self.win.solid_edges(), [])
        self.assertIs(self.only()[0], it)

    def test_is_in_the_history(self):
        self.assertIn('solid_edges', HI.RECORDED)
        self.add()
        out = self.win.solid_edges(params={'radius': 2.0, 'picks': [[10, 0, 20]]})
        hist = HI.history_of(out[0])
        self.assertEqual(hist['steps'][-1]['cmd'], 'solid_edges')
        self.assertEqual(hist['steps'][-1]['params']['picks'], [[10, 0, 20]])
        self.assertIn('2', hist['steps'][-1]['shown'])

    def test_history_replays_with_another_radius(self):
        self.add()
        it = self.win.solid_edges(params={'radius': 2.0, 'picks': [[10, 0, 20]]})[0]
        ref = len(HI.history_of(it)['steps']) - 1
        new = self.win.history_set_params(it, ref, {'radius': 4.0, 'picks': [[10, 0, 20]]})
        self.assertIsNotNone(new)
        s = self.only()[1]
        self.assertAlmostEqual((8000 - s.volume()) / (A * 16 * 20), 1.0, delta=0.04)

    def test_history_says_when_the_edge_is_gone(self):
        self.add()
        it = self.win.solid_edges(params={'radius': 2.0, 'picks': [[10, 0, 20]]})[0]
        ref = len(HI.history_of(it)['steps']) - 1
        self.assertIsNone(self.win.history_set_params(it, ref, {'radius': 2.0, 'picks': [[10, 10, 10]]}))
        self.assertAlmostEqual((8000 - self.only()[1].volume()) / (A * 4 * 20), 1.0, delta=0.04)

    def test_history_edit_opens_the_window_with_its_edges(self):
        self.add()
        out = self.win.solid_edges(params={'radius': 2.0, 'picks': [[10, 0, 20]]})
        it = out[0]
        from vectordrive.ui import edges3d_dialog as ED
        seen = {}

        def fake(dlg):
            seen['picked'] = len(dlg.view.sel_edges)
            seen['radius'] = dlg.radius.value()
            dlg.radius.setValue(4.0)
            return 1
        with mock.patch.object(ED.EdgesDialog, 'exec', fake):
            new = self.win.history_edit_params(it, len(HI.history_of(it)['steps']) - 1)
        self.assertEqual(seen, {'picked': 1, 'radius': 2.0})
        self.assertIsNotNone(new)
        self.assertAlmostEqual((8000 - self.only()[1].volume()) / (A * 16 * 20), 1.0, delta=0.04)

    def test_ribbon(self):
        action = self.win.A['solid_edges']
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups()
                 for b in g.buttons() if b.defaultAction() is action]
        self.assertEqual(len(found), 1)


if __name__ == '__main__':
    unittest.main()
