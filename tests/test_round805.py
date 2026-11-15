"""Round 805 : supprimer des faces d'un volume déjà fait."""
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
from vectordrive.core import face_delete as FD
from vectordrive.core import history3d as HI
from vectordrive.core import solids as SO

app = QApplication.instance() or QApplication([])


def face_near(solid, normal, near):
    """La face de cette normale la plus proche de `near`."""
    faces = DR._faces(solid)
    tris, face_of, nrm = faces
    k = np.flatnonzero(nrm @ np.array(normal, dtype=float) > 0.999)
    k = k[np.argmin(np.linalg.norm(tris[k].mean(axis=1) - np.array(near, dtype=float), axis=1))]
    return DR.pick_of(solid, int(face_of[k]), faces)


def curved(solid):
    faces = DR._faces(solid)
    tris, face_of, nrm = faces
    out = []
    for f in np.unique(face_of):
        n = nrm[face_of == f]
        if float(np.linalg.norm(n - n[0], axis=1).max()) > 0.1:
            out.append(DR.pick_of(solid, int(f), faces))
    return out


def plate():
    return SO.box(-20, -20, 0, 40, 40, 10)


def through_hole(x=0.0, y=0.0):
    return SO._solid(plate().manifold() - SO.cylinder(x, y, -1, 5, 12).manifold(), 'p')


def blind_hole():
    return SO._solid(plate().manifold() - SO.cylinder(0, 0, 4, 5, 12).manifold(), 'p')


def pocket():
    return SO._solid(plate().manifold() - SO.box(-5, -5, 4, 10, 10, 10).manifold(), 'p')


def boss():
    return SO._solid(plate().manifold() + SO.cylinder(0, 0, 10, 6, 10).manifold(), 'p')


def groove():
    return SO._solid(plate().manifold() - SO.box(-4, -30, 6, 8, 60, 10).manifold(), 'p')


def pocket_faces(s):
    return [face_near(s, (1, 0, 0), (-5, 0, 7)), face_near(s, (-1, 0, 0), (5, 0, 7)), face_near(s, (0, 1, 0), (0, -5, 7)),
            face_near(s, (0, -1, 0), (0, 5, 7)), face_near(s, (0, 0, 1), (0, 0, 4))]


class Kernel(unittest.TestCase):
    def full(self, out):
        self.assertAlmostEqual(out.volume(), 16000.0, delta=0.01)
        self.assertEqual(out.manifold().status(), SO._m().Error.NoError)
        self.assertEqual(out.manifold().genus(), 0)

    def test_through_hole_is_plugged(self):
        s = through_hole()
        self.assertLess(s.volume(), 16000.0)
        self.full(FD.apply(s, {'picks': curved(s)}))

    def test_blind_hole(self):
        s = blind_hole()
        self.full(FD.apply(s, {'picks': curved(s) + [face_near(s, (0, 0, 1), (0, 0, 4))]}))

    def test_the_wall_of_a_blind_hole_is_enough(self):
        s = blind_hole()
        self.full(FD.apply(s, {'picks': curved(s)}))

    def test_a_floor_alone_has_a_curved_neighbour(self):
        s = blind_hole()
        with self.assertRaises(DR.DraftError) as ctx:
            FD.apply(s, {'picks': [face_near(s, (0, 0, 1), (0, 0, 4))]})
        self.assertIn('courbe', str(ctx.exception))

    def test_pocket(self):
        s = pocket()
        self.full(FD.apply(s, {'picks': pocket_faces(s)}))

    def test_the_walls_of_a_pocket_are_enough(self):
        s = pocket()
        self.full(FD.apply(s, {'picks': pocket_faces(s)[:4]}))

    def test_a_floor_without_its_walls_is_refused(self):
        s = pocket()
        with self.assertRaises(DR.DraftError):
            FD.apply(s, {'picks': pocket_faces(s)[4:]})

    def test_the_wall_of_a_boss_is_enough(self):
        s = boss()
        self.full(FD.apply(s, {'picks': curved(s)}))

    def test_boss(self):
        s = boss()
        self.full(FD.apply(s, {'picks': curved(s) + [face_near(s, (0, 0, 1), (0, 0, 20))]}))

    def test_a_groove_across_the_plate(self):
        s = groove()
        self.assertLess(s.volume(), 16000.0)
        picks = [face_near(s, (1, 0, 0), (-4, 0, 8)), face_near(s, (-1, 0, 0), (4, 0, 8)), face_near(s, (0, 0, 1), (0, 0, 6))]
        self.full(FD.apply(s, {'picks': picks}))

    def test_a_flat_step_is_extended(self):
        s = SO._solid(plate().manifold() + SO.box(-20, -20, 10, 20, 40, 5).manifold(), 'p')   # une marche d'un bord à l'autre
        v0 = s.volume()
        # Le dessus de la marche et son flanc : les faces d'extrémité et le dessus se prolongent ?
        picks = [face_near(s, (0, 0, 1), (-10, 0, 15)), face_near(s, (1, 0, 0), (0, 0, 12))]
        try:
            out = FD.apply(s, {'picks': picks})
        except DR.DraftError:
            return                                                     # refusé proprement : c'est permis
        self.assertLess(out.volume(), v0)
        self.assertEqual(out.manifold().status(), SO._m().Error.NoError)

    def test_a_corner_notch(self):
        s = SO._solid(plate().manifold() - SO.box(10, 10, 5, 20, 20, 20).manifold(), 'p')
        picks = [face_near(s, (1, 0, 0), (10, 15, 7)), face_near(s, (0, 1, 0), (15, 10, 7)), face_near(s, (0, 0, 1), (15, 15, 5))]
        self.full(FD.apply(s, {'picks': picks}))

    def chamfered(self, kind='chamfer'):
        from vectordrive.core import edge_blend as EB
        s = plate()
        top = [list(map(float, c.middle())) for c in EB.sharp_chains(s)
               if abs(c.middle()[2] - 10.0) < 1e-6 and abs(c.middle()[0] - 20.0) < 1e-6]
        self.assertEqual(len(top), 1)
        return EB.apply(s, {'kind': kind, 'radius': 2.0, 'radius_end': 2.0, 'picks': top})

    def test_a_chamfer_goes_back_to_a_sharp_edge(self):
        s = self.chamfered()
        self.assertLess(s.volume(), 16000.0)
        n = np.array([1.0, 0, 1.0]) / np.sqrt(2.0)
        out = FD.apply(s, {'picks': [face_near(s, n, (19, 0, 9))]})
        self.full(out)
        self.assertAlmostEqual(out.verts[:, 0].max(), 20.0, places=4)
        self.assertAlmostEqual(out.verts[:, 2].max(), 10.0, places=4)

    def test_a_chamfer_in_an_inner_corner_is_taken_off(self):
        from vectordrive.core import edge_blend as EB
        s = SO._solid(plate().manifold() + SO.box(-20, -20, 10, 20, 40, 10).manifold(), 'p')
        v0 = s.volume()
        inner = [list(map(float, c.middle())) for c in EB.sharp_chains(s) if not c.convex]
        self.assertEqual(len(inner), 1)
        added = EB.apply(s, {'kind': 'chamfer', 'radius': 2.0, 'radius_end': 2.0, 'picks': inner})
        self.assertGreater(added.volume(), v0)
        n = np.array([1.0, 0, 1.0]) / np.sqrt(2.0)
        out = FD.apply(added, {'picks': [face_near(added, n, (1, 0, 11))]})
        self.assertAlmostEqual(out.volume(), v0, delta=0.01)

    def test_extending_must_not_reach_something_else(self):
        # Une entaille de coin, avec un perçage juste à côté, dans la boîte du second moyen
        man = plate().manifold() - SO.box(10, 10, 5, 20, 20, 20).manifold() - SO.cylinder(7, 15, -1, 1.5, 12).manifold()
        s = SO._solid(man, 'p')
        picks = [face_near(s, (1, 0, 0), (10, 15, 7)), face_near(s, (0, 1, 0), (15, 10, 7)), face_near(s, (0, 0, 1), (15, 15, 5))]
        out = FD.apply(s, {'picks': picks})
        self.assertEqual(len(curved(out)), 1)                       # le perçage est toujours là
        self.assertAlmostEqual(out.volume(), s.volume() + 10 * 10 * 5, delta=0.02)

    def test_extending_that_would_fill_a_neighbour_is_refused(self):
        # Un plot resté au fond de l'entaille : il n'a rien à voir avec les plans qu'on prolonge
        man = plate().manifold() - SO.box(10, 10, 5, 20, 20, 20).manifold() + SO.box(14, 14, 5, 2, 2, 2).manifold()
        s = SO._solid(man, 'p')
        picks = [face_near(s, (1, 0, 0), (10, 15, 7)), face_near(s, (0, 1, 0), (15, 10, 7)), face_near(s, (0, 0, 1), (15, 15, 5))]
        with self.assertRaises(DR.DraftError):
            FD.apply(s, {'picks': picks})

    def test_several_holes_at_once(self):
        man = plate().manifold() - SO.cylinder(-10, 0, -1, 3, 12).manifold() - SO.cylinder(10, 0, -1, 3, 12).manifold()
        s = SO._solid(man, 'p')
        self.assertEqual(len(curved(s)), 2)
        self.full(FD.apply(s, {'picks': curved(s)}))

    def test_one_hole_of_two(self):
        man = plate().manifold() - SO.cylinder(-10, 0, -1, 3, 12).manifold() - SO.cylinder(10, 0, -1, 3, 12).manifold()
        s = SO._solid(man, 'p')
        out = FD.apply(s, {'picks': curved(s)[:1]})
        self.assertEqual(len(curved(out)), 1)
        self.assertEqual(out.manifold().genus(), 1)
        self.assertAlmostEqual(out.volume() - s.volume(), (16000.0 - s.volume()) / 2.0, delta=0.05)

    def test_an_outer_wall_cannot_go(self):
        s = plate()
        with self.assertRaises(DR.DraftError):
            FD.apply(s, {'picks': [face_near(s, (1, 0, 0), (20, 0, 5))]})

    def test_a_neighbour_on_a_curved_face(self):
        s = SO._solid(SO.cylinder(0, 0, 0, 20, 40).manifold() - SO.box(-3, 15, 10, 6, 10, 6).manifold(), 'p')
        with self.assertRaises(DR.DraftError):
            FD.apply(s, {'picks': [face_near(s, (0, 1, 0), (0, 15, 13))]})

    def test_refusals(self):
        s = plate()
        for v in ({'picks': []}, {}, {'picks': [[500, 0, 0, 1, 0, 0]]}):
            with self.assertRaises(DR.DraftError):
                FD.apply(s, v)
        faces = DR._faces(s)
        with self.assertRaises(DR.DraftError) as ctx:
            FD.apply(s, {'picks': [DR.pick_of(s, int(f), faces) for f in np.unique(faces[1])]})
        self.assertIn('rien', str(ctx.exception))

    def test_name_and_color_stay(self):
        s = through_hole()
        s.name, s.color = 'pièce', (0.1, 0.2, 0.3)
        out = FD.apply(s, {'picks': curved(s)})
        self.assertEqual((out.name, out.color), ('pièce', (0.1, 0.2, 0.3)))

    def test_rings(self):
        self.assertEqual(FD._rings([(0, 1), (1, 2), (2, 0)]), [[0, 1, 2]])
        self.assertEqual(FD._rings([(0, 1), (1, 2)]), [[0, 1, 2]])
        self.assertEqual(FD._rings([(0, 1), (5, 6)]), [[0, 1, 5, 6]])
        with self.assertRaises(DR.DraftError):
            FD._rings([(0, 1), (2, 3), (4, 5)])
        with self.assertRaises(DR.DraftError):
            FD._rings([(0, 1), (0, 2)])


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

    def dialog(self, solid, last=None):
        from vectordrive.ui.draft3d_dialog import DeleteFacesDialog
        d = DeleteFacesDialog(self.win, solid, last)
        self.addCleanup(d.deleteLater)
        return d

    def test_stays_open_on_an_error(self):
        s = through_hole()
        d = self.dialog(s)
        d.accept()
        self.assertEqual(d.result(), 0)
        self.assertIn('aucune', d.status.text())

    def test_accepts(self):
        s = through_hole()
        d = self.dialog(s, {'picks': curved(s)})
        self.assertEqual(len(d.view.sel_faces), 1)
        d.accept()
        self.assertEqual(d.result(), int(QDialog.DialogCode.Accepted))
        self.assertEqual(set(d.values()), {'picks'})

    def test_preview(self):
        s = through_hole()
        d = self.dialog(s, {'picks': curved(s)})
        before = d.view.model
        d.preview_button.setChecked(True)
        self.assertIsNot(d.view.model, before)
        d.preview_button.setChecked(False)
        self.assertIs(d.view.model, before)


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
        self.win.settings.remove('cad/solide_suppr_faces')
        self.addCleanup(self.win.settings.remove, 'cad/solide_suppr_faces')

    def add(self, s=None):
        it = SO.make_shape(s or through_hole())
        self.doc.add(it)
        self.c.select([it])
        return it

    def only(self):
        items = [it for it in self.doc.layers[0].items if SO.is_solid(it)]
        self.assertEqual(len(items), 1)
        return items[0], SO.of_item(items[0])

    def test_with_given_values(self):
        s = through_hole()
        self.add(s)
        self.assertEqual(len(self.win.solid_delete_faces(params={'picks': curved(s)})), 1)
        self.assertAlmostEqual(self.only()[1].volume(), 16000.0, delta=0.01)

    def test_error_in_the_status_bar(self):
        s = plate()
        it = self.add(s)
        self.assertEqual(self.win.solid_delete_faces(params={'picks': [face_near(s, (1, 0, 0), (20, 0, 5))]}), [])
        self.assertIn('Opération impossible', self.win.statusBar().currentMessage())
        self.assertIs(self.only()[0], it)

    def test_undo(self):
        s = through_hole()
        self.add(s)
        v0 = s.volume()
        self.win.solid_delete_faces(params={'picks': curved(s)})
        self.win.undo()
        self.assertAlmostEqual(self.only()[1].volume(), v0, delta=0.01)

    def test_dialog_path(self):
        s = through_hole()
        self.add(s)
        from vectordrive.ui import draft3d_dialog as DD

        def fake(dlg):
            dlg.choose([DR.find(dlg.faces, q) for q in curved(s)])
            return 1
        with mock.patch.object(DD.DeleteFacesDialog, 'exec', fake):
            self.assertEqual(len(self.win.solid_delete_faces()), 1)

    def test_dialog_cancelled(self):
        it = self.add()
        from vectordrive.ui import draft3d_dialog as DD
        with mock.patch.object(DD.DeleteFacesDialog, 'exec', lambda dlg: 0):
            self.assertEqual(self.win.solid_delete_faces(), [])
        self.assertIs(self.only()[0], it)

    def test_history(self):
        self.assertIn('solid_delete_faces', HI.RECORDED)
        s = through_hole()
        self.add(s)
        it = self.win.solid_delete_faces(params={'picks': curved(s)})[0]
        step = HI.history_of(it)['steps'][-1]
        self.assertEqual(step['cmd'], 'solid_delete_faces')
        self.assertEqual(len(step['params']['picks']), 1)

    def test_history_edit_opens_the_window_with_its_faces(self):
        s = through_hole()
        self.add(s)
        it = self.win.solid_delete_faces(params={'picks': curved(s)})[0]
        from vectordrive.ui import draft3d_dialog as DD
        seen = {}

        def fake(dlg):
            seen['faces'] = len(dlg.view.sel_faces)
            return 1
        with mock.patch.object(DD.DeleteFacesDialog, 'exec', fake):
            new = self.win.history_edit_params(it, len(HI.history_of(it)['steps']) - 1)
        self.assertEqual(seen, {'faces': 1})
        self.assertIsNotNone(new)

    def test_ribbon(self):
        action = self.win.A['solid_delete_faces']
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups()
                 for b in g.buttons() if b.defaultAction() is action]
        self.assertEqual(len(found), 1)


if __name__ == '__main__':
    unittest.main()
