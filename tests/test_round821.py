"""Round 821 : Maj garde l'original ; Raccorder : distance de liaison, Séparément, Ctrl pour les réglages."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vectordrive.core import chain as CH
from vectordrive.core import nodes as N
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Line, Path, polyline, rect

app = QApplication.instance() or QApplication([])


def box(x, y, w, h):
    return Shape(path=Path([rect(x, y, w, h)]))


def line(*pts):
    return polyline(list(pts), False)


class Chain(unittest.TestCase):
    def test_merge_below_the_merge_distance(self):
        out, j, c = CH.chain([line((0, 0), (10, 0)), line((10.5, 0), (20, 0))], 1.0, 3.0)
        self.assertEqual((j, c, len(out)), (1, 0, 1))
        self.assertEqual(len(out[0].segments), 2)         # le point est fusionné : pas de segment de plus
        self.assertEqual(out[0].segments[1].p0, (10, 0))

    def test_link_between_the_two_distances(self):
        out, j, c = CH.chain([line((0, 0), (10, 0)), line((11.5, 0), (20, 0))], 1.0, 3.0)
        self.assertEqual((j, c, len(out)), (1, 0, 1))
        self.assertEqual(len(out[0].segments), 3)         # un segment de plus : les formes n'ont pas bougé
        self.assertEqual((out[0].segments[1].p0, out[0].segments[1].p1), ((10, 0), (11.5, 0)))

    def test_nothing_beyond_both(self):
        out, j, c = CH.chain([line((0, 0), (10, 0)), line((14, 0), (20, 0))], 1.0, 3.0)
        self.assertEqual((j, c, len(out)), (0, 0, 2))

    def test_link_backwards(self):
        out, j, _c = CH.chain([line((11.5, 0), (20, 0)), line((0, 0), (10, 0))], 1.0, 3.0)
        self.assertEqual(j, 1)
        self.assertEqual(len(out), 1)
        self.assertEqual(len(out[0].segments), 3)
        self.assertEqual(out[0].start, (0, 0))
        self.assertEqual(out[0].end, (20, 0))

    def test_reversed_contour(self):
        out, j, _c = CH.chain([line((0, 0), (10, 0)), line((20, 0), (11.5, 0))], 1.0, 3.0)
        self.assertEqual(j, 1)
        self.assertEqual(out[0].end, (20, 0))

    def test_closing_by_a_segment(self):
        out, j, c = CH.chain([line((0, 0), (10, 0), (10, 10), (0, 2))], 0.5, 3.0)
        self.assertEqual((j, c), (0, 1))
        self.assertTrue(out[0].closed)
        self.assertEqual(len(out[0].segments), 4)
        self.assertEqual(out[0].segments[-1].p1, (0, 0))
        self.assertEqual(out[0].segments[-1].p0, (0, 2))

    def test_a_lone_line_never_closes(self):
        out, _j, c = CH.chain([line((0, 0), (2, 0))], 0.5, 3.0)
        self.assertEqual(c, 0)
        self.assertFalse(out[0].closed)

    def test_own_end_nearer_than_a_neighbour(self):
        a = line((0, 0), (10, 0), (10, 10), (0, 1))
        b = line((0, 3), (-10, 3))
        out, j, c = CH.chain([a, b], 0.1, 5.0)
        self.assertEqual((j, c), (0, 1))
        self.assertEqual(sum(k.closed for k in out), 1)

    def test_default_is_as_before(self):
        out, j, _c = CH.chain([line((0, 0), (10, 0)), line((10.001, 0), (20, 0))], 0.01)
        self.assertEqual((j, len(out), len(out[0].segments)), (1, 1, 2))
        out, j, _c = CH.chain([line((0, 0), (10, 0)), line((11, 0), (20, 0))], 0.01)
        self.assertEqual(j, 0)

    def test_link_smaller_than_merge_merges(self):
        out, j, _c = CH.chain([line((0, 0), (10, 0)), line((10.5, 0), (20, 0))], 1.0, 0.2)
        self.assertEqual((j, len(out[0].segments)), (1, 2))


class Separately(unittest.TestCase):
    def layer(self):
        self.a = Shape(path=Path([line((0, 0), (10, 0), (10, 10), (0, 2))]))
        self.b = Shape(path=Path([line((0, 3), (-10, 3), (-10, 10), (0, 4))]))
        return Layer(name='P', items=[self.a, self.b])

    def test_each_closes_on_itself(self):
        L = self.layer()
        j, c, touched = CH.chain_layers([L], 0.5, None, 3.0, True)
        self.assertEqual((j, c), (0, 2))
        self.assertEqual(len(L.items), 2)
        self.assertTrue(all(it.path.contours[0].closed for it in L.items))
        self.assertEqual(len(touched), 2)

    def test_without_the_option_they_may_join(self):
        L = self.layer()
        j, _c, _t = CH.chain_layers([L], 0.5, None, 3.0)
        self.assertGreaterEqual(j, 1)

    def test_nothing_to_close(self):
        L = Layer(name='P', items=[Shape(path=Path([line((0, 0), (10, 0))]))])
        before = L.items[0]
        j, c, touched = CH.chain_layers([L], 0.5, None, 3.0, True)
        self.assertEqual((j, c, touched), (0, 0, []))
        self.assertIs(L.items[0], before)

    def test_closed_contours_stay(self):
        keep = rect(50, 50, 5, 5)
        L = Layer(name='P', items=[Shape(path=Path([keep, line((0, 0), (10, 0), (10, 10), (0, 2))]))])
        CH.chain_layers([L], 0.5, None, 3.0, True)
        self.assertEqual(len(L.items[0].path.contours), 2)
        self.assertEqual(L.items[0].path.contours[0], keep)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.MW = MainWindow
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

    def shift(self, on=True):
        return mock.patch.object(self.MW, '_shift_held', return_value=on)


class KeepOriginal(Base):
    def test_every_key_is_a_command(self):
        self.assertEqual([k for k in self.MW.KEEP_ORIGINAL if k not in self.win.A], [])

    def test_portion_commands_keep_their_meaning(self):
        for k in ('node_segment', 'node_angle', 'node_arc'):
            self.assertNotIn(k, self.MW.KEEP_ORIGINAL)

    def test_align_on_a_copy(self):
        s = box(30, 10, 5, 5)
        self.layer.items.append(s)
        self.win.canvas.select([s])
        with self.shift():
            self.win.A['align_plate_left'].trigger()
        self.assertEqual(len(self.layer.items), 2)
        self.assertEqual(self.layer.items[0].bbox()[0], 30.0)
        self.assertAlmostEqual(self.layer.items[1].bbox()[0], 0.0)
        self.assertEqual([x.id for x in self.win.canvas.selection], [self.layer.items[1].id])
        self.assertNotEqual(self.layer.items[0].id, self.layer.items[1].id)

    def test_without_shift_there_is_no_copy(self):
        s = box(30, 10, 5, 5)
        self.layer.items.append(s)
        self.win.canvas.select([s])
        with self.shift(False):
            self.win.A['align_plate_left'].trigger()
        self.assertEqual(len(self.layer.items), 1)

    def test_a_single_undo_brings_all_back(self):
        s = box(30, 10, 5, 5)
        self.layer.items.append(s)
        self.win.canvas.select([s])
        with self.shift():
            self.win.A['align_plate_left'].trigger()
        self.assertEqual(len(self.win._undo), 1)
        self.win.undo()
        L = self.win.canvas.doc.layers[0]
        self.assertEqual(len(L.items), 1)
        self.assertEqual(L.items[0].bbox()[0], 30.0)

    def test_copy_sits_just_above_its_original(self):
        a, b = box(30, 10, 5, 5), box(50, 10, 5, 5)
        self.layer.items.extend([a, b])
        self.win.canvas.select([a])
        with self.shift():
            self.win.A['align_plate_left'].trigger()
        self.assertEqual(len(self.layer.items), 3)
        self.assertIs(self.layer.items[0], a)
        self.assertIs(self.layer.items[2], b)

    def test_a_command_that_does_nothing_leaves_no_copy(self):
        s = box(0, 10, 5, 5)                               # déjà contre la marge
        self.layer.items.append(s)
        self.win.canvas.select([s])
        with self.shift():
            self.win.A['align_plate_left'].trigger()
        self.assertEqual(len(self.layer.items), 1)
        self.assertEqual(len(self.win._undo), 0)
        self.assertEqual(self.win.canvas.selection, [s])

    def test_a_cancelled_window_leaves_no_copy(self):
        s = Shape(path=Path([line((0, 0), (10, 0), (10, 10), (0, 1))]))
        self.layer.items.append(s)
        self.win.canvas.select([s])
        self.win.settings.setValue('raccord/liaison', 0.0)
        with self.shift(), mock.patch.object(self.MW, '_ctrl_held', return_value=True), \
                mock.patch('vectordrive.ui.main_window.QDialog.exec', return_value=0):
            self.win.A['chain'].trigger()
        self.win.settings.remove('raccord/liaison')
        self.assertEqual(len(self.layer.items), 1)
        self.assertEqual(len(self.win._undo), 0)

    def test_no_selection_no_copy(self):
        s = box(30, 10, 5, 5)
        self.layer.items.append(s)
        with self.shift(), mock.patch('vectordrive.ui.main_window.QMessageBox.information'):
            self.win.A['align_plate_left'].trigger()
        self.assertEqual(len(self.layer.items), 1)

    def test_shortcut_with_shift_is_not_a_request(self):
        act = self.win.A['align_left']
        s = box(30, 10, 5, 5)
        self.layer.items.append(s)
        self.win.canvas.select([s])
        with self.shift():
            self.assertTrue(self.win._wants_copy(act))
            with mock.patch.object(act, 'shortcuts', return_value=[mock.Mock(toString=lambda: 'Shift+H')]):
                self.assertFalse(self.win._wants_copy(act))

    def test_other_commands_ignore_shift(self):
        s = box(30, 10, 5, 5)
        self.layer.items.append(s)
        self.win.canvas.select([s])
        with self.shift():
            self.assertFalse(self.win._wants_copy(self.win.A['undo']))

    def test_point_mode_works_on_the_copy(self):
        s = Shape(path=Path([polyline([(0, 0), (10, 2), (12, 10), (1, 9)], True)]))
        self.layer.items.append(s)
        self.win.canvas.select([s])
        self.win.set_tool('node')
        tool = self.win.canvas.tool_obj
        tool.sel = {(0, 0), (0, 2)}
        tool.first_node = (0, 2)
        want = N.node_point(s.path.contours[0], 2)[0]
        before = N.node_point(s.path.contours[0], 0)
        with self.shift():
            self.win.A['node_align_v'].trigger()
        self.assertEqual(len(self.layer.items), 2)
        self.assertEqual(N.node_point(self.layer.items[0].path.contours[0], 0), before)
        self.assertEqual(N.node_point(self.layer.items[1].path.contours[0], 0)[0], want)
        self.win.set_tool('select')


class ChainWindow(Base):
    def test_first_use_opens_the_window(self):
        s = Shape(path=Path([line((0, 0), (10, 0), (10, 10), (0, 1))]))
        self.layer.items.append(s)
        self.win.canvas.select([s])
        self.win.settings.remove('raccord/liaison')
        with mock.patch('vectordrive.ui.main_window.QDialog.exec', return_value=0) as ex:
            self.win.chain_dialog()
        ex.assert_called_once()

    def test_later_clicks_use_the_last_settings(self):
        s = Shape(path=Path([line((0, 0), (10, 0), (10, 10), (0, 1))]))
        self.layer.items.append(s)
        self.win.canvas.select([s])
        self.win.settings.setValue('raccord/tolerance', 0.01)
        self.win.settings.setValue('raccord/liaison', 2.0)
        self.win.settings.setValue('raccord/separement', False)
        with mock.patch('vectordrive.ui.main_window.QDialog.exec', side_effect=AssertionError('pas de fenêtre')), \
                mock.patch.object(self.MW, '_ctrl_held', return_value=False):
            self.win.chain_dialog()
        self.assertTrue(self.layer.items[0].path.contours[0].closed)
        for k in ('tolerance', 'liaison', 'separement'):
            self.win.settings.remove('raccord/' + k)

    def test_ctrl_opens_the_window_and_remembers(self):
        s = Shape(path=Path([line((0, 0), (10, 0), (10, 10), (0, 1))]))
        self.layer.items.append(s)
        self.win.canvas.select([s])
        self.win.settings.setValue('raccord/liaison', 0.0)

        def run(_dlg):
            w_tol, w_link, w_apart = self.win.last_chain_dialog
            w_tol.setValue(0.5)
            w_link.setValue(2.0)
            w_apart.setChecked(True)
            return 1
        with mock.patch.object(self.MW, '_ctrl_held', return_value=True), \
                mock.patch('vectordrive.ui.main_window.QDialog.exec', run):
            self.win.chain_dialog()
        self.assertEqual(float(self.win.settings.value('raccord/liaison')), 2.0)
        self.assertIn(self.win.settings.value('raccord/separement'), (True, 'true'))
        self.assertTrue(self.layer.items[0].path.contours[0].closed)
        for k in ('tolerance', 'liaison', 'separement'):
            self.win.settings.remove('raccord/' + k)

    def test_the_segment_is_a_line(self):
        s = Shape(path=Path([line((0, 0), (10, 0), (10, 10), (0, 1))]))
        self.layer.items.append(s)
        self.win.canvas.select([s])
        self.assertEqual(self.win.chain_contours(0.01, 2.0), (0, 1))
        c = next(iter(self.layer.items)).path.contours[0]
        self.assertIsInstance(c.segments[-1], Line)


if __name__ == '__main__':
    unittest.main()
