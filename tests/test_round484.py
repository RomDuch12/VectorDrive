"""Round 484 : 3D — les parcours cochés dans la liste FAO, mis à jour seuls."""
import os
import pathlib
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

ISO = "T1 M6\nG0 X0 Y0 Z5\nG1 Z-1 F500\nG1 X50\nT2 M6\nG0 X0 Y20 Z5\nG1 Z-0.5\nG1 X40\nG0 Z5\n"


class TestChecked3D(unittest.TestCase):
    def test_uncheck(self):
        from vectordrive.ui.main_window import MainWindow
        f = pathlib.Path(tempfile.mkdtemp()) / 'prog.nc'
        f.write_text(ISO, encoding='ascii')
        w = MainWindow()
        try:
            w.view_nc_program(str(f))
            p3 = w.panel3d
            self.assertEqual(len(p3.relief.toolpaths), 2)
            w.cam_panel.paths.item(1).setCheckState(Qt.CheckState.Unchecked)
            t = time.time()
            while time.time() - t < 3 and len(p3.relief.toolpaths) != 1:
                app.processEvents()
                time.sleep(0.02)
            self.assertEqual(len(p3.relief.toolpaths), 1)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
