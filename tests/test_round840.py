"""Round 840 : Duplication linéaire et circulaire à la souris, Duplication libre avec point de saisie, axe et F2."""
import math
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import duplicate as D
from vectordrive.core import geom
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Path
from vectordrive.ui import shortcuts as S
from vectordrive.ui import tools as T
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])


class Ev:
    def __init__(self, mods=Qt.KeyboardModifier.NoModifier):
        self.mods = mods

    def modifiers(self):
        return self.mods


PLAIN = Ev()
CTRL = Ev(Qt.KeyboardModifier.ControlModifier)
TAB = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)


def centers(items):
    out = []
    for it in items:
        bb = it.bbox()
        out.append((round((bb[0] + bb[2]) / 2, 6), round((bb[1] + bb[3]) / 2, 6)))
    return out


class Core(unittest.TestCase):
    def test_offsets_shift_rows_and_columns(self):
        s = Shape(path=Path([geom.rect(-1.0, -1.0, 2.0, 2.0)]))
        got = centers(D.grid([s], 2, 2, 10.0, 20.0, 3.0, 4.0))
        self.assertEqual(sorted(got), sorted([(10.0, 4.0), (3.0, 20.0), (13.0, 24.0)]))

    def test_without_offsets_it_is_the_old_grid(self):
        s = Shape(path=Path([geom.rect(-1.0, -1.0, 2.0, 2.0)]))
        self.assertEqual(sorted(centers(D.grid([s], 2, 2, 10.0, 20.0))), sorted([(10.0, 0.0), (0.0, 20.0), (10.0, 20.0)]))


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.c = self.win.canvas
        self.doc = self.c.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()
        self.c.scale = 8.0
        self.s = Shape(path=Path([geom.rect(-1.0, -1.0, 2.0, 2.0)]))
        self.layer.items.append(self.s)
        self.c.select([self.s])

    def tearDown(self):
        self.win.set_tool('select')

    def drag(self, t, a, b, ev=PLAIN):
        t.press(None, a, ev)
        t.move(None, b, ev)
        t.release(None, b, ev)


class Linear(Base):
    def test_columns_only_follow_the_gesture(self):
        t = self.win.dup_linear({'cols': 3, 'rows': 1})
        self.assertIs(self.c.tool_obj, t)
        self.drag(t, (0.0, 0.0), (10.0, 5.0))
        self.assertEqual(centers(self.layer.items), [(0.0, 0.0), (10.0, 5.0), (20.0, 10.0)])

    def test_rows_only_too(self):
        self.drag(self.win.dup_linear({'cols': 1, 'rows': 3}), (0.0, 0.0), (10.0, 5.0))
        self.assertEqual(centers(self.layer.items), [(0.0, 0.0), (10.0, 5.0), (20.0, 10.0)])

    def test_columns_and_rows_make_a_grid(self):
        self.drag(self.win.dup_linear({'cols': 2, 'rows': 2}), (0.0, 0.0), (10.0, 5.0))
        self.assertEqual(sorted(centers(self.layer.items)), [(0.0, 0.0), (0.0, 5.0), (10.0, 0.0), (10.0, 5.0)])

    def test_tab_sends_the_last_copy_to_the_pointer(self):
        t = self.win.dup_linear({'cols': 3, 'rows': 1})
        self.assertTrue(t.wants_key(TAB))
        self.assertTrue(t.key(TAB))
        self.drag(t, (0.0, 0.0), (20.0, 10.0))
        self.assertEqual(centers(self.layer.items)[-1], (20.0, 10.0))
        self.assertEqual(centers(self.layer.items)[1], (10.0, 5.0))

    def test_tab_on_a_grid(self):
        t = self.win.dup_linear({'cols': 3, 'rows': 3})
        t.key(TAB)
        self.drag(t, (0.0, 0.0), (20.0, 10.0))
        self.assertIn((20.0, 10.0), centers(self.layer.items))
        self.assertIn((10.0, 5.0), centers(self.layer.items))
        self.assertEqual(len(self.layer.items), 9)

    def test_ctrl_takes_45_degrees(self):
        self.drag(self.win.dup_linear({'cols': 2, 'rows': 1}), (0.0, 0.0), (10.0, 1.0), CTRL)
        self.assertEqual(centers(self.layer.items)[1][1], 0.0)

    def test_a_click_without_gesture_does_nothing(self):
        t = self.win.dup_linear({'cols': 3, 'rows': 1})
        n = len(self.win._undo)
        self.drag(t, (0.0, 0.0), (0.1, 0.0))
        self.assertEqual(len(self.layer.items), 1)
        self.assertEqual(len(self.win._undo), n)
        self.assertIs(self.c.tool_obj, t)

    def test_undo_is_one_step(self):
        self.drag(self.win.dup_linear({'cols': 4, 'rows': 1}), (0.0, 0.0), (10.0, 0.0))
        self.win.undo()
        self.assertEqual(len(self.doc.layers[0].items), 1)

    def test_the_tool_ends_after_the_gesture(self):
        self.drag(self.win.dup_linear({'cols': 2, 'rows': 1}), (0.0, 0.0), (10.0, 0.0))
        self.assertEqual(self.c.tool, 'select')

    def test_preview_is_what_is_placed(self):
        t = self.win.dup_linear({'cols': 3, 'rows': 2})
        t.press(None, (0.0, 0.0), PLAIN)
        t.move(None, (10.0, 5.0), PLAIN)
        seen = []
        with mock.patch.object(t, 'preview', lambda p, path, color=None: seen.append(path)):
            t.paint(mock.MagicMock())
        shown = sorted((round((b[0] + b[2]) / 2, 6), round((b[1] + b[3]) / 2, 6)) for b in (x.bbox() for x in seen))
        t.release(None, (10.0, 5.0), PLAIN)
        self.assertEqual(shown, sorted(centers(self.layer.items)[1:]))

    def test_a_huge_preview_uses_boxes(self):
        t = self.win.dup_linear({'cols': 3, 'rows': 1})
        t.MAX_PREVIEW = 0
        t.press(None, (0.0, 0.0), PLAIN)
        t.move(None, (10.0, 5.0), PLAIN)
        seen = []
        with mock.patch.object(t, 'preview', lambda p, path, color=None: seen.append(path)):
            t.paint(mock.MagicMock())
        self.assertEqual(len(seen), 2)
        t.cancel()

    def test_no_selection_explains(self):
        self.c.select([])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as say:
            self.assertIsNone(self.win.dup_linear({'cols': 3, 'rows': 1}))
        say.assert_called_once()

    def test_cancelled_window_leaves_the_tool(self):
        before = self.c.tool_obj
        with mock.patch.object(self.win, '_ask', return_value=None):
            self.assertIsNone(self.win.dup_linear())
        self.assertIs(self.c.tool_obj, before)

    def test_f2_with_offsets(self):
        t = self.win.dup_linear({'cols': 2, 'rows': 2})
        new = self.win.array_dialog(t, {'cols': 2, 'rows': 2, 'dx': 10.0, 'dy': 20.0, 'ox': 3.0, 'oy': 4.0})
        self.assertEqual(sorted(centers(new)), sorted([(10.0, 4.0), (3.0, 20.0), (13.0, 24.0)]))
        self.assertEqual(self.c.tool, 'select')

    def test_f2_key_opens_the_numbers(self):
        t = self.win.dup_linear({'cols': 2, 'rows': 1})
        with mock.patch.object(self.win, 'array_dialog', return_value=[]) as dlg:
            self.win.f2()
        dlg.assert_called_once_with(t)

    def test_real_window_values(self):
        for key in ('dup_lineaire', 'dup_lineaire_f2'):
            self.win.settings.remove(f'cad/{key}')
        try:
            with mock.patch('vectordrive.ui.dialogs.ParamsDialog.exec', return_value=1):
                t = self.win.dup_linear()
                self.assertEqual((t.cols, t.rows), (3, 1))
                t.press(None, (0.0, 0.0), PLAIN)
                t.move(None, (7.0, 0.0), PLAIN)
                self.win.array_dialog(t)
            self.assertEqual(len(self.layer.items), 3)
            self.assertEqual(centers(self.layer.items)[1], (7.0, 0.0))
        finally:
            for key in ('dup_lineaire', 'dup_lineaire_f2'):
                self.win.settings.remove(f'cad/{key}')


class Circular(Base):
    def setUp(self):
        super().setUp()
        self.s.path = Path([geom.rect(9.0, -1.0, 2.0, 2.0)])

    def test_the_gesture_ends_at_the_centre(self):
        self.drag(self.win.dup_circular({'count': 4}), (10.0, 0.0), (0.0, 0.0))
        got = sorted(centers(self.layer.items))
        self.assertEqual(len(got), 4)
        for want in ((10.0, 0.0), (0.0, 10.0), (-10.0, 0.0), (0.0, -10.0)):
            self.assertTrue(any(math.dist(q, want) < 1e-6 for q in got), want)

    def test_rotation_turns_the_copies(self):
        self.s.path = Path([geom.rect(9.0, -1.0, 2.0, 4.0)])
        self.drag(self.win.dup_circular({'count': 4, 'rotate': True}), (10.0, 0.0), (0.0, 0.0))
        b = self.layer.items[1].bbox()
        self.assertAlmostEqual(b[2] - b[0], 4.0)
        self.assertAlmostEqual(b[3] - b[1], 2.0)

    def test_without_rotation_copies_stay_aligned(self):
        self.s.path = Path([geom.rect(9.0, -1.0, 2.0, 4.0)])
        self.drag(self.win.dup_circular({'count': 4, 'rotate': False}), (10.0, 0.0), (0.0, 0.0))
        for it in self.layer.items:
            b = it.bbox()
            self.assertAlmostEqual(b[2] - b[0], 2.0)
            self.assertAlmostEqual(b[3] - b[1], 4.0)

    def test_preview_is_what_is_placed(self):
        for rotate in (True, False):
            with self.subTest(rotate):
                del self.layer.items[1:]
                self.c.select([self.s])
                t = self.win.dup_circular({'count': 5, 'rotate': rotate})
                t.press(None, (10.0, 0.0), PLAIN)
                t.move(None, (0.0, 0.0), PLAIN)
                seen = []
                with mock.patch.object(t, 'preview', lambda p, path, color=None: seen.append(path)):
                    t.paint(mock.MagicMock())
                shown = [(round((b[0] + b[2]) / 2, 6), round((b[1] + b[3]) / 2, 6)) for b in (x.bbox() for x in seen)]
                t.release(None, (0.0, 0.0), PLAIN)
                self.assertEqual(sorted(shown), sorted(centers(self.layer.items[1:])))

    def test_tab_is_not_taken(self):
        self.assertFalse(self.win.dup_circular({'count': 4}).wants_key(TAB))

    def test_at_least_two(self):
        self.assertEqual(self.win.dup_circular({'count': 0}).cols, 2)

    def test_f2(self):
        t = self.win.dup_circular({'count': 4})
        new = self.win.array_dialog(t, {'count': 3, 'angle': 180.0, 'x': 0.0, 'y': 0.0, 'rotate': False})
        self.assertEqual(len(new), 2)
        self.assertEqual(self.c.tool, 'select')

    def test_real_window_values(self):
        for key in ('dup_circulaire', 'dup_circulaire_f2'):
            self.win.settings.remove(f'cad/{key}')
        try:
            with mock.patch('vectordrive.ui.dialogs.ParamsDialog.exec', return_value=1):
                t = self.win.dup_circular()
                self.assertEqual(t.cols, 6)
                self.assertTrue(t.rotate)
                self.win.array_dialog(t)
            self.assertEqual(len(self.layer.items), 6)
        finally:
            for key in ('dup_circulaire', 'dup_circulaire_f2'):
                self.win.settings.remove(f'cad/{key}')


class Free(Base):
    def tool(self, held=False):
        with mock.patch.object(MainWindow, '_ctrl_held', staticmethod(lambda: held)):
            self.win.A['tool_dup_free'].trigger()
        return self.c.tool_obj

    def test_a_click_places_the_centre(self):
        t = self.tool()
        self.drag(t, (20.0, 20.0), (20.0, 20.0))
        self.assertEqual(centers(self.layer.items)[-1], (20.0, 20.0))

    def test_a_drag_follows_the_grabbed_point(self):
        t = self.tool()
        self.drag(t, (1.0, 1.0), (21.0, 21.0))
        self.assertEqual(centers(self.layer.items)[-1], (20.0, 20.0))

    def test_several_copies(self):
        t = self.tool()
        self.drag(t, (20.0, 0.0), (20.0, 0.0))
        self.drag(t, (40.0, 0.0), (40.0, 0.0))
        self.assertEqual(len(self.layer.items), 3)
        self.assertIs(self.c.tool_obj, t)

    def test_ctrl_keeps_to_an_axis(self):
        t = self.tool()
        t.move(None, (30.0, 2.0), CTRL)
        self.assertEqual(t.hover, (30.0, 0.0))
        t.move(None, (2.0, 30.0), CTRL)
        self.assertEqual(t.hover, (0.0, 30.0))

    def test_ctrl_at_the_start_of_the_tool_constrains_it(self):
        t = self.tool(held=True)
        self.assertTrue(t.constrain)
        self.drag(t, (1.0, 1.0), (21.0, 3.0))
        self.assertEqual(centers(self.layer.items)[-1], (20.0, 0.0))

    def test_f2_while_grabbing(self):
        t = self.tool()
        t.press(None, (1.0, 1.0), PLAIN)
        t.move(None, (5.0, 5.0), PLAIN)
        self.win.free_copy_dialog(t, {'x': 11.0, 'y': 21.0})
        self.assertEqual(centers(self.layer.items)[-1], (10.0, 20.0))
        self.assertIsNone(t.down)

    def test_f2_key_opens_the_numbers(self):
        t = self.tool()
        with mock.patch.object(self.win, 'free_copy_dialog') as dlg:
            self.win.f2()
        dlg.assert_called_once_with(t)

    def test_no_selection(self):
        self.c.select([])
        t = self.tool()
        self.drag(t, (1.0, 1.0), (5.0, 5.0))
        self.assertEqual(len(self.layer.items), 1)


class Links(unittest.TestCase):
    def test_typeedit_commands(self):
        self.assertEqual(S.TE_ACTIONS['ID_COMPO_RESEAU'], 'dup_linear')
        self.assertEqual(S.TE_ACTIONS['ID_COMPO_RESEAUCIRC'], 'dup_circular')

    def test_tool_exists(self):
        self.assertTrue(issubclass(T.ArrayDragTool, T.Tool))


if __name__ == '__main__':
    unittest.main()
