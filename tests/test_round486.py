"""Round 486 : panneau FAO sur toute la hauteur — Dimensions en onglet tant qu'il est ouvert."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget

app = QApplication.instance() or QApplication([])


class TestCamFullHeight(unittest.TestCase):
    def test_tabified_and_restored(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.resize(1400, 900)
            w.show()
            app.processEvents()
            w.A['cam_panel'].setChecked(False)                                # état laissé par un autre essai
            dims = w.findChild(QDockWidget, 'dims')
            dims.setVisible(True)
            if dims in w.tabifiedDockWidgets(w.findChild(QDockWidget, 'layers')):
                w.columns.untab(dims, remember=False)                         # d'office en onglet (round 1022)
            if dims in w.tabifiedDockWidgets(w.dock_paths):
                w.splitDockWidget(w.findChild(QDockWidget, 'layers'), dims, Qt.Orientation.Vertical)
            app.processEvents()
            self.assertNotIn(dims, w.tabifiedDockWidgets(w.dock_paths))
            w.A['cam_panel'].setChecked(True)
            app.processEvents()
            self.assertIn(dims, w.tabifiedDockWidgets(w.dock_paths))           # en onglet à côté
            self.assertGreater(w.dock_paths.height(), w.height() * 0.6)
            w.focus_dimensions()                                               # F2 : l'onglet montré
            app.processEvents()
            self.assertFalse(dims.visibleRegion().isEmpty())
            w.A['cam_panel'].setChecked(False)
            app.processEvents()
            self.assertFalse(w.dock_paths.isVisible())
            self.assertNotIn(dims, w.tabifiedDockWidgets(w.findChild(QDockWidget, 'layers')))
        finally:
            w.settings.setValue('vue/panneau_fao', False)
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
