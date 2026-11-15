"""Round 824 : assistant Texte en colonnes."""
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts
from vectordrive.core import text as TX
from vectordrive.core import textcolumns as TC
from vectordrive.core.document import Group, Layer, Plate, Shape, Text
from vectordrive.core.geom import Affine
from vectordrive.ui import shortcuts as S

app = QApplication.instance() or QApplication([])
HAS_ARIAL = bool(fonts.find_font('Arial'))


def line_spec(**kw):
    out = TC.TextColumns(method='baseline', rows=2, cols=2, x=10.0, y=50.0, anchor=[0.0, 1.0], line_height=8.0,
                         columns=[TC.Column(width=30.0, left=10.0, text_width=80.0, bottom=2.0)],
                         cells=[['a', 'b'], ['c', 'd']])
    for k, v in kw.items():
        setattr(out, k, v)
    return out


def table_spec(**kw):
    out = TC.TextColumns(method='table', rows=2, cols=2, x=0.0, y=20.0, anchor=[0.0, 1.0], total_w=60.0, total_h=20.0,
                         columns=[TC.Column(left=10.0, text_width=80.0, bottom=2.0)], cells=[['a', 'b'], ['c', 'd']])
    for k, v in kw.items():
        setattr(out, k, v)
    return out


class Spec(unittest.TestCase):
    def test_round_trip(self):
        spec = TC.clean(line_spec(same=False, cols=2, columns=[TC.Column(width=10.0), TC.Column(width=20.0)]))
        back = TC.TextColumns.from_dict(json.loads(json.dumps(spec.to_dict())))
        self.assertEqual(back, spec)

    def test_unknown_keys_are_ignored(self):
        self.assertEqual(TC.TextColumns.from_dict({'rows': 4, 'later': 1}).rows, 4)

    def test_clean_limits(self):
        spec = TC.clean(TC.TextColumns(rows=0, cols=99999, height=-1.0))
        self.assertEqual((spec.rows, spec.cols), (1, TC.MAX_COLS))
        self.assertGreater(spec.height, 0.0)
        self.assertEqual(len(spec.columns), TC.MAX_COLS)

    def test_clean_adds_and_cuts_columns(self):
        self.assertEqual(len(TC.clean(TC.TextColumns(cols=3)).columns), 3)
        self.assertEqual(len(TC.clean(TC.TextColumns(cols=1, columns=[TC.Column(), TC.Column()])).columns), 1)

    def test_clean_keeps_text_inside_its_cell(self):
        c = TC.clean(TC.TextColumns(cols=1, columns=[TC.Column(left=70.0, text_width=90.0)])).columns[0]
        self.assertAlmostEqual(c.text_width, 30.0)

    def test_a_table_keeps_its_borders(self):
        self.assertEqual(TC.clean(table_spec(borders='none')).borders, 'all')
        self.assertEqual(TC.clean(line_spec(borders='none')).borders, 'none')

    def test_lines_from_a_text(self):
        spec = TC.seed_from_lines(TC.TextColumns(rows=2), ['x', 'y', 'z'])
        self.assertEqual(spec.rows, 3)
        self.assertEqual(TC.cell_text(spec, 2, 0), 'z')
        self.assertEqual(TC.cell_text(spec, 2, 1), '')


class Geometry(unittest.TestCase):
    def test_widths(self):
        self.assertEqual(TC.widths(TC.clean(line_spec())), [30.0, 30.0])
        self.assertEqual(TC.widths(TC.clean(table_spec())), [30.0, 30.0])
        spec = TC.clean(line_spec(same=False, columns=[TC.Column(width=10.0), TC.Column(width=25.0)]))
        self.assertEqual(TC.widths(spec), [10.0, 25.0])

    def test_table_columns_with_their_own_widths(self):
        spec = TC.clean(table_spec(same=False, columns=[TC.Column(width=10.0), TC.Column(width=25.0)]))
        self.assertEqual(TC.corner(spec)[2], 35.0)

    def test_row_height(self):
        self.assertEqual(TC.row_height(TC.clean(line_spec())), 8.0)
        self.assertEqual(TC.row_height(TC.clean(table_spec())), 10.0)

    def test_first_baseline_point(self):
        for fx, left in ((0.0, 10.0), (0.5, -20.0), (1.0, -50.0)):
            x0, top, w, h = TC.corner(TC.clean(line_spec(anchor=[fx, 1.0])))
            self.assertAlmostEqual(x0, left)
            self.assertAlmostEqual(top, 50.0 - 2.0 + 8.0)         # sous la ligne de base : la marge inférieure
            self.assertEqual((w, h), (60.0, 16.0))

    def test_nine_points_of_a_table(self):
        for (fx, fy), (x0, top) in {(0.0, 1.0): (0.0, 20.0), (1.0, 1.0): (-60.0, 20.0), (0.5, 0.5): (-30.0, 30.0),
                                    (0.0, 0.0): (0.0, 40.0), (1.0, 0.0): (-60.0, 40.0)}.items():
            got = TC.corner(TC.clean(table_spec(anchor=[fx, fy])))
            self.assertAlmostEqual(got[0], x0)
            self.assertAlmostEqual(got[1], top)

    def counts(self, kind):
        spec = TC.clean(table_spec(rows=3, cols=4, borders=kind))
        return len(TC.lines_of(spec).contours)

    def test_borders(self):
        self.assertEqual(self.counts('all'), 1 + 2 + 3)     # le cadre et les traits intérieurs
        self.assertEqual(self.counts('frame'), 1)
        self.assertEqual(self.counts('h'), 4)
        self.assertEqual(self.counts('v'), 5)

    def test_no_border(self):
        self.assertEqual(TC.lines_of(TC.clean(line_spec(borders='none'))).contours, [])


@unittest.skipUnless(HAS_ARIAL, 'Arial absente')
class Build(unittest.TestCase):
    def texts(self, g):
        return [c for c in g.children if isinstance(c, Text)]

    def test_one_text_per_filled_cell(self):
        g = TC.build(line_spec(cells=[['a', ''], ['  ', 'd']]))
        self.assertEqual([t.text for t in self.texts(g)], ['a', 'd'])

    def test_group_keeps_its_settings(self):
        g = TC.build(line_spec())
        self.assertEqual(TC.TextColumns.from_dict(g.extra['text_columns']).rows, 2)
        json.dumps(g.extra['text_columns'])

    def test_positions(self):
        g = TC.build(line_spec())
        a, b, c, _d = self.texts(g)
        self.assertAlmostEqual(a.matrix.e, 10.0 + 3.0)            # 10 % de 30 mm
        self.assertAlmostEqual(a.matrix.f, 50.0)                   # la première ligne de base est au point donné
        self.assertAlmostEqual(b.matrix.e, 10.0 + 30.0 + 3.0)
        self.assertAlmostEqual(c.matrix.f, 50.0 - 8.0)

    def test_alignments(self):
        for align, x in (('left', 3.0), ('center', 15.0), ('right', 27.0)):
            g = TC.build(table_spec(cols=1, cells=[['a']], total_w=30.0, columns=[TC.Column(left=10.0, text_width=80.0, align=align)]))
            t = self.texts(g)[0]
            self.assertAlmostEqual(t.matrix.e, x)
            self.assertEqual(t.align, align)

    def test_long_text_stays_in_its_cell(self):
        g = TC.build(table_spec(cols=1, rows=1, total_h=10.0, cells=[['Un texte beaucoup trop long pour cette cellule']]))
        bb = self.texts(g)[0].outline.bbox()
        self.assertLessEqual(bb[2] - bb[0], 60.0 * 0.8 + 0.01)

    def test_justified_text_fills_its_width(self):
        g = TC.build(table_spec(cols=1, rows=1, total_h=10.0, cells=[['ABC']],
                                columns=[TC.Column(left=10.0, text_width=80.0, align='justify', bottom=2.0)]))
        t = self.texts(g)[0]
        self.assertEqual(t.extra['fit']['width'], 48.0)
        bb = t.outline.bbox()
        self.assertGreater(bb[2] - bb[0], 45.0)

    def test_text_height_wins_over_the_line(self):
        g = TC.build(line_spec(line_height=2.0, height=7.0))
        self.assertEqual(self.texts(g)[0].size, 7.0)

    def test_border_colour_is_its_own(self):
        g = TC.build(table_spec(border_tool=3), tool=1)
        self.assertEqual(g.children[0].tool, 3)
        self.assertEqual(self.texts(g)[0].tool, 1)

    def test_nothing_at_all(self):
        self.assertEqual(TC.build(line_spec(cells=[], borders='none')).children, [])


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
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()
        self.win.canvas.select([])


@unittest.skipUnless(HAS_ARIAL, 'Arial absente')
class Command(Base):
    def test_new(self):
        g = self.win.text_table(line_spec())
        self.assertIn(g, self.layer.items)
        self.assertEqual(g.name, 'Texte en colonnes')

    def test_from_a_selected_text(self):
        t = Text(text='un\ndeux\ntrois', font='Arial', size=4.0, matrix=Affine.translation(5, 60))
        t.outline = TX.outline_for(t)
        self.layer.items.append(t)
        self.win.canvas.select([t])
        seen = {}

        def fake(dlg):
            seen['spec'] = dlg.spec()
            return 1
        with mock.patch('vectordrive.ui.text_columns_dialog.TextColumnsDialog.exec', fake):
            g = self.win.text_table()
        spec = seen['spec']
        self.assertEqual((spec.rows, spec.height, spec.x, spec.y), (3, 4.0, 5.0, 60.0))
        self.assertEqual(TC.cell_text(spec, 1, 0), 'deux')
        self.assertEqual(self.layer.items, [g])                    # il remplace le texte
        self.win.undo()
        self.assertIsInstance(self.win.canvas.doc.layers[0].items[0], Text)

    def test_reopen_by_double_click(self):
        g = self.win.text_table(table_spec())
        with mock.patch('vectordrive.ui.text_columns_dialog.TextColumnsDialog.exec', return_value=0) as ex:
            self.win._item_double_clicked(g)
        ex.assert_called_once()
        self.assertEqual(self.win.last_text_table.cells()[1][1], 'd')

    def test_reopen_after_a_move(self):
        g = self.win.text_table(table_spec())
        moved = g.transformed(Affine.translation(7.0, -3.0))
        self.layer.items[0] = moved
        seen = {}

        def fake(dlg):
            seen['x'], seen['y'] = dlg.x.value(), dlg.y.value()
            return 0
        with mock.patch('vectordrive.ui.text_columns_dialog.TextColumnsDialog.exec', fake):
            self.win.text_table(target=moved)
        self.assertAlmostEqual(seen['x'], 7.0)
        self.assertAlmostEqual(seen['y'], 17.0)

    def test_reopening_changes_settings_not_text(self):
        g = self.win.text_table(table_spec())

        def fake(dlg):
            dlg.total_w.setValue(100.0)
            return 1
        with mock.patch('vectordrive.ui.text_columns_dialog.TextColumnsDialog.exec', fake):
            new = self.win.text_table(target=g)
        self.assertEqual(self.layer.items, [new])
        self.assertEqual(TC.TextColumns.from_dict(new.extra['text_columns']).total_w, 100.0)
        self.assertEqual([c.text for c in new.children if isinstance(c, Text)], ['a', 'b', 'c', 'd'])
        self.win.undo()
        self.assertEqual(len(self.win.canvas.doc.layers[0].items), 1)

    def test_nothing_to_place_says_so(self):
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertIsNone(self.win.text_table(line_spec(cells=[], borders='none')))
        info.assert_called_once()
        self.assertEqual(self.layer.items, [])

    def test_cancel(self):
        with mock.patch('vectordrive.ui.text_columns_dialog.TextColumnsDialog.exec', return_value=0):
            self.assertIsNone(self.win.text_table())
        self.assertEqual(self.layer.items, [])

    def test_te_command_leads_here(self):
        self.assertEqual(S.TE_ACTIONS['ID_TXTCOLONNE_VN'], 'text_table')
        self.assertIn('text_columns', self.win.A)

    def test_the_action(self):
        with mock.patch('vectordrive.ui.text_columns_dialog.TextColumnsDialog.exec', return_value=0) as ex:
            self.win.A['text_table'].trigger()
        ex.assert_called_once()


class Window(unittest.TestCase):
    def dlg(self, spec=None, tools=((0, 'un'), (1, 'deux'))):
        from vectordrive.ui.main_window import ReferenceGrid
        from vectordrive.ui.text_columns_dialog import TextColumnsDialog
        return TextColumnsDialog(None, spec or line_spec(), list(tools), ReferenceGrid)

    def test_values_travel(self):
        d = self.dlg(table_spec(anchor=[0.5, 0.5], border_tool=1, borders='frame'))
        s = d.spec()
        self.assertEqual((s.method, s.anchor, s.border_tool, s.borders), ('table', [0.5, 0.5], 1, 'frame'))
        self.assertEqual(s.cells, [['a', 'b'], ['c', 'd']])
        d.deleteLater()

    def test_method_changes_what_can_be_set(self):
        d = self.dlg()
        self.assertTrue(d.point3.isEnabled())
        self.assertTrue(d.line_height.isEnabled())
        self.assertFalse(d.total_w.isEnabled())
        self.assertFalse(d.grid.isEnabled())
        d.by_table.setChecked(True)
        self.assertFalse(d.point3.isEnabled())
        self.assertTrue(d.total_w.isEnabled())
        self.assertTrue(d.grid.isEnabled())
        d.deleteLater()

    def test_table_drops_no_border(self):
        d = self.dlg(line_spec(borders='none'))
        self.assertEqual(d.borders.currentData(), 'none')
        d.by_table.setChecked(True)
        self.assertEqual(d.borders.currentData(), 'all')
        d.deleteLater()

    def test_same_width_greys_the_other_columns(self):
        d = self.dlg()
        self.assertTrue(d.table.cellWidget(0, d.C_WIDTH).isEnabled())
        self.assertFalse(d.table.cellWidget(1, d.C_WIDTH).isEnabled())
        d.same.setChecked(False)
        self.assertTrue(d.table.cellWidget(1, d.C_WIDTH).isEnabled())
        d.deleteLater()

    def test_table_width_comes_from_the_total(self):
        d = self.dlg(table_spec())
        self.assertFalse(d.table.cellWidget(0, d.C_WIDTH).isEnabled())
        d.deleteLater()

    def test_own_widths_grey_the_total(self):
        d = self.dlg(table_spec())
        self.assertTrue(d.total_w.isEnabled())
        d.same.setChecked(False)
        self.assertFalse(d.total_w.isEnabled())
        self.assertTrue(d.total_h.isEnabled())
        d.deleteLater()

    def test_more_columns_and_rows(self):
        d = self.dlg()
        d.cols.setValue(4)
        d.rows.setValue(5)
        self.assertEqual(d.table.rowCount(), 4)
        self.assertEqual(d.content.columnCount(), 4)
        self.assertEqual(d.content.rowCount(), 5)
        s = d.spec()
        self.assertEqual((s.cols, s.rows, len(s.columns)), (4, 5, 4))
        self.assertEqual(s.cells[0][0], 'a')
        d.deleteLater()

    def test_fewer_columns(self):
        d = self.dlg()
        d.cols.setValue(1)
        self.assertEqual(d.spec().cells[1], ['c'])
        d.deleteLater()

    def test_paste_grows_the_table(self):
        d = self.dlg()
        d.content.setCurrentCell(1, 1)
        d.paste('x\ty\tz\r\nu\tv\tw\r\n')
        self.assertEqual((d.rows.value(), d.cols.value()), (3, 4))
        self.assertEqual(d.spec().cells[2][3], 'w')
        self.assertEqual(d.spec().cells[1][1], 'x')
        d.deleteLater()

    def test_paste_nothing(self):
        d = self.dlg()
        d.paste('\n')
        self.assertEqual(d.rows.value(), 2)
        d.deleteLater()

    def test_ctrl_v(self):
        d = self.dlg()
        QApplication.clipboard().setText('k\tl')
        d.content.setCurrentCell(0, 0)
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(d.eventFilter(d.content, ev))
        self.assertEqual(d.spec().cells[0], ['k', 'l'])
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
