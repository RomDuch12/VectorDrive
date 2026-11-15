"""Round 851 : les touches du manuel de TypeEdit sur les transformations et les formes."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import forms, geom
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.ui import tools as T
from vectordrive.ui.canvas import Canvas
from vectordrive.ui.main_window import MainWindow

K = Qt.KeyboardModifier


def held(ctrl=False, shift=False):
    """Les touches lues au clic sur un bouton."""
    return (mock.patch.object(MainWindow, '_ctrl_held', staticmethod(lambda: ctrl)),
            mock.patch.object(MainWindow, '_shift_held', staticmethod(lambda: shift)))


class Base(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.win = MainWindow()
        cls.win.resize(1200, 800)
        cls.win.show()
        cls.c = cls.win.canvas

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.win.set_tool('select')
        self.doc = self.c.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()
        self.c.scale = 8.0
        self.c.ox, self.c.oy = 200.0, 400.0
        self.c.move_delay_ms = 0
        self.c.snap.enabled = False
        self.c.pivot = None
        self.c.rot_mode = False
        self.c.select([])

    def add(self, path):
        sh = Shape(path=path if isinstance(path, geom.Path) else geom.Path([path]))
        self.layer.items.append(sh)
        return sh

    def box(self, it):
        return tuple(round(v, 6) for v in it.bbox())


class TestMirrors(Base):

    def setUp(self):
        super().setUp()
        self.sh = self.add(geom.rect(0, 0, 10, 5))
        self.c.select([self.sh])

    def click(self, key, ctrl=False, shift=False):
        a, b = held(ctrl, shift)
        with a, b:
            self.win.A[key].trigger()

    def test_plain_mirror_turns_around_the_middle(self):
        self.click('mirror_h')
        self.assertEqual(len(self.layer.items), 1)
        self.assertEqual(self.box(self.layer.items[0]), (0, 0, 10, 5))

    def test_ctrl_puts_the_vertical_axis_on_the_right(self):
        self.click('mirror_h', ctrl=True)
        self.assertEqual(len(self.layer.items), 1)
        self.assertEqual(self.box(self.layer.items[0]), (10, 0, 20, 5))

    def test_ctrl_puts_the_horizontal_axis_at_the_base(self):
        self.click('mirror_v', ctrl=True)
        self.assertEqual(self.box(self.layer.items[0]), (0, -5, 10, 0))

    def test_shift_keeps_the_original(self):
        self.click('mirror_h', shift=True)
        self.assertEqual(len(self.layer.items), 2)
        self.assertEqual(self.box(self.layer.items[0]), (0, 0, 10, 5))

    def test_ctrl_and_shift_copy_on_the_side(self):
        self.click('mirror_h', ctrl=True, shift=True)
        self.assertEqual(sorted(self.box(i) for i in self.layer.items), [(0, 0, 10, 5), (10, 0, 20, 5)])

    def test_one_undo_removes_the_copy(self):
        self.click('mirror_h', ctrl=True, shift=True)
        self.win.undo()
        self.assertEqual(len(self.doc.layers[0].items), 1)

    def test_shift_on_a_quarter_turn_keeps_the_original(self):
        self.click('rot90', shift=True)
        self.assertEqual(len(self.layer.items), 2)
        self.assertEqual(self.box(self.layer.items[0]), (0, 0, 10, 5))

    def test_own_shortcut_is_not_a_gesture(self):
        act = self.win.A['mirror_h']
        act.setShortcut('Ctrl+Alt+Y')
        try:
            a, b = held(ctrl=True)
            with a, b:
                self.assertFalse(self.win._ctrl_on('mirror_h'))
                self.assertFalse(self.win._held_on('mirror_h'))
                self.assertTrue(self.win._ctrl_on('mirror_v'))
        finally:
            act.setShortcuts([])


class TestMirrorOnAnAxis(Base):

    def setUp(self):
        super().setUp()
        self.sh = self.add(geom.rect(2, 0, 3, 3))
        self.axis = self.add(geom.polyline([(0, -10), (0, 10)]))
        self.c.select([self.sh, self.axis])

    def run_it(self, ctrl=False, shift=False):
        a, b = held(ctrl, shift)
        with a, b:
            self.win.mirror_axis()

    def test_by_default_the_objects_turn(self):
        self.run_it()
        self.assertEqual(len(self.layer.items), 2)
        self.assertEqual(self.box(self.layer.items[0]), (-5, 0, -2, 3))
        self.assertEqual(self.box(self.layer.items[1]), (0, -10, 0, 10))

    def test_ctrl_keeps_the_originals(self):
        self.run_it(ctrl=True)
        self.assertEqual(len(self.layer.items), 3)
        self.assertEqual(self.box(self.sh), (2, 0, 5, 3))

    def test_shift_keeps_the_originals(self):
        self.run_it(shift=True)
        self.assertEqual(len(self.layer.items), 3)

    def test_two_markers_are_an_axis(self):
        self.layer.items.remove(self.axis)
        m = [forms.make(forms.Marker(cx=0.0, cy=y)) for y in (-10.0, 10.0)]
        self.layer.items.extend(m)
        self.c.select([self.sh, *m])
        self.run_it()
        self.assertEqual(self.box(self.layer.items[0]), (-5, 0, -2, 3))
        self.assertEqual(len(self.layer.items), 3)

    def test_nothing_to_use_as_an_axis(self):
        self.c.select([self.sh])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.run_it()
        info.assert_called_once()


class TestKeepTheOriginals(Base):

    def two(self):
        a, b = self.add(geom.rect(0, 0, 10, 10)), self.add(geom.rect(5, 0, 10, 10))
        self.c.select([a, b])

    def test_boolean_replaces(self):
        self.two()
        a, b = held()
        with a, b:
            self.win.boolean('union')
        self.assertEqual(len(self.layer.items), 1)

    def test_ctrl_on_a_boolean(self):
        self.two()
        a, b = held(ctrl=True)
        with a, b:
            self.win.boolean('union')
        self.assertEqual(len(self.layer.items), 3)

    def test_shift_on_a_boolean(self):
        self.two()
        a, b = held(shift=True)
        with a, b:
            self.win.boolean('difference')
        self.assertEqual(len(self.layer.items), 3)

    def offset_keep(self, saved, ctrl=False, shift=False):
        self.c.select([self.add(geom.rect(0, 0, 10, 10))])
        self.win.settings.setValue('decalage/garder', saved)
        seen = {}

        def fake(parent, distance, join, keep, last, **_k):
            seen['keep'] = keep
            d = mock.MagicMock()
            d.exec.return_value = False
            return d
        a, b = held(ctrl, shift)
        try:
            with a, b, mock.patch('vectordrive.ui.dialogs.OffsetDialog', fake):
                self.win.offset_dialog()
        finally:
            self.win.settings.remove('decalage/garder')
        return seen['keep']

    def test_offset_uses_what_was_chosen(self):
        self.assertFalse(self.offset_keep(False))

    def test_ctrl_on_offset(self):
        self.assertTrue(self.offset_keep(False, ctrl=True))

    def test_shift_on_offset(self):
        self.assertTrue(self.offset_keep(False, shift=True))

    def test_shift_on_clip(self):
        frame = self.add(geom.rect(0, 0, 10, 10))
        line = self.add(geom.polyline([(5, 5), (30, 5)]))
        self.c.select([frame, line])
        a, b = held(shift=True)
        with a, b:
            self.win.A['clip'].trigger()
        self.assertIn(line, self.layer.items)
        self.assertEqual(self.box(line), (5, 5, 30, 5))
        self.assertGreater(len(self.layer.items), 2)


class TestForms(Base):

    def draft(self, tool, b, mods):
        return self.c._draft_path({'a': (10.0, 10.0), 'b': b, 'tool': tool, 'mods': mods}).bbox()

    def test_rectangle(self):
        self.assertEqual(self.draft('rect', (14.0, 12.0), K.NoModifier), (10, 10, 14, 12))

    def test_ctrl_square(self):
        self.assertEqual(self.draft('rect', (14.0, 12.0), K.ControlModifier), (10, 10, 14, 14))

    def test_shift_rectangle_from_the_centre(self):
        self.assertEqual(self.draft('rect', (14.0, 12.0), K.ShiftModifier), (6, 8, 14, 12))

    def test_ctrl_shift_from_the_centre(self):
        self.assertEqual(self.draft('rect', (14.0, 12.0), K.ControlModifier | K.ShiftModifier), (6, 8, 14, 12))

    def test_shift_ellipse_centred_on_the_first_point(self):
        b = self.draft('ellipse', (14.0, 12.0), K.ShiftModifier)
        self.assertAlmostEqual((b[0] + b[2]) / 2, 10.0, places=6)
        self.assertAlmostEqual((b[1] + b[3]) / 2, 10.0, places=6)
        self.assertAlmostEqual(b[2] - b[0], 8.0, places=3)

    def radial(self, kind, **mods):
        tool = T.RadialTool(self.c, kind)
        tool.a, tool.b = (0.0, 0.0), (10.0, 0.0)
        for k, v in mods.items():
            setattr(tool, k, v)
        return tool.spec()

    def test_polygon_from_the_centre(self):
        s = self.radial('polygon')
        self.assertEqual((s.cx, s.size), (0.0, 10.0))
        self.assertEqual(s.size_mode, 'sommet')

    def test_shift_polygon_on_two_opposite_points(self):
        s = self.radial('polygon', shift=True)
        self.assertEqual((s.cx, s.cy, s.size), (5.0, 0.0, 5.0))
        self.assertEqual(s.size_mode, 'sommet')
        xs = [p[0] for p in s.build().contours[0].nodes()]
        self.assertAlmostEqual(max(xs), 10.0, places=6)

    def test_shift_star_on_two_opposite_points(self):
        s = self.radial('star', shift=True)
        self.assertEqual((s.cx, s.cy, s.r_out), (5.0, 0.0, 5.0))

    def test_alt_polygon_is_circumscribed(self):
        self.assertEqual(self.radial('polygon', alt=True).size_mode, 'cote')

    def test_shift_spiral_still_turns_the_other_way(self):
        s = self.radial('spiral', shift=True)
        self.assertTrue(s.clockwise)
        self.assertEqual(s.cx, 0.0)

    def test_marker_ctrl_asks_for_its_look(self):
        for ctrl, shift, n in ((False, False, 0), (True, False, 1), (False, True, 1)):
            a, b = held(ctrl, shift)
            with a, b, mock.patch.object(MainWindow, 'tool_form_dialog') as dlg:
                self.win.A['tool_marker'].trigger()
            self.assertEqual(dlg.call_count, n)
            self.win.set_tool('select')


class TestScaleMatrix(unittest.TestCase):
    BB = (0.0, 0.0, 10.0, 10.0)

    def factor(self, p, i=2):
        return Canvas.scale_matrix(self.BB, i, p, centered=True, whole=True)

    def corner(self):
        hs = Canvas.doc_handles(self.BB)
        return next(i for i in range(8) if tuple(hs[i]) == (10.0, 10.0))

    def test_whole_steps_up(self):
        m = Canvas.scale_matrix(self.BB, self.corner(), (13.0, 13.0), centered=True, whole=True)
        self.assertEqual(m.apply((10.0, 10.0)), (15.0, 15.0))

    def test_whole_steps_down(self):
        m = Canvas.scale_matrix(self.BB, self.corner(), (6.5, 6.5), centered=True, whole=True)   # 0,3 : un tiers
        x, y = m.apply((10.0, 10.0))
        self.assertAlmostEqual(x, 5.0 + 5.0 / 3.0, places=6)
        self.assertAlmostEqual(y, x, places=6)

    def test_never_below_one_step_up(self):
        m = Canvas.scale_matrix(self.BB, self.corner(), (10.5, 10.5), centered=True, whole=True)
        self.assertEqual(m.apply((10.0, 10.0)), (10.0, 10.0))

    def test_a_side_only_changes_its_axis(self):
        hs = Canvas.doc_handles(self.BB)
        i = next(k for k in range(8) if tuple(hs[k]) == (10.0, 5.0))
        m = Canvas.scale_matrix(self.BB, i, (13.0, 5.0), centered=True, whole=True)
        self.assertEqual(m.apply((10.0, 10.0)), (15.0, 10.0))


class TestHandles(Base):
    """À la souris, sur une poignée."""

    def setUp(self):
        super().setUp()
        self.sh = self.add(geom.rect(0, 0, 10, 10))
        self.c.select([self.sh])
        self.c.update()

    def drag(self, to, mods=K.NoModifier):
        hs = self.c.doc_handles(self.c.selection_bbox())
        i = next(k for k in range(8) if tuple(hs[k]) == (10.0, 10.0))
        a = QPointF(self.c.to_screen(*hs[i]))
        b = QPointF(self.c.to_screen(*to))
        for kind, pos, buttons, meth in ((QEvent.Type.MouseButtonPress, a, Qt.MouseButton.LeftButton, self.c.mousePressEvent),
                                         (QEvent.Type.MouseMove, b, Qt.MouseButton.LeftButton, self.c.mouseMoveEvent),
                                         (QEvent.Type.MouseButtonRelease, b, Qt.MouseButton.NoButton, self.c.mouseReleaseEvent)):
            meth(QMouseEvent(kind, pos, self.c.mapToGlobal(pos.toPoint()), Qt.MouseButton.LeftButton, buttons, mods))

    def test_plain_keeps_the_opposite_corner(self):
        self.drag((20.0, 20.0))
        self.assertEqual(len(self.layer.items), 1)
        self.assertEqual(self.box(self.layer.items[0]), (0, 0, 20, 20))

    def test_shift_keeps_the_original(self):
        self.drag((20.0, 20.0), K.ShiftModifier)
        self.assertEqual(sorted(self.box(i) for i in self.layer.items), [(0, 0, 10, 10), (0, 0, 20, 20)])

    def test_alt_keeps_the_original_too(self):
        self.drag((20.0, 20.0), K.AltModifier)
        self.assertEqual(len(self.layer.items), 2)

    def test_tab_from_the_centre(self):
        self.c._tab_held = True
        try:
            self.drag((15.0, 15.0))
        finally:
            self.c._tab_held = False
        self.assertEqual(self.box(self.layer.items[0]), (-5, -5, 15, 15))

    def test_shift_and_tab(self):
        self.c._tab_held = True
        try:
            self.drag((15.0, 15.0), K.ShiftModifier)
        finally:
            self.c._tab_held = False
        self.assertEqual(sorted(self.box(i) for i in self.layer.items), [(-5, -5, 15, 15), (0, 0, 10, 10)])

    def test_ctrl_whole_steps_from_the_centre(self):
        self.drag((13.0, 13.0), K.ControlModifier)
        self.assertEqual(len(self.layer.items), 1)
        self.assertEqual(self.box(self.layer.items[0]), (-5, -5, 15, 15))

    def test_ctrl_shift_whole_steps_and_a_copy(self):
        self.drag((13.0, 13.0), K.ControlModifier | K.ShiftModifier)
        self.assertEqual(sorted(self.box(i) for i in self.layer.items), [(-5, -5, 15, 15), (0, 0, 10, 10)])

    def test_ctrl_alt_is_free_and_no_copy(self):
        self.drag((20.0, 15.0), K.ControlModifier | K.AltModifier)
        self.assertEqual(len(self.layer.items), 1)
        self.assertEqual(self.box(self.layer.items[0]), (0, 0, 20, 15))

    def test_the_pivot_still_wins(self):
        self.c.pivot = (0.0, 0.0)
        self.drag((20.0, 20.0))
        self.assertEqual(self.box(self.layer.items[0]), (0, 0, 20, 20))


class TestTabKey(Base):

    def send(self, kind, key=Qt.Key.Key_Tab, mods=K.NoModifier):
        return self.c.event(QKeyEvent(kind, key, mods))

    def test_held_with_a_selection(self):
        self.c.select([self.add(geom.rect(0, 0, 5, 5))])
        self.assertTrue(self.send(QEvent.Type.KeyPress))
        self.assertTrue(self.c._tab_held)
        self.send(QEvent.Type.KeyRelease)
        self.assertFalse(self.c._tab_held)

    def test_shift_tab_is_seen_too(self):
        self.c.select([self.add(geom.rect(0, 0, 5, 5))])
        self.send(QEvent.Type.KeyPress, Qt.Key.Key_Backtab, K.ShiftModifier)
        self.assertTrue(self.c._tab_held)
        self.send(QEvent.Type.KeyRelease, Qt.Key.Key_Tab)
        self.assertFalse(self.c._tab_held)

    def test_without_a_selection_it_moves_on(self):
        self.send(QEvent.Type.KeyPress)
        self.assertFalse(self.c._tab_held)

    def test_losing_the_focus_forgets_it(self):
        from PySide6.QtGui import QFocusEvent
        self.c._tab_held = True
        self.c.event(QFocusEvent(QEvent.Type.FocusOut))
        self.assertFalse(self.c._tab_held)

    def test_a_tool_that_wants_it_keeps_it(self):
        self.c.select([self.add(geom.rect(0, 0, 5, 5))])
        self.win.set_tool('dim')
        self.send(QEvent.Type.KeyPress)
        self.assertFalse(self.c._tab_held)
        self.win.set_tool('select')


class TestLoopEraser(Base):

    def setUp(self):
        super().setUp()
        self.sh = self.add(geom.polyline([(0, 0), (10, 10), (10, 0), (0, 10)]))
        self.c.select([self.sh])
        self.win.settings.remove('boucles/longueur')

    def tearDown(self):
        for k in ('longueur', 'critere', 'separer'):
            self.win.settings.remove(f'boucles/{k}')

    def fake(self):
        d = mock.MagicMock()
        d.exec.return_value = False
        return mock.MagicMock(return_value=d)

    def run_it(self, ctrl=False):
        fake = self.fake()
        a, b = held(ctrl)
        with a, b, mock.patch('vectordrive.ui.dialogs.ParamsDialog', fake):
            self.win.remove_loops_dialog()
        return fake.call_count

    def test_first_use_asks(self):
        self.assertEqual(self.run_it(), 1)

    def test_then_the_last_settings_without_asking(self):
        self.win.settings.setValue('boucles/longueur', 0.0)
        self.assertEqual(self.run_it(), 0)

    def test_ctrl_asks(self):
        self.win.settings.setValue('boucles/longueur', 0.0)
        self.assertEqual(self.run_it(ctrl=True), 1)


class TestKeys(Base):

    def keys(self, key):
        return [s.toString() for s in self.win.A[key].shortcuts()]

    def test_order_on_page_keys(self):
        self.assertIn('Shift+PgUp', self.keys('order_back'))
        self.assertIn('Shift+PgDown', self.keys('order_front'))

    def test_viewer(self):
        self.assertEqual(self.keys('open'), ['Ctrl+O', 'Ctrl+Shift+O'])

    def test_no_shortcut_twice(self):
        seen = {}
        for key, act in self.win.A.items():
            for s in act.shortcuts():
                seen.setdefault(s.toString(), []).append(key)
        for s in ('Shift+PgUp', 'Shift+PgDown', 'Ctrl+Shift+O'):
            self.assertEqual(len(seen[s]), 1, (s, seen[s]))

    def test_the_tips_say_it(self):
        self.assertIn('Maj', self.win.A['tool_rect'].toolTip())
        self.assertIn('Alt', self.win.A['tool_polygon'].toolTip())
        self.assertIn('marqueurs', self.win.A['mirror_axis'].toolTip())

    def test_a_click_back_on_the_selection_explains_the_handles(self):
        got = []
        self.c.measured.connect(got.append)
        try:
            sh = self.add(geom.rect(0, 0, 10, 10))
            self.c.select([sh])
            self.c.rot_mode = True
            p = QPointF(self.c.to_screen(5.0, 0.0))
            for kind, meth, buttons in ((QEvent.Type.MouseButtonPress, self.c.mousePressEvent, Qt.MouseButton.LeftButton),
                                        (QEvent.Type.MouseButtonRelease, self.c.mouseReleaseEvent, Qt.MouseButton.NoButton)):
                meth(QMouseEvent(kind, p, self.c.mapToGlobal(p.toPoint()), Qt.MouseButton.LeftButton, buttons, K.NoModifier))
        finally:
            self.c.measured.disconnect(got.append)
        self.assertTrue(any('Tab' in m for m in got), got)
        self.assertFalse(math.isnan(self.c.scale))


if __name__ == '__main__':
    unittest.main()
