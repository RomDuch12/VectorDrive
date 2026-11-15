"""Round 159 : duplication homothétique sur une courbe de TypeEdit
(ID_COMPO_DUPHOMOTSURCOURBE)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import duplicate as D, geom
from vectordrive.core.document import Shape


def sq(x, y, s):
    return Shape(path=geom.Path([geom.rect(x, y, s, s)]))


def center(it):
    b = it.bbox()
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def size(it):
    b = it.bbox()
    return b[2] - b[0]


class TestScaledAlong(unittest.TestCase):
    def test_sizes_and_positions(self):
        line = geom.polyline([(0, 0), (100, 0)])
        out = D.scaled_along(sq(0, 50, 2), sq(30, 50, 10), line, 5, rotate=False)
        self.assertEqual(len(out), 5)
        for it, s, x in zip(out, (2, 4, 6, 8, 10), (0, 25, 50, 75, 100)):
            self.assertAlmostEqual(size(it), s, places=6)
            cx, cy = center(it)
            self.assertAlmostEqual(cx, x, places=6)
            self.assertAlmostEqual(cy, 0, places=6)

    def test_equidistant(self):
        line = geom.polyline([(0, 0), (100, 0)])
        out = D.scaled_along(sq(0, 50, 2), sq(30, 50, 10), line, 5, rotate=False, equidistant=True)
        boxes = [it.bbox() for it in out]
        gaps = [boxes[i + 1][0] - boxes[i][2] for i in range(4)]
        for g in gaps:
            self.assertAlmostEqual(g, gaps[0], places=6)                         # écart constant
        self.assertAlmostEqual(center(out[0])[0], 0, places=6)
        self.assertAlmostEqual(center(out[-1])[0], 100, places=6)

    def test_rotate_and_closed(self):
        circle = geom.circle((0, 0), 20)
        out = D.scaled_along(sq(0, 0, 2), sq(0, 0, 2), circle, 4)
        self.assertEqual(len(out), 4)
        for it in out:
            cx, cy = center(it)
            self.assertAlmostEqual((cx ** 2 + cy ** 2) ** 0.5, 20, places=3)
        self.assertEqual(D.scaled_along(sq(0, 0, 2), sq(0, 0, 4), circle, 0), [])


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_COMPO_DUPHOMOTSURCOURBE'], 'duplicate_scaled')
        w = MainWindow()
        try:
            doc = w.canvas.doc
            a, b = doc.add(sq(0, 50, 2)), doc.add(sq(30, 50, 6))
            curve = doc.add(Shape(path=geom.Path([geom.polyline([(0, 0), (60, 0)])])))
            w.canvas.select([a, b])
            from unittest import mock
            with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
                self.assertEqual(w.duplicate_scaled_dialog(exec_dialog=False), [])  # pas de courbe
            self.assertTrue(info.called)
            w.canvas.select([a, b, curve])
            new = w.duplicate_scaled_dialog(exec_dialog=False, count=3)
            self.assertEqual([round(size(x), 6) for x in new], [2, 4, 6])
            self.assertEqual(w.canvas.selection, new)
            w.undo()
            self.assertEqual(len(doc.layers[0].items), 3)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
