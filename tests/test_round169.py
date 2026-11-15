"""Round 169 : sélection au lasso (TypeEdit)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Group, Shape


class Ev:
    def __init__(self, ctrl=False, held=False):
        self._m = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
        self._b = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton

    def modifiers(self):
        return self._m

    def buttons(self):
        return self._b


class TestLasso(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        c = self.w.canvas
        c.resize(800, 600)
        self.a = c.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), name='a'))
        self.b = c.doc.add(Shape(path=geom.Path([geom.rect(30, 0, 10, 10)]), name='b'))
        self.g = c.doc.add(Group(children=[Shape(path=geom.Path([geom.circle((60, 5), 3)]))], name='g'))
        # un grand cadre qui entoure le tout sans être touché par un petit lasso intérieur
        self.frame = c.doc.add(Shape(path=geom.Path([geom.rect(-20, -20, 120, 60)]), name='cadre'))

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_lasso_items(self):
        c = self.w.canvas
        tri = [(-2, -2), (35, 5), (-2, 12)]                                        # touche a et b
        self.assertEqual([it.name for it in c.lasso_items(tri)], ['a', 'b'])
        inside = [(2, 2), (8, 2), (5, 8)]                                          # dans a, sans toucher son bord
        self.assertEqual(c.lasso_items(inside), [])                               # aucun tracé touché (ni le cadre)
        self.assertEqual([it.name for it in c.lasso_items([(55, 0), (65, 0), (60, 10)])], ['g'])
        c.pick_filter = {'open'}
        self.assertEqual(c.lasso_items(tri), [])                                  # filtre F9
        c.pick_filter = None
        self.assertEqual(c.lasso_items([(0, 0), (1, 1)]), [])

    def test_polygon_clicks(self):
        from vectordrive.ui import tools as T
        c = self.w.canvas
        self.w.set_tool('lasso')
        t = c.tool_obj
        self.assertIsInstance(t, T.LassoTool)
        for dp in ((-2, -2), (35, 5), (-2, 12)):
            sp = c.to_screen(*dp)
            t.press(QPointF(sp), dp, Ev())
            t.release(QPointF(sp), dp, Ev())
        t.double(QPointF(0, 0), (-2, 12), Ev())
        self.assertEqual([it.name for it in c.selection], ['a', 'b'])

    def test_freehand_and_operator(self):
        c = self.w.canvas
        self.w.set_tool('lasso')
        t = c.tool_obj
        c.select([self.a])
        c.select_op = 'ajout'
        pts = [(55, -2), (66, -2), (66, 12), (55, 12)]
        sp0 = c.to_screen(*pts[0])
        t.press(QPointF(sp0), pts[0], Ev(held=True))
        for dp in pts[1:]:
            sp = c.to_screen(*dp)
            t.move(QPointF(sp), dp, Ev(held=True))
        t.release(QPointF(c.to_screen(*pts[-1])), pts[-1], Ev())
        self.assertEqual([it.name for it in c.selection], ['a', 'g'])              # ajouté à la sélection
        c.select_op = 'standard'

    def test_action_and_dialog_button(self):
        dlg = self.w.selection_modes(True)
        self.assertIn('tool_lasso', self.w.A)
        from PySide6.QtWidgets import QPushButton
        b = [x for x in dlg.findChildren(QPushButton) if 'Lasso' in x.text()][0]
        b.click()
        self.assertEqual(self.w.canvas.tool, 'lasso')
        self.w.selection_modes(False)


if __name__ == '__main__':
    unittest.main()
