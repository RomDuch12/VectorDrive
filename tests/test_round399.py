"""Round 399 : accrochage intuitif de la cotation (TypeEdit) — sans F3,
l'outil Cote s'accroche aux points."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestIntuitive(unittest.TestCase):
    def test_dimension_snaps(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            c.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])))
            c.snap.enabled = False
            near = c.to_screen(10.0 + 2 / c.scale, 10.0 + 2 / c.scale)   # 2 pixels du coin
            w.set_tool('dim')
            self.assertNotEqual(c.snap_doc(near), (10.0, 10.0))              # sans l'option : pas d'accroche
            w.set_intuitive_snap(True)
            self.assertEqual(c.snap_doc(near), (10.0, 10.0))                 # cotation : accrochée au coin
            w.set_tool('polyline')
            self.assertNotEqual(c.snap_doc(near), (10.0, 10.0))              # autre outil : non
        finally:
            w.set_intuitive_snap(False)
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
