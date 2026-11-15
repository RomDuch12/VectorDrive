"""Round 862 : aperçu du reste de matière, fenêtre et bon à tirer (manuel de TE, pages 690 à 695 imprimées)."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from shapely.geometry import Polygon, box

from vectordrive.cam import model as M
from vectordrive.core import geom
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.ui import rest_preview_dialog as RP

app = QApplication.instance() or QApplication([])

SQUARE = box(0, 0, 20, 20)
F4 = M.CamTool(name='F4', kind='droite', diameter=4.0, number=4)
F1 = M.CamTool(name='F1', kind='droite', diameter=1.0, number=1)
V = M.CamTool(name='V30', kind='conique', diameter=6.0, tip=0.2, angle=30.0, number=7)
L_SHAPE = Polygon([(0, 0), (40, 0), (40, 10), (10, 10), (10, 40), (0, 40)])


def dialog(region=SQUARE, tools=(F4, F1, V), **kw):
    return RP.RestPreviewDialog(None, region, list(tools), **kw)


def red(c):
    return c.red() > 180 and c.green() < 110 and c.blue() < 110


def count_red(image):
    return sum(1 for y in range(0, image.height(), 2) for x in range(0, image.width(), 2) if red(image.pixelColor(x, y)))


class TestTools(unittest.TestCase):

    def test_painter_path_keeps_holes(self):
        holed = box(0, 0, 10, 10).difference(box(4, 4, 6, 6))
        path = RP.painter_path(holed)
        self.assertFalse(path.contains(QPointF(5, 5)))
        self.assertTrue(path.contains(QPointF(2, 2)))

    def test_painter_path_of_several(self):
        path = RP.painter_path(box(0, 0, 1, 1).union(box(5, 5, 6, 6)))
        self.assertTrue(path.contains(QPointF(0.5, 0.5)))
        self.assertTrue(path.contains(QPointF(5.5, 5.5)))

    def test_painter_path_of_nothing(self):
        self.assertTrue(RP.painter_path(Polygon()).isEmpty())

    def test_thin_zones(self):
        thin = box(0, 0, 10, 0.2).union(box(20, 20, 25, 25))
        kept = RP.thick_only(thin, 0.5)
        self.assertLess(kept.area, 26.0)
        self.assertAlmostEqual(kept.area, 25.0, delta=0.1)
        self.assertIs(RP.thick_only(thin, 0.0), thin)


class TestDialog(unittest.TestCase):

    def test_all_tools(self):
        d = dialog()
        self.assertEqual(d.tool_list.count(), 3)
        self.assertEqual(d.tool().name, 'F4')
        d.done(0)

    def test_the_kind_filter(self):
        d = dialog()
        d.kinds.setCurrentIndex(d.kinds.findData('conique'))
        self.assertEqual(d.tool_list.count(), 1)
        self.assertEqual(d.tool().name, 'V30')
        d.done(0)

    def test_the_given_tool_is_chosen(self):
        d = dialog(tool=F1)
        self.assertEqual(d.tool().name, 'F1')
        d.done(0)

    def test_a_tool_of_the_library_joins(self):
        other = M.CamTool(name='Autre', diameter=3.0)
        d = dialog(tools=(F4,), tool=other)
        self.assertEqual(d.tool_list.count(), 2)
        self.assertEqual(d.tool().name, 'Autre')
        d.done(0)

    def test_the_corners_remain(self):
        d = dialog()
        expected = 4 * (4 - 3.14159265) * 4 / 4           # quatre coins de rayon 2 : (4 - pi) x r² au total
        self.assertAlmostEqual(d.rest.area, expected, delta=0.2)
        self.assertEqual(d.radius, 2.0)
        self.assertIn('%', d.info.text())
        d.done(0)

    def test_a_smaller_tool_leaves_less(self):
        d = dialog()
        was = d.rest.area
        d.tool_list.setCurrentRow(1)
        self.assertLess(d.rest.area, was)
        d.done(0)

    def test_the_allowance_widens_the_tool(self):
        d = dialog()
        d.stock.setValue(1.0)
        self.assertEqual(d.radius, 3.0)
        self.assertEqual((d.view.radius, d.view.outer), (2.0, 3.0))
        d.done(0)

    def test_the_depth_of_a_cone(self):
        d = dialog(tool=V)
        was = d.radius
        d.depth.setValue(1.0)
        self.assertGreater(d.radius, was)
        d.done(0)

    def test_the_ignored_thickness(self):
        d = dialog()
        was = d.rest.area
        d.thin.setValue(5.0)
        self.assertLess(d.rest.area, was)
        d.done(0)

    def test_everything_reached(self):
        d = dialog(region=box(0, 0, 20, 20).buffer(3), tools=(F1,))
        self.assertIn('vide tout', d.info.text())
        self.assertFalse(d.lay_button.isEnabled())
        d.done(0)

    def test_no_tool_of_this_kind(self):
        d = dialog(tools=())
        self.assertIsNone(d.tool())
        self.assertIsNone(d.rest)
        self.assertFalse(d.lay_button.isEnabled())
        d.done(0)

    def test_the_coordinates(self):
        d = dialog()
        d.view.resize(400, 400)
        d._moved(1.5, -2.25)
        self.assertEqual(d.coords.text(), 'X 1,500 ; Y -2,250')
        d.done(0)

    def test_lay_button_hidden_without_callback(self):
        d = dialog()
        self.assertTrue(d.lay_button.isHidden())
        d.done(0)

    def test_lay(self):
        got = []
        d = dialog(on_lay=lambda t, rest, r: got.append((t.name, rest.area > 0, r)) or 'posé')
        self.assertEqual(d.lay(), 'posé')
        self.assertEqual(d.laid, 'posé')
        self.assertEqual(got, [('F4', True, 2.0)])

    def test_lay_without_rest(self):
        d = dialog(region=box(0, 0, 20, 20).buffer(3), tools=(F1,), on_lay=lambda *_a: self.fail('rien à poser'))
        self.assertIsNone(d.lay())
        d.done(0)


class TestView(unittest.TestCase):

    def setUp(self):
        self.d = dialog(region=L_SHAPE, tools=(F4,))
        self.v = self.d.view
        self.v.resize(500, 500)

    def tearDown(self):
        self.d.done(0)

    def test_round_trip(self):
        p = self.v.to_px(12.0, 30.0)
        x, y = self.v.to_mm(p)
        self.assertAlmostEqual(x, 12.0, places=6)
        self.assertAlmostEqual(y, 30.0, places=6)

    def test_y_goes_up(self):
        self.assertLess(self.v.to_px(0, 40).y(), self.v.to_px(0, 0).y())

    def test_it_fits(self):
        for x, y in ((0, 0), (40, 40)):
            p = self.v.to_px(x, y)
            self.assertTrue(0 <= p.x() <= 500 and 0 <= p.y() <= 500)

    def test_the_zoom_keeps_the_point(self):
        before = self.v.to_px(30.0, 5.0)
        self.v.zoom_by(4.0, (30.0, 5.0))
        after = self.v.to_px(30.0, 5.0)
        self.assertAlmostEqual(before.x(), after.x(), places=4)
        self.assertAlmostEqual(before.y(), after.y(), places=4)
        self.assertEqual(self.v.zoom, 4.0)

    def test_fit_comes_back(self):
        was = self.v.to_px(30.0, 5.0)
        self.v.zoom_by(4.0, (10.0, 5.0))
        self.d.fit_button.click()
        self.assertEqual(self.v.zoom, 1.0)
        self.assertAlmostEqual(self.v.to_px(30.0, 5.0).x(), was.x(), places=6)

    def test_never_smaller_than_the_whole(self):
        self.v.zoom_by(0.1)
        self.assertEqual(self.v.zoom, 1.0)

    def test_the_mouse_gives_the_tool(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent
        got = []
        self.v.moved.connect(lambda x, y: got.append((x, y)))
        pos = self.v.to_px(5.0, 5.0)
        ev = QMouseEvent(QEvent.Type.MouseMove, pos, pos, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.v, ev)
        self.assertAlmostEqual(got[0][0], 5.0, places=6)
        self.assertAlmostEqual(self.v.at[1], 5.0, places=6)

    def test_the_rest_is_red(self):
        im = self.v.image(400)
        self.assertGreater(count_red(im), 0)
        self.d.tool_list.clearSelection()

    def test_a_tool_that_reaches_everything_shows_no_red(self):
        d = dialog(region=box(0, 0, 20, 20).buffer(3), tools=(F1,))
        d.view.resize(400, 400)
        self.assertEqual(count_red(d.view.image(400)), 0)
        d.done(0)

    def test_the_image_ignores_the_zoom(self):
        a = self.v.image(300).pixelColor(150, 150)
        self.v.zoom_by(8.0, (5.0, 5.0))
        self.assertEqual(self.v.image(300).pixelColor(150, 150), a)
        self.assertEqual(self.v.zoom, 8.0)

    def test_the_circles_at_the_cursor(self):
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtCore import QRectF
        im = QImage(500, 500, QImage.Format.Format_RGB32)
        self.v.at = (5.0, 20.0)
        p = QPainter(im)
        self.v.draw(p, QRectF(im.rect()))
        p.end()
        blue = sum(1 for y in range(0, 500, 2) for x in range(0, 500, 2) if im.pixelColor(x, y).blue() > 170 and im.pixelColor(x, y).red() < 120)
        self.assertGreater(blue, 0)

    def test_it_paints(self):
        self.v.grab()


class TestReport(unittest.TestCase):

    def test_the_text(self):
        d = dialog(tool=V, source='C:/x/a.vnd', depth=0.5, stock=0.1)
        t = d.report_html()
        for word in ('Bon à tirer', 'C:/x/a.vnd', 'T7 V30', '6,000 mm', '30°', '0,200 mm', '0,100 mm', '0,500 mm', d.started.strftime('%d/%m/%Y')):
            self.assertIn(word, t)
        d.done(0)

    def test_the_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'bat.pdf')
            d = dialog(region=L_SHAPE)
            with mock.patch('PySide6.QtGui.QDesktopServices.openUrl') as opened:
                self.assertEqual(d.print_report(p), p)
            opened.assert_not_called()
            data = pathlib.Path(p).read_bytes()
            self.assertTrue(data.startswith(b'%PDF'))
            self.assertGreater(len(data), 2000)
            d.done(0)

    def test_the_window_asks_and_shows(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'bat.pdf')
            d = dialog(region=L_SHAPE, source=os.path.join(td, 'piece.vnd'))
            seen = []

            def ask(_parent, _title, start, _filter):
                seen.append(os.path.basename(start))
                return p, ''
            with mock.patch.object(QFileDialog, 'getSaveFileName', ask), mock.patch.object(RP.QDesktopServices, 'openUrl') as opened:
                self.assertEqual(d.print_report(), p)
            self.assertEqual(seen, ['piece_Reste.pdf'])
            opened.assert_called_once()
            d.done(0)

    def test_cancel(self):
        d = dialog()
        with mock.patch.object(QFileDialog, 'getSaveFileName', return_value=('', '')):
            self.assertIsNone(d.print_report())
        d.done(0)

    def test_an_error_is_told(self):
        d = dialog()
        bad = os.path.join(tempfile.gettempdir(), 'pas_de_dossier_862', 'a.pdf')
        with mock.patch.object(QMessageBox, 'warning') as warn:
            self.assertIsNone(d.print_report(bad))
        warn.assert_called_once()
        d.done(0)


class TestWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()

    def setUp(self):
        w = self.win
        doc = w.canvas.doc
        self.s = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
        layer = Layer(name='Plan 1', items=[self.s])
        doc.layers[:] = [layer]
        doc.active = layer.id
        doc.plate = Plate(width=60.0, height=60.0)
        w.canvas.select([self.s])
        setup = w.cam_panel.setup()
        setup.tools[:] = [F4]
        setup.operations[:] = []
        w.cam_panel.save(setup)

    def test_the_window(self):
        d = self.win.rest_dialog(exec_dialog=False)
        self.assertEqual(d.tool().name, 'F4')
        self.assertFalse(d.lay_button.isHidden())
        d.done(0)

    def test_nothing_selected(self):
        self.win.canvas.select([])
        self.assertIsNone(self.win.rest_dialog(exec_dialog=False))
        self.assertIsNone(self.win.rest_preview())

    def test_lay_from_the_window(self):
        d = self.win.rest_dialog(exec_dialog=False)
        g = d.lay()
        self.assertEqual(len(g.children), 4)
        L = self.win.canvas.doc.layers[-1]
        self.assertTrue(L.extra.get('rest_preview'))
        self.assertIn(g, L.items)

    def test_the_action_returns_what_was_laid(self):
        def run(dlg):
            dlg.lay()
            return 1
        with mock.patch.object(RP.RestPreviewDialog, 'exec', run):
            g = self.win.rest_preview()
        self.assertEqual(len(g.children), 4)

    def test_without_window_as_before(self):
        g = self.win.rest_preview(F4)
        self.assertEqual(len(g.children), 4)


class TestForm(unittest.TestCase):

    def form(self, items=True):
        from vectordrive.core.document import Document
        from vectordrive.ui.cam_panel import FieldsDialog
        doc = Document()
        s = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
        doc.layers = [Layer(name='A', items=[s])]
        op = M.Operation(kind='poche', tool_id=F4.id, depth=0.3, stock=0.2, items=[s.id] if items else ['parti'])
        return FieldsDialog(None, 'x', op, doc=doc, tools=[F4, F1])

    def test_the_button(self):
        d = self.form()
        self.assertIsNotNone(d.rest_button)
        d.done(0)

    def test_it_takes_the_form(self):
        d = self.form()
        r = d.rest_preview(exec_dialog=False)
        self.assertEqual(r.tool().name, 'F4')
        self.assertEqual(r.depth.value(), 0.3)
        self.assertEqual(r.stock.value(), 0.2)
        self.assertTrue(r.lay_button.isHidden())
        self.assertAlmostEqual(r.radius, 2.2, places=6)
        r.done(0)
        d.done(0)

    def test_no_closed_shape(self):
        d = self.form(items=False)
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(d.rest_preview(exec_dialog=False))
        info.assert_called_once()
        d.done(0)


if __name__ == '__main__':
    unittest.main()
