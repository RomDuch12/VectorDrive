"""Round 774 : tampon : format du support, formats enregistrés, forme de la découpe."""
import json
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

from PySide6.QtWidgets import QApplication

from vectordrive.core import pathops
from vectordrive.core import stamp as S
from vectordrive.core.document import Layer, Shape
from vectordrive.core.geom import Affine, Path, rect


def art(w=40.0, h=10.0, x=100.0, y=100.0):
    return Path([rect(x, y, w, h)])


def shape(w=40.0, h=10.0, x=100.0, y=100.0):
    return Shape(path=art(w, h, x, y))


def size(path):
    b = path.bbox()
    return b[2] - b[0], b[3] - b[1]


def center(path):
    b = path.bbox()
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def child(g, name):
    return next(c for c in g.children if c.name == name)


class Support(unittest.TestCase):
    def test_auto_is_as_before(self):
        f = S.frame_of(art(), S.StampSpec(margin=2, radius=0))
        self.assertEqual(size(f), (44.0, 14.0))

    def test_rectangle_format(self):
        f = S.frame_of(art(), S.StampSpec(support='rect', width=60, height=30))
        w, h = size(f)
        self.assertAlmostEqual(w, 60.0)
        self.assertAlmostEqual(h, 30.0)
        self.assertEqual(center(f), center(art()))

    def test_circle_ignores_height(self):
        f = S.frame_of(art(), S.StampSpec(support='cercle', width=50, height=7))
        w, h = size(f)
        self.assertAlmostEqual(w, 50.0, places=3)
        self.assertAlmostEqual(h, 50.0, places=3)

    def test_ellipse(self):
        f = S.frame_of(art(), S.StampSpec(support='ellipse', width=75, height=50))
        w, h = size(f)
        self.assertAlmostEqual(w, 75.0, places=3)
        self.assertAlmostEqual(h, 50.0, places=3)

    def test_rect_radius_kept_and_limited(self):
        s = S.StampSpec(support='rect', width=20, height=10, radius=500.0)
        self.assertAlmostEqual(pathops.area(S.frame_of(art(), s)), math.pi * 25 + 10 * 10, delta=0.5)

    def test_null_format_stays_valid(self):
        f = S.frame_of(art(), S.StampSpec(support='rect', width=0, height=-3))
        self.assertGreater(size(f)[0], 0.0)
        self.assertGreater(size(f)[1], 0.0)

    def test_presets_are_well_formed(self):
        for name, kind, w, h in S.SUPPORTS:
            self.assertIn(kind, S.SUPPORT_KINDS[1:], name)
            self.assertGreater(w, 0.0)
            self.assertGreater(h, 0.0)
            if kind == 'cercle':
                self.assertEqual(w, h)
        self.assertEqual(len({f[0] for f in S.SUPPORTS}), len(S.SUPPORTS))


class Fit(unittest.TestCase):
    def test_scale_up_to_width(self):
        p = S.placed_source(art(40, 10), S.StampSpec(support='rect', width=60, height=40, margin=2))
        w, h = size(p)
        self.assertAlmostEqual(w, 56.0, places=6)
        self.assertAlmostEqual(h, 14.0, places=6)

    def test_scale_down_to_height(self):
        p = S.placed_source(art(40, 40), S.StampSpec(support='rect', width=60, height=20, margin=1))
        self.assertAlmostEqual(size(p)[1], 18.0, places=6)

    def test_center_stays(self):
        src = art()
        p = S.placed_source(src, S.StampSpec(support='rect', width=60, height=40))
        self.assertAlmostEqual(center(p)[0], center(src)[0], places=6)
        self.assertAlmostEqual(center(p)[1], center(src)[1], places=6)

    def test_no_fit_keeps_the_size(self):
        src = art()
        self.assertIs(S.placed_source(src, S.StampSpec(support='rect', width=60, height=40, fit=False)), src)

    def test_auto_never_scales(self):
        src = art()
        self.assertIs(S.placed_source(src, S.StampSpec()), src)

    def test_circle_judged_on_the_drawing(self):
        spec = S.StampSpec(support='cercle', width=50, margin=1)
        p = S.placed_source(art(30, 30), spec)                    # un carré : ses coins touchent le cercle
        cx, cy = center(p)
        far = max(math.hypot(x - cx, y - cy) for x, y in p.contours[0].flatten(0.01))
        self.assertAlmostEqual(far, 24.0, delta=0.01)

    def test_ellipse_judged_on_the_drawing(self):
        spec = S.StampSpec(support='ellipse', width=80, height=40, margin=0)
        p = S.placed_source(art(30, 30), spec)
        cx, cy = center(p)
        far = max(((x - cx) / 40) ** 2 + ((y - cy) / 20) ** 2 for x, y in p.contours[0].flatten(0.01))
        self.assertAlmostEqual(far, 1.0, delta=0.002)

    def test_margin_larger_than_the_support(self):
        src = art()
        self.assertEqual(S.fit_scale(src, S.StampSpec(support='rect', width=10, height=10, margin=50)), 1.0)

    def test_flat_drawing(self):
        s = Path([rect(0, 0, 10, 0.0)])
        self.assertGreater(S.fit_scale(s, S.StampSpec(support='rect', width=20, height=20)), 0.0)

    def test_overflow_reported(self):
        self.assertTrue(S.overflows(art(200, 10), S.StampSpec(support='rect', width=60, height=40, fit=False)))
        self.assertFalse(S.overflows(art(200, 10), S.StampSpec(support='rect', width=60, height=40, fit=True)))
        self.assertFalse(S.overflows(art(20, 10), S.StampSpec(support='rect', width=60, height=40, fit=False)))
        self.assertFalse(S.overflows(art(200, 10), S.StampSpec()))


class Cut(unittest.TestCase):
    def test_support_by_default(self):
        s = S.StampSpec(support='rect', width=60, height=40, radius=0)
        self.assertEqual(size(S.cut_path(art(), S.frame_of(art(), s), s)), (60.0, 40.0))

    def test_support_with_offset(self):
        s = S.StampSpec(support='rect', width=60, height=40, radius=0, cut_offset=2)
        w, h = size(S.cut_path(art(), S.frame_of(art(), s), s))
        self.assertAlmostEqual(w, 64.0, places=3)
        self.assertAlmostEqual(h, 44.0, places=3)

    def test_rectangle(self):
        s = S.StampSpec(cut='rectangle', cut_offset=1)
        w, h = size(S.cut_path(art(40, 10), S.frame_of(art(40, 10), s), s))
        self.assertAlmostEqual(w, 42.0)
        self.assertAlmostEqual(h, 12.0)

    def test_optimised_follows_the_objects(self):
        two = Path([rect(0, 0, 10, 10), rect(20, 0, 10, 10)])
        s = S.StampSpec(cut='optimise', cut_offset=1)
        got = S.cut_path(two, S.frame_of(two, s), s)
        self.assertEqual(len(got.contours), 2)
        self.assertLess(pathops.area(got), 30 * 12)

    def test_optimised_has_no_holes(self):
        ring = Path([rect(0, 0, 30, 30), rect(10, 10, 10, 10).reversed()])
        s = S.StampSpec(cut='optimise', cut_offset=1)
        got = S.cut_path(ring, S.frame_of(ring, s), s)
        self.assertEqual(len(got.contours), 1)

    def test_optimised_without_offset(self):
        s = S.StampSpec(cut='optimise')
        got = S.cut_path(art(), S.frame_of(art(), s), s)
        self.assertEqual(size(got), (40.0, 10.0))

    def test_merged_boxes_one_per_line(self):
        two_lines = Path([rect(0, 0, 10, 5), rect(12, 1, 5, 3), rect(0, 20, 30, 5)])
        s = S.StampSpec(cut='boites', cut_offset=1)
        got = S.cut_path(two_lines, S.frame_of(two_lines, s), s)
        self.assertEqual(len(got.contours), 2)
        self.assertAlmostEqual(pathops.area(got), 19 * 7 + 32 * 7, delta=0.01)

    def test_merged_boxes_touch_when_close(self):
        close = Path([rect(0, 0, 10, 5), rect(0, 6, 10, 5)])
        s = S.StampSpec(cut='boites', cut_offset=1)
        self.assertEqual(len(S.cut_path(close, S.frame_of(close, s), s).contours), 1)

    def test_negative_offset_cannot_invert_the_rectangle(self):
        s = S.StampSpec(cut='rectangle', cut_offset=-100)
        w, h = size(S.cut_path(art(), S.frame_of(art(), s), s))
        self.assertGreater(w, 0.0)
        self.assertGreater(h, 0.0)


class Build(unittest.TestCase):
    def test_build_on_a_format(self):
        g = S.build([shape()], S.StampSpec(support='cercle', width=50, margin=2, border=1, mirror=False))
        self.assertEqual(g.extra['stamp']['support'], 'cercle')
        w, h = size(child(g, 'Découpe').path)
        self.assertAlmostEqual(w, 50.0, places=3)
        self.assertAlmostEqual(h, 50.0, places=3)

    def test_zone_inside_the_support(self):
        g = S.build([shape()], S.StampSpec(support='ellipse', width=75, height=50, margin=2, border=1, mirror=False))
        z = child(g, 'Zone à graver').path
        self.assertLessEqual(size(z)[0], 75.0)
        self.assertGreater(pathops.area(z), 0.0)

    def test_source_keeps_the_original_size(self):
        g = S.build([shape()], S.StampSpec(support='rect', width=120, height=60))
        src = next(c for c in g.children if c.extra.get('stamp_source'))
        self.assertEqual(size(src.path), (40.0, 10.0))

    def test_change_format_on_edit(self):
        g = S.build([shape()], S.StampSpec(support='rect', width=120, height=60, mirror=False))
        g2 = S.rebuild(g, S.StampSpec(support='cercle', width=30, mirror=False))
        self.assertAlmostEqual(size(child(g2, 'Découpe').path)[0], 30.0, places=3)

    def test_mirror_on_the_support(self):
        g = S.build([shape()], S.StampSpec(support='rect', width=120, height=60, mirror=True, radius=0))
        self.assertAlmostEqual(center(child(g, 'Découpe').path)[0], center(art())[0], places=6)

    def test_cut_kind_in_the_result(self):
        g = S.build([shape()], S.StampSpec(cut='rectangle', cut_offset=1, mirror=False))
        self.assertEqual(size(child(g, 'Découpe').path), (42.0, 12.0))

    def test_old_settings_still_read(self):
        s = S.StampSpec.from_dict({'margin': 3.0, 'radius': 1.0, 'border': 0.8, 'shoulder': 0.0, 'mirror': True,
                                   'negative': True, 'hatch': 0.0})
        self.assertEqual(s.support, 'auto')
        self.assertEqual(s.cut, 'support')
        g = S.build([shape()], s)
        w, h = size(child(g, 'Découpe').path)
        self.assertAlmostEqual(w, 46.0, places=6)
        self.assertAlmostEqual(h, 16.0, places=6)

    def test_moved_stamp_rebuilds_in_place(self):
        g = S.build([shape()], S.StampSpec(support='rect', width=60, height=40, mirror=False))
        g2 = S.rebuild(g.transformed(Affine.translation(30, 0)), S.StampSpec(support='rect', width=60, height=40, mirror=False))
        self.assertAlmostEqual(center(child(g2, 'Découpe').path)[0], center(art())[0] + 30.0, places=6)


class Dialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dlg(self, spec=None, saved=None):
        from vectordrive.ui.stamp_dialog import StampDialog
        return StampDialog(None, spec or S.StampSpec(), saved)

    def test_auto_disables_the_format(self):
        d = self._dlg()
        self.assertFalse(d.width.isEnabled())
        self.assertFalse(d.format.isEnabled())
        d.kind.setCurrentIndex(d.kind.findData('rect'))
        self.assertTrue(d.width.isEnabled())
        self.assertTrue(d.height.isEnabled())

    def test_circle_height_follows_width(self):
        d = self._dlg()
        d.kind.setCurrentIndex(d.kind.findData('cercle'))
        self.assertFalse(d.height.isEnabled())
        self.assertFalse(d.radius.isEnabled())
        d.width.setValue(33.0)
        self.assertEqual(d.height.value(), 33.0)
        self.assertEqual(d.result_params().height, 33.0)

    def test_choosing_a_format(self):
        d = self._dlg(S.StampSpec(support='rect'))
        i = d.format.findText('47 × 18')
        d.format.setCurrentIndex(i)
        d.format.activated.emit(i)
        spec = d.result_params()
        self.assertEqual((spec.support, spec.width, spec.height), ('rect', 47.0, 18.0))

    def test_choosing_a_round_format(self):
        d = self._dlg(S.StampSpec(support='rect'))
        i = d.format.findText('ø 40')
        d.format.setCurrentIndex(i)
        d.format.activated.emit(i)
        self.assertEqual(d.result_params().support, 'cercle')
        self.assertEqual(d.result_params().width, 40.0)

    def test_custom_entry_changes_nothing(self):
        d = self._dlg(S.StampSpec(support='rect', width=12.0, height=34.0))
        d.format.setCurrentIndex(0)
        d.format.activated.emit(0)
        self.assertEqual(d.result_params().width, 12.0)

    def test_save_format(self):
        d = self._dlg(S.StampSpec(support='rect', width=12.0, height=34.0))
        d.name.setText('Mon format')
        self.assertTrue(d.save_format())
        self.assertEqual(d.saved, [('Mon format', 'rect', 12.0, 34.0)])
        self.assertGreater(d.format.findText('Mon format'), 0)
        self.assertEqual(d.format.currentText(), 'Mon format')

    def test_save_replaces_same_name(self):
        d = self._dlg(S.StampSpec(support='rect', width=12.0, height=34.0), saved=[('A', 'rect', 1.0, 2.0)])
        d.name.setText('A')
        d.save_format()
        self.assertEqual(d.saved, [('A', 'rect', 12.0, 34.0)])

    def test_save_needs_a_name_and_a_format(self):
        d = self._dlg(S.StampSpec(support='rect'))
        d.name.setText('   ')
        self.assertFalse(d.save_format())
        d = self._dlg()
        d.name.setText('A')
        self.assertFalse(d.save_format())
        self.assertEqual(d.saved, [])

    def test_saved_formats_offered(self):
        d = self._dlg(S.StampSpec(support='rect'), saved=[('A', 'ellipse', 80.0, 30.0)])
        i = d.format.findText('A')
        d.format.setCurrentIndex(i)
        d.format.activated.emit(i)
        spec = d.result_params()
        self.assertEqual((spec.support, spec.width, spec.height), ('ellipse', 80.0, 30.0))

    def test_all_settings_come_back(self):
        d = self._dlg(S.StampSpec(margin=1.5, radius=0.5, border=0.25, shoulder=0.1, mirror=False, negative=False, hatch=0.3,
                                  cut='boites', cut_offset=0.7, fit=False))
        spec = d.result_params()
        self.assertEqual((spec.margin, spec.radius, spec.border, spec.shoulder, spec.mirror, spec.negative, spec.hatch,
                          spec.cut, spec.cut_offset, spec.fit), (1.5, 0.5, 0.25, 0.1, False, False, 0.3, 'boites', 0.7, False))


class Command(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.settings.remove('tampon')
        cls.win.close()

    def setUp(self):
        self.win.settings.remove('tampon')
        doc = self.win.canvas.doc
        doc.layers = [Layer(name='Plan 1')]
        doc.active = doc.layers[0].id
        self.src = shape()
        doc.layers[0].items = [self.src]
        self.win.canvas.select([self.src])

    def test_new_stamp_on_a_format(self):
        with mock.patch.object(self.win, '_stamp_dialog', return_value=S.StampSpec(support='cercle', width=40, mirror=False)):
            self.win.new_stamp()
        g = self.win.canvas.doc.layers[0].items[0]
        self.assertEqual(g.extra['stamp']['support'], 'cercle')

    def test_settings_remembered_with_text_values(self):
        with mock.patch.object(self.win, '_stamp_dialog', return_value=S.StampSpec(support='ellipse', cut='boites', width=70, height=30)):
            self.win.new_stamp()
        seen = {}

        def ask(spec):
            seen['spec'] = spec
            return None
        self.win.canvas.doc.layers[0].items = [self.src]
        self.win.canvas.select([self.src])
        with mock.patch.object(self.win, '_stamp_dialog', side_effect=ask):
            self.win.new_stamp()
        self.assertEqual(seen['spec'].support, 'ellipse')
        self.assertEqual(seen['spec'].cut, 'boites')
        self.assertEqual(seen['spec'].width, 70.0)

    def test_bad_values_in_settings(self):
        self.win.settings.setValue('tampon/support', 'triangle')
        self.win.settings.setValue('tampon/cut', 'rien')
        seen = {}

        def ask(spec):
            seen['spec'] = spec
            return None
        with mock.patch.object(self.win, '_stamp_dialog', side_effect=ask):
            self.win.new_stamp()
        self.assertEqual(seen['spec'].support, 'auto')
        self.assertEqual(seen['spec'].cut, 'support')

    def test_overflow_warned(self):
        self.win.statusBar().clearMessage()
        spec = S.StampSpec(support='rect', width=10, height=5, fit=False)
        with mock.patch.object(self.win, '_stamp_dialog', return_value=spec):
            self.win.new_stamp()
        self.assertIn('dépasse', self.win.statusBar().currentMessage())

    def test_formats_saved_in_settings(self):
        from vectordrive.ui import stamp_dialog as SD
        with mock.patch.object(SD.StampDialog, 'exec', return_value=1), \
                mock.patch.object(SD.StampDialog, 'result_params', return_value=S.StampSpec()):
            real = SD.StampDialog.__init__

            def init(dlg, *a, **k):
                real(dlg, *a, **k)
                dlg.saved = [('A', 'rect', 10.0, 20.0)]
            with mock.patch.object(SD.StampDialog, '__init__', init):
                self.win._stamp_dialog(S.StampSpec())
        self.assertEqual(self.win._stamp_formats(), [('A', 'rect', 10.0, 20.0)])

    def test_bad_saved_formats_ignored(self):
        self.win.settings.setValue('tampon/formats', 'pas du json')
        self.assertEqual(self.win._stamp_formats(), [])
        self.win.settings.setValue('tampon/formats', json.dumps([['A', 'carré', 1, 2], ['B', 'rect', 1, 2], ['C']]))
        self.assertEqual(self.win._stamp_formats(), [])
        self.win.settings.setValue('tampon/formats', json.dumps([['B', 'rect', 1, 2]]))
        self.assertEqual(self.win._stamp_formats(), [('B', 'rect', 1.0, 2.0)])


if __name__ == '__main__':
    unittest.main()
