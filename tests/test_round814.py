"""Round 814 : Multicopie : quantité et plans, départ, position, aller-retour, lignes de découpe, variables."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

from vectordrive.core import multicopy as MC
from vectordrive.core import text as TX
from vectordrive.core import variables as V
from vectordrive.core.document import Group, Layer, Plate, Shape, Text
from vectordrive.core.duplicate import fill_layout
from vectordrive.core.geom import Affine, Path, rect

app = QApplication.instance() or QApplication([])

BOX = (0.0, 0.0, 100.0, 100.0)
BB = (0.0, 0.0, 20.0, 10.0)


def box(x, y, w, h=None):
    return Shape(path=Path([rect(x, y, w, h if h is not None else w)]))


def spec(**kw):
    kw.setdefault('margin', 2.0)
    kw.setdefault('gap_x', 2.0)
    kw.setdefault('gap_y', 2.0)
    return MC.MultiSpec(**kw)


def lines(path):
    out = []
    for c in path.contours:
        a, b = c.segments[0].start, c.segments[-1].end
        out.append(tuple(round(v, 6) for v in (a[0], a[1], b[0], b[1])))
    return sorted(out)


class Grid(unittest.TestCase):
    def test_fills_like_before(self):
        lay = MC.layout(BB, BOX, spec())
        old = fill_layout(20.0, 10.0, BOX, 2.0, 2.0, 2.0)
        self.assertEqual((lay.cols, lay.rows), (old['cols'], old['rows']))
        self.assertEqual(len(lay.cells), old['cols'] * old['rows'])
        self.assertAlmostEqual(lay.ox, old['origin'][0])
        self.assertAlmostEqual(lay.oy, old['origin'][1])

    def test_nothing_fits(self):
        lay = MC.layout((0, 0, 200, 10), BOX, spec())
        self.assertEqual(lay.per_plate, 0)
        self.assertEqual(lay.cells, [])

    def test_exact_fit_counts(self):
        lay = MC.layout((0, 0, 47, 47), BOX, spec())
        self.assertEqual((lay.cols, lay.rows), (2, 2))

    def test_total_goes_on_to_new_planes(self):
        lay = MC.layout((0, 0, 40, 40), BOX, spec(total=7))
        self.assertEqual(lay.per_plate, 4)
        self.assertEqual(lay.plates, 2)
        self.assertEqual([c.plate for c in lay.cells], [0, 0, 0, 0, 1, 1, 1])

    def test_planes_multiply(self):
        lay = MC.layout((0, 0, 40, 40), BOX, spec(planes=3))
        self.assertEqual(len(lay.cells), 12)
        self.assertEqual(lay.plates, 3)

    def test_total_wins_over_planes(self):
        lay = MC.layout((0, 0, 40, 40), BOX, spec(planes=3, total=2))
        self.assertEqual(len(lay.cells), 2)

    def test_quarter_turn_only_if_more(self):
        narrow = (0, 0, 90, 10)
        plain = MC.layout(narrow, (0, 0, 100, 100), spec(margin=0.0))
        self.assertFalse(plain.turned)
        wide = MC.layout((0, 0, 60, 10), (0, 0, 70, 130), spec(margin=0.0, quarter_turn=True))
        self.assertTrue(wide.turned)
        self.assertEqual(wide.per_plate, 12)
        self.assertEqual((wide.w, wide.h), (10, 60))

    def test_nine_places(self):
        s = (0, 0, 20, 20)
        for place, (x, y) in {'haut_gauche': (2, 78), 'bas_droit': (78, 2), 'centre': (40, 40), 'haut_centre': (40, 78),
                              'milieu_droit': (78, 40), 'bas_gauche': (2, 2), 'bas_centre': (40, 2), 'haut_droit': (78, 78),
                              'milieu_gauche': (2, 40)}.items():
            lay = MC.layout(s, BOX, spec(place=place, total=1, gap_x=200.0, gap_y=200.0))
            self.assertEqual((lay.cols, lay.rows), (1, 1))
            self.assertAlmostEqual(lay.cells[0].x, x, msg=place)
            self.assertAlmostEqual(lay.cells[0].y, y, msg=place)
        self.assertEqual(len(MC.PLACES), 9)


class Order(unittest.TestCase):
    """Les numéros, d'après la figure du manuel : 1 2 3 / 4 5 6 / 7, puis 1 2 3 / 6 5 4 / 7 en optimisé."""

    def grid(self, **kw):
        lay = MC.layout((0, 0, 30, 30), BOX, spec(margin=0.0, gap_x=3.0, gap_y=3.0, total=7, **kw))
        self.assertEqual((lay.cols, lay.rows), (3, 3))
        return [(c.col, c.row) for c in lay.cells]

    def test_top_left(self):
        self.assertEqual(self.grid(), [(0, 2), (1, 2), (2, 2), (0, 1), (1, 1), (2, 1), (0, 0)])

    def test_optimised_comes_back(self):
        self.assertEqual(self.grid(optimised=True), [(0, 2), (1, 2), (2, 2), (2, 1), (1, 1), (0, 1), (0, 0)])

    def test_bottom_right(self):
        self.assertEqual(self.grid(start='bas_droit')[:4], [(2, 0), (1, 0), (0, 0), (2, 1)])

    def test_top_right_optimised(self):
        self.assertEqual(self.grid(start='haut_droit', optimised=True)[:4], [(2, 2), (1, 2), (0, 2), (0, 1)])

    def test_bottom_left(self):
        self.assertEqual(self.grid(start='bas_gauche')[:4], [(0, 0), (1, 0), (2, 0), (0, 1)])


class Selection(unittest.TestCase):
    def test_first_copy_stays_top_left(self):
        bb = (10, 70, 30, 90)
        lay = MC.layout(bb, BOX, spec(from_selection=True))
        c = lay.cells[0]
        self.assertAlmostEqual(c.x, 10)
        self.assertAlmostEqual(c.y, 70)
        self.assertEqual((lay.cols, lay.rows), (4, 4))
        self.assertAlmostEqual(lay.cells[1].x, 32)
        self.assertAlmostEqual(lay.cells[4].y, 48)
        self.assertGreaterEqual(min(k.y for k in lay.cells), 2.0)
        self.assertLessEqual(max(k.x for k in lay.cells) + 20, 98.0)

    def test_first_copy_stays_bottom_right(self):
        bb = (60, 10, 80, 30)
        lay = MC.layout(bb, BOX, spec(from_selection=True, start='bas_droit'))
        self.assertAlmostEqual(lay.cells[0].x, 60)
        self.assertAlmostEqual(lay.cells[0].y, 10)
        self.assertAlmostEqual(lay.cells[1].x, 38)

    def test_at_least_itself(self):
        lay = MC.layout((150, 150, 170, 170), BOX, spec(from_selection=True))
        self.assertEqual((lay.cols, lay.rows), (1, 1))


class Matrices(unittest.TestCase):
    def test_copies_land_in_their_cells(self):
        it = box(30, 40, 20, 10)
        res = MC.build([it], BOX, spec())
        lay = res.layout
        for c, copy in zip(lay.cells, res.planes[0]):
            bb = copy.bbox()
            self.assertAlmostEqual(bb[0], c.x)
            self.assertAlmostEqual(bb[1], c.y)
            self.assertAlmostEqual(bb[2], c.x + 20)
            self.assertAlmostEqual(bb[3], c.y + 10)

    def test_quarter_turn_stays_in_the_cell(self):
        res = MC.build([box(5, 5, 60, 10)], (0, 0, 70, 130), spec(margin=0.0, quarter_turn=True))
        lay = res.layout
        self.assertTrue(lay.turned)
        for c, copy in zip(lay.cells, res.planes[0]):
            bb = copy.bbox()
            self.assertAlmostEqual(bb[0], c.x)
            self.assertAlmostEqual(bb[1], c.y)
            self.assertAlmostEqual(bb[2], c.x + 10)
            self.assertAlmostEqual(bb[3], c.y + 60)

    def test_back_rows_turned_in_place(self):
        """Un trait décentré : retourné sur les rangées du retour, comme dans la figure du manuel."""
        it = Shape(path=Path([rect(0, 0, 30, 30), rect(1, 1, 4, 4)]))
        lay_spec = spec(margin=0.0, gap_x=3.0, gap_y=3.0, total=6, optimised=True, turn_back=True)
        res = MC.build([it], BOX, lay_spec)
        for c, copy in zip(res.layout.cells, res.planes[0]):
            bb = copy.bbox()
            self.assertAlmostEqual(bb[0], c.x)
            self.assertAlmostEqual(bb[1], c.y)
            mark = copy.path.contours[1].bbox() if hasattr(copy.path.contours[1], 'bbox') else None
            pts = [s.start for s in copy.path.contours[1].segments]
            mx = min(p[0] for p in pts) - c.x
            self.assertAlmostEqual(mx, 25.0 if c.back else 1.0, msg=str(mark))

    def test_turn_back_needs_optimised(self):
        it = box(0, 0, 30, 30)
        lay = MC.layout(it.bbox(), BOX, spec(margin=0.0, gap_x=3.0, gap_y=3.0, turn_back=True))
        self.assertFalse(any(c.back for c in lay.cells))


class Cuts(unittest.TestCase):
    """D'après la figure du manuel : les lignes entourent les cellules remplies, et elles seules."""

    def setUp(self):
        self.lay = MC.layout((0, 0, 30, 30), BOX, spec(margin=2.0, gap_x=2.0, gap_y=2.0))
        self.assertEqual((self.lay.cols, self.lay.rows), (3, 3))

    def all_cells(self):
        return [(c.col, c.row) for c in self.lay.cells]

    def test_none(self):
        self.assertIsNone(MC.cut_lines(self.lay, self.all_cells(), spec(), BOX))
        self.assertIsNone(MC.cut_lines(self.lay, [], spec(cuts='totale'), BOX))

    def test_total_merges_shared_edges(self):
        p = MC.cut_lines(self.lay, self.all_cells(), spec(cuts='totale'), BOX)
        self.assertEqual(len(p.contours), 8)                               # 4 à l'horizontale, 4 à la verticale
        got = lines(p)
        xs = sorted({g[0] for g in got if g[0] == g[2]})
        self.assertEqual(len(xs), 4)
        self.assertAlmostEqual(xs[1] - xs[0], 32.0)
        for a, b, c, d in got:
            self.assertTrue(a == c or b == d)
            self.assertGreaterEqual(min(a, c), 0.0)
            self.assertLessEqual(max(b, d), 100.0)

    def test_lines_run_in_the_middle_of_the_gap(self):
        p = MC.cut_lines(self.lay, self.all_cells(), spec(cuts='totale'), BOX)
        xs = sorted({g[0] for g in lines(p) if g[0] == g[2]})
        self.assertAlmostEqual(xs[1], self.lay.ox + 30 + 1.0)

    def test_empty_cells_get_no_line(self):
        """La figure : 1 _ 3 / 4 _ 6 / 7 8 _ : seules les cellules remplies ont leur cadre."""
        used = [(0, 2), (2, 2), (0, 1), (2, 1), (0, 0), (1, 0)]
        p = MC.cut_lines(self.lay, used, spec(cuts='totale'), BOX)
        got = lines(p)
        x = [self.lay.ox - 1 + k * 32 for k in range(4)]
        y = [self.lay.oy - 1 + k * 32 for k in range(4)]
        # le haut de la colonne du milieu est vide : pas de trait entre x1 et x2 tout en haut
        top = [g for g in got if g[1] == g[3] and abs(g[1] - y[3]) < 1e-6]
        self.assertEqual(len(top), 2)
        self.assertAlmostEqual(top[0][2], x[1])
        self.assertAlmostEqual(top[1][0], x[2])
        # la cellule en bas à droite est vide : la ligne du bas s'arrête en x2
        bottom = [g for g in got if g[1] == g[3] and abs(g[1] - y[0]) < 1e-6]
        self.assertEqual(len(bottom), 1)
        self.assertAlmostEqual(bottom[0][2], x[2])

    def test_lines_stay_on_the_plate(self):
        lay = MC.layout((0, 0, 50, 100), (0, 0, 100, 100), spec(margin=0.0, gap_x=0.0, gap_y=40.0))
        p = MC.cut_lines(lay, [(c.col, c.row) for c in lay.cells], spec(margin=0.0, gap_x=0.0, gap_y=40.0, cuts='totale'), (0, 0, 100, 100))
        for g in lines(p):
            self.assertGreaterEqual(min(g[1], g[3]), 0.0)
            self.assertLessEqual(max(g[1], g[3]), 100.0)

    def test_partial_makes_crosses_and_corners(self):
        p = MC.cut_lines(self.lay, self.all_cells(), spec(cuts='partielle', tick=3.0), BOX)
        got = lines(p)
        x = [self.lay.ox - 1 + k * 32 for k in range(4)]
        y = [self.lay.oy - 1 + k * 32 for k in range(4)]
        # croix au milieu, de 6 mm
        self.assertIn((round(x[1] - 3, 6), round(y[1], 6), round(x[1] + 3, 6), round(y[1], 6)), got)
        self.assertIn((round(x[1], 6), round(y[1] - 3, 6), round(x[1], 6), round(y[1] + 3, 6)), got)
        # coin bas gauche : un L, vers l'intérieur
        self.assertIn((round(x[0], 6), round(y[0], 6), round(x[0] + 3, 6), round(y[0], 6)), got)
        self.assertIn((round(x[0], 6), round(y[0], 6), round(x[0], 6), round(y[0] + 3, 6)), got)
        # 4 × 4 nœuds : 12 horizontaux bord compris, le tout sans doublon
        self.assertEqual(len(got), len(set(got)))
        self.assertEqual(len(got), 32)

    def test_partial_tick_is_limited_by_the_cell(self):
        p = MC.cut_lines(self.lay, self.all_cells(), spec(cuts='partielle', tick=500.0), BOX)
        for a, b, c, d in lines(p):
            self.assertLessEqual(abs(c - a) + abs(d - b), 32.0 + 1e-6)


class Build(unittest.TestCase):
    def test_empty_selection_box(self):
        res = MC.build([Shape()], BOX, spec())
        self.assertEqual(res.planes, [])

    def test_ignore_first_uses_it_for_the_size_only(self):
        frame = box(0, 0, 40, 40)
        mark = box(10, 10, 5, 5)
        res = MC.build([frame, mark], BOX, spec(ignore_first=True, total=4))
        self.assertEqual(len(res.planes[0]), 4)
        self.assertEqual((res.layout.w, res.layout.h), (40, 40))
        c = res.layout.cells[1]
        self.assertAlmostEqual(res.planes[0][1].bbox()[0], c.x + 10)

    def test_cuts_per_plate(self):
        res = MC.build([box(0, 0, 40, 40)], BOX, spec(total=5, cuts='totale'))
        self.assertEqual(len(res.cuts), 2)
        self.assertEqual(len(res.cuts[1].contours), 4)                     # une seule cellule sur le 2e plan

    def test_dress_says_which_are_empty(self):
        res = MC.build([box(0, 0, 40, 40)], BOX, spec(total=4, cuts='totale'), dress=lambda _c, n: n < 1)
        self.assertEqual(len(res.cuts[0].contours), 4)


class Rows(unittest.TestCase):
    def test_wanted(self):
        self.assertIsNone(MC.wanted(spec(), 0))
        self.assertEqual(MC.wanted(spec(), 5), 5)
        self.assertEqual(MC.wanted(spec(total=3), 5), 3)
        self.assertEqual(MC.wanted(spec(total=9), 5), 5)
        self.assertIsNone(MC.wanted(spec(limit_to_rows=False), 5))

    def test_uses_variables(self):
        t = Text(text='N° |A|', font='Arial', size=10.0)
        self.assertTrue(V.uses_variables([t]))
        self.assertTrue(V.uses_variables([Group(children=[t])]))
        self.assertFalse(V.uses_variables([Text(text='plain', font='Arial', size=10.0), box(0, 0, 5)]))


class Window(unittest.TestCase):
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
        self.doc.plate = Plate(width=100.0, height=100.0)
        self.doc.extra.pop('variables', None)
        self.win._undo.clear()

    def test_replaces_the_original(self):
        it = box(5, 5, 40)
        self.layer.items.append(it)
        self.win.canvas.select([it])
        res = self.win.fill_plate(spec())
        self.assertEqual(res.count, 4)
        self.assertEqual(len(self.layer.items), 4)
        self.assertFalse(any(x is it for x in self.layer.items))

    def test_total_includes_the_original_and_adds_planes(self):
        it = box(5, 5, 40)
        self.layer.items.append(it)
        self.win.canvas.select([it])
        res = self.win.fill_plate(spec(total=6))
        self.assertEqual(res.count, 6)
        self.assertEqual(len(self.doc.layers), 2)
        self.assertEqual([len(L.items) for L in self.doc.layers], [4, 2])

    def test_keep_original(self):
        it = box(5, 5, 40)
        self.layer.items.append(it)
        self.win.canvas.select([it])
        self.win.fill_plate(spec(total=3, keep_original=True))
        self.assertEqual(self.layer.items, [it])
        self.assertEqual(len(self.doc.layers), 2)
        self.assertEqual(len(self.doc.layers[1].items), 3)

    def test_no_selection_takes_the_active_layer(self):
        a, b, off, locked = box(0, 0, 10), box(12, 0, 10), box(30, 0, 10), box(50, 0, 10)
        off.visible = False
        locked.locked = True
        self.layer.items.extend([a, b, off, locked])
        self.win.canvas.select([])
        res = self.win.fill_plate(spec(total=2, keep_original=True))
        self.assertEqual(len(self.doc.layers[1].items), 4)
        self.assertEqual(res.layout.w, 22)

    def test_nothing_selected_at_all(self):
        self.win.canvas.select([])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertIsNone(self.win.fill_plate(spec()))
        info.assert_called_once()

    def test_too_big(self):
        it = box(5, 5, 500)
        self.layer.items.append(it)
        self.win.canvas.select([it])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            res = self.win.fill_plate(spec())
        info.assert_called_once()
        self.assertEqual(res.planes, [])
        self.assertEqual(self.layer.items, [it])

    def test_cut_lines_are_a_shape_of_their_colour(self):
        it = box(5, 5, 40)
        self.layer.items.append(it)
        self.win.canvas.select([it])
        res = self.win.fill_plate(spec(cuts='totale', cut_tool=1))
        self.assertEqual(len(self.layer.items), 5)
        cut = self.layer.items[-1]
        self.assertEqual(cut.tool, 1)
        self.assertEqual(len(cut.path.contours), 6)
        self.assertFalse(cut.path.contours[0].closed)
        self.assertEqual(len(self.win.canvas.selection), res.count)         # sélection : les exemplaires seuls

    def test_undo_restores(self):
        it = box(5, 5, 40)
        self.layer.items.append(it)
        self.win.canvas.select([it])
        self.win.fill_plate(spec(total=6, cuts='totale'))
        self.win.undo()
        self.assertEqual(len(self.win.canvas.doc.layers), 1)
        self.assertEqual(len(self.win.canvas.doc.layers[0].items), 1)

    def _text(self, tail='|Nom|'):
        t = Text(text=tail, font='Arial', size=10.0, matrix=Affine.translation(5, 5))
        t.outline = TX.outline_for(t)
        self.layer.items.append(t)
        self.win.canvas.select([t])
        return t

    def _rows(self, n):
        table = V.VarTable()
        table.add_variable('Nom', [f'P{k + 1}' for k in range(n)])
        V.store(self.doc, table)

    def test_one_copy_per_row(self):
        self._text()
        self._rows(3)
        res = self.win.fill_plate(spec())
        self.assertEqual(res.count, 3)
        self.assertEqual([t.text for t in res.planes[0]], ['P1', 'P2', 'P3'])

    def test_rows_spill_to_new_planes(self):
        self._text()
        self._rows(3)
        s = spec(total=2)
        res = self.win.fill_plate(s)
        self.assertEqual([t.text for t in res.planes[0]], ['P1', 'P2'])

    def test_without_the_limit_the_rest_is_blank_and_uncut(self):
        self._text()
        self._rows(2)
        res = self.win.fill_plate(spec(limit_to_rows=False, total=4, cuts='totale'))
        texts = [t.text for t in res.planes[0]]
        self.assertEqual(texts, ['P1', 'P2', '', ''])
        cells = {(c.col, c.row) for c in res.layout.cells[:2]}
        expected = MC.cut_lines(res.layout, cells, spec(cuts='totale'), (0, 0, 100, 100))
        self.assertEqual(lines(res.cuts[0]), lines(expected))

    def test_without_variables_the_table_is_ignored(self):
        it = box(5, 5, 40)
        self.layer.items.append(it)
        self._rows(1)
        self.win.canvas.select([it])
        self.assertEqual(self.win.fill_plate(spec()).count, 4)

    def test_settings_come_back(self):
        s = spec(total=7, planes=2, start='bas_droit', place='haut_centre', from_selection=True, optimised=True, turn_back=True,
                 quarter_turn=True, ignore_first=True, keep_original=True, limit_to_rows=False, cuts='partielle', cut_tool=1, tick=4.0)
        self.win._remember_multicopy(s)
        try:
            self.assertEqual(self.win._multicopy_spec(), s)
        finally:
            self.win.settings.remove('multicopie')

    def test_old_or_bad_settings_are_safe(self):
        self.win.settings.setValue('multicopie/depart', 'ailleurs')
        self.win.settings.setValue('multicopie/position', 'ailleurs')
        self.win.settings.setValue('multicopie/decoupe', 'ailleurs')
        try:
            s = self.win._multicopy_spec()
            self.assertEqual((s.start, s.place, s.cuts), ('haut_gauche', 'centre', 'aucune'))
        finally:
            self.win.settings.remove('multicopie')

    def test_the_action_opens_the_dialog(self):
        it = box(5, 5, 40)
        self.layer.items.append(it)
        self.win.canvas.select([it])
        with mock.patch('vectordrive.ui.multicopy_dialog.MulticopyDialog.exec', return_value=0) as ex:
            self.win.A['fill_plate'].trigger()
        ex.assert_called_once()
        self.assertEqual(self.layer.items, [it])


class Dialog(unittest.TestCase):
    def dlg(self, **kw):
        from vectordrive.ui.multicopy_dialog import MulticopyDialog
        return MulticopyDialog(None, (0, 0, 40, 40), BOX, spec(**kw), [(0, '1 — a'), (1, '2 — b')], kw.pop('rows', 0) if False else 0)

    def test_gives_back_what_it_got(self):
        s = spec(total=7, planes=2, start='bas_droit', place='haut_centre', optimised=True, turn_back=True, quarter_turn=True,
                 ignore_first=True, keep_original=True, cuts='partielle', cut_tool=1, tick=4.0)
        from vectordrive.ui.multicopy_dialog import MulticopyDialog
        d = MulticopyDialog(None, (0, 0, 40, 40), BOX, s, [(0, 'a'), (1, 'b')])
        self.assertEqual(d.result_spec(), s)
        d.deleteLater()

    def test_summary_and_preview(self):
        d = self.dlg(total=6)
        self.assertIn('6', d.summary.text())
        self.assertEqual((d.preview.lay.cols, d.preview.lay.rows), (2, 2))
        d.total.setValue(2)
        self.assertEqual(len(d.preview.lay.cells), 2)
        d.cuts.setCurrentIndex(d.cuts.findData('totale'))
        d.resize(800, 600)
        img = d.grab().toImage()
        self.assertGreater(img.width(), 100)
        d.deleteLater()

    def test_preview_paints_every_mode(self):
        for kw in ({'cuts': 'partielle'}, {'cuts': 'totale', 'optimised': True, 'turn_back': True}, {'margin': 500.0}):
            d = self.dlg(**kw)
            d.preview.resize(400, 300)
            self.assertFalse(d.preview.grab().toImage().isNull())
            d.deleteLater()

    def test_too_big_says_so(self):
        d = self.dlg(margin=500.0)
        self.assertEqual(d.preview.lay.cells, [])
        self.assertTrue(d.summary.text())
        d.deleteLater()

    def test_options_follow_each_other(self):
        d = self.dlg()
        self.assertFalse(d.turn_back.isEnabled())
        d.optimised.setChecked(True)
        self.assertTrue(d.turn_back.isEnabled())
        self.assertFalse(d.tick.isEnabled())
        d.cuts.setCurrentIndex(d.cuts.findData('partielle'))
        self.assertTrue(d.tick.isEnabled())
        d.from_sel.setChecked(True)
        self.assertFalse(d.place.isEnabled())
        d.deleteLater()

    def test_rows_shown_only_with_variables(self):
        from vectordrive.ui.multicopy_dialog import MulticopyDialog
        d = MulticopyDialog(None, (0, 0, 40, 40), BOX, spec(), [(0, 'a')], rows_count=3)
        self.assertEqual(len(d.preview.lay.cells), 3)
        d.limit.setChecked(False)
        self.assertEqual(len(d.preview.lay.cells), 4)
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
