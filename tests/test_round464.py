"""Round 464 : lecture des parcours en 3D — temps écoulé sur le total, vue qui suit l'outil."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, ncread, timing

app = QApplication.instance() or QApplication([])


class TestCumulative(unittest.TestCase):
    def test_times(self):
        tp = ncread.read('G21\nG0 X0 Y0 Z5\nG1 Z-1 F60\nG1 X60 F600\n', 'a.nc')
        t = timing.cumulative([tp], model.CamSetup())
        self.assertEqual(len(t), len(tp.moves))
        self.assertAlmostEqual(t[1] - t[0], 6.0, places=3)                        # 6 mm à 60 mm/min
        self.assertAlmostEqual(t[2] - t[1], 6.0, places=3)                        # 60 mm à 600 mm/min


class TestPlayer(unittest.TestCase):
    def test_label_and_follow(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = pathlib.Path(tempfile.mkdtemp()) / 'p.nc'
            p.write_text('G0 X0 Y0 Z5\nG1 Z-1 F60\nG1 X60 F600\nG1 Y40\n', encoding='ascii')
            w.view_nc_program(str(p))
            pl = w.panel3d.player
            self.assertEqual(len(pl.times), len(pl.moves))
            pl.follow.setChecked(True)
            pl.slider.setValue(3)
            self.assertIn(' / ', pl.label.text().split('—')[-1])                 # temps écoulé / total
            v = w.panel3d.view
            x0, y0, _z0, x1, y1, _z1 = v.bounds()
            self.assertAlmostEqual(v.pan.x(), 60 - (x0 + x1) / 2, places=4)       # centrée sur l'outil
            self.assertAlmostEqual(v.pan.y(), 0 - (y0 + y1) / 2, places=4)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
