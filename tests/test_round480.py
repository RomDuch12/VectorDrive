"""Round 480 : visualiseur — un seul calcul de la vue 3D ; pas d'import dans les fonctions d'arcs."""
import os
import pathlib
import re
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

ISO = "G0 X0 Y0 Z5\nG1 Z-1 F500\nG1 X50\nG2 X20 Y30 I-15 J0\nG0 Z5\n"


class TestViewerOnce(unittest.TestCase):
    def test_single_refresh(self):
        from vectordrive.ui import view3d as V
        from vectordrive.ui.main_window import MainWindow
        f = pathlib.Path(tempfile.mkdtemp()) / 'a.nc'
        f.write_text(ISO, encoding='ascii')
        w = MainWindow()
        try:
            real = V.Panel3D.refresh
            with mock.patch.object(V.Panel3D, 'refresh', autospec=True, side_effect=real) as rf:
                w.view_nc_program(str(f))
            self.assertEqual(rf.call_count, 1)
            self.assertIsNotNone(w.panel3d.relief)
        finally:
            w.modified = False
            w.close()

    def test_no_import_in_arc_helpers(self):
        from vectordrive.cam import model
        src = pathlib.Path(model.__file__).read_text(encoding='utf-8')
        self.assertFalse(re.search(r'^ +import math$', src, flags=re.M))
        m = model.Move('arc_ccw', -10, 0, 0, 0, 0)
        self.assertAlmostEqual(model.arc_length((10, 0, 0), m), 31.4159265, places=6)


if __name__ == '__main__':
    unittest.main()
