"""Round 799 : coins réglables (d'après VectorCraft)."""
import json
import math
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from vectordrive.core import corners as CO
from vectordrive.core.document import Shape
from vectordrive.core.geom import Affine, Conic, Contour, Cubic, Line, Path, arc_conics, circle, polyline, rect
from vectordrive.io import native

app = QApplication.instance() or QApplication([])


def square(a=20.0):
    return Path([polyline([(0, 0), (a, 0), (a, a), (0, a)], True)])


def area(path):
    return abs(sum(c.signed_area(1e-7) for c in path.contours))


def all_radii(path, r):
    return {c.key: r for c in CO.path_corners(path)}


def continuous(contour):
    segs = contour.segments
    for a, b in zip(segs, segs[1:] + (segs[:1] if contour.closed else [])):
        if math.dist(a.end, b.start) > 1e-9:
            return False
    return True


class Corners(unittest.TestCase):
    def test_square_has_four_right_angles(self):
        cs = CO.path_corners(square())
        self.assertEqual([c.key for c in cs], ['0:0', '0:1', '0:2', '0:3'])
        for c in cs:
            self.assertAlmostEqual(c.angle_deg(), 90.0)
            self.assertAlmostEqual(c.setback(2.0), 2.0)
            self.assertAlmostEqual(c.max_radius(), 10.0)

    def test_open_line_has_no_corner_at_its_ends(self):
        p = Path([polyline([(0, 0), (10, 0), (10, 10)], False)])
        self.assertEqual([c.key for c in CO.path_corners(p)], ['0:1'])

    def test_smooth_joints_are_no_corners(self):
        self.assertEqual(CO.path_corners(Path([circle((0, 0), 10)])), [])
        straight = Path([polyline([(0, 0), (10, 0), (20, 0.01)], False)])
        self.assertEqual(CO.path_corners(straight), [])
        back = Path([polyline([(0, 0), (10, 0), (0, 0)], False)])
        self.assertEqual(CO.path_corners(back), [])

    def test_acute_and_obtuse(self):
        tri = Path([polyline([(0, 0), (40, 0), (20, 10)], True)])
        for c in CO.path_corners(tri):
            r = c.max_radius()
            self.assertAlmostEqual(c.setback(r), min(c.lu, c.lv) / 2.0)
            self.assertAlmostEqual(c.fitted(r * 10), r)
            self.assertEqual(c.fitted(-1.0), 0.0)
            self.assertEqual(c.fitted(float('nan')), 0.0)

    def test_widget_moves_with_the_drag_along_the_bisector(self):
        c = CO.path_corners(square())[0]                        # coin (0, 0) : le centre va en (r, r)
        self.assertAlmostEqual(c.radius_change(1.0, 1.0), 1.0)
        self.assertAlmostEqual(c.radius_change(1.0, -1.0), 0.0)
        self.assertEqual(c.on_bisector(2.0), (2.0, 2.0))


class Cuts(unittest.TestCase):
    def test_round_is_a_true_arc(self):
        base = square()
        out = CO.cut(base, all_radii(base, 3.0))
        contour = out.contours[0]
        self.assertTrue(contour.closed)
        self.assertTrue(continuous(contour))
        conics = [s for s in contour.segments if isinstance(s, Conic)]
        self.assertEqual(len(conics), 4)
        for s in conics:
            params = s.circle_params()
            self.assertIsNotNone(params)
            self.assertAlmostEqual(params[1], 3.0, places=6)
        self.assertAlmostEqual(area(out), 400 - (4 - math.pi) * 9, places=4)

    def test_each_corner_its_own_radius(self):
        base = square()
        out = CO.cut(base, {'0:0': 2.0, '0:2': 5.0})
        self.assertAlmostEqual(area(out), 400 - (4 - math.pi) * (4 + 25) / 4, places=4)
        self.assertEqual(sum(isinstance(s, Conic) for s in out.contours[0].segments), 2)
        self.assertEqual(out.bbox(), (0, 0, 20, 20))

    def test_first_node_cut_closes_the_contour(self):
        out = CO.cut(square(), {'0:0': 2.0})
        c = out.contours[0]
        self.assertTrue(continuous(c))
        self.assertIsInstance(c.segments[-1], Conic)
        self.assertAlmostEqual(c.segments[0].start[0], 2.0)

    def test_chamfer(self):
        base = square()
        out = CO.cut(base, all_radii(base, 2.0), {c.key: CO.CHAMFER for c in CO.path_corners(base)})
        self.assertAlmostEqual(area(out), 400 - 4 * 2, places=6)
        self.assertTrue(all(isinstance(s, Line) for s in out.contours[0].segments))

    def test_inverted_is_an_arc_about_the_corner(self):
        base = square()
        out = CO.cut(base, {'0:0': 3.0}, {'0:0': CO.INVERTED})
        arc = next(s for s in out.contours[0].segments if isinstance(s, Conic))
        (cx, cy), r, *_ = arc.circle_params()
        self.assertAlmostEqual(cx, 0.0, places=5)
        self.assertAlmostEqual(cy, 0.0, places=5)
        self.assertAlmostEqual(r, 3.0, places=5)
        self.assertAlmostEqual(area(out), 400 - math.pi * 9 / 4, places=3)

    def test_too_large_is_brought_back(self):
        base = square()
        out = CO.cut(base, all_radii(base, 500.0))
        self.assertEqual(sum(isinstance(s, Line) for s in out.contours[0].segments), 0)  # les côtés ont disparu
        self.assertAlmostEqual(area(out), math.pi * 100, places=3)
        self.assertTrue(continuous(out.contours[0]))

    def test_open_contour_keeps_its_ends(self):
        base = Path([polyline([(0, 0), (10, 0), (10, 10)], False)])
        out = CO.cut(base, {'0:1': 2.0})
        c = out.contours[0]
        self.assertFalse(c.closed)
        self.assertEqual(c.start, (0, 0))
        self.assertEqual(c.end, (10, 10))
        self.assertEqual(len(c.segments), 3)

    def test_curved_side_is_trimmed(self):
        arc = arc_conics((0, 0), 20, 20, 0, 90)                 # de (20, 0) à (0, 20)
        c = Contour([Line((0, 0), (20, 0))] + list(arc) + [Line((0, 20), (0, 0))], True)
        base = Path([c])
        keys = {x.key: x for x in CO.path_corners(base)}
        self.assertEqual(len(keys), 3)
        out = CO.cut(base, {'0:1': 2.0})
        got = out.contours[0]
        self.assertTrue(continuous(got))
        self.assertLess(area(out), area(base))
        self.assertGreater(area(out), area(base) - 4)
        # ce qui reste de l'arc est toujours sur le cercle
        rest = next(s for s in got.segments if isinstance(s, Conic) and abs(s.w - math.sqrt(0.5)) > 1e-6 and
                    abs(math.hypot(*s.end) - 20) < 1e-6 and s.end[1] > 15)
        for t in (0.25, 0.5, 0.75):
            self.assertAlmostEqual(math.hypot(*rest.point(t)), 20.0, places=4)

    def test_cubic_side(self):
        c = Contour([Line((0, 0), (20, 0)), Cubic((20, 0), (25, 10), (15, 20), (0, 20)), Line((0, 20), (0, 0))], True)
        base = Path([c])
        out = CO.cut(base, all_radii(base, 1.5))
        self.assertTrue(continuous(out.contours[0]))
        self.assertLess(area(out), area(base))
        for s in out.contours[0].segments:
            x0, y0, x1, y1 = s.bbox()
            self.assertGreater(x0, -1e-6)
            self.assertGreater(y0, -1e-6)
            self.assertLess(x1, 25)
            self.assertLess(y1, 20 + 1e-6)

    def test_several_contours_keep_their_own_keys(self):
        base = Path(square().contours + [polyline([(5, 5), (15, 5), (10, 15)], True)])
        self.assertEqual(len(CO.path_corners(base)), 7)
        out = CO.cut(base, {'1:1': 1.0})
        self.assertEqual(len(out.contours[0].segments), 4)
        self.assertEqual(len(out.contours[1].segments), 4)

    def test_no_radius_returns_the_same_contours(self):
        base = square()
        self.assertIs(CO.cut(base, {}).contours[0], base.contours[0])


class Live(unittest.TestCase):
    def shape(self):
        s = Shape(path=square(), name='s')
        path, data = CO.settings(s.path, {'0:0': 3.0, '0:1': 1.0}, {'0:1': CO.CHAMFER})
        s.path = path
        s.extra[CO.KEY] = data
        return s

    def test_comes_back(self):
        s = self.shape()
        base, radii, kinds = CO.live_of(s)
        self.assertEqual(len(base.contours[0].segments), 4)
        self.assertEqual(radii, {'0:0': 3.0, '0:1': 1.0})
        self.assertEqual(kinds, {'0:1': CO.CHAMFER})

    def test_nothing_kept_at_zero(self):
        path, data = CO.settings(square(), {'0:0': 0.0}, {'0:0': CO.CHAMFER})
        self.assertIsNone(data)
        self.assertEqual(len(path.contours[0].segments), 4)

    def test_edited_otherwise_is_forgotten(self):
        s = self.shape()
        s.path = Path([polyline([(0, 0), (30, 0), (30, 30)], True)])
        base, radii, _ = CO.live_of(s)
        self.assertIs(base, s.path)
        self.assertEqual(radii, {})

    def test_moved_rotated_mirrored_keep_following(self):
        for m in (Affine.translation(50, 7), Affine.rotation(30, (3, 4)), Affine.mirror_x(5.0),
                  Affine.scaling(2.0) @ Affine.translation(1, 1)):
            with self.subTest(m.to_tuple()):
                s = self.shape().transformed(m)
                base, radii, kinds = CO.live_of(s)
                k = math.hypot(m.a, m.b)
                self.assertAlmostEqual(radii['0:0'], 3.0 * k)
                self.assertEqual(kinds, {'0:1': CO.CHAMFER})
                redo = CO.cut(base, radii, kinds)
                self.assertAlmostEqual(area(redo), area(s.path), places=4)
                for a, b in zip(redo.bbox(), s.path.bbox()):
                    self.assertAlmostEqual(a, b, places=6)

    def test_stretched_is_no_longer_live(self):
        s = self.shape().transformed(Affine.scaling(2.0, 1.0))
        self.assertNotIn(CO.KEY, s.extra)
        self.assertEqual(CO.live_of(s)[1], {})

    def test_identity_changes_nothing(self):
        s = self.shape()
        self.assertIs(s.transformed(Affine.translation(0, 0)).extra[CO.KEY], s.extra[CO.KEY])

    def test_original_is_not_touched_by_a_transform(self):
        s = self.shape()
        was = json.dumps(s.extra[CO.KEY])
        s.transformed(Affine.translation(5, 5))
        self.assertEqual(json.dumps(s.extra[CO.KEY]), was)

    def test_saved_in_the_file(self):
        from vectordrive.core.document import Document
        doc = Document()
        doc.add(self.shape())
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'c.vdz'
            native.write(doc, p)
            back = native.read(p).layers[0].items[0]
        self.assertEqual(CO.live_of(back)[1], {'0:0': 3.0, '0:1': 1.0})


class Event:
    def __init__(self, mods=Qt.KeyboardModifier.NoModifier, key=None):
        self._mods, self._key = mods, key

    def modifiers(self):
        return self._mods

    def key(self):
        return self._key


class Tool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.c = self.win.canvas
        self.doc = self.c.doc
        self.doc.layers[0].items = []
        self.c.selection = []
        self.win._undo.clear()
        self.win.resize(1200, 800)
        self.win.show()
        app.processEvents()
        self.shape = Shape(path=square(100.0), name='s')
        self.doc.add(self.shape)
        self.c.select([self.shape])
        self.win.set_tool('corners')
        self.c.fit((-20, -20, 120, 120))
        self.tool = self.c.tool_obj
        self.addCleanup(self.win.set_tool, 'select')

    def press_widget(self, index=0, ev=None):
        w = self.tool.widgets()[index]
        self.tool.press(w[4], self.c.to_doc(w[4]), ev)
        return w

    def drag_by(self, w, dx, dy, ev=None):
        """Tire la poignée `w`, déjà prise, de (dx, dy) en mm."""
        a = self.c.to_doc(w[4])
        b = (a[0] + dx, a[1] + dy)
        sp = self.c.to_screen(*b)
        self.tool.move(sp, b, ev)
        self.tool.release(sp, b, ev)

    def test_is_a_corner_tool(self):
        from vectordrive.ui.tools import CornerTool
        self.assertIsInstance(self.tool, CornerTool)
        self.assertEqual(len(self.tool.widgets()), 4)

    def test_widget_found_by_position(self):
        w = self.tool.widgets()[2]
        self.assertIs(self.tool.widget_at(w[4])[1], w[1])
        self.assertIsNone(self.tool.widget_at(QPointF(w[4].x() + 200, w[4].y() + 200)))

    def test_drag_rounds_every_corner_of_the_shape(self):
        w = self.press_widget(0)
        undo = len(self.win._undo)
        self.drag_by(w, 5.0, 5.0)
        self.assertEqual(len(self.win._undo), undo + 1)
        radii = CO.live_of(self.shape)[1]
        self.assertEqual(len(radii), 4)
        r = next(iter(radii.values()))
        self.assertAlmostEqual(r, w[2] + 5.0, places=3)
        self.assertAlmostEqual(area(self.shape.path), 10000 - (4 - math.pi) * r * r, places=2)
        self.assertEqual(self.tool.preview_paths, [])

    def test_preview_changes_nothing_until_release(self):
        w = self.press_widget(0)
        a = self.c.to_doc(w[4])
        b = (a[0] + 5, a[1] + 5)
        self.tool.move(self.c.to_screen(*b), b, None)
        self.assertEqual(len(self.tool.preview_paths), 1)
        self.assertEqual(len(self.shape.path.contours[0].segments), 4)

    def test_undo_brings_the_corners_back(self):
        w = self.press_widget(0)
        self.drag_by(w, 5.0, 5.0)
        self.win.undo()
        s = self.doc.layers[0].items[0]
        self.assertEqual(len(s.path.contours[0].segments), 4)
        self.assertNotIn(CO.KEY, s.extra)

    def test_click_then_drag_touches_only_the_picked_corner(self):
        w = self.press_widget(1)
        self.tool.release(w[4], self.c.to_doc(w[4]), None)
        self.assertEqual(self.tool.picked, {(id(self.shape), w[1].key)})
        self.assertEqual(self.win._undo, [])                           # un clic ne change rien
        w = self.press_widget(1)
        c = w[1]
        self.drag_by(w, (c.u[0] + c.v[0]) * 4, (c.u[1] + c.v[1]) * 4)
        self.assertEqual(list(CO.live_of(self.shape)[1]), [c.key])

    def test_drag_of_another_corner_than_the_picked_one(self):
        w = self.press_widget(0)
        self.tool.release(w[4], self.c.to_doc(w[4]), None)
        w2 = self.press_widget(2)
        c = w2[1]
        self.drag_by(w2, (c.u[0] + c.v[0]) * 3, (c.u[1] + c.v[1]) * 3)
        self.assertEqual(list(CO.live_of(self.shape)[1]), [c.key])

    def test_ctrl_click_adds_and_removes(self):
        ctrl = Event(Qt.KeyboardModifier.ControlModifier)
        for i in (0, 2):
            w = self.press_widget(i, ctrl)
            self.tool.release(w[4], self.c.to_doc(w[4]), ctrl)
        self.assertEqual(len(self.tool.picked), 2)
        w = self.press_widget(0, ctrl)
        self.tool.release(w[4], self.c.to_doc(w[4]), ctrl)
        self.assertEqual(len(self.tool.picked), 1)

    def test_alt_click_cycles_the_kind(self):
        self.tool.set_radius(5.0)
        alt = Event(Qt.KeyboardModifier.AltModifier)
        self.press_widget(0, alt)
        kinds = CO.live_of(self.shape)[2]
        self.assertEqual(set(kinds.values()), {CO.INVERTED})
        self.press_widget(0, alt)
        self.assertEqual(set(CO.live_of(self.shape)[2].values()), {CO.CHAMFER})
        self.press_widget(0, alt)
        self.assertEqual(CO.live_of(self.shape)[2], {})

    def test_shift_goes_by_half_millimetres(self):
        w = self.press_widget(0)
        self.drag_by(w, 3.3, 3.3, Event(Qt.KeyboardModifier.ShiftModifier))
        r = next(iter(CO.live_of(self.shape)[1].values()))
        self.assertAlmostEqual(r * 2, round(r * 2), places=6)

    def test_double_click_asks_the_radius(self):
        w = self.tool.widgets()[0]
        with mock.patch('PySide6.QtWidgets.QInputDialog.getDouble', return_value=(7.5, True)):
            self.tool.double(w[4], self.c.to_doc(w[4]), None)
        self.assertEqual(set(CO.live_of(self.shape)[1].values()), {7.5})

    def test_double_click_cancelled(self):
        w = self.tool.widgets()[0]
        with mock.patch('PySide6.QtWidgets.QInputDialog.getDouble', return_value=(7.5, False)):
            self.tool.double(w[4], self.c.to_doc(w[4]), None)
        self.assertEqual(self.win._undo, [])

    def test_delete_makes_it_sharp_again(self):
        self.tool.set_radius(5.0)
        self.assertTrue(self.tool.wants_key(Event(key=Qt.Key.Key_Delete)))
        self.assertTrue(self.tool.key(Event(key=Qt.Key.Key_Delete)))
        self.assertEqual(len(self.shape.path.contours[0].segments), 4)
        self.assertNotIn(CO.KEY, self.shape.extra)

    def test_escape_clears_the_picked_corners(self):
        w = self.press_widget(0)
        self.tool.release(w[4], self.c.to_doc(w[4]), None)
        self.assertTrue(self.tool.key(Event(key=Qt.Key.Key_Escape)))
        self.assertEqual(self.tool.picked, set())
        self.assertFalse(self.tool.key(Event(key=Qt.Key.Key_Escape)))

    def test_radius_is_kept_when_coming_back(self):
        self.tool.set_radius(5.0)
        self.assertEqual(len(self.tool.widgets()), 4)                  # toujours quatre coins, ceux de la forme d'avant
        w = self.press_widget(0)
        self.assertAlmostEqual(w[2], 5.0)
        self.drag_by(w, 1.0, 1.0)
        self.assertAlmostEqual(next(iter(CO.live_of(self.shape)[1].values())), 6.0, places=3)

    def test_click_outside_selects_what_is_under(self):
        other = Shape(path=square(10.0).transformed(Affine.translation(300, 0)), name='o')
        self.doc.add(other)
        at = self.c.to_screen(600, 600)
        self.tool.press(at, (600, 600), None)
        self.assertEqual(self.c.selection, [])
        self.assertEqual(self.tool.widgets(), [])

    def test_small_sides_have_no_widget(self):
        self.shape.path = square(0.0001)
        self.tool._memo.clear()
        self.assertEqual(self.tool.widgets(), [])

    def test_volumes_and_text_are_left_out(self):
        from vectordrive.core import solids as SO
        if not SO.available():
            self.skipTest('manifold3d absent')
        v = SO.make_shape(SO.box(0, 0, 0, 50, 50, 5))
        self.doc.add(v)
        self.c.select([v])
        self.assertEqual(self.tool.shapes(), [])

    def test_exports_see_a_plain_path(self):
        self.tool.set_radius(5.0)
        self.assertTrue(any(isinstance(s, Conic) for s in self.shape.path.contours[0].segments))
        self.assertAlmostEqual(self.shape.path.bbox()[2], 100.0)

    def test_paint_does_not_fail(self):
        from PySide6.QtGui import QImage, QPainter
        w = self.press_widget(0)
        a = self.c.to_doc(w[4])
        b = (a[0] + 5, a[1] + 5)
        self.tool.move(self.c.to_screen(*b), b, None)
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        self.tool.paint(p)
        p.end()
        self.tool.cancel()

    def test_ribbon(self):
        action = self.win.A['tool_corners']
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups()
                 for b in g.buttons() if b.defaultAction() is action]
        self.assertEqual(len(found), 1)
        self.assertEqual(action.text(), 'Coins réglables')


if __name__ == '__main__':
    unittest.main()
