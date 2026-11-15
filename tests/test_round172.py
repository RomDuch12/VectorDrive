"""Round 172 : ordre des contours (TypeEdit : Ctrl+T)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape


class TestOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_marks(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            a = c.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 5, 5)])))
            b = c.doc.add(Shape(path=geom.Path([geom.rect(20, 0, 5, 5)])))
            ranks = [n for n, _xy in c.order_marks()]
            self.assertEqual(ranks[-2:], [ranks[-2], ranks[-2] + 1])            # tout le dessin, dans l'ordre
            c.select([b, a])
            marks = c.order_marks()
            self.assertEqual([n for n, _ in marks], [1, 2])
            self.assertEqual(marks[0][1], b.path.contours[0].segments[0].point(0.0))
            img = QImage(200, 200, QImage.Format.Format_RGB32)
            p = QPainter(img)
            c._paint_directions(p)                                               # dessin sans erreur
            p.end()
        finally:
            w.modified = False
            w.close()

    def test_sort_then_marks(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            items = [c.doc.add(Shape(path=geom.Path([geom.rect(x, 0, 4, 4)]))) for x in (20, 0, 10)]
            c.select(items)
            w.sort_selection('h')
            xs = [round(xy[0]) for _n, xy in c.order_marks()]
            self.assertEqual(xs, sorted(xs))                                     # rangs de gauche à droite
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
