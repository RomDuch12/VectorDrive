"""Round 565 : pose d'un dessin au clic — R le tourne de 90° (Maj+R : dans l'autre sens) avant de le poser."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

DXF = "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n20\n21\n0\n0\nENDSEC\n0\nEOF\n"


def key(k, mods=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QEvent.Type.KeyPress, k, mods)


class TestRotate(unittest.TestCase):
    def test_r_rotates(self):
        from vectordrive.ui.main_window import MainWindow
        f = pathlib.Path(tempfile.mkdtemp()) / 'trait.dxf'
        f.write_text(DXF, encoding='ascii')
        w = MainWindow()
        try:
            self.assertTrue(w.place_symbol_by_click(str(f)))
            t = w.canvas.tool_obj
            self.assertTrue(t.wants_key(key(Qt.Key.Key_R)))
            self.assertTrue(t.key(key(Qt.Key.Key_R)))
            self.assertEqual(t.angle, 90.0)
            t.key(key(Qt.Key.Key_R, Qt.KeyboardModifier.ShiftModifier))
            t.key(key(Qt.Key.Key_R, Qt.KeyboardModifier.ShiftModifier))
            self.assertEqual(t.angle, 270.0)
            t.press(None, (50.0, 50.0), None)
            g = list(w.canvas.doc.iter_items())[0]
            bb = g.bbox()
            self.assertAlmostEqual(bb[2] - bb[0], 0.0, places=6)               # trait de 20 mm debout
            self.assertAlmostEqual(bb[3] - bb[1], 20.0, places=6)
            self.assertAlmostEqual((bb[1] + bb[3]) / 2, 50.0, places=6)        # centré sur le clic
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
