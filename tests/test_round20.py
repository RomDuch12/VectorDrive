"""Round 20 : ordre, gel, masquage (et exports qui ignorent le masqué)."""
import os
import pathlib
import re
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Shape
from vectordrive.core.geom import Path
from vectordrive.io import dxf


def sq(x):
    return Shape(path=Path([geom.rect(x, 0, 5, 5)]), name=f's{x}')


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.items = [self.w.canvas.doc.add(sq(x)) for x in (0, 10, 20, 30)]

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def names(self):
        return [it.name for it in self.w.canvas.doc.layers[0].items]

    def test_order(self):
        w = self.w
        w.canvas.select([self.items[1]])
        w.reorder('front')
        self.assertEqual(self.names(), ['s0', 's20', 's30', 's10'])
        w.reorder('back')
        self.assertEqual(self.names(), ['s10', 's0', 's20', 's30'])
        w.reorder('forward')
        self.assertEqual(self.names(), ['s0', 's10', 's20', 's30'])
        w.reorder('backward')
        self.assertEqual(self.names(), ['s10', 's0', 's20', 's30'])
        w.undo()
        self.assertEqual(self.names(), ['s0', 's10', 's20', 's30'])

    def test_freeze_and_hide(self):
        w = self.w
        w.canvas.select(self.items[:2])
        w.freeze_selection()
        w.canvas.select_all()
        self.assertEqual(len(w.canvas.selection), 2)              # les gelés ne se sélectionnent plus
        w.unfreeze_all()
        w.canvas.select([self.items[3]])
        w.hide_selection()
        w.canvas.select_all()
        self.assertEqual(len(w.canvas.selection), 3)
        w.show_all()
        w.canvas.select_all()
        self.assertEqual(len(w.canvas.selection), 4)


class TestHiddenNotExported(unittest.TestCase):
    def test_hidden_group(self):
        d = Document()
        d.add(sq(0))
        g = d.add(Group(children=[sq(10), sq(20)]))
        g.visible = False
        with tempfile.TemporaryDirectory() as t:                  # SimPl : essais du plugin (round 218)
            f2 = pathlib.Path(t) / 'a.dxf'
            dxf.write(d, f2)
            back = dxf.read(f2)
        self.assertEqual(back.stats()['contours'], 1)


if __name__ == '__main__':
    unittest.main()
