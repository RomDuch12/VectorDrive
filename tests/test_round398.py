"""Round 398 : afficher les points de départ et de contrôle de tous les
contours (options d'affichage de TypeEdit)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestPoints(unittest.TestCase):
    def test_marks(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            c.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])))
            c.doc.add(Shape(path=geom.Path([geom.circle((30, 5), 5)])))
            self.assertEqual(c.point_marks(), ([], []))
            w._toggle_points('starts', True)
            w._toggle_points('nodes', True)
            starts, marks = c.point_marks()
            self.assertEqual(len(starts), 2)
            corners = [m for m in marks if not m[2]]
            smooth = [m for m in marks if m[2]]
            self.assertEqual(len(corners), 4)                         # le carré : quatre angles
            self.assertGreaterEqual(len(smooth), 4)                   # le cercle : des points lisses
            img = QImage(400, 300, QImage.Format.Format_ARGB32)
            p = QPainter(img)
            c._paint_points(p)                                        # se dessine sans erreur
            p.end()
        finally:
            w._toggle_points('starts', False)
            w._toggle_points('nodes', False)
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
