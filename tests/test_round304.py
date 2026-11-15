"""Round 304 : concepteur de formes — glisser à travers les pièces de formes
qui se recouvrent les réunit, un clic en isole une, Alt les supprime."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core import pathfinder as PF
from vectordrive.core.cadtools import mass_properties
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def two():
    return [(geom.Path([geom.rect(0, 0, 10, 10)]), 1), (geom.Path([geom.rect(5, 0, 10, 10)]), 2)]


def area(p):
    return mass_properties(p)['area']


class TestBuilder(unittest.TestCase):
    def test_merge(self):
        res, n = PF.build(two(), [(2, 5), (7, 5)])                  # pièce gauche + milieu
        self.assertEqual(n, 2)
        self.assertEqual(len(res), 2)
        areas = sorted(round(area(p), 6) for p, _t in res)
        self.assertEqual(areas, [50.0, 100.0])
        merged = max(res, key=lambda pt: area(pt[0]))
        self.assertEqual(merged[1], 1)                              # outil de la première traversée

    def test_click_and_delete(self):
        res, n = PF.build(two(), [(7, 5)])
        self.assertEqual((n, len(res)), (1, 3))                     # trois pièces séparées
        res, n = PF.build(two(), [(7, 5)], delete=True)
        self.assertEqual(len(res), 2)
        self.assertAlmostEqual(sum(area(p) for p, _t in res), 100, 6)
        self.assertEqual(PF.build(two(), [(30, 30)])[1], 0)

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            shapes = [Shape(path=p, tool=t) for p, t in two()]
            for s in shapes:
                c.doc.add(s)
            c.select(shapes)
            w.set_tool('shape_builder')
            t = c.tool_obj

            def e(kind, buttons=Qt.MouseButton.LeftButton):
                return QMouseEvent(kind, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton, buttons,
                                   Qt.KeyboardModifier.NoModifier)
            t.press(c.to_screen(2, 5), (2, 5), e(QEvent.Type.MouseButtonPress))
            for x in (4, 6, 8, 12):
                t.move(c.to_screen(x, 5), (x, 5), e(QEvent.Type.MouseMove))
            t.release(c.to_screen(12, 5), (12, 5), e(QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton))
            items = c.doc.layers[0].items
            self.assertEqual(len(items), 1)                         # tout réuni
            self.assertAlmostEqual(area(items[0].path), 150, 6)
            w.undo()
            self.assertEqual(len(c.doc.layers[0].items), 2)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
