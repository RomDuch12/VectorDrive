"""Round 615 : mécanismes — course libre (chaque corps seul, jusqu'à sa première collision) et « Course jusqu'à
la butée » dans la fenêtre ; moins de deux corps fermés : rien à contrôler (et non « aucune collision »)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round595 import box_tris, model_of
from vectordrive.core import mechanics as M
from vectordrive.core import solids as SO

app = QApplication.instance() or QApplication([])


def caged():
    """Socle, coulisseau posé dessus et couvercle à 8 mm au-dessus ; un second coulisseau libre à côté."""
    base = np.concatenate([box_tris(0, 0, 0, 60, 10, 5), box_tris(0, 0, 5, 5, 10, 18), box_tris(25, 0, 5, 30, 10, 18),
                           box_tris(0, 0, 18, 30, 10, 20)])
    return model_of(base, box_tris(5, 0, 5, 25, 10, 10), box_tris(40, 0, 5, 50, 10, 10))


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestFreeTravel(unittest.TestCase):
    def test_free_travel(self):
        m = caged()
        mans, _f = M.body_manifolds(m)
        up = [M.Motion(1, 'translation', (0, 0, 1), (0, 0, 0), 20.0, 0, 'appui'),
              M.Motion(2, 'translation', (0, 0, 1), (0, 0, 0), 20.0, 0, 'appui')]
        self.assertAlmostEqual(M.free_travel(mans, up, 1), 8.0, delta=0.01)      # sous le couvercle
        self.assertIsNone(M.free_travel(mans, up, 2))                            # rien au-dessus
        self.assertIsNone(M.free_travel(mans, up, 0))                            # pas de mouvement
        sideways = [M.Motion(1, 'translation', (1, 0, 0), (0, 0, 0), 20.0, 0, 'appui'), up[1]]
        self.assertLess(M.free_travel(mans, sideways, 1), 0.01)                  # contre le montant


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
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

    def test_stop_at_collisions(self):
        dlg = self.show(caged())
        dlg.fixed.setCurrentIndex(dlg.fixed.findData(0))
        dlg.detect()
        for mo in dlg.shown_motions():
            mo.axis, mo.amount = (0.0, 0.0, 1.0), 20.0
        found = dlg.stop_at_collisions()
        self.assertEqual(list(found), [1])
        self.assertAlmostEqual(found[1], 8.0, delta=0.01)
        mo = next(x for x in dlg.shown_motions() if x.body == 1)
        self.assertAlmostEqual(mo.amount, found[1], 9)
        row = [x.body for x in dlg.shown_motions()].index(1)
        self.assertAlmostEqual(dlg.moves_table.cellWidget(row, 3).value(), round(found[1], 1), 6)
        self.assertIn('butée', dlg.clash_label.text())
        self.assertIn('libre', dlg.clash_label.text())
        self.assertEqual(self.w.canvas.doc.extra['mecanismes']['moves']['1']['amount'], found[1])   # gardé
        self.assertEqual(dlg.check_collisions(), [])                            # plus de collision sur la course
        dlg.done(0)

    def test_not_enough_solids(self):
        dlg = self.show(model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10)))
        with mock.patch.object(M, 'body_manifolds', lambda model: ({0: None}, {1: 'ouvert'})):
            self.assertEqual(dlg.check_collisions(), [])
        self.assertIn('rien à contrôler', dlg.clash_label.text())
        self.assertNotIn('Aucune collision', dlg.clash_label.text())
        self.assertEqual(dlg.stop_at_collisions(), {})
        dlg.done(0)


if __name__ == '__main__':
    unittest.main()
