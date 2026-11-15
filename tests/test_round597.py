"""Round 597 : vue 3D par prise — la pièce (ou le corps) posée comme pour les usinages d'une prise, avec
leurs seules trajectoires ; automatisme d'usinage 3D aussi depuis le panneau FAO."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from tests.test_round596 import two_boxes_stl
from vectordrive.core import solids as SO

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestSetupView(unittest.TestCase):
    def test_setups(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(two_boxes_stl())
            w._ensure_panel3d()
            p = w.panel3d
            self.assertTrue(p.refresh())
            self.assertFalse(p.setup_view.isVisibleTo(p))                  # aucune prise particulière
            dlg = p.auto3d(exec_dialog=False, sequence='Ébauche seule')
            dlg.body_mode.setCurrentIndex(dlg.body_mode.findData('chacun'))
            dlg.side_mode.setCurrentIndex(dlg.side_mode.findData('toutes'))
            w.cam_panel.apply_auto3d(dlg.planned)
            p.refresh()
            self.assertEqual(p.setup_groups(), [('', 0), ('-Z', 0), ('', 1), ('-Z', 1)])   # dessus : le dessin
            labels = [p.setup_view.itemText(i) for i in range(p.setup_view.count())]
            self.assertEqual(labels[0], 'Prise : comme le dessin')
            self.assertIn('Prise : Corps 2, dessous', labels)
            self.assertIn('Prise : Corps 1, comme le dessin', labels)
            p.setup_view.setCurrentIndex(p.setup_view.findData('-Z|1'))
            self.assertEqual(p.current_setup(), ('-Z', 1))
            b = p.view.model.bounds()
            self.assertAlmostEqual(b[0], 40.0, 5)                              # le corps 2 seul
            self.assertAlmostEqual(b[2], -4.0, 5)                              # retourné
            self.assertEqual(len(p.view.model_paths), 1)                       # sa seule trajectoire
            ops = {o.id: o for o in w.cam_panel.setup().operations}
            o = ops[p.view.model_paths[0].op_id]
            self.assertEqual((o.setup_face, o.body3d), ('-Z', 1))
            p.setup_view.setCurrentIndex(0)
            self.assertAlmostEqual(p.view.model.bounds()[0], 0.0, 5)           # toute la pièce
            self.assertEqual(p.view.model_paths, [])
        finally:
            w.modified = False
            w.close()

    def test_from_cam_panel(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(two_boxes_stl())
            dlg = w.cam_panel.auto3d(exec_dialog=False)
            self.assertIsNotNone(dlg)
            self.assertEqual(dlg.model3d.body_count(), 2)
            self.assertIs(w.stage.currentWidget(), w.panel3d)                  # la vue 3D est montrée
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
