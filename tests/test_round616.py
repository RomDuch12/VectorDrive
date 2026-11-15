"""Round 616 : trous d'un simple maillage (STL, volumes du dessin percés ou modifiés) — une face aux parois
verticales dont les sommets tombent sur un cercle est un cylindre ; creux (trou) si ses normales regardent
l'axe. Les trous d'un volume percé deviennent des perçages comme ceux d'un STEP.

Corrections de la relecture des mécanismes : « Course » et « Rotation des pivots » encore actives après un
premier repérage ; facettes de cylindres ajustés tolérées (épaisseur) ; une paire qui s'interpénètre au repos
encore contrôlée pendant le mouvement ; course libre prise du côté libre ; corps bloqué dès le départ ; enfant
non animé qui suit son parent ; course du bon corps dans le message ; surface ouverte non contrôlée ; réglages
d'une autre pièce ou d'un autre dessin."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round595 import box_tris, model_of
from vectordrive.core import holes3d as H
from vectordrive.core import mechanics as M
from vectordrive.core import solids as SO

app = QApplication.instance() or QApplication([])


def drilled_part():
    """Bloc 60 × 40 × 20 : trou débouchant Ø8, trou borgne Ø5 de 8 mm, trou horizontal Ø6, bossage Ø6 dessus."""
    blk = SO.box(0, 0, 0, 60, 40, 20)
    horiz = SO.cylinder(0, 0, 0, 3, 100).transformed(
        np.array([[0, 0, 1, -10], [0, 1, 0, 30], [-1, 0, 0, 10], [0, 0, 0, 1.0]]))
    part = SO.boolean('subtract', [blk, SO.cylinder(15, 20, -1, 4, 22), SO.cylinder(35, 20, 12, 2.5, 9), horiz])
    return SO.boolean('union', [part, SO.cylinder(50, 30, 20, 3, 5)])


class TestMeshCylinder(unittest.TestCase):
    def test_kinds(self):
        a = np.linspace(0, 2 * np.pi, 49)[:-1]
        ring = []
        for i in range(len(a)):
            p0 = [10 + 3 * np.cos(a[i]), 5 + 3 * np.sin(a[i])]
            p1 = [10 + 3 * np.cos(a[(i + 1) % len(a)]), 5 + 3 * np.sin(a[(i + 1) % len(a)])]
            ring += [[[*p0, 0], [*p1, 0], [*p1, 4]], [[*p0, 0], [*p1, 4], [*p0, 4]]]   # normales vers l'extérieur
        ring = np.array(ring)
        k = H.mesh_cylinder(ring)
        self.assertAlmostEqual(k['rayon'], 3.0, 9)
        np.testing.assert_allclose(k['centre'][:2], [10, 5], atol=1e-9)
        self.assertFalse(k['creux'])                                        # bossage
        self.assertTrue(H.mesh_cylinder(ring[:, ::-1])['creux'])            # trou
        self.assertIsNone(H.mesh_cylinder(box_tris(0, 0, 0, 10, 10, 5)[:4]))   # paroi plane / dessus
        tilted = ring.copy()
        tilted[:, :, 0] += tilted[:, :, 2] * 0.2                            # axe penché
        self.assertIsNone(H.mesh_cylinder(tilted))


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestVolumes(unittest.TestCase):
    def test_holes_of_a_drilled_volume(self):
        m = SO.to_model([drilled_part()])
        hs = H.find(m)
        self.assertEqual([(h.x, h.y, h.radius, h.through) for h in hs], [(15.0, 20.0, 4.0, True),
                                                                        (35.0, 20.0, 2.5, False)])
        self.assertAlmostEqual(hs[1].depth, 13.0, 6)                       # sous le haut du bossage (z 25)
        self.assertEqual(H.find(SO.to_model([SO.box(0, 0, 0, 10, 10, 10)])), [])

    def test_drilling_from_drawing_volumes(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.view3d import Panel3D
        w = MainWindow()
        try:
            p = Panel3D(w)
            m = SO.to_model([drilled_part()])
            p.model = m
            p.view.set_model(m)
            circles, ops = p.holes_to_drilling()
            self.assertEqual(len(circles), 2)
            self.assertEqual(sorted(round(o.depth, 2) for o in ops), [13.0, 25.5])   # débouchant : +0,5
        finally:
            w.modified = False
            w.close()


def pivot(shaft_segments=48, bore_segments=48):
    """Bloc percé Ø10 (corps 0) et axe Ø10 dedans (corps 1), même rayon nominal."""
    blk = SO.boolean('subtract', [SO.box(-10, -10, 0, 20, 20, 10),
                                  SO.cylinder(0, 0, -1, 5, 12, segments=bore_segments)])
    return SO.to_model([blk, SO.cylinder(0, 0, 0, 5, 10, segments=shaft_segments)])


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestCollisionFixes(unittest.TestCase):
    def test_faceted_pivot_is_free(self):
        turn = [M.Motion(1, 'rotation', (0, 0, 1), (0, 0, 0), 90.0, 0, 'pivot')]
        for segs in ((48, 48), (48, 40)):
            mans, failed = M.body_manifolds(pivot(*segs))
            self.assertEqual(failed, {})
            self.assertEqual(M.collisions(mans, turn), [], segs)              # ni au repos, ni en tournant
            self.assertIsNone(M.free_travel(mans, turn, 1))

    def test_overlap_at_rest_still_checked(self):
        base = np.concatenate([box_tris(0, 0, 0, 60, 10, 5), box_tris(40, 0, 5, 45, 10, 15)])   # un plot à x 40
        m = model_of(base, box_tris(5, 0, 4.95, 20, 10, 10))                   # enfoncé de 0,05 dans le socle
        mans, _f = M.body_manifolds(m)
        mv = [M.Motion(1, 'translation', (1, 0, 0), (0, 0, 0), 40.0, 0, 'appui')]
        c = M.collisions(mans, mv)
        self.assertEqual([x.k > 0 for x in c], [True])                        # le plot, pas seulement le repos
        self.assertAlmostEqual(c[0].k * 40.0, 20.0, delta=0.02)
        self.assertAlmostEqual(M.free_travel(mans, mv, 1), 20.0, delta=0.02)

    def test_free_travel_stays_free(self):
        lid = box_tris(0, 0, 12.4008, 30, 10, 14)
        m = model_of(np.concatenate([box_tris(0, 0, 0, 30, 10, 5), lid]), box_tris(5, 0, 5, 25, 10, 10))
        mans, _f = M.body_manifolds(m)
        mv = [M.Motion(1, 'translation', (0, 0, 1), (0, 0, 0), 20.0, 0, 'appui')]
        t = M.free_travel(mans, mv, 1)
        self.assertLessEqual(t, 2.4008)
        self.assertAlmostEqual(t, 2.4008, delta=0.01)
        mv[0].amount = t
        self.assertEqual(M.collisions(mans, mv), [])                           # réglée dessus : plus de collision

    def test_sheet_is_not_a_solid(self):
        sheet = box_tris(2, 2, 2, 8, 8, 3)[:2]                                 # deux triangles, une surface ouverte
        mans, failed = M.body_manifolds(model_of(box_tris(0, 0, 0, 10, 10, 10), sheet))
        self.assertEqual(list(mans), [0])
        self.assertIn(1, failed)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestDialogFixes(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.view3d import Panel3D
        self.w = MainWindow()
        self.p = Panel3D(self.w)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def show(self, m):
        self.p.model = m
        self.p.view.set_model(m)
        return self.p.mechanisms(show=False)

    def test_travel_setting_still_works(self):
        dlg = self.show(model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10)))
        for v in (30.0, 50.0):
            dlg.travel.setValue(v)
            dlg.detect()
            self.assertEqual(dlg.shown_motions()[0].amount, v)
        dlg.moves_table.cellWidget(0, 3).setValue(12.0)                     # course réglée à la main
        dlg.detect()
        self.assertEqual(dlg.shown_motions()[0].amount, 12.0)               # gardée tant que la course repérée l'est
        dlg.travel.setValue(0.0)
        dlg.detect()
        self.assertNotEqual(dlg.shown_motions()[0].amount, 12.0)            # « auto » : course repérée
        dlg.done(0)

    def test_blocked_at_start_keeps_travel(self):
        dlg = self.show(model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10)))
        dlg.moves_table.cellWidget(0, 4).setChecked(True)                   # vers le socle
        amount = dlg.shown_motions()[0].amount
        self.assertEqual(dlg.stop_at_collisions(), {})
        self.assertEqual(dlg.shown_motions()[0].amount, amount)
        self.assertIn('bloqué', dlg.clash_label.text())
        dlg.done(0)

    def test_disabled_body_and_child(self):
        dlg = self.show(model_of(box_tris(0, 0, 0, 40, 10, 5), box_tris(0, 0, 5, 10, 10, 10),
                                 box_tris(20, 0, 5, 30, 10, 10)))
        dlg.motions = [M.Motion(1, 'translation', (1.0, 0.0, 0.0), (0, 0, 0), 20.0, 0, 'appui'),
                       M.Motion(2, 'translation', (0.0, 0.0, 1.0), (0, 0, 0), 80.0, 0, 'appui')]
        dlg.enabled = {1: True, 2: False}
        c = dlg.check_collisions()
        self.assertEqual(len(c), 1)
        self.assertIn('10,0 mm', dlg.clash_label.text())                    # la course du corps 1, pas du 2
        mans, _f = M.body_manifolds(dlg.model)
        dlg.motions = [M.Motion(1, 'translation', (0.0, 0.0, 1.0), (0, 0, 0), 20.0, 0, 'appui'),
                       M.Motion(2, 'translation', (1.0, 0.0, 0.0), (0, 0, 0), 5.0, 1, 'appui')]
        dlg.enabled = {1: True, 2: False}
        self.assertIsNone(M.free_travel(mans, dlg.active(), 1))             # l'enfant non animé suit : pas de heurt
        dlg.done(0)

    def test_settings_of_another_part(self):
        dlg = self.show(model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10)))
        dlg.moves_table.cellWidget(0, 3).setValue(33.0)
        dlg.done(0)
        other = self.show(model_of(box_tris(0, 0, 0, 20, 10, 5), box_tris(0, 0, 5, 20, 10, 10)))   # 2 corps aussi
        self.assertNotEqual(other.shown_motions()[0].amount, 33.0)
        other.done(0)
        again = self.show(model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10)))
        self.assertEqual(again.shown_motions()[0].amount, 33.0)
        again.done(0)

    def test_other_drawing_shown(self):
        dlg = self.show(model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10)))
        first = self.w.canvas.doc
        dlg.doc = object()                                                  # la fenêtre appartient à un autre dessin
        dlg.moves_table.cellWidget(0, 3).setValue(44.0)
        self.assertNotIn('mecanismes', first.extra)
        dlg.done(0)


if __name__ == '__main__':
    unittest.main()
