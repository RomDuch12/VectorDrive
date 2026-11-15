"""Courbe par équation et guilloché."""
import math
import os
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

from PySide6.QtWidgets import QApplication, QDialogButtonBox

from vectordrive.core import equation as EQ
from vectordrive.core.document import Shape
from vectordrive.ui.curves_dialog import EquationDialog, GuillocheDialog
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])


def points(path, tol=0.005):
    out = []
    for c in path.contours:
        for s in c.segments:
            out.extend(s.flatten(tol))
    return out


class TestFormula(unittest.TestCase):
    def test_values(self):
        for text, x, want in (('2*t+1', 3.0, 7.0), ('t^2', 3.0, 9.0), ('sin(pi/2)', 0.0, 1.0), ('sqrt(t)', 16.0, 4.0),
                              ('max(t,2)', 1.0, 2.0), ('-t', 2.0, -2.0), ('rad(180)', 0.0, math.pi), ('5%3', 0.0, 2.0),
                              ('2×3÷4', 0.0, 1.5), ('π', 0.0, math.pi), ('0,5*t', 4.0, 2.0)):
            self.assertAlmostEqual(EQ.compile_expr(text, 't')(x), want, places=9, msg=text)

    def test_refused(self):
        for text in ('__import__("os")', 'open("x")', 'a.b', 't[0]', 'lambda: 1', '(t,2)', '', '   ', 'inconnu', 'exec("1")',
                     'sin', 'sin(1, 2)', '1 +', '[t for t in (1,)]', 'sin.__class__', '"texte"', 'True', 'sin(t=1)'):
            with self.assertRaises(ValueError, msg=text):
                EQ.compile_expr(text, 't')

    def test_giant_power_does_not_hang(self):
        t0 = time.perf_counter()
        f = EQ.compile_expr('9^9^9^9', 't')
        with self.assertRaises(OverflowError):
            f(0.0)
        self.assertLess(time.perf_counter() - t0, 1.0)

    def test_outside_the_domain_is_no_typing_error(self):
        EQ.compile_expr('sqrt(-t)', 't')
        EQ.compile_expr('1/(t-1)', 't')

    def test_bounds(self):
        self.assertAlmostEqual(EQ.value_of('2*pi'), math.tau)
        self.assertEqual(EQ.value_of('12'), 12.0)
        self.assertEqual(EQ.value_of('2,5'), 2.5)
        for bad in ('t', '1/0', 'x', '', 'log(0)'):
            with self.assertRaises(ValueError, msg=bad):
                EQ.value_of(bad)


class TestCurves(unittest.TestCase):
    def test_circle_within_tolerance_and_closed(self):
        p = EQ.equation_path('xy', '30*cos(t)', '30*sin(t)', '0', '2*pi')
        self.assertEqual(len(p.contours), 1)
        self.assertTrue(p.contours[0].closed)
        for x, y in points(p):
            self.assertAlmostEqual(math.hypot(x, y), 30.0, delta=EQ.TOL * 1.5)

    def test_fitted_to_few_segments(self):
        p = EQ.equation_path('xy', '30*cos(t)', '30*sin(t)', '0', '2*pi')
        self.assertLess(len(p.contours[0].segments), 40)

    def test_function_of_x(self):
        p = EQ.equation_path('y', 'x^2/10', '', '0', '10')
        c = p.contours[0]
        self.assertFalse(c.closed)
        self.assertEqual(c.segments[0].start, (0.0, 0.0))
        self.assertAlmostEqual(c.segments[-1].end[0], 10.0, places=6)
        self.assertAlmostEqual(c.segments[-1].end[1], 10.0, places=6)
        for x, y in points(p):
            self.assertAlmostEqual(y, x * x / 10, delta=EQ.TOL * 1.5)

    def test_polar(self):
        p = EQ.equation_path('polar', '20', '', '0', '2*pi')
        self.assertTrue(p.contours[0].closed)
        for x, y in points(p):
            self.assertAlmostEqual(math.hypot(x, y), 20.0, delta=EQ.TOL * 1.5)

    def test_backward_interval(self):
        p = EQ.equation_path('y', 'x', '', '10', '0')
        self.assertAlmostEqual(p.contours[0].segments[0].start[0], 10.0, places=6)

    def test_straight_line_stays_simple(self):
        p = EQ.equation_path('y', '2*x+1', '', '0', '50')
        self.assertLessEqual(len(p.contours[0].segments), 2)

    def test_jump_cuts_the_curve(self):
        p = EQ.equation_path('y', '1/x', '', '-5', '5')
        self.assertEqual(len(p.contours), 2)                    # pas de trait entre -∞ et +∞

    def test_huge_values_are_cut(self):
        bb = EQ.equation_path('y', '1/x', '', '-5', '5').bbox()
        self.assertLessEqual(bb[3], EQ.MAX_COORD)
        self.assertGreaterEqual(bb[1], -EQ.MAX_COORD)

    def test_step_cuts_the_curve(self):
        p = EQ.equation_path('y', 'floor(x)', '', '0.5', '2.5')
        self.assertEqual(len(p.contours), 3)

    def test_outside_domain_cut_up_to_the_edge(self):
        p = EQ.equation_path('y', 'sqrt(4-x*x)', '', '-5', '5')
        self.assertEqual(len(p.contours), 1)
        bb = p.bbox()
        self.assertAlmostEqual(bb[0], -2.0, delta=0.01)
        self.assertAlmostEqual(bb[2], 2.0, delta=0.01)
        self.assertAlmostEqual(bb[3], 2.0, delta=0.01)

    def test_nothing_valid(self):
        self.assertEqual(EQ.equation_path('y', 'sqrt(-1-x*x)', '', '0', '5').contours, [])

    def test_empty_interval(self):
        with self.assertRaises(ValueError):
            EQ.equation_path('y', 'x', '', '3', '3')

    def test_unknown_kind(self):
        with self.assertRaises(ValueError):
            EQ.equation_path('z', 'x', '', '0', '1')

    def test_bad_formula(self):
        with self.assertRaises(ValueError):
            EQ.equation_path('xy', 'open("x")', 't', '0', '1')

    def test_wild_function_stays_bounded(self):
        t0 = time.perf_counter()
        p = EQ.equation_path('y', 'sin(1/x)*10', '', '0.001', '1')
        self.assertTrue(p.contours)
        self.assertLess(time.perf_counter() - t0, 30.0)

    def test_presets_all_draw(self):
        for name, kind, first, second, start, end in EQ.PRESETS:
            p = EQ.equation_path(kind, first, second, start, end)
            self.assertEqual(len(p.contours), 1, name)
            bb = p.bbox()
            self.assertGreater(bb[2] - bb[0], 5.0, name)

    def test_rose_has_its_size(self):
        p = EQ.equation_path('polar', '30*cos(5*a)', '', '0', 'pi')
        for x, y in points(p):
            self.assertLessEqual(math.hypot(x, y), 30.0 + EQ.TOL * 2)
        self.assertGreater(max(math.hypot(x, y) for x, y in points(p)), 29.9)


class TestGuilloche(unittest.TestCase):
    def test_rosette_one_closed_curve_per_line(self):
        p = EQ.guilloche(EQ.GuillocheSpec(lines=6, lobes=8, radius=40, amplitude=5))
        self.assertEqual(len(p.contours), 6)
        self.assertTrue(all(c.closed for c in p.contours))

    def test_rosette_stays_in_its_ring(self):
        p = EQ.guilloche(EQ.GuillocheSpec(lines=6, lobes=8, radius=40, amplitude=5))
        rs = [math.hypot(x, y) for x, y in points(p)]
        self.assertAlmostEqual(min(rs), 35.0, delta=0.05)
        self.assertAlmostEqual(max(rs), 45.0, delta=0.05)

    def test_rosette_lines_are_shifted(self):
        p = EQ.guilloche(EQ.GuillocheSpec(lines=4, lobes=4, radius=40, amplitude=5))
        a, b = p.contours[0].segments[0].start, p.contours[1].segments[0].start
        self.assertNotEqual(a, b)

    def test_second_wave_widens_it(self):
        p = EQ.guilloche(EQ.GuillocheSpec(lines=4, lobes=8, radius=40, amplitude=5, amplitude2=3, lobes2=2))
        rs = [math.hypot(x, y) for x, y in points(p)]
        self.assertGreater(max(rs), 46.0)

    def test_band(self):
        p = EQ.guilloche(EQ.GuillocheSpec(kind='band', lines=5, length=100, wavelength=20, amplitude=4))
        self.assertEqual(len(p.contours), 5)
        self.assertFalse(any(c.closed for c in p.contours))
        bb = p.bbox()
        self.assertAlmostEqual(bb[0], 0.0, places=6)
        self.assertAlmostEqual(bb[2], 100.0, places=6)
        self.assertAlmostEqual(bb[3], 4.0, delta=0.05)

    def test_spirograph_closes(self):
        p = EQ.guilloche(EQ.GuillocheSpec(kind='spiro', lines=1, big=50, small=20, pen=15))
        self.assertEqual(len(p.contours), 1)
        self.assertTrue(p.contours[0].closed)
        rs = [math.hypot(x, y) for x, y in points(p)]
        self.assertAlmostEqual(max(rs), 45.0, delta=0.05)              # R - r + d
        self.assertAlmostEqual(min(rs), 15.0, delta=0.05)              # R - r - d

    def test_spirograph_outside(self):
        p = EQ.guilloche(EQ.GuillocheSpec(kind='spiro', lines=1, big=50, small=20, pen=15, outside=True))
        rs = [math.hypot(x, y) for x, y in points(p)]
        self.assertAlmostEqual(max(rs), 85.0, delta=0.05)              # R + r + d
        self.assertAlmostEqual(min(rs), 55.0, delta=0.05)              # R + r - d

    def test_spirograph_copies_turn(self):
        p = EQ.guilloche(EQ.GuillocheSpec(kind='spiro', lines=3, big=50, small=20, pen=15))
        self.assertEqual(len(p.contours), 3)

    def test_spirograph_never_closing_is_refused(self):
        with self.assertRaises(ValueError):
            EQ.guilloche(EQ.GuillocheSpec(kind='spiro', big=50.0, small=17.123))

    def test_limits(self):
        for bad in (EQ.GuillocheSpec(lines=0), EQ.GuillocheSpec(lines=EQ.MAX_LINES + 1), EQ.GuillocheSpec(lobes=0),
                    EQ.GuillocheSpec(radius=0.0), EQ.GuillocheSpec(kind='band', length=0.0),
                    EQ.GuillocheSpec(kind='band', wavelength=0.0), EQ.GuillocheSpec(kind='band', length=1e6, wavelength=1.0),
                    EQ.GuillocheSpec(kind='spiro', small=0.0), EQ.GuillocheSpec(kind='x')):
            with self.assertRaises(ValueError, msg=bad):
                EQ.guilloche(bad)

    def test_full_pattern_in_a_reasonable_time(self):
        t0 = time.perf_counter()
        p = EQ.guilloche(EQ.GuillocheSpec(lines=48, lobes=16))
        self.assertEqual(len(p.contours), 48)
        self.assertLess(time.perf_counter() - t0, 30.0)


class TestDialogs(unittest.TestCase):
    def test_equation_starts_on_a_preset(self):
        d = EquationDialog()
        self.assertIsNotNone(d.result)
        self.assertTrue(d.box.button(QDialogButtonBox.StandardButton.Ok).isEnabled())

    def test_equation_preset_fills(self):
        d = EquationDialog()
        i = d.preset.findText('Lissajous')
        d.preset.setCurrentIndex(i)
        self.assertEqual(d.kind.currentData(), 'xy')
        self.assertIn('sin', d.first.text())
        self.assertIsNotNone(d.result)

    def test_equation_error_blocks_ok(self):
        d = EquationDialog()
        d.first.setText('open("x")')
        d.refresh()
        self.assertIsNone(d.result)
        self.assertTrue(d.message.text())
        self.assertFalse(d.box.button(QDialogButtonBox.StandardButton.Ok).isEnabled())

    def test_equation_nothing_valid_blocks_ok(self):
        d = EquationDialog()
        d.kind.setCurrentIndex(d.kind.findData('y'))
        d.first.setText('sqrt(-1-x*x)')
        d.refresh()
        self.assertIsNone(d.result)
        self.assertFalse(d.box.button(QDialogButtonBox.StandardButton.Ok).isEnabled())

    def test_equation_second_formula_only_for_xy(self):
        d = EquationDialog()
        d.show()
        d.kind.setCurrentIndex(d.kind.findData('polar'))
        self.assertFalse(d.second.isVisible())
        d.kind.setCurrentIndex(d.kind.findData('xy'))
        self.assertTrue(d.second.isVisible())
        d.close()

    def test_equation_remembers(self):
        last = {'kind': 'y', 'first': 'x/2', 'second': '', 'start': '1', 'end': '9'}
        d = EquationDialog(last=last)
        self.assertEqual(d.values(), last)

    def test_equation_bad_memory(self):
        d = EquationDialog(last='rien')
        self.assertIsNotNone(d.result)

    def test_guilloche_default(self):
        d = GuillocheDialog()
        self.assertEqual(len(d.result.contours), EQ.GuillocheSpec().lines)

    def test_guilloche_fields_follow_the_pattern(self):
        d = GuillocheDialog()
        d.show()
        d.kind.setCurrentIndex(d.kind.findData('band'))
        self.assertTrue(d.fields['wavelength'].isVisible())
        self.assertFalse(d.fields['radius'].isVisible())
        d.kind.setCurrentIndex(d.kind.findData('spiro'))
        self.assertTrue(d.fields['small'].isVisible())
        self.assertTrue(d.outside.isVisible())
        self.assertFalse(d.fields['amplitude'].isVisible())
        d.close()

    def test_guilloche_value_changes_it(self):
        d = GuillocheDialog()
        d.fields['lines'].setValue(3)
        d.refresh()
        self.assertEqual(len(d.result.contours), 3)

    def test_guilloche_impossible_blocks_ok(self):
        d = GuillocheDialog()
        d.kind.setCurrentIndex(d.kind.findData('spiro'))
        d.fields['small'].setValue(17.13)
        d.fields['big'].setValue(50.01)
        d.refresh()
        self.assertIsNone(d.result)
        self.assertTrue(d.message.text())

    def test_guilloche_remembers_and_survives_bad_memory(self):
        d = GuillocheDialog(last={'lines': 7, 'kind': 'rosette', 'lobes': 'abc', 'inconnu': 1})
        self.assertEqual(d.fields['lines'].value(), 7)
        self.assertEqual(d.fields['lobes'].value(), EQ.GuillocheSpec().lobes)

    def test_preview_is_quick_and_the_result_fine(self):
        d = GuillocheDialog()
        t0 = time.perf_counter()
        d.refresh()
        self.assertLess(time.perf_counter() - t0, 1.5)
        rough = sum(len(c.segments) for c in d.result.contours)
        d.accept()
        fine = d.result
        self.assertEqual(len(fine.contours), EQ.GuillocheSpec().lines)
        self.assertNotEqual(sum(len(c.segments) for c in fine.contours), rough)
        for x, y in points(fine):
            self.assertLessEqual(math.hypot(x, y), 48.0 + EQ.TOL * 2)
        self.assertEqual(d.result.contours[0].closed, True)

    def test_accept_refused_without_a_curve(self):
        d = EquationDialog()
        d.first.setText('open("x")')
        d.accept()
        self.assertIsNone(d.result)
        self.assertFalse(d.isHidden() and d.result is not None)

    def test_preview_paints(self):
        d = GuillocheDialog()
        img = d.preview.grab()
        self.assertFalse(img.isNull())
        non_white = {img.toImage().pixelColor(x, y).name() for x in range(0, img.width(), 7) for y in range(0, img.height(), 7)}
        self.assertGreater(len(non_white), 1)


class TestWindow(unittest.TestCase):
    def setUp(self):
        self.w = MainWindow()

    def tearDown(self):
        self.w.settings.remove('cad/equation')
        self.w.settings.remove('cad/guilloche')
        self.w.modified = False
        self.w.close()

    def test_curve_added_centred_and_undone(self):
        n = len(list(self.w.canvas.doc.iter_leaves()))
        s = self.w.equation_curve(params=dict(kind='xy', first='30*cos(t)', second='30*sin(t)', start='0', end='2*pi'))
        self.assertIsInstance(s, Shape)
        self.assertEqual(s.tool, self.w.canvas.current_tool_index)
        bb = s.bbox()
        cx, cy = self.w._view_center()
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, cx, places=6)
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, cy, places=6)
        self.assertEqual(len(list(self.w.canvas.doc.iter_leaves())), n + 1)
        self.w.undo()
        self.assertEqual(len(list(self.w.canvas.doc.iter_leaves())), n)

    def test_guilloche_added(self):
        s = self.w.guilloche_dialog(spec=EQ.GuillocheSpec(lines=4, lobes=6))
        self.assertEqual(len(s.path.contours), 4)
        self.assertFalse(s.filled)

    def test_dialogs_open(self):
        self.assertIsInstance(self.w.equation_curve(exec_dialog=False), EquationDialog)
        self.assertIsInstance(self.w.guilloche_dialog(exec_dialog=False), GuillocheDialog)

    def test_in_the_ribbon(self):
        pages = [self.w.ribbon.page(i) for i in range(self.w.ribbon.count())]
        for key in ('equation_curve', 'guilloche'):
            a = self.w.A[key]
            self.assertFalse(a.icon().isNull())
            n = sum(1 for page in pages if page for g in page.groups() for b in g.buttons() if b.defaultAction() is a)
            self.assertEqual(n, 1, key)


if __name__ == '__main__':
    unittest.main()
