"""Round 823 : texte dans un rectangle : à la souris, F2 en chiffres, comprimé, centré, ressorts."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts
from vectordrive.core import text as TX
from vectordrive.core.document import Layer, Plate, Shape, Text
from vectordrive.core.geom import Path, rect

app = QApplication.instance() or QApplication([])
HAS_ARIAL = bool(fonts.find_font('Arial'))


def params(**kw):
    out = {'text': 'ABC', 'font': 'Arial', 'align': 'center', 'line_spacing': 1.2, 'stretch': False, 'compress': True}
    out.update(kw)
    return out


def boxed(s, box, **kw):
    t = Text(text=s, font='Arial', align='center')
    t.extra['box'] = dict({'x0': box[0], 'y0': box[1], 'x1': box[2], 'y1': box[3]}, **kw)
    t.outline = TX.outline_for(t)
    return t


@unittest.skipUnless(HAS_ARIAL, 'Arial absente')
class Fit(unittest.TestCase):
    def test_compress_keeps_the_height(self):
        wide = TX.fit_box('A', 'Arial', 100.0, 20.0, compress=True)
        long = TX.fit_box('ABCDEFGHIJKLMNOP', 'Arial', 100.0, 20.0, compress=True)
        self.assertAlmostEqual(long['size'], wide['size'])
        self.assertLess(long['width_ratio'], 1.0)
        self.assertEqual(wide['width_ratio'], 1.0)            # on comprime, on n'étire jamais

    def test_compressed_text_fills_the_width(self):
        t = boxed('ABCDEFGHIJKLMNOP', (0, 0, 100, 20), compress=True)
        bb = t.outline.bbox()
        self.assertLess(bb[2] - bb[0], 100.0)
        self.assertGreater(bb[2] - bb[0], 95.0)
        self.assertGreater(bb[0], -0.5)

    def test_without_compress_it_reduces_as_before(self):
        f = TX.fit_box('ABCDEFGHIJKLMNOP', 'Arial', 100.0, 20.0)
        self.assertEqual(f['width_ratio'], 1.0)
        self.assertLess(f['size'], TX.fit_box('ABCDEFGHIJKLMNOP', 'Arial', 100.0, 20.0, compress=True)['size'])

    def test_stretch_as_before(self):
        self.assertGreater(TX.fit_box('A', 'Arial', 100.0, 20.0, stretch=True)['width_ratio'], 1.0)

    def test_used_height(self):
        f = TX.fit_box('A', 'Arial', 100.0, 20.0, compress=True)
        self.assertAlmostEqual(f['used'], 20.0)
        self.assertLess(TX.fit_box('ABCDEFGHIJKLMNOP', 'Arial', 100.0, 20.0)['used'], 20.0)

    def test_empty(self):
        self.assertEqual(TX.fit_box('', 'Arial', 10.0, 10.0)['used'], 0.0)

    def test_middle_centres_in_height(self):
        top = boxed('ABCDEFGHIJKLMNOP', (0, 0, 100, 40))
        mid = boxed('ABCDEFGHIJKLMNOP', (0, 0, 100, 40), middle=True)
        a, b = top.outline.bbox(), mid.outline.bbox()
        self.assertLess(b[3], a[3])
        self.assertAlmostEqual(b[0], a[0])
        self.assertAlmostEqual((b[1] + b[3]) / 2, 20.0, delta=2.0)

    def test_springs_use_the_box_width(self):
        s = TX.SPRING
        t = boxed(f'A{s}B', (0, 0, 100, 20), compress=True)
        bb = t.outline.bbox()
        self.assertGreater(bb[2] - bb[0], 90.0)

    def test_old_boxes_are_unchanged(self):
        t = boxed('ABC', (0, 0, 100, 40))
        self.assertAlmostEqual(t.matrix.f, 40.0 - t.size)


class _Ev:
    def __init__(self, key=None):
        self.k = key

    def key(self):
        return self.k

    def modifiers(self):
        return Qt.KeyboardModifier.NoModifier


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
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()
        self.win.canvas.select([])
        self.win.set_tool('select')

    def tearDown(self):
        self.win.set_tool('select')


@unittest.skipUnless(HAS_ARIAL, 'Arial absente')
class Mouse(Base):
    def drag(self, a, b):
        tool = self.win.canvas.tool_obj
        tool.press(QPointF(0, 0), a, None)
        tool.move(QPointF(0, 0), b, None)
        tool.release(QPointF(0, 0), b, None)

    def test_no_selection_starts_the_tool(self):
        self.assertIsNone(self.win.text_in_box())
        self.assertEqual(type(self.win.canvas.tool_obj).__name__, 'DragRectTool')

    def test_drag_then_the_window(self):
        self.win.text_in_box()
        with mock.patch('vectordrive.ui.dialogs.BoxTextDialog.exec', return_value=1), \
                mock.patch('vectordrive.ui.dialogs.BoxTextDialog.values', return_value=params()):
            self.drag((10.0, 60.0), (70.0, 20.0))
        self.assertEqual(len(self.layer.items), 1)
        t = self.layer.items[0]
        self.assertEqual((t.extra['box']['x0'], t.extra['box']['y0'], t.extra['box']['x1'], t.extra['box']['y1']),
                         (10.0, 20.0, 70.0, 60.0))
        self.assertIsNone(self.win.canvas.tool_obj)

    def test_a_click_does_not_finish(self):
        self.win.text_in_box()
        tool = self.win.canvas.tool_obj
        self.drag((10.0, 60.0), (10.0, 60.0))
        self.assertIs(self.win.canvas.tool_obj, tool)
        self.assertEqual(self.layer.items, [])

    def test_escape_like_cancel_adds_nothing(self):
        self.win.text_in_box()
        tool = self.win.canvas.tool_obj
        tool.cancel()
        tool.release(QPointF(0, 0), (5.0, 5.0), None)
        self.assertEqual(self.layer.items, [])

    def test_cancelled_window_adds_nothing(self):
        self.win.text_in_box()
        with mock.patch('vectordrive.ui.dialogs.BoxTextDialog.exec', return_value=0):
            self.drag((10.0, 60.0), (70.0, 20.0))
        self.assertEqual(self.layer.items, [])

    def test_a_closed_shape_still_gives_the_rectangle(self):
        s = Shape(path=Path([rect(5, 5, 50, 20)]))
        self.layer.items.append(s)
        self.win.canvas.select([s])
        t = self.win.text_in_box(params=params())
        self.assertEqual(t.extra['box']['x1'], 55.0)
        self.assertIsNone(self.win.canvas.tool_obj)

    def test_the_action(self):
        self.win.A['text_box'].trigger()
        self.assertEqual(type(self.win.canvas.tool_obj).__name__, 'DragRectTool')

    def test_empty_text_adds_nothing(self):
        self.assertIsNone(self.win.text_in_box((0, 0, 10, 10), params(text=' ')))
        self.assertEqual(self.layer.items, [])

    def test_new_text_is_centred_in_height(self):
        t = self.win.text_in_box((0, 0, 100, 40), params(compress=False))
        self.assertTrue(t.extra['box']['middle'])


@unittest.skipUnless(HAS_ARIAL, 'Arial absente')
class Reopen(Base):
    def opened_with(self, t):
        seen = {}

        def fake(dlg):
            seen['fit'] = dlg.fit.currentData()
            return 1
        with mock.patch('vectordrive.ui.dialogs.BoxTextDialog.exec', fake):
            self.win.edit_text_box(t)
        return seen['fit']

    def test_old_box_stays_reduced(self):
        t = boxed('ABC', (0, 0, 50, 20))
        self.layer.items.append(t)
        self.assertEqual(self.opened_with(t), 'reduce')
        self.assertFalse(t.extra['box']['compress'])
        self.assertFalse(t.extra['box']['middle'])

    def test_new_box_stays_compressed_and_centred(self):
        t = self.win.text_in_box((0, 0, 50, 20), params())
        self.assertEqual(self.opened_with(t), 'compress')
        self.assertTrue(t.extra['box']['compress'])
        self.assertTrue(t.extra['box']['middle'])


class Numeric(Base):
    def run_with(self, point=(0.5, 0.5), x=50.0, y=30.0, w=40.0, h=10.0, accept=1):
        def fake(_dlg):
            ww, hh, grid, xx, yy = self.win.last_box_numeric
            ww.setValue(w)
            hh.setValue(h)
            grid.set_point(point)
            xx.setValue(x)
            yy.setValue(y)
            return accept
        with mock.patch('vectordrive.ui.main_window.QDialog.exec', fake):
            return self.win._text_box_numeric()

    def test_centre(self):
        self.assertEqual(self.run_with(), (30.0, 25.0, 70.0, 35.0))

    def test_top_left(self):
        self.assertEqual(self.run_with((0.0, 1.0)), (50.0, 20.0, 90.0, 30.0))

    def test_bottom_right(self):
        self.assertEqual(self.run_with((1.0, 0.0)), (10.0, 30.0, 50.0, 40.0))

    def test_cancel(self):
        self.assertIsNone(self.run_with(accept=0))

    def test_size_is_remembered(self):
        self.run_with(w=33.0, h=11.0)
        self.assertEqual(float(self.win.settings.value('texte/cadre_l')), 33.0)
        self.win.settings.remove('texte/cadre_l')
        self.win.settings.remove('texte/cadre_h')

    def test_f2_in_the_tool(self):
        self.win.text_in_box()
        tool = self.win.canvas.tool_obj
        self.assertTrue(tool.wants_key(_Ev(Qt.Key.Key_F2)))
        self.assertFalse(tool.wants_key(_Ev(Qt.Key.Key_A)))
        got = []
        tool.callback = got.append
        with mock.patch.object(tool, 'numeric', return_value=(1.0, 2.0, 3.0, 4.0)):
            self.assertTrue(tool.key(_Ev(Qt.Key.Key_F2)))
        self.assertEqual(got, [(1.0, 2.0, 3.0, 4.0)])

    def test_f2_cancelled_stays_in_the_tool(self):
        self.win.text_in_box()
        tool = self.win.canvas.tool_obj
        with mock.patch.object(tool, 'numeric', return_value=None):
            self.assertTrue(tool.key(_Ev(Qt.Key.Key_F2)))
        self.assertIs(self.win.canvas.tool_obj, tool)


class Window(unittest.TestCase):
    def dlg(self, **kw):
        from vectordrive.ui.dialogs import BoxTextDialog
        return BoxTextDialog(None, **kw)

    def test_compress_first(self):
        d = self.dlg()
        v = d.values()
        self.assertTrue(v['compress'])
        self.assertFalse(v['stretch'])
        d.deleteLater()

    def test_three_choices(self):
        d = self.dlg()
        d.fit.setCurrentIndex(d.fit.findData('reduce'))
        self.assertFalse(d.values()['compress'] or d.values()['stretch'])
        d.fit.setCurrentIndex(d.fit.findData('stretch'))
        self.assertTrue(d.values()['stretch'])
        d.deleteLater()

    def test_tab_is_a_spring(self):
        d = self.dlg(text='AB')
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
        self.assertTrue(d.eventFilter(d.text, ev))
        self.assertIn(TX.SPRING, d.text.toPlainText())
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
