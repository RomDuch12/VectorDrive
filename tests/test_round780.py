"""Round 780 : objet en repères, liste des repères, répartition sur la plaque."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

from PySide6.QtWidgets import QApplication

from vectordrive.core import guides as GD
from vectordrive.core.document import Group, Layer, Plate, Shape, Text
from vectordrive.core.geom import Path, circle, polyline, rect
from vectordrive.ui import shortcuts as S


def shape(contour):
    return Shape(path=Path([contour]))


class Lines(unittest.TestCase):
    def test_rectangle_gives_four_guides(self):
        guides, obliques = GD.split(GD.lines_of([shape(rect(10, 20, 30, 40))]))
        self.assertEqual(obliques, [])
        self.assertEqual(sorted(guides), [['h', 20.0], ['h', 60.0], ['v', 10.0], ['v', 40.0]])

    def test_triangle_gives_construction_lines(self):
        guides, obliques = GD.split(GD.lines_of([shape(polyline([(0, 0), (10, 0), (0, 10)], True))]))
        self.assertEqual(guides, [['h', 0.0], ['v', 0.0]])
        self.assertEqual(len(obliques), 1)
        self.assertAlmostEqual(obliques[0][2], 135.0)

    def test_curve_gives_its_box(self):
        guides, obliques = GD.split(GD.lines_of([shape(circle((50, 50), 10))]))
        self.assertEqual(obliques, [])
        self.assertEqual(sorted(guides), [['h', 40.0], ['h', 60.0], ['v', 40.0], ['v', 60.0]])

    def test_text_gives_its_box(self):
        t = Text(text='A', font='VD Trait', size=5.0)
        self.assertEqual(len(GD.lines_of([t])), 4)

    def test_group_is_walked(self):
        g = Group(children=[shape(rect(0, 0, 1, 1)), shape(rect(5, 5, 1, 1))])
        guides, _o = GD.split(GD.lines_of([g]))
        self.assertEqual(len(guides), 8)

    def test_hidden_stays_out(self):
        s = shape(rect(0, 0, 1, 1))
        s.visible = False
        self.assertEqual(GD.lines_of([s]), [])

    def test_collinear_edges_are_one_guide(self):
        comb = polyline([(0, 0), (10, 0), (10, 5), (20, 5), (20, 0), (30, 0), (30, 9), (0, 9)], True)
        guides, _o = GD.split(GD.lines_of([shape(comb)]))
        self.assertEqual(sum(g == ['h', 0.0] for g in guides), 1)

    def test_parallel_edges_stay_two(self):
        band = polyline([(0, 0), (10, 10), (10, 12), (0, 2)], True)
        _g, obliques = GD.split(GD.lines_of([shape(band)]))
        self.assertEqual(len(obliques), 2)

    def test_same_oblique_through_another_point_is_one(self):
        _g, ob = GD.split([(0, 0, 45.0), (5, 5, 45.0)])
        self.assertEqual(len(ob), 1)

    def test_angle_is_folded(self):
        guides, ob = GD.split([(0, 3, 180.0), (2, 0, 270.0)])
        self.assertEqual((guides, ob), ([['h', 3.0], ['v', 2.0]], []))

    def test_only_new(self):
        g, o = GD.new_only([['h', 1.0], ['v', 2.0]], [[0, 0, 45.0], [0, 9, 45.0]], [['h', 1.0]], [[3, 3, 45.0]])
        self.assertEqual(g, [['v', 2.0]])
        self.assertEqual(o, [[0, 9, 45.0]])


class Spread(unittest.TestCase):
    def test_columns_and_rows(self):
        got = GD.spread((0, 0, 100, 50), 2, 1)
        self.assertEqual(got, [['v', 0.0], ['v', 50.0], ['v', 100.0], ['h', 0.0], ['h', 50.0]])

    def test_margin(self):
        got = GD.spread((0, 0, 100, 50), 1, 0, margin=10.0)
        self.assertEqual(got, [['v', 10.0], ['v', 90.0]])

    def test_margin_eats_everything(self):
        self.assertEqual(GD.spread((0, 0, 10, 10), 2, 2, margin=6.0), [])

    def test_nothing_asked(self):
        self.assertEqual(GD.spread((0, 0, 10, 10), 0, 0), [])


class Dialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dlg(self, guides=(), obliques=()):
        from vectordrive.ui.guides_dialog import GuidesDialog
        return GuidesDialog(None, guides, obliques, (0, 0, 100, 50))

    def test_values_round_trip(self):
        d = self._dlg([['h', 3.0], ['v', 4.5]], [[1.0, 2.0, 30.0]])
        self.assertEqual(d.table.rowCount(), 3)
        self.assertEqual(d.values(), ([['h', 3.0], ['v', 4.5]], [[1.0, 2.0, 30.0]]))

    def test_edit_a_value(self):
        d = self._dlg([['h', 3.0]])
        d.table.item(0, 2).setText('7,5')
        self.assertEqual(d.values()[0], [['h', 7.5]])

    def test_bad_value_reads_as_zero(self):
        d = self._dlg([['h', 3.0]])
        d.table.item(0, 2).setText('abc')
        self.assertEqual(d.values()[0], [['h', 0.0]])

    def test_change_the_kind(self):
        d = self._dlg([['h', 3.0]])
        d.table.cellWidget(0, 0).setCurrentIndex(1)
        d.table.item(0, 1).setText('8')
        self.assertEqual(d.values()[0], [['v', 8.0]])

    def test_only_useful_cells_are_editable(self):
        from PySide6.QtCore import Qt
        d = self._dlg([['h', 3.0]])
        self.assertFalse(d.table.item(0, 1).flags() & Qt.ItemFlag.ItemIsEditable)
        self.assertTrue(d.table.item(0, 2).flags() & Qt.ItemFlag.ItemIsEditable)
        d.table.cellWidget(0, 0).setCurrentIndex(2)
        self.assertTrue(d.table.item(0, 1).flags() & Qt.ItemFlag.ItemIsEditable)

    def test_oblique_at_zero_becomes_a_guide(self):
        d = self._dlg([], [[1.0, 2.0, 30.0]])
        d.table.item(0, 3).setText('0')
        self.assertEqual(d.values(), ([['h', 2.0]], []))

    def test_add_remove_clear(self):
        d = self._dlg([['h', 3.0], ['h', 4.0]])
        d.add_row()
        self.assertEqual(d.table.rowCount(), 3)
        d.table.setCurrentCell(0, 1)
        d.remove_row()
        self.assertEqual(d.values()[0][0], ['h', 4.0])
        d.clear()
        self.assertEqual(d.values(), ([], []))

    def test_spread_button(self):
        d = self._dlg()
        d.columns.setValue(2)
        d.rows.setValue(0)
        d.margin.setValue(10.0)
        d.spread()
        self.assertEqual(d.values()[0], [['v', 10.0], ['v', 50.0], ['v', 90.0]])

    def test_spread_keeps_existing(self):
        d = self._dlg([['h', 3.0]])
        d.columns.setValue(1)
        d.rows.setValue(0)
        d.spread()
        self.assertEqual(len(d.values()[0]), 3)


class Commands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.close()

    def setUp(self):
        c = self.win.canvas
        c.doc.layers = [Layer(name='Plan 1')]
        c.doc.active = c.doc.layers[0].id
        c.doc.plate = Plate(x=0.0, y=0.0, width=100.0, height=50.0)
        c.doc.extra.pop('guides', None)
        c.doc.extra.pop(c.OBLIQUES, None)

    def _select(self, *items):
        self.win.canvas.doc.layers[0].items = list(items)
        self.win.canvas.select(list(items))

    def test_ribbon_and_te_name(self):
        for k in ('guides_dialog', 'object_to_guides'):
            found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups() for b in g.buttons()
                     if b.defaultAction() is self.win.A[k]]
            self.assertEqual(len(found), 1, k)
        self.assertEqual(S.TE_ACTIONS['ID_MANIPULER_PLANREPERE'], 'guides_dialog')

    def test_object_stays_and_guides_appear(self):
        s = shape(rect(10, 20, 30, 40))
        self._select(s)
        self.assertEqual(self.win.object_to_guides(), 4)
        self.assertEqual(len(self.win.canvas.guides), 4)
        self.assertIn(s, self.win.canvas.doc.layers[0].items)

    def test_oblique_goes_to_construction_lines(self):
        self._select(shape(polyline([(0, 0), (10, 0), (0, 10)], True)))
        self.assertEqual(self.win.object_to_guides(), 3)
        self.assertEqual(len(self.win.canvas.oblique_guides), 1)

    def test_second_time_adds_nothing(self):
        self._select(shape(rect(10, 20, 30, 40)))
        self.win.object_to_guides()
        self.assertEqual(self.win.object_to_guides(), 0)
        self.assertEqual(len(self.win.canvas.guides), 4)
        self.assertIn('déjà', self.win.statusBar().currentMessage())

    def test_nothing_selected(self):
        self._select()
        self.assertEqual(self.win.object_to_guides(), 0)

    def test_undo(self):
        self._select(shape(polyline([(0, 0), (10, 0), (0, 10)], True)))
        self.win.object_to_guides()
        self.win.undo()
        self.assertEqual(self.win.canvas.guides, [])
        self.assertEqual(self.win.canvas.oblique_guides, [])

    def test_too_many_refused(self):
        self._select(shape(rect(0, 0, 1, 1)))
        with mock.patch.object(GD, 'MAX_GUIDES', 2):
            self.assertEqual(self.win.object_to_guides(), 0)
        self.assertEqual(self.win.canvas.guides, [])

    def test_dialog_result_applied(self):
        self.assertTrue(self.win.guides_dialog(([['h', 5.0]], [[1.0, 1.0, 30.0]])))
        self.assertEqual(self.win.canvas.guides, [['h', 5.0]])
        self.assertEqual(self.win.canvas.oblique_guides, [[1.0, 1.0, 30.0]])

    def test_dialog_can_empty_everything(self):
        self.win.guides_dialog(([['h', 5.0]], [[1.0, 1.0, 30.0]]))
        self.assertTrue(self.win.guides_dialog(([], [])))
        self.assertEqual(self.win.canvas.guides, [])
        self.assertEqual(self.win.canvas.oblique_guides, [])

    def test_dialog_undo(self):
        self.win.guides_dialog(([['h', 5.0]], []))
        self.win.undo()
        self.assertEqual(self.win.canvas.guides, [])

    def test_same_values_do_nothing(self):
        self.win.guides_dialog(([['h', 5.0]], []))
        self.assertFalse(self.win.guides_dialog(([['h', 5.0]], [])))

    def test_dialog_uses_the_plate(self):
        from vectordrive.ui import guides_dialog as D
        seen = {}

        def fake(dlg):
            seen['box'] = dlg.box
            return 0
        with mock.patch.object(D.GuidesDialog, 'exec', fake):
            self.assertFalse(self.win.guides_dialog())
        self.assertEqual(seen['box'], (0.0, 0.0, 100.0, 50.0))

    def test_guides_are_saved_with_the_drawing(self):
        from vectordrive.io import native, registry
        self.win.guides_dialog(([['v', 7.0]], [[1.0, 1.0, 30.0]]))
        p = os.path.join(tempfile.mkdtemp(), 'g.vdz')
        registry.save_document(self.win.canvas.doc, p)
        back = native.read(p)
        self.assertEqual(back.extra['guides'], [['v', 7.0]])


if __name__ == '__main__':
    unittest.main()
