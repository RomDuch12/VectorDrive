"""Round 778 : texte dans une forme."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

from PySide6.QtWidgets import QApplication, QMessageBox
from shapely.geometry import Polygon

from vectordrive.core import text as TX
from vectordrive.core import textflow as TF
from vectordrive.core.document import Document, Group, Layer, Shape, Text
from vectordrive.core.geom import Affine, Path, circle, polyline, rect

FONT = 'VD Trait'
WORDS = 'Le texte coule dans une forme fermee ligne apres ligne sans jamais en sortir'


def spec(**kw):
    kw.setdefault('margin', 0.0)
    kw.setdefault('size', 4.0)
    kw.setdefault('align', 'left')
    kw.setdefault('middle', False)
    return TF.FlowSpec(**kw)


def boxes(got):
    out = []
    for ln in got.lines:
        b = TX.layout_bbox(ln.text, FONT, got.size, spacing=ln.spacing)
        out.append((b[0] + ln.x, b[1] + ln.y, b[2] + ln.x, b[3] + ln.y))
    return out


def inside(zone, b, tol=1e-6):
    return zone.buffer(tol).contains(Polygon([(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]))


class Flow(unittest.TestCase):
    def test_long_text_wraps(self):
        got = TF.flow(WORDS, FONT, Path([rect(0, 0, 60, 60)]), spec())
        self.assertGreater(len(got.lines), 1)
        self.assertEqual(got.rest, '')
        self.assertEqual(' '.join(ln.text for ln in got.lines), WORDS)

    def test_lines_go_downward(self):
        got = TF.flow(WORDS, FONT, Path([rect(0, 0, 60, 60)]), spec())
        ys = [ln.y for ln in got.lines]
        self.assertEqual(ys, sorted(ys, reverse=True))
        self.assertEqual(len(set(ys)), len(ys))

    def test_stays_in_a_rectangle(self):
        region = Path([rect(10, 20, 60, 40)])
        got = TF.flow(WORDS, FONT, region, spec())
        zone = TF.region_of(region)
        for b in boxes(got):
            self.assertTrue(inside(zone, b), b)

    def test_stays_in_a_circle(self):
        region = Path([circle((0, 0), 40)])
        got = TF.flow(WORDS, FONT, region, spec(align='center'))
        zone = TF.region_of(region)
        self.assertGreater(len(got.lines), 2)
        for b in boxes(got):
            self.assertTrue(inside(zone, b), b)

    def test_circle_lines_follow_the_width(self):
        got = TF.flow(' '.join(['mot'] * 80), FONT, Path([circle((0, 0), 40)]), spec(size=3.0, align='center'))
        counts = [len(ln.text) for ln in got.lines]
        self.assertGreater(max(counts), counts[0])
        self.assertGreater(max(counts), counts[-1])

    def test_hole_is_avoided(self):
        hole = rect(25, 25, 30, 30)
        region = Path([rect(0, 0, 80, 80), hole.reversed()])
        got = TF.flow(' '.join(['mot'] * 90), FONT, region, spec(size=3.0))
        square = Polygon(hole.flatten(0.1))
        self.assertGreater(len(got.lines), 10)
        for b in boxes(got):
            self.assertLess(square.intersection(Polygon([(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])])).area, 1e-6, b)

    def test_same_height_on_both_sides_of_a_hole(self):
        region = Path([rect(0, 0, 80, 80), rect(30, 0.5, 20, 79).reversed()])
        got = TF.flow(' '.join(['mot'] * 40), FONT, region, spec(size=3.0))
        ys = [ln.y for ln in got.lines]
        self.assertLess(len(set(ys)), len(ys))

    def test_concave_shape(self):
        u = Path([polyline([(0, 0), (60, 0), (60, 60), (40, 60), (40, 20), (20, 20), (20, 60), (0, 60)], True)])
        got = TF.flow(' '.join(['ab'] * 80), FONT, u, spec(size=3.0))
        zone = TF.region_of(u)
        self.assertGreater(len(got.lines), 5)
        for b in boxes(got):
            self.assertTrue(inside(zone, b), b)

    def test_margin_is_respected(self):
        region = Path([rect(0, 0, 60, 60)])
        got = TF.flow(WORDS, FONT, region, spec(margin=8.0))
        for b in boxes(got):
            self.assertGreaterEqual(b[0], 8.0 - 1e-6)
            self.assertLessEqual(b[2], 52.0 + 1e-6)
            self.assertLessEqual(b[3], 52.0 + 1e-6)

    def test_margin_eats_the_shape(self):
        with self.assertRaises(ValueError):
            TF.flow(WORDS, FONT, Path([rect(0, 0, 10, 10)]), spec(margin=6.0))

    def test_open_shape_refused(self):
        with self.assertRaises(ValueError):
            TF.flow(WORDS, FONT, Path([polyline([(0, 0), (50, 0)], False)]), spec())

    def test_alignments(self):
        region = Path([rect(0, 0, 100, 30)])
        left = TF.flow('mot', FONT, region, spec()).lines[0]
        mid = TF.flow('mot', FONT, region, spec(align='center')).lines[0]
        right = TF.flow('mot', FONT, region, spec(align='right')).lines[0]
        w = TX.line_widths('mot', FONT, 4.0)[0]
        self.assertAlmostEqual(mid.x, (100 - w) / 2, delta=0.02)
        self.assertAlmostEqual(right.x, 100 - w, delta=0.02)
        self.assertLess(left.x, mid.x)

    def test_justify_fills_the_line_but_the_last(self):
        region = Path([rect(0, 0, 60, 60)])
        got = TF.flow(WORDS, FONT, region, spec(align='justify'))
        spread = [ln for ln in got.lines if ln.spacing > 0]
        self.assertTrue(spread)
        for ln in spread:
            self.assertLessEqual(ln.spacing, 4.0 * TF.MAX_GAP)
            self.assertAlmostEqual(TX.line_widths(ln.text, FONT, 4.0, spacing=ln.spacing)[0], 60.0, delta=0.01)
        self.assertEqual(got.lines[-1].spacing, 0.0)

    def test_justify_stops_at_an_ugly_gap(self):
        got = TF.flow('un deux\nfin', FONT, Path([rect(0, 0, 100, 40)]), spec(align='justify'))
        self.assertEqual(got.lines[0].spacing, 0.0)

    def test_paragraphs(self):
        got = TF.flow('un\ndeux', FONT, Path([rect(0, 0, 100, 40)]), spec())
        self.assertEqual([ln.text for ln in got.lines], ['un', 'deux'])

    def test_blank_lines_and_spaces(self):
        got = TF.flow('  un   deux \n\n trois\n', FONT, Path([rect(0, 0, 100, 40)]), spec())
        self.assertEqual([ln.text for ln in got.lines], ['un deux', 'trois'])

    def test_empty_text(self):
        got = TF.flow('  \n ', FONT, Path([rect(0, 0, 100, 40)]), spec())
        self.assertEqual(got.lines, [])

    def test_missing_font(self):
        with mock.patch.object(TF.fonts, 'find_font', return_value=None):
            got = TF.flow('un', 'Police absente', Path([rect(0, 0, 100, 40)]), spec())
        self.assertEqual(got.lines, [])
        self.assertEqual(got.rest, 'un')

    def test_too_long_keeps_the_rest(self):
        region = Path([rect(0, 0, 30, 12)])
        got = TF.flow(WORDS, FONT, region, spec())
        self.assertTrue(got.rest)
        placed = ' '.join(ln.text for ln in got.lines)
        self.assertEqual(f'{placed} {got.rest}', WORDS)
        zone = TF.region_of(region)
        for b in boxes(got):
            self.assertTrue(inside(zone, b), b)

    def test_rest_keeps_paragraphs(self):
        got = TF.flow('un\ndeux\ntrois\nquatre', FONT, Path([rect(0, 0, 50, 12)]), spec(size=4.0, line_spacing=2.0))
        self.assertIn('\n', got.rest)

    def test_too_wide_word_is_not_forced(self):
        got = TF.flow('ANTICONSTITUTIONNELLEMENT', FONT, Path([rect(0, 0, 20, 40)]), spec())
        self.assertEqual(got.lines, [])
        self.assertEqual(got.rest, 'ANTICONSTITUTIONNELLEMENT')

    def test_top_of_shape_is_narrow(self):
        # triangle pointe en haut : la première ligne descend jusqu'à trouver la place de son premier mot
        tri = Path([polyline([(-40, 0), (40, 0), (0, 60)], True)])
        got = TF.flow('un mot puis un autre', FONT, tri, spec(size=3.0))
        zone = TF.region_of(tri)
        self.assertEqual(got.rest, '')
        for b in boxes(got):
            self.assertTrue(inside(zone, b), b)

    def test_fit_finds_the_largest_size(self):
        region = Path([rect(0, 0, 60, 60)])
        got = TF.flow(WORDS, FONT, region, spec(fit=True))
        self.assertEqual(got.rest, '')
        self.assertGreater(got.size, 4.0)
        bigger = TF.flow(WORDS, FONT, region, spec(size=got.size * 1.1))
        self.assertTrue(bigger.rest)

    def test_fit_stays_inside(self):
        region = Path([circle((0, 0), 30)])
        got = TF.flow(WORDS, FONT, region, spec(fit=True, align='center'))
        zone = TF.region_of(region)
        for b in boxes(got):
            self.assertTrue(inside(zone, b), b)

    def test_fit_too_small_a_shape(self):
        got = TF.flow(WORDS, FONT, Path([rect(0, 0, 0.5, 0.5)]), spec(fit=True))
        self.assertAlmostEqual(got.size, TF.MIN_SIZE)
        self.assertTrue(got.rest)

    def test_block_is_centred_in_height(self):
        region = Path([rect(0, 0, 80, 80)])
        got = TF.flow('un mot', FONT, region, spec(middle=True))
        b = boxes(got)[0]
        self.assertAlmostEqual(80 - b[3], b[1], delta=1.5)

    def test_block_on_top_otherwise(self):
        got = TF.flow('un mot', FONT, Path([rect(0, 0, 80, 80)]), spec(middle=False))
        self.assertAlmostEqual(boxes(got)[0][3], 80.0, delta=1.0)

    def test_centring_keeps_everything(self):
        got = TF.flow(WORDS, FONT, Path([circle((0, 0), 30)]), spec(middle=True, size=3.0))
        self.assertEqual(got.rest, '')

    def test_only_capitals_use_their_real_height(self):
        got = TF.flow('HH', FONT, Path([rect(0, 0, 80, 4.05)]), spec(size=4.0))
        self.assertEqual(len(got.lines), 1)
        low = TF.flow('Hg', FONT, Path([rect(0, 0, 80, 4.05)]), spec(size=4.0))
        self.assertEqual(low.lines, [])


class Build(unittest.TestCase):
    def test_group(self):
        g, got = TF.build(WORDS, FONT, Path([rect(0, 0, 60, 60)]), spec(), tool=3)
        self.assertIsInstance(g, Group)
        hidden = TF.region_child(g)
        self.assertFalse(hidden.visible)
        lines = [c for c in g.children if isinstance(c, Text)]
        self.assertEqual(len(lines), len(got.lines))
        self.assertTrue(all(t.tool == 3 and t.outline for t in lines))
        self.assertEqual(g.extra[TF.KEY]['text'], WORDS)

    def test_bbox_ignores_the_hidden_shape(self):
        g, _got = TF.build('un', FONT, Path([rect(0, 0, 60, 60)]), spec())
        box = g.bbox()
        self.assertLess(box[2] - box[0], 30)

    def test_nothing_placed(self):
        g, got = TF.build('ANTICONSTITUTIONNELLEMENT', FONT, Path([rect(0, 0, 20, 40)]), spec())
        self.assertIsNone(g)
        self.assertTrue(got.rest)

    def test_rebuild_after_a_move(self):
        g, _got = TF.build(WORDS, FONT, Path([rect(0, 0, 60, 60)]), spec())
        moved = g.transformed(Affine.translation(500, 0))
        new, _ = TF.rebuild(moved, 'autre chose', FONT, spec())
        self.assertGreaterEqual(new.bbox()[0], 500.0)
        self.assertEqual(new.extra[TF.KEY]['text'], 'autre chose')

    def test_spec_round_trip(self):
        s = TF.FlowSpec(size=2.0, fit=True, line_spacing=1.5, margin=3.0, align='right', middle=False)
        self.assertEqual(TF.FlowSpec.from_dict({**s.to_dict(), 'inconnu': 1}), s)

    def test_written_to_files(self):
        from vectordrive.io import native, registry, vnd
        g, _got = TF.build(WORDS, FONT, Path([rect(0, 0, 60, 60)]), spec())
        doc = Document(layers=[Layer(items=[g])])
        folder = tempfile.mkdtemp()
        vdz = os.path.join(folder, 'a.vdz')
        registry.save_document(doc, vdz)
        back = native.read(vdz)
        kept = back.layers[0].items[0]
        self.assertEqual(kept.extra[TF.KEY]['text'], WORDS)
        self.assertIsNotNone(TF.region_child(kept))
        path = os.path.join(folder, 'a.vnd')
        registry.save_document(doc, path)
        self.assertTrue(any(L.items for L in vnd.read(path).layers))
        svg_path = os.path.join(folder, 'a.svg')
        registry.save_document(doc, svg_path)
        with open(svg_path, encoding='utf-8') as fh:
            self.assertGreater(fh.read().count('<path'), 3)


class Command(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.close()

    def setUp(self):
        doc = self.win.canvas.doc
        doc.layers = [Layer(name='Plan 1')]
        doc.active = doc.layers[0].id
        self.form = Shape(path=Path([circle((100, 100), 40)]), tool=2)
        doc.layers[0].items = [self.form]
        self.win.canvas.select([self.form])

    def _params(self, **kw):
        d = {'text': WORDS, 'font': FONT, 'size': 4.0, 'fit': False, 'align': 'center', 'line_spacing': 1.2,
             'margin': 1.0, 'middle': True}
        d.update(kw)
        return d

    def test_ribbon(self):
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups() for b in g.buttons()
                 if b.defaultAction() is self.win.A['text_flow']]
        self.assertEqual(len(found), 1)

    def test_shape_stays_and_group_added(self):
        g = self.win.text_in_shape(self._params())
        items = self.win.canvas.doc.layers[0].items
        self.assertEqual(items, [self.form, g])
        self.assertEqual(self.win.canvas.selection, [g])
        self.assertEqual(g.tool, 2)
        self.assertIn('ligne', self.win.statusBar().currentMessage())

    def test_selected_text_is_used_and_replaced(self):
        t = Text(text='Texte choisi', font=FONT, size=3.0)
        self.win.canvas.doc.layers[0].items.append(t)
        self.win.canvas.select([self.form, t])
        p = self._params()
        del p['text'], p['font']
        g = self.win.text_in_shape(p)
        self.assertNotIn(t, self.win.canvas.doc.layers[0].items)
        self.assertEqual(g.extra[TF.KEY]['text'], 'Texte choisi')
        self.assertEqual(g.extra[TF.KEY]['font'], FONT)

    def test_dialog_is_filled_from_the_selected_text(self):
        t = Text(text='Texte choisi', font=FONT, size=3.0)
        self.win.canvas.doc.layers[0].items.append(t)
        self.win.canvas.select([self.form, t])
        from vectordrive.ui import textflow_dialog as D
        seen = {}

        def fake(dlg):
            seen.update(dlg.values())
            return 0
        with mock.patch.object(D.TextFlowDialog, 'exec', fake):
            self.assertIsNone(self.win.text_in_shape())
        self.assertEqual(seen['text'], 'Texte choisi')
        self.assertAlmostEqual(seen['size'], 3.0)

    def test_undo(self):
        self.win.text_in_shape(self._params())
        self.win.undo()
        self.assertEqual(len(self.win.canvas.doc.layers[0].items), 1)

    def test_rest_is_reported(self):
        self.form.path = Path([rect(0, 0, 30, 12)])
        self.win.text_in_shape(self._params(margin=0.0))
        self.assertIn('sans place', self.win.statusBar().currentMessage())

    def test_nothing_selected(self):
        self.win.canvas.select([])
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(self.win.text_in_shape(self._params()))
        info.assert_called_once()

    def test_open_shape_refused(self):
        self.form.path = Path([polyline([(0, 0), (50, 0)], False)])
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(self.win.text_in_shape(self._params()))
        info.assert_called_once()

    def test_margin_too_large(self):
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(self.win.text_in_shape(self._params(margin=100.0)))
        info.assert_called_once()

    def test_nothing_fits(self):
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(self.win.text_in_shape(self._params(text='ANTICONSTITUTIONNELLEMENT', size=30.0)))
        info.assert_called_once()
        self.assertEqual(len(self.win.canvas.doc.layers[0].items), 1)

    def test_empty_text_does_nothing(self):
        self.assertIsNone(self.win.text_in_shape(self._params(text='  ')))
        self.assertEqual(len(self.win.canvas.doc.layers[0].items), 1)

    def test_double_click_edits(self):
        g = self.win.text_in_shape(self._params())
        with mock.patch.object(self.win, 'text_flow_edit') as edit:
            self.win._item_double_clicked(g)
        edit.assert_called_once_with(g)

    def test_edit_changes_text(self):
        g = self.win.text_in_shape(self._params())
        new = self.win.text_flow_edit(g, {'text': 'Autre texte', 'size': 6.0})
        items = self.win.canvas.doc.layers[0].items
        self.assertIn(new, items)
        self.assertNotIn(g, items)
        self.assertEqual(new.extra[TF.KEY]['text'], 'Autre texte')
        self.assertAlmostEqual(new.extra[TF.KEY]['size'], 6.0)
        self.assertEqual(new.extra[TF.KEY]['align'], 'center')

    def test_edit_dialog_shows_the_settings(self):
        g = self.win.text_in_shape(self._params(align='right', fit=True))
        from vectordrive.ui import textflow_dialog as D
        seen = {}

        def fake(dlg):
            seen.update(dlg.values())
            seen['enabled'] = dlg.size.isEnabled()
            return 0
        with mock.patch.object(D.TextFlowDialog, 'exec', fake):
            self.assertIsNone(self.win.text_flow_edit(g))
        self.assertEqual(seen['text'], WORDS)
        self.assertEqual(seen['align'], 'right')
        self.assertFalse(seen['enabled'])

    def test_edit_undo(self):
        g = self.win.text_in_shape(self._params())
        self.win.text_flow_edit(g, {'text': 'Autre'})
        self.win.undo()
        kinds = [i.extra[TF.KEY]['text'] for i in self.win.canvas.doc.layers[0].items if isinstance(i, Group)]
        self.assertEqual(kinds, [WORDS])


if __name__ == '__main__':
    unittest.main()
