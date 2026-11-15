"""Round 485 : lecture pas à pas calée sur la durée de la machine."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import ncread, relief
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])

ISO = "G0 X0 Y0 Z5\nG1 Z-1 F600\nG1 X60\nG1 Y30\nG0 Z5\n"


class TestMachineTime(unittest.TestCase):
    def test_scaled(self):
        from vectordrive.ui.main_window import MainWindow
        tp = ncread.read(ISO, 'a.nc')
        tp.machine_seconds = 3600.0
        w = MainWindow()
        self.addCleanup(lambda: (setattr(w, 'modified', False), w.close()))
        w.set_view_mode('3d')
        p = w.panel3d.player
        p.load([tp], relief.from_paths(Document(), [tp], cut=False))
        self.assertTrue(p.machine_timed)
        self.assertAlmostEqual(p.times[-1], 3600.0)
        p.slider.setValue(2)
        self.assertIn('durée machine', p.label.text())
        tp.machine_seconds = None
        p.load([tp])
        self.assertFalse(p.machine_timed)


if __name__ == '__main__':
    unittest.main()
