"""Round 827 : Étendre en arc : le point à atteindre se choisit."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core import trim as TR
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Contour, Cubic, Line, Path
from vectordrive.ui import shortcuts as S
from vectordrive.ui import tools as T
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
BOX = geom.rect(-20.0, -5.0, 15.0, 10.0)              # à gauche, le cercle de rayon 10 la coupe à y = 5 puis y = -5
X = math.sqrt(100.0 - 25.0)


def quarter():
    return geom.arc((0.0, 0.0), 10.0, 0.0, 90.0)      # de (10, 0) à (0, 10), sens trigonométrique


def all_on_circle(c, r=10.0, tol=1e-3):
    return all(abs(math.hypot(*q) - r) < tol for q in c.flatten(0.01))


class Targets(unittest.TestCase):
    def test_both_crossings_in_order(self):
        a = TR.arc_targets(Path([quarter()]), list(BOX.segments), (0.0, 10.0))
        self.assertEqual(len(a.targets), 2)
        self.assertLess(a.targets[0][0], a.targets[1][0])
        self.assertAlmostEqual(a.targets[0][1][0], -X, places=2)
        self.assertAlmostEqual(a.targets[0][1][1], 5.0, places=2)
        self.assertAlmostEqual(a.targets[1][1][0], -X, places=2)
        self.assertAlmostEqual(a.targets[1][1][1], -5.0, places=2)

    def test_extend_to_the_second(self):
        p = Path([quarter()])
        a = TR.arc_targets(p, list(BOX.segments), (0.0, 10.0))
        out = a.extended(p, 1)
        c = out.contours[0]
        self.assertFalse(c.closed)
        self.assertTrue(all_on_circle(c))
        self.assertAlmostEqual(c.start[0], 10.0)
        self.assertAlmostEqual(c.end[0], -X, places=2)
        self.assertAlmostEqual(c.end[1], -5.0, places=2)
        # l'arc n'a pas fait le tour par l'autre côté : il est passé par (-10, 0), pas par (0, -10)
        pts = c.flatten(0.01)
        self.assertLess(min(q[0] for q in pts), -9.99)
        self.assertGreater(min(q[1] for q in pts), -5.01)

    def test_from_the_start_goes_the_other_way(self):
        p = Path([quarter()])
        a = TR.arc_targets(p, list(BOX.segments), (10.0, 0.0))
        self.assertAlmostEqual(a.targets[0][1][1], -5.0, places=2)
        self.assertAlmostEqual(a.targets[1][1][1], 5.0, places=2)
        c = a.extended(p, 0).contours[0]
        self.assertAlmostEqual(c.end[1], 10.0)
        self.assertAlmostEqual(c.start[1], -5.0, places=2)
        self.assertTrue(all_on_circle(c))
        self.assertLess(min(q[1] for q in c.flatten(0.01)), -9.99)       # passé par (0, -10)

    def test_extension_is_drawn_from_the_end(self):
        a = TR.arc_targets(Path([quarter()]), list(BOX.segments), (10.0, 0.0))
        e = a.extension(0)
        self.assertAlmostEqual(e.start[0], 10.0)
        self.assertAlmostEqual(e.end[1], -5.0, places=2)

    def test_first_is_the_old_behaviour(self):
        out = TR.extend_arc(Path([quarter()]), list(BOX.segments), (0.0, 10.0))
        self.assertAlmostEqual(out.contours[0].end[1], 5.0, places=2)

    def test_not_an_arc(self):
        self.assertIsNone(TR.arc_targets(Path([geom.polyline([(0.0, 0.0), (10.0, 0.0)])]), [], (10.0, 0.0)))
        self.assertIsNone(TR.arc_targets(Path([geom.circle((0.0, 0.0), 10.0)]), [], (10.0, 0.0)))
        self.assertIsNone(TR.arc_targets(Path([]), [], (0.0, 0.0)))
        wavy = Contour([Cubic((0.0, 0.0), (5.0, 20.0), (10.0, -20.0), (15.0, 0.0))], False)
        self.assertIsNone(TR.arc_targets(Path([wavy]), [], (15.0, 0.0)))
        straight = Contour([Cubic((0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (15.0, 0.0))], False)
        self.assertIsNone(TR.arc_targets(Path([straight]), [], (15.0, 0.0)))

    def test_nothing_on_the_circle(self):
        a = TR.arc_targets(Path([quarter()]), list(geom.rect(100.0, 100.0, 5.0, 5.0).segments), (0.0, 10.0))
        self.assertEqual(a.targets, [])
        self.assertIsNone(TR.extend_arc(Path([quarter()]), [], (0.0, 10.0)))

    def test_cubic_arc_of_an_imported_file(self):
        k = 0.5522847498 * 10.0
        c = Contour([Cubic((10.0, 0.0), (10.0, k), (k, 10.0), (0.0, 10.0))], False)
        p = Path([c])
        a = TR.arc_targets(p, list(BOX.segments), (0.0, 10.0))
        self.assertEqual(len(a.targets), 2)
        self.assertAlmostEqual(a.targets[1][1][1], -5.0, places=1)
        out = a.extended(p, 1).contours[0]
        self.assertFalse(out.closed)
        self.assertAlmostEqual(out.end[1], -5.0, places=1)
        self.assertTrue(all_on_circle(out, tol=0.01))

    def test_big_arc_in_several_segments_does_not_hit_itself(self):
        big = geom.arc((0.0, 0.0), 10.0, 0.0, 200.0)        # plusieurs coniques
        self.assertGreater(len(big.segments), 1)
        a = TR.arc_targets(Path([big]), [], (big.end[0], big.end[1]))
        self.assertEqual(a.targets, [])
        self.assertAlmostEqual(a.room, 160.0, places=3)
        wall = geom.polyline([(0.0, -20.0), (0.0, 0.0)])
        a = TR.arc_targets(Path([big]), list(wall.segments), (big.end[0], big.end[1]))
        self.assertEqual(len(a.targets), 1)
        self.assertAlmostEqual(a.targets[0][1][1], -10.0, places=2)

    def test_arc_after_a_line(self):
        """Le bout est un arc, le début du contour une droite : elle n'est pas prise pour l'arc."""
        c = Contour([Line((30.0, 0.0), (10.0, 0.0))] + list(quarter().segments), False)
        p = Path([c])
        a = TR.arc_targets(p, list(BOX.segments), (0.0, 10.0))
        self.assertEqual(len(a.targets), 2)
        out = a.extended(p, 0).contours[0]
        self.assertEqual(out.start, (30.0, 0.0))
        self.assertAlmostEqual(out.end[1], 5.0, places=2)

    def test_own_other_contour_is_a_target(self):
        p = Path([quarter(), geom.polyline([(-20.0, 0.0), (-5.0, 0.0)])])
        a = TR.arc_targets(p, [], (0.0, 10.0))
        self.assertEqual(len(a.targets), 1)
        self.assertAlmostEqual(a.targets[0][1][0], -10.0, places=2)
        self.assertEqual(len(a.extended(p, 0).contours), 2)

    def test_segment_circle(self):
        (c, r, sweep) = TR.segment_circle(quarter().segments[0])
        self.assertAlmostEqual(r, 10.0)
        self.assertAlmostEqual(sweep, 90.0)
        self.assertIsNone(TR.segment_circle(Line((0.0, 0.0), (1.0, 0.0))))
        k = 0.5522847498 * 10.0
        (c, r, sweep) = TR.segment_circle(Cubic((10.0, 0.0), (10.0, k), (k, 10.0), (0.0, 10.0)))
        self.assertAlmostEqual(sweep, 90.0, places=1)
        self.assertAlmostEqual(c[0], 0.0, places=1)
        (c, r, sweep) = TR.segment_circle(Cubic((0.0, 10.0), (k, 10.0), (10.0, k), (10.0, 0.0)))
        self.assertAlmostEqual(sweep, -90.0, places=1)


class Tool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        c = self.win.canvas
        self.doc = c.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=200.0, height=100.0, x=-100.0, y=-50.0)
        self.win._undo.clear()
        c.scale = 8.0
        self.said = []
        c.measured.connect(self.said.append)
        self.arc = Shape(path=Path([quarter()]))
        self.box = Shape(path=Path([BOX]))
        self.layer.items[:] = [self.arc, self.box]
        self.win.set_tool('extend_arc')
        self.t = c.tool_obj

    def tearDown(self):
        self.win.canvas.measured.disconnect(self.said.append)
        self.win.set_tool('select')

    def click(self, q):
        self.t.press(self.win.canvas.to_screen(*q), q, None)

    def test_tool_type(self):
        self.assertIsInstance(self.t, T.ExtendArcTool)

    def test_choose_the_second_point(self):
        self.click((0.0, 10.0))
        self.assertIsNotNone(self.t.reach)
        self.assertEqual(len(self.t.reach.targets), 2)
        self.assertIn('2', self.said[-1])
        self.t.move(QPointF(0, 0), (-8.0, -6.0), None)
        self.assertEqual(self.t.k, 1)
        self.t.move(QPointF(0, 0), (-8.0, 6.0), None)
        self.assertEqual(self.t.k, 0)
        self.click((-8.0, -6.0))
        c = self.arc.path.contours[0]
        self.assertAlmostEqual(c.end[1], -5.0, places=2)
        self.assertIsNone(self.t.reach)
        self.assertIs(self.win.canvas.tool_obj, self.t)     # l'outil reste actif

    def test_undo(self):
        self.click((0.0, 10.0))
        self.click((-8.0, 6.0))
        self.assertGreater(len(self.arc.path.contours[0].segments), 1)
        self.win.undo()
        arc = next(i for i in self.doc.iter_items() if isinstance(i, Shape) and not i.path.contours[0].closed)
        self.assertEqual(len(arc.path.contours[0].segments), len(quarter().segments))

    def test_a_line_is_refused(self):
        line = Shape(path=Path([geom.polyline([(30.0, 30.0), (40.0, 30.0)])]))
        self.layer.items.append(line)
        self.click((30.0, 30.0))
        self.assertIsNone(self.t.reach)
        self.assertEqual(self.said[-1], 'Le contour à étendre doit être un arc.')

    def test_nothing_under_the_pointer(self):
        self.click((60.0, 40.0))
        self.assertIsNone(self.t.reach)
        self.assertIn('arc de cercle', self.said[-1])

    def test_locked_is_refused(self):
        self.arc.locked = True
        self.click((0.0, 10.0))
        self.assertIsNone(self.t.reach)

    def test_nothing_on_this_circle(self):
        self.layer.items.remove(self.box)
        self.click((0.0, 10.0))
        self.assertIsNone(self.t.reach)
        self.assertIn('Rien', self.said[-1])

    def test_cancel(self):
        self.click((0.0, 10.0))
        self.t.cancel()
        self.assertIsNone(self.t.reach)
        self.assertEqual(len(self.arc.path.contours[0].segments), len(quarter().segments))

    def test_paint(self):
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        self.t.paint(p)
        self.click((0.0, 10.0))
        self.t.move(QPointF(0, 0), (-8.0, -6.0), None)
        self.t.paint(p)
        p.end()

    def test_typeedit_command(self):
        self.assertEqual(S.TE_ACTIONS['ID_COMPO_EXTEND_ARC'], 'tool_extend_arc')
        self.assertEqual(S.TE_ACTIONS['ID_COMPO_EXTEND'], 'tool_extend')

    def test_other_segments(self):
        c = self.win.canvas
        self.assertEqual(len(c.other_segments(self.arc)), len(BOX.segments))
        self.assertEqual(c.other_segments(self.arc, (100.0, 100.0, 110.0, 110.0)), [])


if __name__ == '__main__':
    unittest.main()
