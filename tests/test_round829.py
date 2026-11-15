"""Round 829 : la flèche en quatre clics."""
import json
import math
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QInputDialog

from vectordrive.core import forms as F
from vectordrive.core.document import Layer, Plate
from vectordrive.ui import tools as T
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
KEY = 'formes/arrow'


class Ev:
    def __init__(self, key=None, mods=Qt.KeyboardModifier.NoModifier):
        self._k, self._m = key, mods

    def key(self):
        return self._k

    def modifiers(self):
        return self._m


class Clicks(unittest.TestCase):
    def test_second_click_gives_length_and_angle(self):
        s = F.arrow_from_clicks(F.Arrow(), [(10.0, 10.0), (10.0, 50.0)])
        self.assertEqual((s.x, s.y), (10.0, 10.0))
        self.assertEqual(s.anchor, 'depart')
        self.assertAlmostEqual(s.length, 40.0)
        self.assertAlmostEqual(s.angle, 90.0)
        self.assertGreater(s.head_width, s.shaft_width)

    def test_third_click_gives_the_head(self):
        s = F.arrow_from_clicks(F.Arrow(), [(0.0, 0.0), (40.0, 0.0), (30.0, 8.0)])
        self.assertAlmostEqual(s.head_width, 16.0)
        self.assertAlmostEqual(s.head_length, 10.0)
        self.assertAlmostEqual(s.shaft_width, 16.0)          # la maison du manuel : queue aussi large que la pointe
        self.assertEqual(F.arrow_from_clicks(F.Arrow(), [(0.0, 0.0), (40.0, 0.0), (30.0, -8.0)]).head_width, 16.0)

    def test_fourth_click_gives_the_tail_and_the_notch(self):
        s = F.arrow_from_clicks(F.Arrow(), [(0.0, 0.0), (40.0, 0.0), (30.0, 8.0), (10.0, 2.0)])
        self.assertAlmostEqual(s.shaft_width, 4.0)
        self.assertAlmostEqual(s.notch, 0.0)
        s = F.arrow_from_clicks(F.Arrow(), [(0.0, 0.0), (40.0, 0.0), (30.0, 8.0), (35.0, 2.0)])
        self.assertAlmostEqual(s.notch, 0.5)

    def test_any_direction(self):
        a, b = (5.0, 5.0), (5.0 + 30.0 * math.cos(math.radians(30)), 5.0 + 30.0 * math.sin(math.radians(30)))
        n = (-math.sin(math.radians(30)), math.cos(math.radians(30)))
        u = (math.cos(math.radians(30)), math.sin(math.radians(30)))
        q = (a[0] + u[0] * 20.0 + n[0] * 6.0, a[1] + u[1] * 20.0 + n[1] * 6.0)
        s = F.arrow_from_clicks(F.Arrow(), [a, b, q])
        self.assertAlmostEqual(s.angle, 30.0)
        self.assertAlmostEqual(s.head_width, 12.0)
        self.assertAlmostEqual(s.head_length, 10.0)
        p = s.build()
        self.assertAlmostEqual(p.contours[0].segments[0].start[0], b[0], places=6)    # le bout est la pointe
        self.assertAlmostEqual(p.contours[0].segments[0].start[1], b[1], places=6)

    def test_orthogonal_head_has_no_notch(self):
        s = F.arrow_from_clicks(F.Arrow(style='orthogonale'), [(0.0, 0.0), (40.0, 0.0), (30.0, 8.0), (39.0, 2.0)])
        self.assertAlmostEqual(s.notch, 0.0)
        self.assertAlmostEqual(s.shaft_width, 4.0)
        self.assertEqual(len(s.build().contours), 1)

    def test_wire(self):
        s = F.arrow_from_clicks(F.Arrow(style='filaire'), [(0.0, 0.0), (40.0, 0.0), (30.0, 8.0)])
        self.assertAlmostEqual(s.head_width, 16.0)
        self.assertEqual(len(s.build().contours), 2)

    def test_head_behind_the_tail_stays_buildable(self):
        s = F.arrow_from_clicks(F.Arrow(), [(0.0, 0.0), (40.0, 0.0), (-10.0, 8.0), (-10.0, 2.0)])
        self.assertTrue(s.build().contours)
        s = F.arrow_from_clicks(F.Arrow(), [(0.0, 0.0), (40.0, 0.0), (60.0, 0.0)])    # devant la pointe, sur l'axe
        self.assertTrue(s.build().contours)

    def test_keeps_the_double_setting(self):
        s = F.arrow_from_clicks(F.Arrow(double=True), [(0.0, 0.0), (40.0, 0.0)])
        self.assertTrue(s.double)


class Window(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.settings.remove(KEY)
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
        self.win.settings.remove(KEY)
        self.win.set_tool('select')

    def tearDown(self):
        self.win.set_tool('select')
        self.win.settings.remove(KEY)

    def tool(self, label='Standard', ok=True):
        with mock.patch.object(QInputDialog, 'getItem', return_value=(label, ok)) as ask:
            self.win.A['arrow'].trigger()
        self.asked = ask
        return self.win.canvas.tool_obj

    def click(self, t, *pts):
        for q in pts:
            t.press(QPointF(0, 0), q, Ev())

    def test_four_clicks_make_an_editable_arrow(self):
        t = self.tool()
        self.assertIsInstance(t, T.ArrowTool)
        self.click(t, (0.0, 0.0), (40.0, 0.0), (30.0, 8.0))
        self.assertEqual(self.layer.items, [])
        self.click(t, (10.0, 2.0))
        self.assertEqual(len(self.layer.items), 1)
        spec = F.spec_of(self.layer.items[0])
        self.assertEqual(spec.kind, 'arrow')
        self.assertEqual(spec.style, 'standard')
        self.assertAlmostEqual(spec.shaft_width, 4.0)
        self.assertTrue(self.win.A['tool_select'].isChecked())
        self.win.undo()
        self.assertEqual(self.doc.layers[0].items, [])

    def test_wire_needs_three_clicks(self):
        t = self.tool('Filaire')
        self.click(t, (0.0, 0.0), (40.0, 0.0))
        self.assertEqual(self.layer.items, [])
        self.click(t, (30.0, 8.0))
        self.assertEqual(F.spec_of(self.layer.items[0]).style, 'filaire')

    def test_orthogonal(self):
        t = self.tool('Orthogonale')
        self.click(t, (0.0, 0.0), (40.0, 0.0), (30.0, 8.0), (10.0, 2.0))
        self.assertEqual(F.spec_of(self.layer.items[0]).style, 'orthogonale')

    def test_type_is_remembered(self):
        self.tool('Filaire')
        self.assertEqual(json.loads(self.win.settings.value(KEY))['style'], 'filaire')
        self.win.set_tool('select')
        self.tool('Filaire')
        self.assertEqual(self.asked.call_args[0][4], 2)      # proposé d'emblée

    def test_cancel_the_type(self):
        self.tool('Standard', ok=False)
        self.assertNotIsInstance(self.win.canvas.tool_obj, T.ArrowTool)

    def test_ctrl_click_goes_to_numbers(self):
        with mock.patch.object(MainWindow, '_ctrl_held', staticmethod(lambda: True)), \
                mock.patch.object(MainWindow, 'create_form') as form:
            self.win.A['arrow'].trigger()
        form.assert_called_once_with('arrow')

    def test_f2_goes_to_numbers(self):
        t = self.tool()
        self.assertTrue(t.wants_key(Ev(Qt.Key.Key_F2)))
        with mock.patch.object(MainWindow, 'create_form') as form:
            self.assertTrue(t.key(Ev(Qt.Key.Key_F2)))
        form.assert_called_once_with('arrow')

    def test_backspace_takes_back_a_click(self):
        t = self.tool()
        self.assertFalse(t.wants_key(Ev(Qt.Key.Key_Backspace)))
        self.click(t, (0.0, 0.0), (40.0, 0.0))
        self.assertTrue(t.key(Ev(Qt.Key.Key_Backspace)))
        self.assertEqual(len(t.pts), 1)
        self.assertFalse(t.key(Ev(Qt.Key.Key_Delete)))

    def test_same_point_is_not_a_tip(self):
        t = self.tool()
        self.click(t, (5.0, 5.0), (5.0, 5.0))
        self.assertEqual(len(t.pts), 1)

    def test_ctrl_snaps_the_tip_at_45(self):
        t = self.tool()
        t.press(QPointF(0, 0), (0.0, 0.0), Ev())
        t.press(QPointF(0, 0), (40.0, 3.0), Ev(mods=Qt.KeyboardModifier.ControlModifier))
        self.assertAlmostEqual(t.pts[1][1], 0.0)

    def test_cancel(self):
        t = self.tool()
        self.click(t, (0.0, 0.0), (40.0, 0.0))
        t.cancel()
        self.assertEqual(t.pts, [])
        self.assertEqual(self.layer.items, [])

    def test_messages(self):
        said = []
        self.win.canvas.measured.connect(said.append)
        try:
            t = self.tool()
            self.click(t, (0.0, 0.0), (40.0, 0.0), (30.0, 8.0))
        finally:
            self.win.canvas.measured.disconnect(said.append)
        self.assertEqual(len(said), 4)
        self.assertIn('épaisseur', said[-1])

    def test_paint(self):
        t = self.tool()
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        t.paint(p)
        t.move(QPointF(0, 0), (1.0, 1.0), Ev())
        t.paint(p)
        for q in ((0.0, 0.0), (40.0, 0.0), (30.0, 8.0)):
            t.press(QPointF(0, 0), q, Ev())
            t.move(QPointF(0, 0), (35.0, 4.0), Ev())
            t.paint(p)
        p.end()
        self.assertEqual(self.layer.items, [])

    def test_numbers_still_work(self):
        sh = self.win.create_form('arrow', spec=F.Arrow(style='filaire'))
        self.assertEqual(F.spec_of(sh).style, 'filaire')


if __name__ == '__main__':
    unittest.main()
