"""Round 804 : déplacer des faces d'un volume déjà fait."""
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
from vectordrive.core import face_move as FM
from vectordrive.core import history3d as HI
from vectordrive.core import solids as SO

app = QApplication.instance() or QApplication([])


def box():
    return SO.box(0, 0, 0, 20, 20, 20)


def pick(solid, normal, near=None):
    """Une face de cette normale ; la plus proche de `near` s'il y en a plusieurs."""
    faces = DR._faces(solid)
    tris, face_of, nrm = faces
    k = np.flatnonzero(nrm @ np.array(normal, dtype=float) > 0.999)
    if near is not None:
        k = k[np.argmin(np.linalg.norm(tris[k].mean(axis=1) - np.array(near, dtype=float), axis=1))]
    else:
        k = k[0]
    return DR.pick_of(solid, int(face_of[k]), faces)


def curved(solid):
    """Les faces courbes : celles qui ont des normales différentes."""
    faces = DR._faces(solid)
    tris, face_of, nrm = faces
    out = []
    for f in np.unique(face_of):
        n = nrm[face_of == f]
        if float(np.linalg.norm(n - n[0], axis=1).max()) > 0.1:
            out.append(DR.pick_of(solid, int(f), faces))
    return out


def plate_with_hole(r=5.0):
    return SO._solid(SO.box(-20, -20, 0, 40, 40, 10).manifold() - SO.cylinder(0, 0, -1, r, 12).manifold(), 'p')


def plate_with_pocket():
    return SO._solid(SO.box(-20, -20, 0, 40, 40, 10).manifold() - SO.box(-5, -5, 4, 10, 10, 10).manifold(), 'p')


def plate_with_boss():
    return SO._solid(SO.box(-20, -20, 0, 40, 40, 5).manifold() + SO.cylinder(0, 0, 5, 6, 10).manifold(), 'p')


class Along(unittest.TestCase):
    def test_one_wall_out(self):
        s = box()
        out = FM.apply(s, {'mode': 'normal', 'distance': 5.0, 'picks': [pick(s, (1, 0, 0))]})
        self.assertAlmostEqual(out.verts[:, 0].max(), 25.0, places=5)
        self.assertAlmostEqual(out.volume(), 8000.0 + 5 * 400, places=2)

    def test_one_wall_in(self):
        s = box()
        out = FM.apply(s, {'mode': 'normal', 'distance': -5.0, 'picks': [pick(s, (1, 0, 0))]})
        self.assertAlmostEqual(out.volume(), 8000.0 - 5 * 400, places=2)

    def test_two_walls_meet_at_their_new_corner(self):
        s = box()
        out = FM.apply(s, {'mode': 'normal', 'distance': 2.0, 'picks': [pick(s, (1, 0, 0)), pick(s, (0, 1, 0))]})
        self.assertAlmostEqual(out.volume(), 22 * 22 * 20, places=2)

    def test_every_face(self):
        s = box()
        faces = DR._faces(s)
        picks = [DR.pick_of(s, int(f), faces) for f in np.unique(faces[1])]
        out = FM.apply(s, {'mode': 'normal', 'distance': 1.0, 'picks': picks})
        self.assertAlmostEqual(out.volume(), 22 ** 3, places=2)

    def test_a_hole_closes_with_a_positive_distance(self):
        s = plate_with_hole()
        hole = curved(s)
        self.assertEqual(len(hole), 1)
        out = FM.apply(s, {'mode': 'normal', 'distance': 1.0, 'picks': hole})
        r = np.hypot(out.verts[:, 0], out.verts[:, 1])
        np.testing.assert_allclose(r[r < 10], 4.0, atol=0.01)
        self.assertGreater(out.volume(), s.volume())

    def test_a_hole_opens_with_a_negative_distance(self):
        s = plate_with_hole()
        out = FM.apply(s, {'mode': 'normal', 'distance': -2.0, 'picks': curved(s)})
        r = np.hypot(out.verts[:, 0], out.verts[:, 1])
        np.testing.assert_allclose(r[r < 10], 7.0, atol=0.01)
        self.assertEqual(out.manifold().status(), SO._m().Error.NoError)

    def test_a_hole_that_reaches_the_edge_is_refused(self):
        s = plate_with_hole()
        with self.assertRaises(DR.DraftError):
            FM.apply(s, {'mode': 'normal', 'distance': -20.0, 'picks': curved(s)})

    def test_a_hole_cannot_close_altogether(self):
        s = plate_with_hole()
        with self.assertRaises(DR.DraftError):
            FM.apply(s, {'mode': 'normal', 'distance': 6.0, 'picks': curved(s)})

    def test_pocket_floor(self):
        s = plate_with_pocket()
        v0 = s.volume()
        floor = pick(s, (0, 0, 1), near=(0, 0, 4))
        out = FM.apply(s, {'mode': 'normal', 'distance': 3.0, 'picks': [floor]})
        self.assertAlmostEqual(out.volume(), v0 + 3 * 100, places=2)
        out = FM.apply(s, {'mode': 'normal', 'distance': -2.0, 'picks': [floor]})
        self.assertAlmostEqual(out.volume(), v0 - 2 * 100, places=2)

    def test_pocket_floor_through_the_top_is_refused(self):
        s = plate_with_pocket()
        with self.assertRaises(DR.DraftError):
            FM.apply(s, {'mode': 'normal', 'distance': 7.0, 'picks': [pick(s, (0, 0, 1), near=(0, 0, 4))]})

    def test_pocket_floor_through_the_bottom_is_refused(self):
        s = plate_with_pocket()
        with self.assertRaises(DR.DraftError):
            FM.apply(s, {'mode': 'normal', 'distance': -5.0, 'picks': [pick(s, (0, 0, 1), near=(0, 0, 4))]})

    def test_pocket_floor_on_the_bottom_is_refused(self):
        s = plate_with_pocket()
        with self.assertRaises(DR.DraftError):                 # épaisseur nulle : le fond touche le dessous
            FM.apply(s, {'mode': 'normal', 'distance': -4.0, 'picks': [pick(s, (0, 0, 1), near=(0, 0, 4))]})

    def test_wall_through_the_opposite_one_is_refused(self):
        s = box()
        with self.assertRaises(DR.DraftError) as ctx:
            FM.apply(s, {'mode': 'normal', 'distance': -25.0, 'picks': [pick(s, (1, 0, 0))]})
        self.assertIn('croisent', str(ctx.exception))

    def test_wall_up_to_the_pocket_is_refused(self):
        s = plate_with_pocket()
        with self.assertRaises(DR.DraftError):
            FM.apply(s, {'mode': 'normal', 'distance': -16.0, 'picks': [pick(s, (1, 0, 0), near=(20, 0, 5))]})

    def test_boss_gets_taller_and_wider(self):
        s = plate_with_boss()
        top = pick(s, (0, 0, 1), near=(0, 0, 15))
        out = FM.apply(s, {'mode': 'normal', 'distance': 3.0, 'picks': [top]})
        self.assertAlmostEqual(out.verts[:, 2].max(), 18.0, places=5)
        side = curved(s)
        self.assertEqual(len(side), 1)
        out = FM.apply(s, {'mode': 'normal', 'distance': 2.0, 'picks': side})
        r = np.hypot(out.verts[:, 0], out.verts[:, 1])
        np.testing.assert_allclose(r[(r < 15)], 8.0, atol=0.01)

    def test_a_slanted_neighbour_follows(self):
        v = np.array([[0.0, 0, 0], [20, 0, 0], [20, 20, 0], [0, 20, 0], [0, 0, 20], [10, 0, 20], [10, 20, 20], [0, 20, 20]])
        t = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                      [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
        s = SO.Solid(v, t, 'p', None)
        out = FM.apply(s, {'mode': 'normal', 'distance': 5.0, 'picks': [pick(s, (0, 0, 1))]})
        top = out.verts[np.isclose(out.verts[:, 2], 25.0, atol=1e-5)]
        self.assertAlmostEqual(top[:, 0].max(), 7.5, places=4)        # la pente continue : 10 de moins pour 20 de haut


class ByVector(unittest.TestCase):
    def test_a_hole_moves_whole(self):
        s = plate_with_hole()
        out = FM.apply(s, {'mode': 'vector', 'dx': 6.0, 'dy': -3.0, 'picks': curved(s)})
        self.assertAlmostEqual(out.volume(), s.volume(), places=1)
        inner = out.verts[np.hypot(out.verts[:, 0] - 6.0, out.verts[:, 1] + 3.0) < 8.0]
        np.testing.assert_allclose(np.hypot(inner[:, 0] - 6.0, inner[:, 1] + 3.0), 5.0, atol=0.01)
        self.assertAlmostEqual(out.verts[:, 0].max(), 20.0, places=5)

    def test_a_hole_keeps_its_top_face_clean(self):
        s = plate_with_hole()
        out = FM.apply(s, {'mode': 'vector', 'dx': 10.0, 'picks': curved(s)})
        tris = out.triangles()
        top = np.isclose(tris[:, :, 2], 10.0, atol=1e-5).all(axis=1)
        faces = DR.faces3d.normals(tris[top])
        keep = DR._areas(tris[top]) > 1e-9
        self.assertTrue((faces[keep][:, 2] > 0.99).all())
        self.assertAlmostEqual(float(DR._areas(tris[top]).sum()), s.volume() / 10.0, delta=0.01)

    def test_a_hole_out_of_the_plate_is_refused(self):
        s = plate_with_hole()
        with self.assertRaises(DR.DraftError):
            FM.apply(s, {'mode': 'vector', 'dx': 18.0, 'picks': curved(s)})

    def test_a_blind_hole_moves_with_its_walls_only(self):
        s = SO._solid(SO.box(-20, -20, 0, 40, 40, 10).manifold() - SO.cylinder(0, 0, 4, 5, 12).manifold(), 'p')
        walls = curved(s)
        self.assertEqual(len(walls), 1)
        out = FM.apply(s, {'mode': 'vector', 'dx': 6.0, 'picks': walls})
        self.assertAlmostEqual(out.volume(), s.volume(), places=1)
        low = out.verts[np.isclose(out.verts[:, 2], 4.0, atol=1e-5)]
        self.assertAlmostEqual(low[:, 0].max(), 11.0, delta=0.02)

    def test_a_boss_moves_on_its_plate(self):
        s = plate_with_boss()
        picks = curved(s) + [pick(s, (0, 0, 1), near=(0, 0, 15))]
        out = FM.apply(s, {'mode': 'vector', 'dx': 7.0, 'picks': picks})
        self.assertAlmostEqual(out.volume(), s.volume(), places=1)
        top = out.verts[np.isclose(out.verts[:, 2], 15.0, atol=1e-5)]
        self.assertAlmostEqual(float(top[:, 0].mean()), 7.0, delta=0.05)

    def test_a_vector_upwards_keeps_the_foot_on_the_plate(self):
        s = plate_with_boss()
        picks = curved(s) + [pick(s, (0, 0, 1), near=(0, 0, 15))]
        out = FM.apply(s, {'mode': 'vector', 'dx': 3.0, 'dz': 2.0, 'picks': picks})
        foot = out.verts[np.isclose(out.verts[:, 2], 5.0, atol=1e-5)]
        inner = foot[np.hypot(foot[:, 0] - 3.0, foot[:, 1]) < 8.0]
        np.testing.assert_allclose(np.hypot(inner[:, 0] - 3.0, inner[:, 1]), 6.0, atol=0.01)
        self.assertAlmostEqual(out.verts[:, 2].max(), 17.0, places=5)

    def test_a_wall_along_itself_changes_nothing(self):
        s = box()
        out = FM.apply(s, {'mode': 'vector', 'dy': 3.0, 'picks': [pick(s, (1, 0, 0))]})
        self.assertAlmostEqual(out.volume(), 8000.0, places=2)
        self.assertAlmostEqual(out.verts[:, 1].max(), 20.0, places=5)


class Refusals(unittest.TestCase):
    def test_refusals(self):
        s = box()
        q = pick(s, (1, 0, 0))
        for v in ({'mode': 'normal', 'distance': 0.0, 'picks': [q]}, {'mode': 'vector', 'picks': [q]},
                  {'mode': 'normal', 'distance': 1.0, 'picks': []}, {'mode': 'w', 'distance': 1.0, 'picks': [q]},
                  {'mode': 'normal', 'distance': 1e7, 'picks': [q]}, {'mode': 'normal', 'distance': float('inf'), 'picks': [q]},
                  {'mode': 'normal', 'distance': 1.0, 'picks': [[500, 0, 0, 1, 0, 0]]}):
            with self.assertRaises(DR.DraftError):
                FM.apply(s, v)


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
        from vectordrive.ui.draft3d_dialog import MoveFacesDialog
        d = MoveFacesDialog(self.win, solid or box(), last)
        self.addCleanup(d.deleteLater)
        return d

    def test_fields_follow_the_mode(self):
        d = self.dialog()
        self.assertFalse(d.distance.isHidden())
        self.assertTrue(d.dx.isHidden())
        d.mode.setCurrentIndex(d.mode.findData('vector'))
        self.assertTrue(d.distance.isHidden())
        self.assertFalse(d.dx.isHidden())

    def test_values(self):
        s = box()
        d = self.dialog(s, {'mode': 'vector', 'dx': 2.0, 'dy': 1.0, 'dz': 0.5, 'picks': [pick(s, (1, 0, 0))]})
        v = d.values()
        self.assertEqual(v['mode'], 'vector')
        self.assertEqual((v['dx'], v['dy'], v['dz']), (2.0, 1.0, 0.5))
        self.assertEqual(len(v['picks']), 1)

    def test_stays_open_on_an_error(self):
        d = self.dialog()
        d.accept()
        self.assertEqual(d.result(), 0)
        self.assertIn('aucune', d.status.text())
        d.choose([0])
        d.distance.setValue(1.0)
        d.accept()
        self.assertEqual(d.result(), int(QDialog.DialogCode.Accepted))

    def test_no_walls_button_here(self):
        d = self.dialog()
        self.assertFalse(hasattr(d, 'walls_button'))
        d.choose([0, 1])
        d.none_button.click()
        self.assertEqual(d.view.sel_faces, set())

    def test_preview_comes_back(self):
        d = self.dialog()
        d.choose([0])
        before = d.view.model
        d.preview_button.setChecked(True)
        self.assertIsNot(d.view.model, before)
        d.preview_button.setChecked(False)
        self.assertIs(d.view.model, before)
        self.assertEqual(d.view.sel_faces, {0})


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
        self.win.settings.remove('cad/solide_faces')
        self.addCleanup(self.win.settings.remove, 'cad/solide_faces')

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
        return dict({'mode': 'normal', 'distance': 5.0, 'dx': 0.0, 'dy': 0.0, 'dz': 0.0, 'picks': [pick(box(), (1, 0, 0))]}, **kw)

    def test_with_given_values(self):
        self.add()
        self.assertEqual(len(self.win.solid_move_faces(params=self.values())), 1)
        self.assertAlmostEqual(self.only()[1].volume(), 10000.0, places=2)

    def test_nothing_selected(self):
        self.assertEqual(self.win.solid_move_faces(params=self.values()), [])

    def test_one_volume_at_a_time(self):
        a, b = SO.make_shape(box()), SO.make_shape(SO.box(50, 0, 0, 5, 5, 5))
        self.doc.add(a)
        self.doc.add(b)
        self.c.select([a, b])
        self.assertEqual(self.win.solid_move_faces(params=self.values()), [])
        self.assertIn('seul', self.win.statusBar().currentMessage())

    def test_error_shows_in_the_status_bar(self):
        it = self.add()
        self.assertEqual(self.win.solid_move_faces(params=self.values(distance=-25.0)), [])
        self.assertIn('croisent', self.win.statusBar().currentMessage())
        self.assertIs(self.only()[0], it)

    def test_undo(self):
        self.add()
        self.win.solid_move_faces(params=self.values())
        self.win.undo()
        self.assertAlmostEqual(self.only()[1].volume(), 8000.0, places=2)

    def test_dialog_path_remembers_the_settings_not_the_faces(self):
        self.add()
        from vectordrive.ui import draft3d_dialog as DD

        def fake(dlg):
            dlg.choose([0])
            dlg.distance.setValue(2.0)
            return 1
        with mock.patch.object(DD.MoveFacesDialog, 'exec', fake):
            self.assertEqual(len(self.win.solid_move_faces()), 1)
        kept = self.win.settings.value('cad/solide_faces')
        self.assertEqual(kept['distance'], 2.0)
        self.assertNotIn('picks', kept)

    def test_dialog_cancelled(self):
        it = self.add()
        from vectordrive.ui import draft3d_dialog as DD
        with mock.patch.object(DD.MoveFacesDialog, 'exec', lambda dlg: 0):
            self.assertEqual(self.win.solid_move_faces(), [])
        self.assertIs(self.only()[0], it)

    def test_history(self):
        self.assertIn('solid_move_faces', HI.RECORDED)
        self.add()
        it = self.win.solid_move_faces(params=self.values())[0]
        step = HI.history_of(it)['steps'][-1]
        self.assertEqual(step['cmd'], 'solid_move_faces')
        self.assertEqual(step['params']['distance'], 5.0)

    def test_history_with_another_distance(self):
        self.add()
        it = self.win.solid_move_faces(params=self.values())[0]
        ref = len(HI.history_of(it)['steps']) - 1
        self.assertIsNotNone(self.win.history_set_params(it, ref, {'distance': 1.0}))
        self.assertAlmostEqual(self.only()[1].volume(), 8400.0, places=2)

    def test_history_edit_opens_the_window_with_its_faces(self):
        self.add()
        it = self.win.solid_move_faces(params=self.values())[0]
        from vectordrive.ui import draft3d_dialog as DD
        seen = {}

        def fake(dlg):
            seen['faces'] = len(dlg.view.sel_faces)
            seen['distance'] = dlg.distance.value()
            return 1
        with mock.patch.object(DD.MoveFacesDialog, 'exec', fake):
            new = self.win.history_edit_params(it, len(HI.history_of(it)['steps']) - 1)
        self.assertEqual(seen, {'faces': 1, 'distance': 5.0})
        self.assertIsNotNone(new)

    def test_ribbon(self):
        action = self.win.A['solid_move_faces']
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups()
                 for b in g.buttons() if b.defaultAction() is action]
        self.assertEqual(len(found), 1)


if __name__ == '__main__':
    unittest.main()
