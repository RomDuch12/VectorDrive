"""Round 820 : alignement comme TE : marges, objet par objet, premier sélectionné, premier point, espacement automatique."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from vectordrive.core import nodes as N
from vectordrive.core import text as TX
from vectordrive.core.document import Group, Layer, Plate, Shape, Text
from vectordrive.core.geom import Affine, Path, polyline, rect
from vectordrive.ui import shortcuts as S

app = QApplication.instance() or QApplication([])


def box(x, y, w, h):
    return Shape(path=Path([rect(x, y, w, h)]))


class Base(unittest.TestCase):
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
        self.doc = self.win.canvas.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=100.0, height=80.0)
        self.win._undo.clear()
        self.win.canvas.select([])

    def boxes(self, *specs):
        out = [box(*s) for s in specs]
        self.layer.items.extend(out)
        return out

    def now(self, it):
        return next(x for x in self.layer.items if x.id == it.id).bbox()


class Margins(Base):
    def test_each_object_goes_against_the_edge(self):
        a, b = self.boxes((30, 10, 5, 5), (50, 30, 5, 5))
        self.win.canvas.select([a, b])
        self.win.align_to_plate('left')
        self.assertAlmostEqual(self.now(a)[0], 0.0)
        self.assertAlmostEqual(self.now(b)[0], 0.0)
        self.assertAlmostEqual(self.now(a)[1], 10.0)
        self.assertAlmostEqual(self.now(b)[1], 30.0)

    def test_margin_is_used_not_the_edge(self):
        self.doc.plate = Plate(width=100.0, height=80.0, margins=[3.0, 4.0, 5.0, 6.0])
        a, b = self.boxes((30, 10, 5, 5), (50, 30, 8, 8))
        for edge, index, want in (('left', 0, 3.0), ('right', 2, 96.0), ('bottom', 1, 5.0), ('top', 3, 74.0)):
            self.win.canvas.select([x for x in self.layer.items])
            self.win.align_to_plate(edge)
            for x in self.layer.items:
                self.assertAlmostEqual(x.bbox()[index], want)

    def test_plate_offset(self):
        self.doc.plate = Plate(width=100.0, height=80.0, x=-50.0, y=-40.0)
        a, = self.boxes((30, 10, 5, 5))
        self.win.canvas.select([a])
        self.win.align_to_plate('right')
        self.assertAlmostEqual(self.now(a)[2], 50.0)

    def test_a_group_moves_as_one(self):
        g = Group(children=[box(30, 10, 5, 5), box(60, 10, 5, 5)])
        self.layer.items.append(g)
        self.win.canvas.select([g])
        self.win.align_to_plate('left')
        got = sorted(c.bbox()[0] for c in next(x for x in self.layer.items if x.id == g.id).children)
        self.assertAlmostEqual(got[0], 0.0)
        self.assertAlmostEqual(got[1], 30.0)

    def test_undo_in_one_step(self):
        a, b = self.boxes((30, 10, 5, 5), (50, 30, 5, 5))
        self.win.canvas.select([a, b])
        self.win.align_to_plate('left')
        self.assertEqual(len(self.win._undo), 1)
        self.win.undo()
        got = sorted(x.bbox()[0] for x in self.win.canvas.doc.layers[0].items)
        self.assertEqual(got, [30.0, 50.0])

    def test_already_there_pushes_no_undo(self):
        a, = self.boxes((0, 10, 5, 5))
        self.win.canvas.select([a])
        self.win.align_to_plate('left')
        self.assertEqual(len(self.win._undo), 0)

    def test_selection_keeps_its_order(self):
        a, b = self.boxes((30, 10, 5, 5), (50, 30, 5, 5))
        self.win.canvas.select([b, a])
        self.win.align_to_plate('top')
        self.assertEqual([x.id for x in self.win.canvas.selection], [b.id, a.id])

    def test_no_plate_says_so(self):
        self.doc.plate = None
        a, = self.boxes((30, 10, 5, 5))
        self.win.canvas.select([a])
        self.win.align_to_plate('left')
        self.assertAlmostEqual(self.now(a)[0], 30.0)
        self.assertEqual(len(self.win._undo), 0)

    def test_a_variable_sits_on_its_baseline(self):
        t = Text(text='|NOM|gjpq', font='Arial', size=5.0, matrix=Affine.translation(20, 30))
        t.outline = TX.outline_for(t)
        self.layer.items.append(t)
        self.assertLess(t.bbox()[1], 30.0)                # des jambages sous la ligne de base
        self.win.canvas.select([t])
        self.win.align_to_plate('bottom')
        self.assertAlmostEqual(next(x for x in self.layer.items if x.id == t.id).matrix.f, 0.0)

    def test_a_plain_text_uses_its_box(self):
        t = Text(text='gjpq', font='Arial', size=5.0, matrix=Affine.translation(20, 30))
        t.outline = TX.outline_for(t)
        self.layer.items.append(t)
        self.win.canvas.select([t])
        self.win.align_to_plate('bottom')
        self.assertAlmostEqual(next(x for x in self.layer.items if x.id == t.id).bbox()[1], 0.0)


class FirstObject(Base):
    def test_same_size_takes_the_first(self):
        a, b = self.boxes((0, 0, 10, 2), (20, 0, 4, 4))
        self.win.canvas.select([b, a])
        self.win.same_size_items('h')
        self.assertAlmostEqual(self.now(a)[3] - self.now(a)[1], 4.0)
        self.assertAlmostEqual(self.now(b)[3] - self.now(b)[1], 4.0)

    def test_same_width(self):
        a, b = self.boxes((0, 0, 10, 2), (20, 0, 4, 4))
        self.win.canvas.select([a, b])
        self.win.same_size_items('w')
        self.assertAlmostEqual(self.now(b)[2] - self.now(b)[0], 10.0)
        self.assertAlmostEqual(self.now(a)[2] - self.now(a)[0], 10.0)

    def test_order_survives_an_alignment(self):
        a, b, c = self.boxes((0, 0, 5, 5), (10, 9, 5, 5), (20, 3, 5, 5))
        self.win.canvas.select([c, a, b])
        self.win.align('top')
        self.assertEqual([x.id for x in self.win.canvas.selection], [c.id, a.id, b.id])
        self.assertAlmostEqual(self.now(a)[3], 8.0)
        self.win.align('left')
        self.assertAlmostEqual(self.now(a)[0], 20.0)


class Spacing(unittest.TestCase):
    def test_commands_lead_to_the_automatic_spacing(self):
        self.assertEqual(S.TE_ACTIONS['ID_COMPO_ALIGNER_ESPACEHORIZ'], 'distribute_h')
        self.assertEqual(S.TE_ACTIONS['ID_COMPO_ALIGNER_ESPACEVERTI'], 'distribute_v')


class SpacingWindow(Base):
    def test_no_dialog_and_ends_stay(self):
        a, b, c = self.boxes((0, 0, 10, 5), (12, 0, 10, 5), (50, 0, 10, 5))
        self.win.canvas.select([a, b, c])
        with mock.patch('vectordrive.ui.dialogs.ParamsDialog.exec', side_effect=AssertionError('pas de fenêtre')):
            self.win.A[S.TE_ACTIONS['ID_COMPO_ALIGNER_ESPACEHORIZ']].trigger()
        self.assertAlmostEqual(self.now(a)[0], 0.0)
        self.assertAlmostEqual(self.now(c)[0], 50.0)
        self.assertAlmostEqual(self.now(b)[0], 25.0)

    def test_fixed_gap_stays_available(self):
        self.assertIn('space_h', self.win.A)
        self.assertIn('space_v', self.win.A)


class Points(unittest.TestCase):
    def square(self):
        return [polyline([(0, 0), (10, 2), (12, 10), (1, 9)], True)]

    def at(self, k):
        return N.node_point(self.square()[0], k)

    def test_first_point_gives_the_value(self):
        out = N.align_nodes(self.square(), {(0, 0), (0, 2)}, 'v', (0, 2))
        self.assertEqual(N.node_point(out[0], 0), (self.at(2)[0], self.at(0)[1]))
        self.assertEqual(N.node_point(out[0], 2), self.at(2))

    def test_first_point_horizontally(self):
        out = N.align_nodes(self.square(), {(0, 1), (0, 3)}, 'h', (0, 3))
        self.assertEqual(N.node_point(out[0], 1), (self.at(1)[0], self.at(3)[1]))
        self.assertEqual(N.node_point(out[0], 3), self.at(3))

    def test_no_first_is_the_mean(self):
        out = N.align_nodes(self.square(), {(0, 0), (0, 2)}, 'v')
        self.assertEqual(N.node_point(out[0], 0)[0], (self.at(0)[0] + self.at(2)[0]) / 2)

    def test_first_outside_the_selection_is_the_mean(self):
        out = N.align_nodes(self.square(), {(0, 0), (0, 2)}, 'v', (0, 3))
        self.assertEqual(N.node_point(out[0], 0)[0], (self.at(0)[0] + self.at(2)[0]) / 2)

    def test_average_stays_the_mean(self):
        out = N.align_nodes(self.square(), {(0, 0), (0, 2)}, 'both', (0, 2))
        want = ((self.at(0)[0] + self.at(2)[0]) / 2, (self.at(0)[1] + self.at(2)[1]) / 2)
        self.assertEqual(N.node_point(out[0], 0), want)


class _Ev:
    def __init__(self, mods=Qt.KeyboardModifier.NoModifier):
        self.m = mods

    def modifiers(self):
        return self.m

    def button(self):
        return Qt.MouseButton.LeftButton

    def buttons(self):
        return Qt.MouseButton.LeftButton


class PointsWithTheMouse(Base):
    def tool(self):
        s = Shape(path=Path(self.pts()))
        self.layer.items.append(s)
        self.win.canvas.select([s])
        self.win.set_tool('node')
        tool = self.win.canvas.tool_obj
        self.assertEqual(type(tool).__name__, 'NodeTool')
        return tool, s

    def pts(self):
        return [polyline([(0, 0), (10, 2), (12, 10), (1, 9)], True)]

    def click(self, tool, k, mods=Qt.KeyboardModifier.NoModifier):
        with mock.patch.object(tool, '_hit', return_value=('node', 0, k)):
            tool.press(QPointF(1, 1), QPointF(1, 1), _Ev(mods))
            tool.release(QPointF(1, 1), QPointF(1, 1), _Ev(mods))

    def test_ctrl_adds_points_as_in_te(self):
        tool, _s = self.tool()
        self.click(tool, 2)
        self.click(tool, 0, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(tool.sel, {(0, 2), (0, 0)})
        self.assertEqual(tool.first_node, (0, 2))
        self.win.set_tool('select')

    def test_shift_still_adds_points(self):
        tool, _s = self.tool()
        self.click(tool, 1)
        self.click(tool, 3, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(tool.sel, {(0, 1), (0, 3)})
        self.assertEqual(tool.first_node, (0, 1))
        self.win.set_tool('select')

    def test_removing_the_first_gives_way_to_the_next_added(self):
        tool, _s = self.tool()
        self.click(tool, 1)
        self.click(tool, 3, Qt.KeyboardModifier.ControlModifier)
        self.click(tool, 1, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(tool.sel, {(0, 3)})
        self.click(tool, 0, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(tool.first_node, (0, 0))
        self.win.set_tool('select')

    def test_the_command_uses_the_first_point(self):
        tool, s = self.tool()
        self.click(tool, 2)
        self.click(tool, 0, Qt.KeyboardModifier.ControlModifier)
        with mock.patch.object(type(self.win), '_shift_held', staticmethod(lambda: False)):   # une touche restée d'un autre essai
            self.win.A['node_align_v'].trigger()
        got = next(x for x in self.layer.items if x.id == s.id).path.contours[0]
        want = N.node_point(self.pts()[0], 2)[0]
        self.assertEqual(N.node_point(got, 0)[0], want)
        self.assertEqual(N.node_point(got, 2)[0], want)
        self.win.set_tool('select')


if __name__ == '__main__':
    unittest.main()
