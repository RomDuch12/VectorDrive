"""Round 743 : Ouvrir toujours agrandie (⛶ et F11 : plein écran, retenu) ;
plaque des nouveaux dessins 500 × 400 × 50, rayon 10, origine au centre."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))


class TestOpenPlate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1000, 700)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_open_large(self):
        from PySide6.QtCore import Qt
        from vectordrive.ui.file_browser import FULL_KEY, FileBrowser
        W = Qt.WindowState
        s = self.w.settings
        s.setValue('navigateur/agrandie', False)            # ancien réglage « pas agrandie » : ignoré
        s.setValue(FULL_KEY, False)
        d = FileBrowser(self.w, tempfile.gettempdir())
        self.assertTrue(d.windowState() & W.WindowMaximized)
        d.b_full.click()                                    # ⛶ : plein écran
        self.assertTrue(d.windowState() & W.WindowFullScreen)
        d.reject()
        self.assertIn(s.value(FULL_KEY), (True, 'true'))
        d = FileBrowser(self.w, tempfile.gettempdir())
        self.assertTrue(d.windowState() & W.WindowFullScreen)
        d.b_full.click()                                    # de nouveau : agrandie
        self.assertFalse(d.windowState() & W.WindowFullScreen)
        self.assertTrue(d.windowState() & W.WindowMaximized)
        d.reject()
        self.assertNotIn(s.value(FULL_KEY), (True, 'true'))

    def test_default_plate(self):
        s = self.w.settings
        for k in ('largeur', 'hauteur', 'epaisseur', 'rayon', 'origine'):
            s.remove(f'plaque/{k}')
        self.w.new_document()
        p = self.w.canvas.doc.plate
        self.assertEqual((p.width, p.height, p.thickness, p.corner_radius), (500, 400, 50, 10))
        self.assertEqual((p.x, p.y), (-250, -200))                     # (0, 0) au centre
        self.assertEqual(p.zero_point('c'), (0, 0))
        s.setValue('plaque/origine', 'coin')
        s.setValue('plaque/largeur', 30.0)
        s.setValue('plaque/hauteur', 12.0)
        self.w.new_document()
        p = self.w.canvas.doc.plate
        self.assertEqual((p.x, p.y, p.corner_radius), (0, 0, 6))       # rayon ramené à la demi-hauteur
        for k in ('largeur', 'hauteur', 'origine'):
            s.remove(f'plaque/{k}')


if __name__ == '__main__':
    unittest.main()
