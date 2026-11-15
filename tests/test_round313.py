"""Round 313 : cotes en ordonnée (abscisse ou ordonnée depuis l'origine du
dessin, trait vertical ou horizontal, coudé) et repères (flèche, coude,
palier, texte), dans l'outil Cote (Tab)."""
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


class TestDims(unittest.TestCase):
    def test_ordinate(self):
        d = D.Dim('ordonnee', [(10, 5), (40, 20), (40, 50)])
        self.assertEqual(D.ordinate_axis(d), 'x')
        self.assertAlmostEqual(d.value(), 30)
        self.assertTrue(d.label().startswith('X 30,00'))
        lines, _f, txt = D.build(d)
        self.assertEqual(len(lines.contours), 1)
        self.assertGreater(txt.bbox()[1], 50)                        # texte au-delà du bout
        d = D.Dim('ordonnee', [(10, 5), (40, 20), (70, 24)])
        self.assertEqual(D.ordinate_axis(d), 'y')
        self.assertTrue(d.label().startswith('Y 15,00'))
        self.assertGreaterEqual(len(D.build(d)[0].contours[0].segments), 2)   # coudé

    def test_leader(self):
        d = D.Dim('repere', [(0, 0), (10, 10)], 0.0, D.DimStyle(prefix='Perçage Ø4'))
        self.assertEqual(d.label(), 'Perçage Ø4')
        lines, filled, txt = D.build(d)
        self.assertEqual(len(filled.contours), 1)                    # flèche pleine sur la pointe
        self.assertGreater(txt.bbox()[0], 10)
        back = D.from_dict(D.to_dict(d))
        self.assertEqual((back.kind, back.style.prefix), ('repere', 'Perçage Ø4'))

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            w.set_tool('dim')
            t = c.tool_obj
            tab = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
            while t.mode != 'ordonnee':
                t.key(tab)
            e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            t.press(c.to_screen(25, 10), (25.0, 10.0), e)
            t.press(c.to_screen(25, 30), (25.0, 30.0), e)
            g = c.doc.layers[0].items[-1]
            self.assertEqual(D.dim_of(g).kind, 'ordonnee')
            t.key(tab)
            self.assertEqual(t.mode, 'repere')
            c.leader_text_fn = lambda: 'Note'
            t.press(c.to_screen(0, 0), (0.0, 0.0), e)
            t.press(c.to_screen(10, 10), (10.0, 10.0), e)
            self.assertEqual(D.dim_of(c.doc.layers[0].items[-1]).label(), 'Note')
            c.leader_text_fn = lambda: None                            # abandon : rien
            n = len(c.doc.layers[0].items)
            t.press(c.to_screen(0, 0), (0.0, 0.0), e)
            t.press(c.to_screen(10, 10), (10.0, 10.0), e)
            self.assertEqual(len(c.doc.layers[0].items), n)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
