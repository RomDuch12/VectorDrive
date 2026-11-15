"""Round 826 : Double trait : type de coins, espacement de chaque côté de l'axe, réglages gardés."""
import json
import math
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from vectordrive.core.doubleline import double_line, sides_of
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Path
from vectordrive.ui import tools as T
from vectordrive.ui.dline_dialog import DoubleLineDialog
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
L = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
KEY = 'ligne_double/reglages'


def bbox(path):
    return tuple(round(v, 6) for v in path.bbox())


def near(path, q, tol=1e-6):
    return any(math.dist(p, q) < tol for c in path.contours for p in c.flatten(0.01))


class CoreCorners(unittest.TestCase):
    def test_sharp_is_the_default(self):
        p = double_line(L, 2)
        self.assertTrue(near(p, (11, -1)))
        self.assertTrue(near(p, (9, 1)))

    def test_chamfer(self):
        p = double_line(L, 2, corners='chanfrein')
        self.assertFalse(near(p, (11, -1), 0.01))
        self.assertTrue(near(p, (10, -1)))
        self.assertTrue(near(p, (11, 0)))
        self.assertTrue(near(p, (9, 1)))                    # l'angle rentrant reste un angle

    def test_round(self):
        p = double_line(L, 2, corners='arrondi')
        self.assertFalse(near(p, (11, -1), 0.01))
        self.assertTrue(near(p, (10 + math.cos(math.radians(45)), -math.sin(math.radians(45))), 0.01))
        outer = [q for c in p.contours for q in c.flatten(0.01) if q[0] > 10.0 and q[1] < 0.0]
        self.assertGreater(len(outer), 10)
        for q in outer:
            self.assertAlmostEqual(math.dist(q, (10.0, 0.0)), 1.0, places=6)
        self.assertTrue(near(p, (9, 1)))

    def test_closed_loop(self):
        sq = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        sharp = double_line(sq, 2, closed=True)
        for corners in ('chanfrein', 'arrondi'):
            p = double_line(sq, 2, closed=True, corners=corners)
            self.assertEqual(len(p.contours), 2)
            self.assertTrue(all(c.closed for c in p.contours))
            self.assertEqual(bbox(p), bbox(sharp))
            self.assertFalse(near(p, (11, -1), 0.01))
            self.assertTrue(near(p, (9, 1)))                # le contour intérieur ne change pas

    def test_closed_ends_with_round_corners(self):
        p = double_line(L, 2, ends='ferme', corners='arrondi')
        self.assertEqual(len(p.contours), 1)
        self.assertTrue(p.contours[0].closed)
        self.assertFalse(near(p, (11, -1), 0.01))


class CoreSides(unittest.TestCase):
    def test_each_side_its_distance(self):
        p = double_line(L, 0, left=1.0, right=3.0)
        self.assertEqual(len(p.contours), 2)
        self.assertEqual(bbox(p), (0, -3, 13, 10))
        self.assertTrue(near(p, (0, 1)))
        self.assertTrue(near(p, (0, -3)))
        self.assertTrue(near(p, (9, 1)))
        self.assertTrue(near(p, (13, -3)))

    def test_one_side_on_the_axis(self):
        p = double_line(L, 0, left=2.0, right=0.0)
        self.assertEqual(bbox(p), bbox(double_line(L, 2, 'gauche')))
        self.assertTrue(near(p, (0, 0)))
        self.assertTrue(near(p, (10, 0)))
        self.assertEqual(len(p.contours), 2)

    def test_nothing_to_draw(self):
        self.assertEqual(double_line(L, 0, left=0.0, right=0.0).contours, [])
        self.assertEqual(double_line(L, 5, left=-1.0, right=-2.0).contours, [])

    def test_flat_ends_unequal(self):
        p = double_line([(0.0, 0.0), (10.0, 0.0)], 0, ends='ferme', left=1.0, right=3.0)
        self.assertEqual(len(p.contours), 1)
        self.assertTrue(p.contours[0].closed)
        self.assertEqual(bbox(p), (0, -3, 10, 1))
        self.assertAlmostEqual(abs(p.contours[0].signed_area()), 40.0, places=6)

    def test_round_ends_unequal(self):
        p = double_line([(0.0, 0.0), (10.0, 0.0)], 0, ends='arrondi', left=1.0, right=3.0)
        self.assertEqual(len(p.contours), 1)
        b = bbox(p)
        self.assertAlmostEqual(b[0], -2.0, places=2)
        self.assertAlmostEqual(b[2], 12.0, places=2)
        self.assertAlmostEqual(b[1], -3.0, places=6)
        self.assertAlmostEqual(b[3], 1.0, places=6)
        # le rond est centré entre les deux traits, des deux côtés, quel que soit le sens
        self.assertTrue(near(p, (-2.0, -1.0), 0.02))
        self.assertTrue(near(p, (12.0, -1.0), 0.02))

    def test_round_ends_unequal_going_up(self):
        p = double_line([(0.0, 0.0), (0.0, 10.0)], 0, ends='arrondi', left=1.0, right=3.0)
        self.assertTrue(near(p, (1.0, -2.0), 0.02))
        self.assertTrue(near(p, (1.0, 12.0), 0.02))

    def test_equal_sides_same_as_width(self):
        self.assertEqual(bbox(double_line(L, 0, left=1.0, right=1.0)), bbox(double_line(L, 2)))

    def test_round_ends_are_not_coarse(self):
        r = double_line([(0.0, 0.0), (10.0, 0.0)], 2, ends='arrondi')
        worst = max(abs(math.dist(q, (10.0, 0.0)) - 1.0) for q in r.contours[0].flatten(0.01) if q[0] > 10.0)
        self.assertLess(worst, 1e-6)
        self.assertGreater(sum(1 for q in r.contours[0].flatten(0.01) if q[0] > 10.0), 30)

    def test_sides_of(self):
        self.assertEqual(sides_of({'left': 1.0, 'right': 2.0}), (1.0, 2.0))
        self.assertEqual(sides_of({'left': 1.0}), (1.0, 0.0))
        self.assertEqual(sides_of({'width': 4.0, 'justify': 'centre'}), (2.0, 2.0))
        self.assertEqual(sides_of({'width': 4.0, 'justify': 'gauche'}), (4.0, 0.0))
        self.assertEqual(sides_of({'width': 4.0, 'justify': 'droite'}), (0.0, 4.0))
        self.assertEqual(sides_of({}), (1.0, 1.0))


class Dialog(unittest.TestCase):
    def test_old_settings_become_sides(self):
        d = DoubleLineDialog(None, {'width': 4.0, 'justify': 'gauche', 'ends': 'ferme'})
        v = d.values()
        self.assertEqual((v['left'], v['right'], v['ends'], v['corners']), (4.0, 0.0, 'ferme', 'aigu'))

    def test_values(self):
        d = DoubleLineDialog(None, {'left': 1.5, 'right': 0.5, 'corners': 'arrondi', 'ends': 'arrondi'})
        self.assertEqual(d.values(), {'left': 1.5, 'right': 0.5, 'corners': 'arrondi', 'ends': 'arrondi'})

    def test_two_zero_sides_cannot_be_accepted(self):
        d = DoubleLineDialog(None, {'left': 1.0, 'right': 0.0})
        self.assertTrue(d.ok.isEnabled())
        d.left.setValue(0.0)
        self.assertFalse(d.ok.isEnabled())
        d.right.setValue(2.0)
        self.assertTrue(d.ok.isEnabled())


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
        self.win.canvas.dline = None
        self.win.set_tool('select')
        self.asked = []
        self.answer = {'left': 1.0, 'right': 2.0, 'corners': 'chanfrein', 'ends': 'ouvert'}

        def dialog(cur):
            self.asked.append(cur)
            return self.answer
        self.win.dline_dialog = dialog

    def tearDown(self):
        del self.win.dline_dialog
        self.win.settings.remove(KEY)

    def shapes(self):
        return [i for i in self.doc.iter_items() if isinstance(i, Shape)]

    def test_first_use_asks_then_keeps(self):
        self.win.set_tool('dline')
        self.assertEqual(len(self.asked), 1)
        self.assertIsInstance(self.win.canvas.tool_obj, T.DoubleLineTool)
        self.win.set_tool('select')
        self.win.set_tool('dline')
        self.assertEqual(len(self.asked), 1)
        self.assertEqual(self.win.canvas.dline, self.answer)

    def test_ctrl_click_asks_with_the_last_settings(self):
        self.win.set_tool('dline')
        self.win.set_tool('select')
        with mock.patch.object(MainWindow, '_ctrl_held', staticmethod(lambda: True)):
            self.win.A['tool_dline'].trigger()              # comme un clic sur le bouton
        self.assertEqual(len(self.asked), 2)
        self.assertEqual(self.asked[1], self.answer)

    def test_cancel_goes_back_to_select(self):
        self.answer = None
        self.win.set_tool('dline')
        self.assertTrue(self.win.A['tool_select'].isChecked())
        self.assertIsNone(self.win.settings.value(KEY))

    def test_settings_survive_a_restart(self):
        self.win.set_tool('dline')
        self.win.set_tool('select')
        self.assertEqual(json.loads(self.win.settings.value(KEY)), self.answer)
        self.win.canvas.dline = None
        self.win.set_tool('dline')
        self.assertEqual(len(self.asked), 1)
        self.assertEqual(self.win.canvas.dline, self.answer)

    def test_broken_setting_asks(self):
        self.win.settings.setValue(KEY, '{pas du json')
        self.win.set_tool('dline')
        self.assertEqual(self.asked, [{}])
        self.win.set_tool('select')
        self.win.canvas.dline = None
        self.win.settings.setValue(KEY, '[1, 2]')
        self.win.set_tool('dline')
        self.assertEqual(self.asked, [{}, {}])

    def test_tool_draws_with_the_settings(self):
        self.win.set_tool('dline')
        t = self.win.canvas.tool_obj
        for q in L:
            t.press(QPointF(0, 0), q, None)
        t.double(QPointF(0, 0), L[-1], None)
        s = self.shapes()[0]
        self.assertEqual(len(s.path.contours), 2)
        self.assertEqual(bbox(s.path), (0, -2, 12, 10))
        self.assertFalse(near(s.path, (12, -2), 0.01))      # chanfrein
        self.assertTrue(near(s.path, (0, 1)))
        self.assertTrue(near(s.path, (0, -2)))

    def test_old_settings_still_draw(self):
        self.win.canvas.dline = {'width': 4.0, 'justify': 'centre', 'ends': 'ferme'}
        self.win.set_tool('dline')
        self.assertEqual(self.asked, [])
        t = self.win.canvas.tool_obj
        for q in L:
            t.press(QPointF(0, 0), q, None)
        t.double(QPointF(0, 0), L[-1], None)
        s = self.shapes()[0]
        self.assertEqual(len(s.path.contours), 1)
        self.assertEqual(bbox(s.path), (0, -2, 12, 10))


if __name__ == '__main__':
    unittest.main()
