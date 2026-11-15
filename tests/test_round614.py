"""Round 614 : mécanismes — contrôle des collisions sur la course : corps fermés en volumes, déplacés pas à pas ;
volume commun = interpénétration (au repos, ou dès la position trouvée par dichotomie) ; deux faces en
contact ne comptent pas ; fenêtre « Mécanismes » : bouton, compte rendu, vue mise à la collision."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round595 import box_tris, model_of
from vectordrive.core import mechanics as M
from vectordrive.core import solids as SO

app = QApplication.instance() or QApplication([])


def slide(axis, amount=20.0):
    return [M.Motion(1, 'translation', axis, (0, 0, 0), amount, 0, 'appui')]


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestCollisions(unittest.TestCase):
    def setUp(self):
        # un socle en U (deux montants) et un coulisseau posé entre eux ; un butoir au-dessus en x 0..10
        base = np.concatenate([box_tris(0, 0, 0, 30, 10, 5), box_tris(0, 0, 5, 5, 10, 15),
                               box_tris(25, 0, 5, 30, 10, 15)])
        self.m = model_of(base, box_tris(5, 0, 5, 25, 10, 10))
        self.mans, self.failed = M.body_manifolds(self.m)

    def test_contacts_are_not_collisions(self):
        self.assertEqual(self.failed, {})
        self.assertEqual(M.collisions(self.mans, slide((0, 0, 1))), [])     # sort par le haut : libre
        self.assertEqual(M.collisions(self.mans, slide((0, 1, 0))), [])     # glisse le long des montants

    def test_blocked_and_refined(self):
        c = M.collisions(self.mans, slide((1, 0, 0), 20.0))
        self.assertEqual(len(c), 1)
        self.assertEqual((c[0].a, c[0].b), (0, 1))
        self.assertLess(c[0].k * 20.0, 0.05)                                # bute tout de suite sur le montant
        self.assertGreater(c[0].volume, 0)
        c = M.collisions(self.mans, slide((0, 0, -1), 20.0))
        self.assertLess(c[0].k * 20.0, 0.05)                                # posé sur le socle

    def test_obstacle_on_the_way(self):
        lid = box_tris(0, 0, 18, 30, 10, 20)                                # 8 mm au-dessus du coulisseau
        m = model_of(np.concatenate([box_tris(0, 0, 0, 30, 10, 5), box_tris(0, 0, 5, 5, 10, 18),
                                     box_tris(25, 0, 5, 30, 10, 18), lid]), box_tris(5, 0, 5, 25, 10, 10))
        mans, _f = M.body_manifolds(m)
        c = M.collisions(mans, slide((0, 0, 1), 20.0))
        self.assertEqual(len(c), 1)
        self.assertAlmostEqual(c[0].k * 20.0, 8.0, delta=0.02)              # heurte le couvercle à 8 mm

    def test_overlap_at_rest(self):
        m = model_of(box_tris(0, 0, 0, 10, 10, 10), box_tris(8, 0, 0, 18, 10, 10))
        mans, _f = M.body_manifolds(m)
        c = M.collisions(mans, [])
        self.assertEqual((len(c), c[0].k), (1, 0.0))
        self.assertAlmostEqual(c[0].volume, 200.0, 6)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    def test_button_and_report(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.view3d import Panel3D
        w = MainWindow()
        try:
            p = Panel3D(w)
            m = model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10))
            p.model = m
            p.view.set_model(m)
            dlg = p.mechanisms(show=False)
            self.assertEqual(dlg.check_collisions(), [])
            self.assertIn('Aucune collision', dlg.clash_label.text())
            dlg.moves_table.cellWidget(0, 4).setChecked(True)                 # sens inversé : dans le socle
            c = dlg.check_collisions()
            self.assertEqual(len(c), 1)
            self.assertIn('heurte', dlg.clash_label.text())
            self.assertAlmostEqual(dlg.k, c[0].k, 9)                          # la vue montre la collision
            dlg.done(0)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
