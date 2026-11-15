"""Round 482 : 3D d'un programme ouvert comme dessin — ses trajectoires, pas le relief plat."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

ISO = "T1 M6\nG0 X0 Y0 Z5\nG1 Z-1 F500\nG1 X50\nT2 M6\nG0 X0 Y20 Z5\nG1 Z-0.5\nG1 X40\nG0 Z5\n"


class TestProgramDocument(unittest.TestCase):
    def test_paths_in_3d(self):
        from vectordrive.ui.main_window import MainWindow
        f = pathlib.Path(tempfile.mkdtemp()) / 'prog.nc'
        f.write_text(ISO, encoding='ascii')
        w = MainWindow()
        try:
            w.canvas.doc.source_path = str(f)
            w.set_view_mode('3d')
            p3 = w.panel3d
            self.assertEqual(p3.relief.source, 'parcours')
            self.assertEqual(len(p3.relief.toolpaths), 2)                     # un parcours par outil
            first = p3._program_cache
            p3.refresh()
            self.assertIs(p3._program_cache, first)                            # lu une fois
            w.canvas.doc.source_path = str(f.with_suffix('.dxf'))
            self.assertEqual(p3._program_paths(), [])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
