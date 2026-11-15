"""Round 828 : poser un texte existant sur une courbe, le déplacer à la souris."""
import math
import os
import types
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.core import geom
from vectordrive.core import text as TX
from vectordrive.core.document import Layer, Plate, Shape, Text
from vectordrive.core.geom import Affine, Contour, Cubic, Path
from vectordrive.ui import tools as T
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
LINE = geom.polyline([(0.0, 0.0), (100.0, 0.0)])
SQUARE = geom.rect(0.0, 0.0, 40.0, 40.0)


def word(text='ABC', align='left', on=None):
    t = Text(text=text, font='Arial', size=5.0, align=align)
    if on is not None:
        t.extra['on_path'] = on
    t.outline = TX.outline_for(t)
    return t


class Ev:
    def __init__(self, key=None):
        self._k = key

    def key(self):
        return self._k

    def modifiers(self):
        return Qt.KeyboardModifier.NoModifier


class Core(unittest.TestCase):
    def test_abscissa_on_a_line(self):
        self.assertAlmostEqual(TX.curve_abscissa(LINE, (30.0, 7.0)), 30.0, places=3)
        self.assertAlmostEqual(TX.curve_abscissa(LINE, (-5.0, 0.0)), 0.0, places=3)
        self.assertAlmostEqual(TX.curve_abscissa(LINE, (500.0, 0.0)), 100.0, places=3)

    def test_abscissa_on_a_closed_square(self):
        self.assertAlmostEqual(TX.curve_abscissa(SQUARE, (42.0, 10.0)), 50.0, places=2)
        self.assertAlmostEqual(TX.curve_abscissa(SQUARE, (-2.0, 10.0)), 150.0, places=2)

    def test_abscissa_goes_with_the_walker(self):
        c = Contour([Cubic((0.0, 0.0), (10.0, 30.0), (40.0, -30.0), (50.0, 0.0))], False)
        total, at = geom.walker(c)
        for f in (0.2, 0.5, 0.8):
            q = at(total * f)[0]
            self.assertAlmostEqual(TX.curve_abscissa(c, q), total * f, delta=0.05)

    def test_empty_curve(self):
        self.assertEqual(TX.curve_abscissa(Contour([], False), (0.0, 0.0)), 0.0)

    def test_closed_curve_wraps_instead_of_piling_up(self):
        t = word('ABCDEFGH', on=SQUARE)
        t.extra['path_offset'] = 155.0
        p = TX.outline_for(t)
        centers = [((c.bbox()[0] + c.bbox()[2]) / 2, (c.bbox()[1] + c.bbox()[3]) / 2) for c in p.contours]
        self.assertGreater(max(x for x, _y in centers), 15.0)   # passé le point de départ, sur le premier côté
        distinct = {(round(x, 1), round(y, 1)) for x, y in centers}
        self.assertGreater(len(distinct), 6)

    def test_open_curve_still_stops_at_its_end(self):
        t = word('ABC', on=geom.polyline([(0.0, 0.0), (10.0, 0.0)]))
        t.extra['path_offset'] = 500.0
        b = TX.outline_for(t).bbox()
        self.assertLess(b[2], 20.0)

    def test_moved_outline_does_not_change_the_text(self):
        t = word(on=LINE)
        moved = TX.outline_moved_on_curve(t, 20.0)
        self.assertAlmostEqual(moved.bbox()[0] - t.outline.bbox()[0], 20.0, places=3)
        self.assertNotIn('path_offset', t.extra)
        t.extra['path_offset'] = 3.0
        TX.outline_moved_on_curve(t, 20.0)
        self.assertEqual(t.extra['path_offset'], 3.0)


class Window(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.doc = self.win.canvas.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()
        self.win.set_tool('select')
        self.text = word()
        self.curve = Shape(path=Path([geom.polyline([(10.0, 10.0), (110.0, 10.0)])]))
        self.layer.items[:] = [self.text, self.curve]

    def tearDown(self):
        self.win.set_tool('select')

    def put(self, *sel, shift=False):
        self.win.canvas.select(list(sel))
        with mock.patch.object(MainWindow, '_shift_held', staticmethod(lambda: shift)):
            self.win.text_on_path()

    def test_text_goes_on_the_curve_and_the_curve_goes_away(self):
        self.put(self.text, self.curve)
        self.assertIsNotNone(self.text.extra.get('on_path'))
        b = self.text.outline.bbox()
        self.assertAlmostEqual(b[0], 10.0, delta=1.0)
        self.assertAlmostEqual(b[1], 10.0, delta=1.0)
        self.assertNotIn(self.curve, self.layer.items)
        self.assertEqual(self.win.canvas.selection, [self.text])

    def test_shift_keeps_the_curve(self):
        self.put(self.text, self.curve, shift=True)
        self.assertIsNotNone(self.text.extra.get('on_path'))
        self.assertIn(self.curve, self.layer.items)

    def test_curve_first_also_works(self):
        self.put(self.curve, self.text)
        self.assertIsNotNone(self.text.extra.get('on_path'))

    def test_alignment_decides_the_position(self):
        self.text.align = 'center'
        self.put(self.text, self.curve)
        b = self.text.outline.bbox()
        self.assertAlmostEqual((b[0] + b[2]) / 2, 60.0, delta=1.0)
        self.assertEqual(self.text.align, 'center')

    def test_undo_gives_everything_back(self):
        self.put(self.text, self.curve)
        self.win.undo()
        items = self.doc.layers[0].items
        self.assertEqual(len(items), 2)
        t = next(i for i in items if isinstance(i, Text))
        self.assertIsNone(t.extra.get('on_path'))

    def test_box_and_arc_settings_are_replaced(self):
        self.text.extra['box'] = {'x0': 0.0, 'y0': 0.0, 'x1': 10.0, 'y1': 10.0}
        self.text.extra['fit'] = {'width': 5.0, 'mode': 'spacing'}
        self.text.extra['arc'] = {'center': [0.0, 0.0], 'radius': 10.0}
        self.text.extra['path_offset'] = 7.0
        self.put(self.text, self.curve)
        for k in ('box', 'fit', 'arc', 'path_offset'):
            self.assertNotIn(k, self.text.extra)

    def test_two_lines_refused(self):
        self.text.text = 'AB\nCD'
        with mock.patch.object(QMessageBox, 'information') as info:
            self.put(self.text, self.curve)
        info.assert_called_once()
        self.assertIsNone(self.text.extra.get('on_path'))
        self.assertIn(self.curve, self.layer.items)

    def test_wrong_selection(self):
        other = Shape(path=Path([LINE]))
        self.layer.items.append(other)
        with mock.patch.object(QMessageBox, 'information') as info:
            self.put(self.curve, other)
            self.put(self.text)
            t2 = word('X')
            self.layer.items.append(t2)
            self.put(self.text, t2, self.curve)
        self.assertEqual(info.call_count, 3)

    def test_curve_alone_still_asks_for_a_new_text(self):
        values = {'text': 'NEUF', 'font': 'Arial', 'height': 5.0, 'align': 'center', 'spacing': 0.0}
        fake = mock.MagicMock()
        fake.return_value.exec.return_value = True
        fake.return_value.values.return_value = values
        with mock.patch('vectordrive.ui.dialogs.TextDialog', fake):
            self.put(self.curve)
        self.assertIn(self.curve, self.layer.items)
        new = [t for t in self.layer.items if isinstance(t, Text) and t.text == 'NEUF']
        self.assertEqual(len(new), 1)

    # --- déplacer à la souris ---------------------------------------------------------
    def start_move(self, on=None):
        t = word(on=on or geom.polyline([(10.0, 10.0), (110.0, 10.0)]))
        self.layer.items.append(t)
        self.win.canvas.select([t])
        self.win.A['text_move_on_path'].trigger()
        return t, self.win.canvas.tool_obj

    def test_mouse_moves_along_the_curve(self):
        t, tool = self.start_move()
        self.assertIsInstance(tool, T.MoveOnCurveTool)
        x0 = t.outline.bbox()[0]
        tool.move(QPointF(0, 0), (20.0, 15.0), None)
        tool.move(QPointF(0, 0), (50.0, 3.0), None)
        self.assertAlmostEqual(tool.delta, 30.0, places=1)
        self.assertAlmostEqual(t.outline.bbox()[0], x0, places=6)     # pas encore posé
        tool.press(QPointF(0, 0), (50.0, 3.0), None)
        self.assertAlmostEqual(t.outline.bbox()[0] - x0, 30.0, delta=0.2)
        self.assertTrue(self.win.A['tool_select'].isChecked())
        self.win.undo()

    def test_click_without_moving_changes_nothing(self):
        t, tool = self.start_move()
        n = len(self.win._undo)
        tool.press(QPointF(0, 0), (20.0, 15.0), None)
        self.assertEqual(len(self.win._undo), n)
        self.assertNotIn('path_offset', t.extra)
        self.assertTrue(self.win.A['tool_select'].isChecked())

    def test_passing_the_start_of_a_closed_curve(self):
        square = geom.rect(10.0, 10.0, 40.0, 40.0)
        t, tool = self.start_move(square)
        tool.move(QPointF(0, 0), (12.0, 10.0), None)                  # abscisse 2
        tool.move(QPointF(0, 0), (10.0, 12.0), None)                  # abscisse 158 : 4 mm en arrière, pas 156 en avant
        self.assertAlmostEqual(tool.delta, -4.0, delta=0.1)

    def test_escape_keeps_the_text(self):
        t, tool = self.start_move()
        tool.move(QPointF(0, 0), (20.0, 15.0), None)
        tool.move(QPointF(0, 0), (50.0, 3.0), None)
        tool.cancel()
        self.assertEqual(tool.delta, 0.0)
        self.assertNotIn('path_offset', t.extra)

    def test_f2_opens_the_numbers(self):
        t, tool = self.start_move()
        self.assertTrue(tool.wants_key(Ev(Qt.Key.Key_F2)))
        self.assertFalse(tool.wants_key(Ev(Qt.Key.Key_F3)))
        spec = types.SimpleNamespace(mode='start', value=12.0)
        fake = mock.MagicMock()
        fake.return_value.exec.return_value = True
        fake.return_value.result_params.return_value = spec
        with mock.patch('vectordrive.ui.dialogs.ParamsDialog', fake):
            self.assertTrue(tool.key(Ev(Qt.Key.Key_F2)))
        self.assertEqual(t.extra['path_offset'], 12.0)
        self.assertEqual(t.align, 'left')
        self.assertTrue(self.win.A['tool_select'].isChecked())

    def test_numbers_from_the_last_position(self):
        t, _tool = self.start_move()
        t.extra['path_offset'] = 5.0
        fake = mock.MagicMock()
        fake.return_value.exec.return_value = True
        fake.return_value.result_params.return_value = types.SimpleNamespace(mode='last', value=2.0)
        with mock.patch('vectordrive.ui.dialogs.ParamsDialog', fake):
            self.win.move_text_on_path_dialog()
        self.assertEqual(t.extra['path_offset'], 7.0)

    def test_numbers_cancelled(self):
        t, _tool = self.start_move()
        fake = mock.MagicMock()
        fake.return_value.exec.return_value = False
        with mock.patch('vectordrive.ui.dialogs.ParamsDialog', fake):
            self.assertEqual(self.win.move_text_on_path_dialog(), [])

    def test_no_text_on_a_curve(self):
        self.win.canvas.select([self.text])
        with mock.patch.object(QMessageBox, 'information') as info:
            self.win.A['text_move_on_path'].trigger()
        info.assert_called_once()
        self.assertNotIsInstance(self.win.canvas.tool_obj, T.MoveOnCurveTool)

    def test_text_in_arc_moves_too(self):
        t = word()
        t.extra['arc'] = {'center': [0.0, 0.0], 'radius': 30.0, 'position': 'top', 'side': 'outside'}
        t.outline = TX.outline_for(t)
        self.layer.items.append(t)
        self.win.canvas.select([t])
        self.win.A['text_move_on_path'].trigger()
        self.assertIsInstance(self.win.canvas.tool_obj, T.MoveOnCurveTool)

    def test_paint(self):
        t, tool = self.start_move()
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        tool.paint(p)
        tool.move(QPointF(0, 0), (20.0, 15.0), None)
        tool.move(QPointF(0, 0), (50.0, 3.0), None)
        tool.paint(p)
        p.end()
        self.assertNotIn('path_offset', t.extra)


if __name__ == '__main__':
    unittest.main()
