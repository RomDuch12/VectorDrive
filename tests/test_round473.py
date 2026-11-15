"""Round 473 : Alt+W — la sélection centrée sur l'origine."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core.document import Shape
from vectordrive.core.geom import Path, rect

app = QApplication.instance() or QApplication([])


class TestCenterOrigin(unittest.TestCase):
    def test_center(self):
        from vectordrive.ui import shortcuts as SC
        from vectordrive.ui.main_window import MainWindow
        self.assertEqual(SC.te_mapping([('ID_MANIPULER_ZONE_CENTRER', 'Alt+W')]).get('center_origin'), ['Alt+W'])
        w = MainWindow()
        try:
            self.assertEqual(w.A['center_origin'].shortcut().toString(), 'Alt+W')
            sh = Shape(path=Path([rect(10, 20, 40, 10)]))
            w.canvas.doc.add(sh)
            w.canvas.select([sh])
            self.assertTrue(w.center_on_origin())
            bb = w.canvas.selection_bbox()
            self.assertAlmostEqual((bb[0] + bb[2]) / 2, 0.0)
            self.assertAlmostEqual((bb[1] + bb[3]) / 2, 0.0)
            self.assertFalse(w.center_on_origin())                            # déjà centrée
            w.canvas.set_origin(100.0, 50.0)                                   # origine placée ailleurs
            self.assertTrue(w.center_on_origin())
            bb = w.canvas.selection_bbox()
            self.assertAlmostEqual((bb[0] + bb[2]) / 2, 100.0)
            w.undo()
            bb = w.canvas.selection_bbox() or w.canvas.doc.bbox()
            self.assertAlmostEqual((bb[0] + bb[2]) / 2, 0.0)
            w.canvas.select([])
            self.assertFalse(w.center_on_origin())
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
