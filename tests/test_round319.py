"""Round 319 : point zéro de la plaque (TypeEdit : Surface active) — coins
ou centre, devient l'origine des coordonnées affichées."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core.document import Plate

app = QApplication.instance() or QApplication([])


class TestZero(unittest.TestCase):
    def test_points(self):
        p = Plate(100, 50, x=10, y=5)
        self.assertEqual(p.zero_point('bg'), (10, 5))
        self.assertEqual(p.zero_point('c'), (60, 30))
        self.assertEqual(p.zero_point('hd'), (110, 55))
        self.assertIsNone(p.zero_point(''))

    def test_dialog(self):
        from vectordrive.ui.main_window import MainWindow, PlateDialog
        w = MainWindow()
        try:
            c = w.canvas
            c.doc.plate = Plate(100, 50)
            dlg = PlateDialog(c.doc.plate, w, settings=w.settings)
            dlg.zero.setCurrentIndex(dlg.zero.findData('c'))
            w.apply_plate(dlg.plate(), dlg.adjust_matrix())
            z = dlg.plate().zero_point(dlg.zero.currentData())
            c.set_origin(*z)
            self.assertEqual(c.origin, (50.0, 25.0))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
