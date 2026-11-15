"""Round 475 : post-processeur choisi dans les Options (FAO) ; panneaux FAO détachés translucides."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestPostInOptions(unittest.TestCase):
    def setUp(self):
        from vectordrive.plugins import REGISTRY
        REGISTRY.posts['essai475'] = ('Machine d\'essai 475', lambda *a, **k: None)

    def tearDown(self):
        from vectordrive.plugins import REGISTRY
        REGISTRY.posts.pop('essai475', None)

    def test_choose_in_options(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = w.cam_panel
            self.assertFalse(p.post.isVisibleTo(p))                          # plus de liste dans le panneau
            dlg = w.options_dialog(exec_dialog=False, page='FAO')
            combo = dlg.widgets['fao/post']
            i = combo.findData('essai475')
            self.assertGreaterEqual(i, 0)
            combo.setCurrentIndex(i)
            dlg.accept()
            w.apply_options()
            self.assertEqual(p.setup().post, 'essai475')
            self.assertIn('Machine d\'essai 475', p.post_label.text())
            dlg2 = w.options_dialog(exec_dialog=False, page='FAO')           # rouverte : celui du dessin
            self.assertEqual(dlg2.widgets['fao/post'].currentData(), 'essai475')
            w.new_document()                                                 # nouveau dessin : celui des Options
            self.assertEqual(w.cam_panel.setup().post, 'essai475')
        finally:
            w.modified = False
            w.close()

    def test_opacity(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.settings.setValue('fao/opacite', 80)
            w.show()
            w.toggle_paths_window(True)
            app.processEvents()
            self.assertAlmostEqual(w.apply_cam_opacity(), 0.8)
            self.assertAlmostEqual(w.dock_paths.windowOpacity(), 0.8, places=2)
            w.toggle_paths_window(False)
            app.processEvents()
            w.apply_cam_opacity()
            self.assertAlmostEqual(w.dock_paths.windowOpacity(), 1.0, places=2)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
