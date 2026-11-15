"""Round 465 : un dessin glissé depuis la bibliothèque est posé là où on le lâche (un dessin venu
d'ailleurs reste importé tel quel)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

DXF = ("0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n8\n0\n90\n4\n70\n1\n10\n100\n20\n100\n10\n110\n20\n100\n10\n110\n"
       "20\n104\n10\n100\n20\n104\n0\nENDSEC\n0\nEOF\n")


class TestDrop(unittest.TestCase):
    def test_drop(self):
        from vectordrive.ui.main_window import MainWindow
        lib = pathlib.Path(tempfile.mkdtemp())
        f = lib / 'plaque.dxf'
        f.write_text(DXF, encoding='ascii')
        other = pathlib.Path(tempfile.mkdtemp()) / 'ailleurs.dxf'
        other.write_text(DXF, encoding='ascii')
        w = MainWindow()
        try:
            w.symbols.roots = [lib]
            self.assertTrue(w._from_library(str(f)))
            self.assertFalse(w._from_library(str(other)))
            w._file_dropped(str(f), 20.0, 30.0)
            bb = w.canvas.selection[0].bbox()
            self.assertAlmostEqual((bb[0] + bb[2]) / 2, 20.0, places=4)          # centré au point de dépôt
            self.assertAlmostEqual((bb[1] + bb[3]) / 2, 30.0, places=4)
            w._file_dropped(str(other), 0.0, 0.0)
            bb2 = w.canvas.selection[0].bbox()
            self.assertAlmostEqual(bb2[0], 100.0, places=4)                       # importé à sa place
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
