"""Round 474 : panneau FAO — partage réglable (outils, opérations, parcours), les opérations d'abord, le
panneau sur toute la hauteur à l'ouverture."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestCamPanelHeight(unittest.TestCase):
    def test_split(self):
        from vectordrive.ui import cam_panel as CP
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.resize(1400, 1000)
            w.show()
            w.A['cam_panel'].setChecked(True)
            app.processEvents()
            p = w.cam_panel
            self.assertEqual(p.split.count(), 3)
            self.assertTrue(p.split.widget(0).isAncestorOf(p.ops))           # round 981 : les opérations en tête
            sizes = p.split.sizes()
            self.assertGreater(sizes[0], sizes[1])                            # les opérations d'abord
            self.assertGreater(sizes[0], sizes[2])
            self.assertGreaterEqual(p.ops.height(), p.ops.minimumHeight())
            self.assertGreater(w.dock_paths.height(), w.height() * 0.5)       # presque toute la hauteur
            p.split.setSizes([300, 100, 100])
            p.split.splitterMoved.emit(100, 1)
            self.assertIsNotNone(w.settings.value(CP.SPLIT_KEY))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
