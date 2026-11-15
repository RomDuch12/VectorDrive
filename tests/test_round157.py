"""Round 157 : filtre de sélection de TypeEdit (F9, ID_DRAW_FILTER)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, selfilter as SF
from vectordrive.core.document import Group, Shape, Text


def items():
    closed = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
    open_ = Shape(path=geom.Path([geom.polyline([(20, 0), (30, 10)])]))
    text = Text(text='A', size=5)
    code = Group(children=[Shape(path=geom.Path([geom.rect(40, 0, 2, 2)]))])
    code.extra['barcode'] = {'kind': 'qr'}
    curves = Group(children=[Shape(path=geom.Path([geom.rect(50, 0, 5, 5)])),
                             Shape(path=geom.Path([geom.rect(60, 0, 5, 5)]))])
    mixed = Group(children=[Shape(path=geom.Path([geom.rect(70, 0, 5, 5)])),
                            Shape(path=geom.Path([geom.polyline([(80, 0), (85, 5)])]))])
    return closed, open_, text, code, curves, mixed


class TestKinds(unittest.TestCase):
    def test_kinds(self):
        closed, open_, text, code, curves, mixed = items()
        self.assertEqual([SF.kind_of(x) for x in (closed, open_, text, code, curves)],
                         ['closed', 'open', 'text', 'barcode', None])
        self.assertEqual(SF.kinds_of(curves), {'closed'})
        self.assertEqual(SF.kinds_of(mixed), {'closed', 'open'})
        boxed = Text(text='B')
        boxed.extra['box'] = {'w': 20}
        self.assertEqual(SF.kind_of(boxed), 'columns')

    def test_allowed(self):
        closed, open_, text, code, curves, mixed = items()
        self.assertTrue(all(SF.allowed(x, None) for x in items()))
        self.assertEqual([SF.allowed(x, {'closed'}) for x in (closed, open_, text, code, curves, mixed)],
                         [True, False, False, False, True, False])
        self.assertTrue(SF.allowed(mixed, {'closed', 'open'}))
        self.assertFalse(SF.allowed(closed, set()))
        self.assertEqual(SF.count(items())['closed'], 3)


class TestCanvasAndDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.its = items()
        for it in self.its:
            self.w.canvas.doc.add(it)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_select_all_and_band(self):
        c = self.w.canvas
        c.pick_filter = {'open'}
        c.select_all()
        self.assertEqual(c.selection, [self.its[1]])
        c.pick_filter = {'closed', 'barcode'}
        c.select_all()
        self.assertEqual(c.selection, [self.its[0], self.its[3], self.its[4]])
        c.select([])
        c.invert_selection()
        self.assertEqual(len(c.selection), 3)
        c.pick_filter = None
        c.select_all()
        self.assertEqual(len(c.selection), 6)

    def test_pick(self):
        c = self.w.canvas
        c.resize(800, 600)
        if hasattr(c, 'fit'):
            c.fit()
        pt = c.to_screen(0.0, 5.0)                                               # bord gauche du carré
        self.assertIs(c.pick(QPointF(pt)), self.its[0])
        c.pick_filter = {'open'}
        self.assertIsNone(c.pick(QPointF(pt)))

    def test_dialog_and_action(self):
        dlg = self.w.selection_filter(True)
        self.assertTrue(self.w.A['select_filter'].isChecked())
        self.assertEqual(self.w.canvas.pick_filter, set())                      # rien de choisi à l'ouverture
        self.assertIn('(3)', dlg.buttons['closed'].text())
        dlg.buttons['text'].setChecked(True)
        self.assertEqual(self.w.canvas.pick_filter, {'text'})
        dlg.select_matching()
        self.assertEqual(self.w.canvas.selection, [self.its[2]])
        dlg.invert()
        self.assertEqual(self.w.canvas.pick_filter, set(SF.KINDS) - {'text'})
        self.w.selection_filter(False)
        self.assertIsNone(self.w.canvas.pick_filter)
        self.assertFalse(self.w.A['select_filter'].isChecked())
        self.w.selection_filter(True)
        self.assertFalse(any(b.isChecked() for b in dlg.buttons.values()))     # réglage non gardé
        dlg.close()
        self.assertIsNone(self.w.canvas.pick_filter)
        self.assertFalse(self.w.A['select_filter'].isChecked())

    def test_f9_toggles(self):
        a = self.w.A['select_filter']
        a.trigger()                                                              # F9
        self.assertTrue(self.w._selfilter.isVisible())
        self.assertEqual(self.w.canvas.pick_filter, set())
        a.trigger()
        self.assertFalse(self.w._selfilter.isVisible())
        self.assertIsNone(self.w.canvas.pick_filter)

    def test_typeedit_link(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_DRAW_FILTER'], 'select_filter')
        self.assertEqual(self.w.A['select_filter'].shortcut().toString(), 'F9')


if __name__ == '__main__':
    unittest.main()
