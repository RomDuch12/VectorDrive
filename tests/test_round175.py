"""Round 175 : déplacer un texte sur sa courbe, courbe de révolution (TypeEdit)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts, geom, text as TX
from vectordrive.core.document import Shape, Text
from vectordrive.core.symmetric import revolution

FONT = next((f for f in ('Arial', 'DejaVu Sans', 'Segoe UI', 'Calibri') if fonts.is_available(f)), None)


class TestRevolution(unittest.TestCase):
    def test_closed_and_rotated(self):
        c = geom.polyline([(10, 0), (12, 3)])
        r = revolution(c, 4, (0, 0))
        self.assertTrue(r.closed)
        pts = [s.start for s in r.segments]
        for p in ((10, 0), (0, -10), (-10, 0), (0, 10)):                         # horaire : 0, -90, 180, 90
            self.assertTrue(any(math.dist(p, q) < 1e-9 for q in pts), p)
        self.assertEqual(len(r.segments), 8)                                     # 4 copies + 4 liaisons
        ccw = revolution(c, 4, (0, 0), clockwise=False)
        self.assertTrue(any(math.dist((0, 10), s.start) < 1e-9 for s in ccw.segments[:3]))

    def test_window_command(self):
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual((TE_ACTIONS['ID_SYMMETRICAL_CURVES_REVOLUTION'], TE_ACTIONS['ID_COMPO_MOVETEXT']),
                         ('revolution', 'text_move_on_path'))
        w = MainWindow()
        try:
            s = w.canvas.doc.add(Shape(path=geom.Path([geom.polyline([(5, 0), (8, 2)])])))
            w.canvas.select([s])
            new = w.revolution(6)
            self.assertTrue(new[0].path.contours[0].closed)
            self.assertNotIn(s, w.canvas.doc.layers[0].items)                    # remplacée
            w.undo()
            self.assertIn(s.id, [it.id for it in w.canvas.doc.layers[0].items])
        finally:
            w.modified = False
            w.close()


@unittest.skipIf(FONT is None, 'aucune police de référence')
class TestMoveText(unittest.TestCase):
    def test_offset_moves_text(self):
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            line = geom.polyline([(0, 0), (100, 0)])
            t = Text(text='AB', font=FONT, size=5, align='center')
            t.extra['on_path'] = line
            t.outline = TX.outline_for(t)
            w.canvas.doc.add(t)
            x0 = t.outline.bbox()[0]
            w.canvas.select([t])
            w.move_text_on_path([t], 10.0, from_start=True)
            self.assertAlmostEqual(t.outline.bbox()[0], 10.0, delta=0.6)          # calé à 10 mm du départ
            self.assertEqual(t.align, 'left')
            w.move_text_on_path([t], 5.0, from_start=False)
            self.assertAlmostEqual(t.outline.bbox()[0], 15.0, delta=0.6)
            self.assertNotAlmostEqual(x0, 15.0, delta=1)
            w.undo()
            w.undo()
            self.assertEqual(w.canvas.doc.layers[0].items[-1].align, 'center')
        finally:
            w.modified = False
            w.close()

    def test_ignores_plain_texts(self):
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            t = w.canvas.doc.add(Text(text='A', font=FONT, size=5))
            self.assertEqual(w.move_text_on_path([t], 3.0), [])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
