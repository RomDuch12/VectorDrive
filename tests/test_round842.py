"""Round 842 : multi-accrochage : Alt fait défiler les points d'accrochage possibles sous le curseur."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.snap import Snap
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
ALT = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Alt, Qt.KeyboardModifier.AltModifier)


class Query(unittest.TestCase):
    def snap(self, *modes):
        return Snap(enabled=True, modes=set(modes))

    def shapes(self):
        return [Shape(path=geom.Path([geom.polyline([(0.0, 0.0), (10.0, 0.0)])])),
                Shape(path=geom.Path([geom.polyline([(0.5, 0.0), (0.5, 10.0)])]))]

    def test_every_point_sorted_by_distance(self):
        got = self.snap('node').query_all(0.1, 0.0, 1.0, self.shapes())
        self.assertEqual([(h.x, h.y) for h in got], [(0.0, 0.0), (0.5, 0.0)])

    def test_the_first_is_what_query_gives(self):
        s = self.snap('node')
        items = self.shapes()
        for x in (0.1, 0.4):
            first = s.query(x, 0.0, 1.0, items)
            self.assertEqual((first.x, first.y), (s.query_all(x, 0.0, 1.0, items)[0].x, 0.0))

    def test_same_point_once(self):
        items = [Shape(path=geom.Path([geom.polyline([(0.0, 0.0), (10.0, 0.0)])])),
                 Shape(path=geom.Path([geom.polyline([(0.0, 0.0), (0.0, 10.0)])]))]
        self.assertEqual(len(self.snap('node', 'intersection').query_all(0.1, 0.1, 1.0, items)), 1)

    def test_several_natures(self):
        c = Shape(path=geom.Path([geom.circle((0.0, 0.0), 0.5)]))
        kinds = {h.kind for h in self.snap('node', 'center', 'quadrant').query_all(0.1, 0.0, 1.0, [c])}
        self.assertIn('center', kinds)
        self.assertIn('quadrant', kinds)

    def test_excluded_and_far_ones_are_left_out(self):
        s = self.snap('node')
        items = self.shapes()
        self.assertEqual(len(s.query_all(0.1, 0.0, 1.0, items, exclude=[items[1]])), 1)
        self.assertEqual(s.query_all(50.0, 50.0, 1.0, items), [])

    def test_disabled(self):
        s = self.snap('node')
        s.enabled = False
        self.assertEqual(s.query_all(0.1, 0.0, 1.0, self.shapes()), [])


class Canvas(unittest.TestCase):
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
        self.layer = Layer(name='Plan 1')
        self.c.doc.layers[:] = [self.layer]
        self.c.doc.active = self.layer.id
        self.c.doc.plate = Plate(width=200.0, height=100.0)
        self.c.scale = 8.0
        self.layer.items.append(Shape(path=geom.Path([geom.polyline([(0.0, 0.0), (10.0, 0.0)])])))
        self.layer.items.append(Shape(path=geom.Path([geom.polyline([(0.5, 0.0), (0.5, 10.0)])])))
        self.was = (self.c.snap.enabled, set(self.c.snap.modes))
        self.c.snap.enabled = True
        self.c.snap.modes = {'node'}
        self.c._snap_cycle = 0
        self.pos = QPointF(self.c.to_screen(0.1, 0.0))

    def tearDown(self):
        self.c.snap.enabled, self.c.snap.modes = self.was
        self.c._snap_cycle = 0
        self.win.set_tool('select')

    def test_alt_goes_round_the_points(self):
        self.assertEqual(self.c.snap_doc(self.pos), (0.0, 0.0))
        self.assertTrue(self.c.cycle_snap())
        self.assertEqual(self.c.snap_doc(self.pos), (0.5, 0.0))
        self.assertTrue(self.c.cycle_snap())
        self.assertEqual(self.c.snap_doc(self.pos), (0.0, 0.0))

    def test_the_key_reaches_it(self):
        self.c.snap_doc(self.pos)
        self.c.keyPressEvent(ALT)
        self.assertEqual(self.c.snap_doc(self.pos), (0.5, 0.0))

    def test_moving_away_starts_again(self):
        self.c.snap_doc(self.pos)
        self.c.cycle_snap()
        self.assertEqual(self.c.snap_doc(self.pos + QPointF(1.0, 0.0)), (0.5, 0.0))     # un tremblement ne perd pas le rang
        self.c.snap_doc(self.pos + QPointF(40.0, 0.0))
        self.assertEqual(self.c._snap_cycle, 0)
        self.assertEqual(self.c.snap_doc(self.pos), (0.0, 0.0))

    def test_one_point_only_nothing_happens(self):
        self.c.snap.modes = {'center'}
        self.layer.items.append(Shape(path=geom.Path([geom.circle((60.0, 0.0), 5.0)])))
        self.c.snap_doc(QPointF(self.c.to_screen(60.0, 0.0)))
        self.assertFalse(self.c.cycle_snap())

    def test_snap_off(self):
        self.c.snap_doc(self.pos)
        self.c.snap.enabled = False
        self.assertFalse(self.c.cycle_snap())

    def test_a_tool_sees_the_new_point(self):
        self.win.A['tool_polyline'].trigger()
        t = self.c.tool_obj
        seen = []
        t.move = lambda sp, dp, ev: seen.append(dp)
        self.c.snap_doc(self.pos, self.c._tool_exclude())
        self.assertTrue(self.c.cycle_snap())
        self.assertEqual(seen, [(0.5, 0.0)])

    def test_the_message_names_the_point(self):
        said = []
        self.c.measured.connect(said.append)
        try:
            self.c.snap_doc(self.pos)
            self.c.cycle_snap()
        finally:
            self.c.measured.disconnect(said.append)
        self.assertTrue(any('2' in x for x in said))


if __name__ == '__main__':
    unittest.main()
