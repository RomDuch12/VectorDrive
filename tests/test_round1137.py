"""Round 1137 : une cote nulle (deux clics au même point, angle ou arc nul) n'est plus posée — l'outil de cote
plantait au clic (« not enough values to unpack ») ; une retouche qui la rendrait nulle laisse la cote telle quelle."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1137.ini'))
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401
from vectordrive.core import dims as D  # noqa: E402

BEFORE = 'avant : pas de dims.drawable'


class NullDims(unittest.TestCase):

    def setUp(self):
        if not hasattr(D, 'drawable'):
            self.fail(BEFORE)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.c = self.w.canvas

    def tearDown(self):
        self.w.set_tool('select')
        self.w.modified = False
        self.w.close()

    def items(self):
        return list(self.c.doc.layers[0].items)

    def test_core(self):
        good = D.Dim('horizontale', [(0, 0), (10, 0)], 5.0)
        nulls = [D.Dim('horizontale', [(3, 3), (3, 3)], 5.0), D.Dim('radiale', [(1, 1), (1, 1)], 4.0),
                 D.Dim('arc', [(0, 0), (0, 0), (0, 0), (0, 0)], 5.0), D.Dim('repere', [(2, 2), (2, 2)], 0.0),
                 D.Dim('angulaire', [(0, 0), (0, 0), (5, 0)], 5.0)]
        self.assertTrue(D.drawable(good))
        self.assertTrue(D.drawable(D.Dim('angulaire', [(10, 0), (0, 0), (0, 10)], 5.0)))
        for d in nulls:
            self.assertFalse(D.drawable(d), d.kind)
            with self.assertRaises(ValueError):
                D.group(d)
        g = D.group(good)
        before = list(g.children), dict(g.extra)
        self.assertFalse(D.rebuild(g, nulls[0]))
        self.assertEqual((g.children, g.extra), before)          # laissée telle quelle
        self.assertTrue(D.rebuild(g, D.Dim('horizontale', [(0, 0), (20, 0)], 5.0)))
        self.assertAlmostEqual(D.dim_of(g).value(), 20.0)

    def test_commit_null(self):
        n0, u0 = len(self.items()), len(self.w._undo)
        self.assertIsNone(self.c.commit_dim(D.Dim('arc', [(0, 0), (0, 0), (0, 0), (0, 0)], 5.0)))
        self.assertEqual((len(self.items()), len(self.w._undo)), (n0, u0))   # rien posé, pas de pas d'annulation
        self.assertIn('nulle', self.w.statusBar().currentMessage())
        self.assertIsNotNone(self.c.commit_dim(D.Dim('horizontale', [(0, 0), (10, 0)], 5.0)))
        self.assertEqual(len(self.items()), n0 + 1)

    def test_tool_clicks(self):
        self.w.set_tool('dim')
        t = self.c.tool_obj
        e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

        def click(x, y):
            t.press(self.c.to_screen(x, y), (float(x), float(y)), e)
        n0 = len(self.items())
        t.mode, t.pts = 'horizontale', []
        click(5, 5); click(5, 9); click(8, 8)                     # l'arrivée ramenée sur le départ : avant, ValueError
        self.assertEqual(len(self.items()), n0)
        self.assertIn('nulle', self.w.statusBar().currentMessage())
        self.assertIsNone(t.prev)                                  # pas suivie en chaîne
        asked = []
        self.c.leader_text_fn = lambda: asked.append(1) or 'X'
        t.mode, t.pts = 'repere', []
        click(2, 2); click(2, 2)                                   # repère sans coude : refusé avant le texte
        self.assertEqual((len(self.items()), asked), (n0, []))
        t.mode, t.pts = 'angulaire', []
        for _ in range(4):
            click(1, 1)
        self.assertEqual(len(self.items()), n0)
        t.mode, t.pts = 'horizontale', []
        click(0, 0); click(10, 0); click(5, 6)
        self.assertEqual(len(self.items()), n0 + 1)
        self.assertIsNotNone(t.prev)

    def test_dialog_null(self):
        from PySide6.QtWidgets import QMessageBox
        from unittest import mock
        g = self.c.commit_dim(D.Dim('libre', [(0, 0), (0, 10)], 5.0))   # alignée sur un trait vertical
        u0, kids = len(self.w._undo), list(g.children)
        dlg = self.w.edit_dim(g, exec_dialog=False)
        dlg.widgets['kind'].setCurrentIndex(dlg.widgets['kind'].findData('horizontale'))   # la rend nulle
        with mock.patch.object(QMessageBox, 'information') as info:
            dlg.accept()
        self.assertTrue(info.called)
        self.assertEqual((len(self.w._undo), g.children), (u0, kids))
        self.assertEqual(D.dim_of(g).kind, 'libre')

    def test_edit_null(self):
        g = self.c.commit_dim(D.Dim('horizontale', [(0, 0), (10, 0)], 5.0))
        u0, kids = len(self.w._undo), list(g.children)
        self.assertIsNone(self.w.edit_dim(g, dim=D.Dim('horizontale', [(4, 4), (4, 4)], 5.0)))
        self.assertEqual((len(self.w._undo), g.children), (u0, kids))
        self.assertIs(self.w.edit_dim(g, dim=D.Dim('horizontale', [(0, 0), (30, 0)], 5.0)), g)
        self.assertAlmostEqual(D.dim_of(g).value(), 30.0)


if __name__ == '__main__':
    unittest.main()
