"""Round 611 : réglages des mécanismes gardés avec le dessin — repérage (écarts, corps fixe, course…) et
réglages de chaque mouvement (animé, course, sens inversé) retrouvés à la réouverture de la fenêtre et du
dessin ; ouvrir la fenêtre ne modifie pas le dessin."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from tests.test_round595 import box_tris, model_of
from vectordrive.core import mechanics as M
from vectordrive.io import native

app = QApplication.instance() or QApplication([])


class TestKeptSettings(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.view3d import Panel3D
        self.w = MainWindow()
        self.w.modified = False
        self.p = Panel3D(self.w)
        self.m = model_of(box_tris(0, 0, 0, 10, 10, 5), box_tris(0, 0, 5, 10, 10, 10))
        self.p.model = self.m
        self.p.view.set_model(self.m)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_open_does_not_modify(self):
        dlg = self.p.mechanisms(show=False)
        self.assertNotIn('mecanismes', self.w.canvas.doc.extra)
        self.assertFalse(self.w.modified)
        dlg.done(0)

    def test_kept_and_restored(self):
        doc = self.w.canvas.doc
        dlg = self.p.mechanisms(show=False)
        dlg.moves_table.cellWidget(0, 3).setValue(12.5)                   # course
        self.assertTrue(self.w.modified)
        self.assertEqual(doc.extra['mecanismes']['moves']['1']['amount'], 12.5)
        dlg.moves_table.cellWidget(0, 4).setChecked(True)                 # sens inversé
        dlg.tol.setValue(0.5)
        dlg.detect()                                                      # « Repérer » : réglages gardés
        self.assertEqual(doc.extra['mecanismes']['settings']['tol'], 0.5)
        self.assertTrue(dlg.moves_table.cellWidget(0, 4).isChecked())     # le sens reste inversé
        dlg.moves_table.cellWidget(0, 0).setChecked(False)                # pas animé
        dlg.done(0)
        back = native.from_dict(native.to_dict(doc))                      # enregistré avec le dessin
        self.assertEqual(back.extra['mecanismes'], doc.extra['mecanismes'])
        self.w.modified = False
        again = self.p.mechanisms(show=False)
        self.assertAlmostEqual(again.tol.value(), 0.5, 6)
        mo = again.shown_motions()[0]
        self.assertTrue(mo.inverted)
        self.assertAlmostEqual(mo.amount, 12.5, 6)
        self.assertLess(mo.axis[2], -0.99)
        self.assertTrue(again.moves_table.cellWidget(0, 4).isChecked())
        self.assertFalse(again.moves_table.cellWidget(0, 0).isChecked())
        again.set_progress(1.0)
        self.assertEqual(self.p.view.body_moves, {})                      # pas animé : ne bouge pas
        self.assertFalse(self.w.modified)
        again.done(0)

    def test_other_part_ignored(self):
        self.w.canvas.doc.extra['mecanismes'] = {'bodies': 3, 'settings': {'tol': 2.0},
                                                 'moves': {'1': {'kind': 'translation', 'joint': 'appui',
                                                                 'amount': 99.0, 'invert': True, 'on': False}}}
        dlg = self.p.mechanisms(show=False)
        self.assertAlmostEqual(dlg.tol.value(), M.Settings().tol, 6)    # réglages d'une pièce à 3 corps
        self.assertFalse(dlg.shown_motions()[0].inverted)
        dlg.done(0)

    def test_fixed_body_restored(self):
        dlg = self.p.mechanisms(show=False)
        dlg.fixed.setCurrentIndex(dlg.fixed.findData(1))
        dlg.detect()
        dlg.done(0)
        again = self.p.mechanisms(show=False)
        self.assertEqual(again.fixed.currentData(), 1)
        self.assertEqual(again.shown_motions()[0].body, 0)               # le corps du bas bouge
        again.done(0)


if __name__ == '__main__':
    unittest.main()
