"""Round 314 : cotation en chaîne (chaque cote part de l'arrivée de la
précédente, sur la même ligne) et depuis une ligne de base (même départ,
lignes de cote décalées)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import dims as D

app = QApplication.instance() or QApplication([])


def line_y(d):
    return d.points[0][1] + d.offset                                   # cote horizontale : n = (0, 1)


class TestChain(unittest.TestCase):
    def test_chain_and_base(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            w.set_tool('dim')
            t = c.tool_obj
            tab = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
            e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

            def click(x, y):
                t.press(c.to_screen(x, y), (float(x), float(y)), e)
            t.key(tab)
            self.assertEqual(t.mode, 'horizontale')
            click(0, 0); click(10, 0); click(5, 8)                      # première cote : 0 → 10, ligne à y = 8
            while t.mode != 'chaine':
                t.key(tab)
            click(25, 3); click(40, -2)
            dims = [D.dim_of(g) for g in c.doc.layers[0].items]
            self.assertEqual([round(d.value(), 6) for d in dims], [10, 15, 15])
            self.assertEqual(dims[1].points[0], (10.0, 0.0))
            self.assertEqual(dims[2].points[0], (25.0, 3.0))
            self.assertTrue(all(abs(line_y(d) - 8) < 1e-9 for d in dims))   # même ligne de cote
            t.key(tab)
            self.assertEqual(t.mode, 'base')
            click(50, 0); click(60, 0)
            base = [D.dim_of(g) for g in c.doc.layers[0].items][-2:]
            self.assertEqual([b.points[0] for b in base], [(25.0, 3.0), (25.0, 3.0)])  # depuis la dernière
            ys = [line_y(b) for b in base]
            self.assertGreater(ys[0], 8)
            self.assertGreater(ys[1], ys[0])                           # lignes décalées
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()

    def test_from_selection(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            g = c.commit_dim(D.Dim('verticale', [(0, 0), (0, 10)], 6.0))
            c.select([g])
            w.set_tool('dim')
            t = c.tool_obj
            t.mode = 'chaine'
            e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            t.press(c.to_screen(3, 25), (3.0, 25.0), e)
            d = D.dim_of(c.doc.layers[0].items[-1])
            self.assertEqual((d.kind, round(d.value(), 6)), ('verticale', 15))
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
