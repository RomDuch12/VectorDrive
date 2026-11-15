"""Italique et souligné réglables : angle, position et épaisseur de la barre."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

from PySide6.QtWidgets import QApplication

from vectordrive.core import text as TX
from vectordrive.core.document import Text
from vectordrive.io import native
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])


def make(s='HH', **kw):
    t = Text(text=s, font='Arial', size=10.0, **kw)
    t.outline = TX.outline_for(t)
    return t


def bar(t):
    return t.outline.contours[-1].bbox()


class TestUnderline(unittest.TestCase):
    def outlined(self, value):
        t = make()
        t.extra['underline'] = value
        t.outline = TX.outline_for(t)
        return t

    def test_default_unchanged(self):
        _x0, y0, _x1, y1 = bar(self.outlined(True))
        self.assertAlmostEqual(y1, -1.5, places=6)                                      # 15 % de 10 mm
        self.assertAlmostEqual(y1 - y0, 0.7, places=6)

    def test_position(self):
        _x0, _y0, _x1, y1 = bar(self.outlined({'pos': 30.0, 'thick': 7.0}))
        self.assertAlmostEqual(y1, -3.0, places=6)

    def test_thickness(self):
        _x0, y0, _x1, y1 = bar(self.outlined({'pos': 15.0, 'thick': 20.0}))
        self.assertAlmostEqual(y1 - y0, 2.0, places=6)
        self.assertAlmostEqual(y1, -1.5, places=6)                                      # le haut de la barre ne bouge pas

    def test_through_the_letters(self):
        _x0, _y0, _x1, y1 = bar(self.outlined({'pos': -50.0, 'thick': 7.0}))
        self.assertAlmostEqual(y1, 5.0, places=6)                                       # barré, au milieu

    def test_bad_values_fall_back(self):
        for bad in ({'pos': 'x', 'thick': 7.0}, {'pos': float('nan'), 'thick': 7.0}, {'pos': 15.0, 'thick': 0.0},
                    {'pos': float('inf'), 'thick': 7.0}, {'pos': 15.0, 'thick': -3.0}, {'pos': None}):
            t = make()
            t.extra['underline'] = bad
            self.assertEqual(TX.underline_style(t), (TX.UNDERLINE_POS, TX.UNDERLINE_THICK), bad)

    def test_multi_line(self):
        t = make('HH\nHH')
        t.extra['underline'] = {'pos': 30.0, 'thick': 7.0}
        t.outline = TX.outline_for(t)
        self.assertEqual(len(t.outline.contours), 4 + 2)

    def test_in_a_file(self):
        t = self.outlined({'pos': 30.0, 'thick': 20.0})
        self.assertEqual(TX.text_format(t)['extra']['underline'], {'pos': 30.0, 'thick': 20.0})


class TestWindow(unittest.TestCase):
    def setUp(self):
        self.w = MainWindow()
        self.t = make()
        self.w.canvas.doc.layers[0].items[:] = [self.t]
        self.w.canvas.invalidate()
        self.w.canvas.select([self.t])

    def tearDown(self):
        self.w.settings.remove('cad/text_style')
        self.w.modified = False
        self.w.close()

    def set(self, **kw):
        p = dict(italic=0.0, underline=False, pos=15.0, thick=7.0)
        p.update(kw)
        return self.w.text_style_options(params=p)

    def test_angle(self):
        self.set(italic=20.0)
        self.assertEqual(self.t.extra['italic'], 20.0)
        straight = make().outline.bbox()
        slanted = self.t.outline.bbox()
        self.assertAlmostEqual(slanted[2] - straight[2], math.tan(math.radians(20)) * (straight[3]), places=4)

    def test_backward_slant(self):
        self.set(italic=-10.0)
        self.assertLess(self.t.outline.bbox()[0], make().outline.bbox()[0])

    def test_zero_is_straight(self):
        self.t.extra['italic'] = 12.0
        self.set(italic=0.0)
        self.assertNotIn('italic', self.t.extra)

    def test_angle_limited(self):
        self.set(italic=89.9)
        self.assertEqual(self.t.extra['italic'], TX.ITALIC_MAX)
        self.set(italic=-400.0)
        self.assertEqual(self.t.extra['italic'], -TX.ITALIC_MAX)

    def test_underline_settings(self):
        self.set(underline=True, pos=30.0, thick=20.0)
        self.assertEqual(self.t.extra['underline'], {'pos': 30.0, 'thick': 20.0})
        self.assertAlmostEqual(self.t.outline.contours[-1].bbox()[3], -3.0, places=6)

    def test_factory_values_stay_plain(self):
        self.set(underline=True)
        self.assertIs(self.t.extra['underline'], True)

    def test_no_underline(self):
        self.t.extra['underline'] = True
        self.set(underline=False)
        self.assertNotIn('underline', self.t.extra)

    def test_thickness_limited(self):
        self.set(underline=True, thick=0.0)
        self.assertEqual(self.t.extra['underline']['thick'], 0.5)

    def test_several_texts(self):
        other = make('A')
        self.w.canvas.doc.layers[0].items.append(other)
        self.w.canvas.select([self.t, other])
        self.assertEqual(len(self.set(italic=5.0)), 2)
        self.assertEqual(other.extra['italic'], 5.0)

    def test_undo(self):
        self.set(italic=20.0, underline=True, pos=30.0)
        self.w.undo()
        item = self.w.canvas.doc.layers[0].items[0]
        self.assertNotIn('italic', item.extra)
        self.assertNotIn('underline', item.extra)

    def test_no_text(self):
        self.w.canvas.select([])
        self.assertEqual(self.set(italic=20.0), [])

    def test_buttons_use_the_last_settings(self):
        self.w.settings.setValue('cad/text_style', {'italic': 25.0, 'underline': True, 'pos': 30.0, 'thick': 20.0})
        self.w.toggle_text_style('italic')
        self.assertEqual(self.t.extra['italic'], 25.0)
        self.w.toggle_text_style('underline')
        self.assertEqual(self.t.extra['underline'], {'pos': 30.0, 'thick': 20.0})

    def test_buttons_factory_values(self):
        self.w.toggle_text_style('italic')
        self.assertEqual(self.t.extra['italic'], 12.0)
        self.w.toggle_text_style('underline')
        self.assertIs(self.t.extra['underline'], True)

    def test_buttons_with_a_last_straight_setting(self):
        self.w.settings.setValue('cad/text_style', {'italic': 0.0, 'underline': False, 'pos': 15.0, 'thick': 7.0})
        self.w.toggle_text_style('italic')
        self.assertEqual(self.t.extra['italic'], 12.0)                                  # le bouton penche toujours

    def test_saved_in_the_file(self):
        self.set(italic=20.0, underline=True, pos=30.0, thick=20.0)
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'a.vdz')
            native.write(self.w.canvas.doc, p)
            back = native.read(p)
        t = next(iter(back.iter_leaves()))
        self.assertEqual(t.extra['underline'], {'pos': 30.0, 'thick': 20.0})
        self.assertEqual(t.extra['italic'], 20.0)

    def test_in_the_ribbon(self):
        a = self.w.A['text_style_options']
        pages = [self.w.ribbon.page(i) for i in range(self.w.ribbon.count())]
        n = sum(1 for page in pages if page for g in page.groups() for b in g.buttons() if b.defaultAction() is a)
        self.assertEqual(n, 1)


if __name__ == '__main__':
    unittest.main()
