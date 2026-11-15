"""Round 812 : rapport d'imbrication."""
import json
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication
from pypdf import PdfReader

from vectordrive.core import nesting as N
from vectordrive.core import nest_report as NR
from vectordrive.core.document import Document, Layer, Plate, Shape
from vectordrive.core.geom import Path, circle, polyline, rect
from vectordrive.ui import nest_report as UI

app = QApplication.instance() or QApplication([])


def box(x, y, w, h=None):
    return Shape(path=Path([rect(x, y, w, h if h is not None else w)]))


def document(*layers, plate=None):
    doc = Document(layers=list(layers))
    doc.plate = plate or Plate(width=200.0, height=100.0, thickness=3.0)
    return doc


class Rows(unittest.TestCase):
    def test_plate_and_pieces(self):
        doc = document(Layer(name='A', items=[box(0, 0, 10), box(50, 0, 20)]))
        row = NR.plane_rows(doc)[0]
        self.assertEqual((row.name, row.width, row.height, row.thickness), ('A', 200.0, 100.0, 3.0))
        self.assertEqual(row.surface, 20000.0)
        self.assertEqual(row.pieces, 2)
        self.assertAlmostEqual(row.pieces_area, 500.0, places=3)
        self.assertAlmostEqual(row.cut_area, 500.0, places=3)
        self.assertAlmostEqual(row.cut_width, 70.0, places=6)
        self.assertAlmostEqual(row.cut_height, 20.0, places=6)
        self.assertAlmostEqual(row.filled, 0.025, places=6)

    def test_holes_are_matter_lost_but_fall_with_the_piece(self):
        ring = Shape(path=Path([rect(0, 0, 40, 40), rect(10, 10, 20, 20)]))
        row = NR.plane_rows(document(Layer(name='A', items=[ring])))[0]
        self.assertAlmostEqual(row.pieces_area, 1600 - 400, places=3)
        self.assertAlmostEqual(row.cut_area, 1600.0, places=3)

    def test_gap_counts_by_half(self):
        row = NR.plane_rows(document(Layer(name='A', items=[box(10, 10, 20)])), gap=4.0)[0]
        self.assertAlmostEqual(row.cut_width, 24.0, places=6)
        self.assertAlmostEqual(row.pieces_area, 400.0, places=3)
        self.assertGreater(row.cut_area, 400.0 + 4 * 20 * 2 - 0.01)
        self.assertLess(row.cut_area, 24 * 24 + 0.01)

    def test_one_row_per_filled_visible_plane(self):
        hidden = Layer(name='caché', items=[box(0, 0, 5)], visible=False)
        rows = NR.plane_rows(document(Layer(name='vide'), Layer(name='A', items=[box(0, 0, 5)]), hidden,
                                      Layer(name='B', items=[box(0, 0, 5)])))
        self.assertEqual([r.name for r in rows], ['A', 'B'])

    def test_open_curve_has_no_matter(self):
        line = Shape(path=Path([polyline([(0, 0), (30, 0)], False)]))
        row = NR.plane_rows(document(Layer(name='A', items=[line])))[0]
        self.assertEqual(row.pieces_area, 0.0)
        self.assertAlmostEqual(row.cut_width, 30.02, places=2)

    def test_circle(self):
        row = NR.plane_rows(document(Layer(name='A', items=[Shape(path=Path([circle((50, 50), 10)]))])))[0]
        self.assertAlmostEqual(row.pieces_area, math.pi * 100, delta=0.5)

    def test_no_plate(self):
        doc = document(Layer(name='A', items=[box(0, 0, 5)]))
        doc.plate = None
        row = NR.plane_rows(doc)[0]
        self.assertEqual((row.surface, row.filled), (0.0, 0.0))


class Remember(unittest.TestCase):
    def test_stays_json(self):
        doc = document(Layer(name='A'))
        items = [box(0, 0, 10)]
        res = N.nest(items, doc.plate, N.NestSpec(tries=3, both_ways=True))
        NR.remember(doc, N.NestSpec(tries=3, both_ways=True), res)
        kept = json.loads(json.dumps(doc.extra['imbrication']))
        self.assertEqual(kept['tries'], 3)
        self.assertEqual(kept['placed'], 1)

    def test_without_optimiser(self):
        doc = document(Layer(name='A'))
        res = N.nest([box(0, 0, 10)], doc.plate, N.NestSpec())
        NR.remember(doc, N.NestSpec(), res)
        self.assertNotIn('tries', doc.extra['imbrication'])


class Html(unittest.TestCase):
    def doc(self):
        d = document(Layer(name='Plan <1>', items=[box(0, 0, 10)]))
        NR.remember(d, N.NestSpec(gap=7.5), N.nest([box(0, 0, 10)], d.plate, N.NestSpec(gap=7.5)))
        return d

    def test_settings_and_plane(self):
        text = UI.build_html(self.doc(), 'x.vdz', 0.0)
        self.assertIn('7.5', text)
        self.assertIn('Plan &lt;1&gt;', text)
        self.assertIn('x.vdz', text)
        self.assertIn('page-break-before', text)

    def test_comment_is_escaped_and_keeps_its_lines(self):
        text = UI.build_html(self.doc(), 'x', 0.0, comment='a<b\nc')
        self.assertIn('a&lt;b<br>c', text)

    def test_no_nesting_yet(self):
        d = document(Layer(name='A', items=[box(0, 0, 10)]))
        text = UI.build_html(d, 'x', 0.0)
        self.assertIn('Pas d’imbrication', text.replace('&#x27;', "'"))

    def test_optimiser_lines(self):
        d = document(Layer(name='A', items=[box(0, 0, 10)]))
        spec = N.NestSpec(tries=2, both_ways=True)
        NR.remember(d, spec, N.nest([box(0, 0, 10)], d.plate, spec))
        self.assertTrue(any('Optimiseur' in a for a, _b in UI._settings_rows(d.extra['imbrication'])))

    def test_shape_settings_only_for_shapes(self):
        rows = UI._settings_rows({'shape': False, 'margin': 1, 'gap': 1})
        self.assertFalse(any(a.startswith('Forme') for a, _b in rows))
        rows = UI._settings_rows({'shape': True, 'margin': 1, 'gap': 1})
        self.assertTrue(any(a.startswith('Forme') for a, _b in rows))


class Drawing(unittest.TestCase):
    def test_lines_are_drawn(self):
        layer = Layer(name='A', items=[box(10, 10, 50)])
        img = UI.plane_image(document(layer), layer)
        self.assertEqual((img.width(), img.height()), (UI.IMAGE_W, UI.IMAGE_H))
        white = QColor('white').rgb()
        dark = sum(1 for x in range(0, img.width(), 1) for y in (img.height() // 2,) if img.pixel(x, y) != white)
        self.assertGreater(dark, 1)

    def test_empty_plane_stays_white(self):
        layer = Layer(name='A')
        doc = document(layer)
        doc.plate = None
        self.assertEqual(UI.plane_image(doc, layer).pixel(5, 5), QColor('white').rgb())


class Pdf(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = os.path.join(self.folder, 'r.pdf')

    def test_pages(self):
        doc = document(Layer(name='A', items=[box(0, 0, 10)]), Layer(name='B', items=[box(0, 0, 20)]))
        UI.write_pdf(self.path, doc, 'x', 0.0)
        reader = PdfReader(self.path)
        self.assertEqual(len(reader.pages), 3)

    def test_with_comment_and_image(self):
        pic = os.path.join(self.folder, 'p.png')
        img = QImage(40, 40, QImage.Format.Format_RGB32)
        img.fill(QColor('red'))
        img.save(pic)
        doc = document(Layer(name='A', items=[box(0, 0, 10)]))
        UI.write_pdf(self.path, doc, 'x', 0.0, 'mot', pic)
        self.assertGreaterEqual(len(PdfReader(self.path).pages), 2)

    def test_bad_image_is_left_out(self):
        doc = document(Layer(name='A', items=[box(0, 0, 10)]))
        UI.write_pdf(self.path, doc, 'x', 0.0, '', os.path.join(self.folder, 'absent.png'))
        self.assertGreaterEqual(len(PdfReader(self.path).pages), 2)

    def test_folder_that_does_not_exist(self):
        doc = document(Layer(name='A', items=[box(0, 0, 10)]))
        with self.assertRaises(OSError):
            UI.write_pdf(os.path.join(self.folder, 'non', 'r.pdf'), doc, 'x', 0.0)


class Command(unittest.TestCase):
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
        self.doc.layers[:] = [Layer(name='Plan 1')]
        self.doc.active = self.doc.layers[0].id
        self.doc.plate = Plate(width=100.0, height=100.0)
        self.doc.extra.pop('imbrication', None)
        self.win._undo.clear()
        self.path = os.path.join(tempfile.mkdtemp(), 'r.pdf')

    def test_nesting_keeps_its_settings(self):
        it = box(0, 0, 10)
        self.doc.layers[0].items.append(it)
        self.win.canvas.select([it])
        self.win.copy_nest({'spec': N.NestSpec(gap=3.0, counts=[3]), 'per_plane': True})
        self.assertEqual(self.doc.extra['imbrication']['gap'], 3.0)
        self.assertEqual(self.doc.extra['imbrication']['placed'], 3)

    def test_report_after_a_nesting_over_several_planes(self):
        it = box(0, 0, 60)
        self.doc.layers[0].items.append(it)
        self.win.canvas.select([it])
        self.win.copy_nest({'spec': N.NestSpec(counts=[3], allow_rotate=False), 'per_plane': True})
        self.assertEqual(len(self.doc.layers), 3)
        got = self.win.nest_report(self.path, {'comment': 'essai'}, open_it=False)
        self.assertEqual(got, self.path)
        self.assertEqual(len(PdfReader(self.path).pages), 4)

    def test_nothing_to_report(self):
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertIsNone(self.win.nest_report(self.path, {}, open_it=False))
        info.assert_called_once()
        self.assertFalse(os.path.exists(self.path))

    def test_write_refused_is_said(self):
        self.doc.layers[0].items.append(box(0, 0, 10))
        with mock.patch('vectordrive.ui.main_window.QMessageBox.warning') as warn:
            self.assertIsNone(self.win.nest_report(os.path.join(self.path, 'non', 'r.pdf'), {}, open_it=False))
        warn.assert_called_once()

    def test_abandoned_save_dialog(self):
        self.doc.layers[0].items.append(box(0, 0, 10))
        with mock.patch('vectordrive.ui.main_window.QFileDialog.getSaveFileName', return_value=('', '')):
            self.assertIsNone(self.win.nest_report(None, {}, open_it=False))

    def test_opens_when_asked(self):
        self.doc.layers[0].items.append(box(0, 0, 10))
        with mock.patch('PySide6.QtGui.QDesktopServices.openUrl') as opened:
            self.win.nest_report(self.path, {})
        opened.assert_called_once()

    def test_settings_travel_with_a_saved_document(self):
        from vectordrive.io import native
        it = box(0, 0, 10)
        self.doc.layers[0].items.append(it)
        self.win.canvas.select([it])
        self.win.copy_nest({'spec': N.NestSpec(gap=3.0, counts=[1]), 'per_plane': True})
        path = os.path.join(tempfile.mkdtemp(), 'a.vdz')
        native.write(self.doc, path)
        self.assertEqual(native.read(path).extra['imbrication']['gap'], 3.0)


if __name__ == '__main__':
    unittest.main()
