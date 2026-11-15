"""Round 364 : ligne double (TypeEdit : Ligne simple/double) — écartement,
calage centre / gauche / droite, bouts ouverts / fermés / arrondis."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core.doubleline import double_line

app = QApplication.instance() or QApplication([])

L = [(0, 0), (10, 0), (10, 10)]


def bbox(path):
    return tuple(round(v, 6) for v in path.bbox())


class TestDoubleLine(unittest.TestCase):
    def test_open_centre(self):
        p = double_line(L, 2)
        self.assertEqual(len(p.contours), 2)
        self.assertFalse(any(c.closed for c in p.contours))
        self.assertEqual(bbox(p), (0, -1, 11, 10))                  # onglet à l'angle extérieur

    def test_justify(self):
        self.assertEqual(bbox(double_line(L, 2, 'gauche')), (0, 0, 10, 10))     # à gauche du parcours
        self.assertEqual(bbox(double_line(L, 2, 'droite')), (0, -2, 12, 10))

    def test_ends(self):
        p = double_line(L, 2, ends='ferme')
        self.assertEqual(len(p.contours), 1)
        self.assertTrue(p.contours[0].closed)
        self.assertEqual(bbox(p), (0, -1, 11, 10))
        r = double_line(L, 2, ends='arrondi')
        self.assertEqual(bbox(r), (-1, -1, 11, 11))

    def test_closed(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        p = double_line(sq, 2, closed=True)
        self.assertEqual(len(p.contours), 2)
        self.assertEqual(sorted(bbox(type(p)([c])) for c in p.contours), [(-1, -1, 11, 11), (1, 1, 9, 9)])
        g = double_line(sq, 2, 'gauche', closed=True)               # anti-horaire : la gauche est dedans
        self.assertEqual(sorted(bbox(type(p)([c])) for c in g.contours), [(0, 0, 10, 10), (2, 2, 8, 8)])

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.dline_dialog = lambda cur: None
            w.set_tool('dline')
            self.assertEqual(w.canvas.tool, 'select')                # réglages abandonnés
            w.dline_dialog = lambda cur: {'width': 4.0, 'justify': 'centre', 'ends': 'ferme'}
            w.set_tool('dline')
            c = w.canvas
            e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            for pt in ((0.0, 0.0), (20.0, 0.0)):
                c.tool_obj.press(c.to_screen(*pt), pt, e)
            c.tool_obj.double(None, (20.0, 0.0), e)
            self.assertEqual(bbox(c.selection[0].path), (0, -2, 20, 2))
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
