"""Round 469 : vue 3D anticrénelée (MSAA ×4 demandé)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestFormat(unittest.TestCase):
    def test_samples(self):
        from vectordrive.ui.view3d import View3D
        v = View3D()
        self.assertEqual(v.format().samples(), 4)
        v.deleteLater()


if __name__ == '__main__':
    unittest.main()
