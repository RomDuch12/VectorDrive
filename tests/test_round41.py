"""Round 41 : boîte Plaque (épaisseur gardée, plaques enregistrées,
ajustement au dessin)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core.document import Plate


class TestPlateDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PySide6.QtCore import QSettings
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(pathlib.Path(self.tmp.name) / 'r.ini'), QSettings.Format.IniFormat)

    def tearDown(self):
        self.tmp.cleanup()

    def test_thickness_and_visibility_kept(self):
        from vectordrive.ui.main_window import PlateDialog
        p = Plate(120, 80, 3, 'Laiton', 5, 6, False, 1.5)
        dlg = PlateDialog(p, settings=self.settings)
        self.assertEqual(dlg.plate(), p)

    def test_presets(self):
        from vectordrive.ui.main_window import PlateDialog
        dlg = PlateDialog(Plate(100, 50, 2, 'Alu', thickness=0.8), settings=self.settings)
        dlg.save_preset('Plaque porte')
        dlg2 = PlateDialog(Plate(10, 10), settings=self.settings)
        i = dlg2.presets.findText('Plaque porte')
        self.assertGreater(i, 0)
        dlg2._apply_preset(i)
        q = dlg2.plate()
        self.assertEqual((q.width, q.height, q.corner_radius, q.thickness, q.material), (100, 50, 2, 0.8, 'Alu'))
        dlg2.presets.setCurrentIndex(i)
        dlg2._remove_preset()
        self.assertEqual(dlg2.presets.findText('Plaque porte'), -1)

    def test_fit_drawing(self):
        from vectordrive.ui.main_window import PlateDialog
        dlg = PlateDialog(Plate(), settings=self.settings, drawing_bbox=(10, 20, 70, 50))
        dlg.margin.setValue(5)
        dlg.fit_drawing()
        q = dlg.plate()
        self.assertEqual((q.x, q.y, q.width, q.height), (5, 15, 70, 40))


if __name__ == '__main__':
    unittest.main()
