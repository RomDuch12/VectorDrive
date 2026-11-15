"""Round 850 : Mode Point, « + » et « - » ; Ctrl sur Combiner et Décombiner ; Maj sur le rectangle de sélection ; Simplifier."""
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

from vectordrive.core import geom
from vectordrive.core.document import Group, Layer, Plate, Shape
from vectordrive.ui.main_window import MainWindow


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
        self.c.ox, self.c.oy = 50.0, 50.0
        self.c.move_delay_ms = 0
        self.c.select([])
        self.win.settings.remove('simplifier/precision')

    def tearDown(self):
        self.win.settings.remove('simplifier/precision')

    def add(self, path):
        sh = Shape(path=path if isinstance(path, geom.Path) else geom.Path([path]))
        self.layer.items.append(sh)
        return sh

    def screen(self, x, y):
        return QPointF(self.c.to_screen(x, y))

    def mouse(self, kind, pos, mods=Qt.KeyboardModifier.NoModifier):
        buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        ev = QMouseEvent(kind, pos, self.c.mapToGlobal(pos.toPoint()), Qt.MouseButton.LeftButton, buttons, mods)
        {QEvent.Type.MouseButtonPress: self.c.mousePressEvent, QEvent.Type.MouseMove: self.c.mouseMoveEvent,
         QEvent.Type.MouseButtonRelease: self.c.mouseReleaseEvent}[kind](ev)

    def click(self, x, y):
        p = self.screen(x, y)
        self.mouse(QEvent.Type.MouseButtonPress, p)
        self.mouse(QEvent.Type.MouseButtonRelease, p)

    def key(self, k, mods=Qt.KeyboardModifier.NoModifier):
        ev = QKeyEvent(QEvent.Type.KeyPress, k, mods)
        tool = self.c.tool_obj
        return tool.wants_key(ev) and tool.key(ev)


class TestAddAPoint(Base):

    def setUp(self):
        super().setUp()
        self.sh = self.add(geom.polyline([(0, 0), (40, 0)]))
        self.c.select([self.sh])
        self.win.set_tool('node')
        self.tool = self.c.tool_obj

    def nodes(self):
        return self.sh.path.contours[0].nodes()

    def test_a_click_on_the_outline_puts_a_red_point(self):
        self.click(10, 0)
        self.assertIsNotNone(self.tool.mark)
        self.assertEqual(len(self.nodes()), 2)

    def test_plus_adds_the_point_there(self):
        self.click(10, 0)
        self.assertTrue(self.key(Qt.Key.Key_Plus))
        pts = self.nodes()
        self.assertEqual(len(pts), 3)
        self.assertAlmostEqual(pts[1][0], 10.0, places=6)
        self.assertIsNone(self.tool.mark)

    def test_plus_with_shift_as_on_a_french_keyboard(self):
        self.click(10, 0)
        self.assertTrue(self.key(Qt.Key.Key_Plus, Qt.KeyboardModifier.ShiftModifier))
        self.assertEqual(len(self.nodes()), 3)

    def test_plus_on_the_numeric_keypad(self):
        self.click(10, 0)
        self.assertTrue(self.key(Qt.Key.Key_Plus, Qt.KeyboardModifier.KeypadModifier))
        self.assertEqual(len(self.nodes()), 3)

    def test_the_added_point_is_selected_and_undoable(self):
        self.click(10, 0)
        self.key(Qt.Key.Key_Plus)
        self.assertEqual(len(self.tool.sel), 1)
        self.win.undo()
        self.assertEqual(len(self.doc.layers[0].items[0].path.contours[0].nodes()), 2)

    def test_plus_keeps_its_shortcut_without_a_red_point(self):
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Plus, Qt.KeyboardModifier.NoModifier)
        self.assertFalse(self.tool.wants_key(ev))

    def test_minus_deletes_the_selected_point(self):
        self.click(10, 0)
        self.key(Qt.Key.Key_Plus)
        self.assertTrue(self.key(Qt.Key.Key_Minus))
        self.assertEqual(len(self.nodes()), 2)

    def test_minus_keeps_its_shortcut_without_a_point(self):
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.NoModifier)
        self.assertFalse(self.tool.wants_key(ev))

    def test_a_click_away_removes_the_red_point(self):
        self.click(10, 0)
        self.click(30, 30)
        self.assertIsNone(self.tool.mark)

    def test_a_rectangle_is_not_a_click(self):
        a, b = self.screen(5, 0), self.screen(35, 5)
        self.mouse(QEvent.Type.MouseButtonPress, a)
        self.mouse(QEvent.Type.MouseMove, b)
        self.mouse(QEvent.Type.MouseButtonRelease, b)
        self.assertIsNone(self.tool.mark)

    def test_the_button(self):
        self.click(10, 0)
        self.assertTrue(self.win.node_add())
        self.assertEqual(len(self.nodes()), 3)

    def test_the_button_without_a_point_says_so(self):
        self.assertFalse(self.win.node_add())
        self.assertIn('cliquez', self.win.statusBar().currentMessage())

    def test_a_curve_stays_the_same_curve(self):
        sh = self.add(geom.circle((60, 0), 10.0))
        self.c.select([sh])
        self.win.set_tool('node')
        tool = self.c.tool_obj
        self.click(60 + 10.0 * math.cos(math.radians(40)), 10.0 * math.sin(math.radians(40)))
        ref = sh.path.flatten(0.001)[0]
        self.assertIsNotNone(tool.mark)
        tool.add_marked()
        got = sh.path.flatten(0.001)[0]
        for x, y in got:
            self.assertAlmostEqual(math.hypot(x - 60, y), 10.0, places=2)
        self.assertGreater(len(ref), 3)

    def test_a_stale_point_does_nothing(self):
        self.click(10, 0)
        self.sh.path = geom.Path([])
        self.assertFalse(self.tool.add_marked())

    def test_the_painting_does_not_fail(self):
        self.click(10, 0)
        self.c.repaint()


class TestCtrlOnCombine(Base):

    def test_ctrl_groups(self):
        a, b = self.add(geom.rect(0, 0, 5, 5)), self.add(geom.rect(10, 0, 5, 5))
        self.c.select([a, b])
        with mock.patch.object(MainWindow, '_ctrl_held', staticmethod(lambda: True)):
            self.win.combine_items()
        self.assertEqual(len(self.layer.items), 1)
        self.assertIsInstance(self.layer.items[0], Group)

    def test_without_ctrl_it_combines(self):
        a, b = self.add(geom.rect(0, 0, 5, 5)), self.add(geom.rect(10, 0, 5, 5))
        self.c.select([a, b])
        with mock.patch.object(MainWindow, '_ctrl_held', staticmethod(lambda: False)):
            self.win.combine_items()
        self.assertEqual(len(self.layer.items[0].path.contours), 2)

    def test_ctrl_ungroups(self):
        a, b = self.add(geom.rect(0, 0, 5, 5)), self.add(geom.rect(10, 0, 5, 5))
        self.c.select([a, b])
        self.win.group()
        with mock.patch.object(MainWindow, '_ctrl_held', staticmethod(lambda: True)):
            self.win.uncombine_items()
        self.assertEqual(len(self.layer.items), 2)


class TestShiftOnTheRectangle(Base):
    """Un disque dont la boîte englobante entre dans le rectangle, sans que son tracé y soit."""

    def setUp(self):
        super().setUp()
        self.disc = self.add(geom.circle((10, 10), 10.0))
        self.inside = self.add(geom.rect(30, 30, 2, 2))

    def band(self, mods=Qt.KeyboardModifier.NoModifier):
        a, b = self.screen(19.5, 19.5), self.screen(35, 35)
        self.mouse(QEvent.Type.MouseButtonPress, a, mods)
        self.mouse(QEvent.Type.MouseMove, b, mods)
        self.mouse(QEvent.Type.MouseButtonRelease, b, mods)
        return list(self.c.selection)

    def test_without_shift_only_what_is_inside(self):
        got = self.band()
        self.assertIn(self.inside, got)
        self.assertNotIn(self.disc, got)

    def test_with_shift_also_what_the_box_touches(self):
        got = self.band(Qt.KeyboardModifier.ShiftModifier)
        self.assertIn(self.inside, got)
        self.assertIn(self.disc, got)

    def test_band_items_directly(self):
        a, b = self.screen(19.5, 19.5), self.screen(35, 35)
        self.assertNotIn(self.disc, self.c.band_items(a, b))
        self.assertIn(self.disc, self.c.band_items(a, b, boxes=True))


class TestSimplify(Base):

    def wavy(self):
        return geom.polyline([(x * 0.5, 0.001 * ((-1) ** x)) for x in range(201)])

    def test_it_reduces_the_points_within_the_precision(self):
        sh = self.add(self.wavy())
        before = sh.path.segment_count()
        self.c.select([sh])
        self.assertTrue(self.win.simplify_curves(params={'precision': 0.05}))
        new = self.layer.items[0]
        self.assertLess(new.path.segment_count(), before / 10)
        for x, y in new.path.flatten(0.001)[0]:
            self.assertLess(abs(y), 0.06)

    def test_the_precision_is_remembered(self):
        sh = self.add(self.wavy())
        self.c.select([sh])
        self.win.simplify_curves(params={'precision': 0.2})
        self.assertAlmostEqual(float(self.win.settings.value('simplifier/precision')), 0.2)

    def test_ctrl_asks_for_it(self):
        sh = self.add(self.wavy())
        self.c.select([sh])
        with mock.patch.object(MainWindow, '_ctrl_held', staticmethod(lambda: True)), \
                mock.patch.object(MainWindow, '_ask', return_value=None) as ask:
            self.assertFalse(self.win.simplify_curves())
        ask.assert_called_once()

    def test_without_ctrl_it_does_not_ask(self):
        sh = self.add(self.wavy())
        self.c.select([sh])
        with mock.patch.object(MainWindow, '_ctrl_held', staticmethod(lambda: False)), \
                mock.patch.object(MainWindow, '_shift_held', staticmethod(lambda: False)), \
                mock.patch.object(MainWindow, '_ask') as ask:
            self.assertTrue(self.win.simplify_curves())
        ask.assert_not_called()

    def test_nothing_selected(self):
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertFalse(self.win.simplify_curves())
        info.assert_called_once()

    def test_in_point_mode_the_current_object(self):
        sh = self.add(self.wavy())
        before = sh.path.segment_count()
        self.c.select([sh])
        self.win.set_tool('node')
        self.assertTrue(self.win.simplify_curves(params={'precision': 0.05}))
        self.assertLess(sh.path.segment_count(), before / 10)
        self.win.undo()
        self.assertEqual(self.doc.layers[0].items[0].path.segment_count(), before)


if __name__ == '__main__':
    unittest.main()
