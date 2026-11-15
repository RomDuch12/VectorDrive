"""Round 822 : texte en arc : distance cordale, quatre directions, angles, texte existant, double-clic."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts
from vectordrive.core import text as TX
from vectordrive.core.document import Layer, Plate, Shape, Text
from vectordrive.core.geom import Affine, Path, circle

app = QApplication.instance() or QApplication([])
HAS_ARIAL = bool(fonts.find_font('Arial'))


def params(**kw):
    out = {'text': 'ABCDEFGH', 'font': 'Arial', 'height': 5.0, 'radius': 30.0, 'position': 'top', 'side': 'outside', 'spacing': 0.0,
           'method': 'circle', 'chord': 2.0, 'center': (0.0, 0.0), 'start': 135.0, 'end': 45.0}
    out.update(kw)
    return out


def nodes(path):
    return [q for c in path.contours for q in c.nodes()]


class Geometry(unittest.TestCase):
    def test_radius_from_chord(self):
        self.assertAlmostEqual(TX.radius_from_chord(8.0, 2.0), 5.0)
        self.assertAlmostEqual(TX.radius_from_chord(2.0, 1.0), 1.0)      # un demi-cercle

    def test_sweep_is_clockwise(self):
        self.assertAlmostEqual(TX.arc_sweep(135, 45), 90.0)
        self.assertAlmostEqual(TX.arc_sweep(45, 135), 270.0)
        self.assertAlmostEqual(TX.arc_sweep(10, 10), 0.0)
        self.assertAlmostEqual(TX.arc_sweep(None, 10), 0.0)

    def middle(self, position):
        c = TX.arc_contour((0, 0), 30, 5, position)
        total, at = TX.geom_walker(c)
        return at(total / 2)

    def test_directions(self):
        for name, want in (('top', (0, 30)), ('right', (30, 0)), ('under', (0, -30)), ('left', (-30, 0))):
            (x, y), _ang = self.middle(name)
            self.assertAlmostEqual(x, want[0], 6, name)
            self.assertAlmostEqual(y, want[1], 6, name)

    def test_direction_vectors(self):
        self.assertAlmostEqual(TX.arc_direction('right')[0], 1.0)
        self.assertAlmostEqual(TX.arc_direction('bottom')[1], -1.0)

    def test_old_positions_are_unchanged(self):
        for pos, r in (('top', 30), ('bottom', 35)):
            (x, y), _a = self.middle(pos)
            self.assertAlmostEqual(math.hypot(x, y), r, 6)

    def test_under_the_baseline(self):
        c = TX.arc_contour((0, 0), 30, 5, 'right', 'inside')
        total, at = TX.geom_walker(c)
        self.assertAlmostEqual(at(total / 2)[0][0], 25.0, 6)

    def test_between_two_angles(self):
        c = TX.arc_contour((0, 0), 30, 5, 'top', 'outside', 135.0, 45.0)
        total, at = TX.geom_walker(c)
        self.assertAlmostEqual(total, math.radians(90) * 30, 3)
        self.assertAlmostEqual(at(0.0)[0][0], 30 * math.cos(math.radians(135)), 3)
        self.assertAlmostEqual(at(total)[0][0], 30 * math.cos(math.radians(45)), 3)
        self.assertAlmostEqual(at(total / 2)[0][1], 30.0, 3)

    def test_too_small_radius_inside_does_not_fail(self):
        self.assertTrue(TX.arc_contour((0, 0), 3, 5, 'top', 'inside').segments)


@unittest.skipUnless(HAS_ARIAL, 'Arial absente')
class Outline(unittest.TestCase):
    def make(self, **arc):
        t = Text(text='ABCDEFGH', font='Arial', size=5.0, align='center')
        t.extra['arc'] = dict({'center': [0.0, 0.0], 'radius': 30.0, 'position': 'top', 'side': 'outside'}, **arc)
        t.outline = TX.outline_for(t)
        return t

    def test_right_direction_sits_on_the_right(self):
        bb = self.make(position='right').outline.bbox()
        self.assertGreater(bb[0], 20.0)

    def test_left_direction_sits_on_the_left(self):
        self.assertLess(self.make(position='left').outline.bbox()[2], -20.0)

    def test_under_is_below(self):
        self.assertLess(self.make(position='under').outline.bbox()[3], -20.0)

    def test_angles_fill_the_arc(self):
        t = self.make(start=135.0, end=45.0)
        self.assertGreater(t.spacing, 0.0)
        angles = [math.degrees(math.atan2(y, x)) for x, y in nodes(t.outline)]
        self.assertGreater(max(angles), 125.0)
        self.assertLess(min(angles), 55.0)
        self.assertLess(max(angles), 142.0)
        self.assertGreater(min(angles), 38.0)

    def test_a_small_arc_tightens_the_letters(self):
        self.assertLess(self.make(start=100.0, end=80.0).spacing, 0.0)

    def test_a_translation_keeps_the_angles(self):
        t = self.make(start=135.0, end=45.0)
        c = t.transformed(Affine.translation(10, 0))
        self.assertEqual(c.extra['arc']['center'], [10.0, 0.0])
        self.assertEqual(c.extra['arc']['start'], 135.0)


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
        self.doc.plate = Plate(width=100.0, height=80.0)
        self.win._undo.clear()
        self.win.canvas.select([])

    def straight(self, s='ABCDEFGH', x=20.0, y=30.0):
        t = Text(text=s, font='Arial', size=5.0, matrix=Affine.translation(x, y))
        t.outline = TX.outline_for(t)
        self.layer.items.append(t)
        return t


@unittest.skipUnless(HAS_ARIAL, 'Arial absente')
class Command(Base):
    def test_new_text_by_centre_and_radius(self):
        t = self.win.text_on_arc(params(center=(5.0, 6.0)))
        self.assertEqual(t.extra['arc']['center'], [5.0, 6.0])
        self.assertEqual(t.extra['arc']['radius'], 30.0)
        self.assertIn(t, self.layer.items)

    def test_chord_on_an_existing_text(self):
        t = self.straight()
        length = TX.advance('ABCDEFGH', 'Arial', 5.0)
        self.win.canvas.select([t])
        mid = (t.bbox()[0] + t.bbox()[2]) / 2
        got = self.win.text_on_arc(params(method='chord', chord=2.0))
        self.assertIs(got, t)
        arc = t.extra['arc']
        self.assertAlmostEqual(arc['radius'], TX.radius_from_chord(length, 2.0))
        self.assertAlmostEqual(arc['center'][0], mid)
        self.assertAlmostEqual(arc['center'][1] + arc['radius'], 32.0)    # le sommet : 2 mm au-dessus de la ligne de base
        self.assertEqual(len(self.layer.items), 1)
        self.assertEqual(len(self.win._undo), 1)

    def test_chord_ends_stay_on_the_baseline(self):
        t = self.straight()
        self.win.canvas.select([t])
        self.win.text_on_arc(params(method='chord', chord=2.0))
        arc = t.extra['arc']
        length = TX.advance('ABCDEFGH', 'Arial', 5.0)
        y = arc['center'][1] + math.sqrt(arc['radius'] ** 2 - (length / 2) ** 2)
        self.assertAlmostEqual(y, 30.0, 6)

    def test_chord_to_the_right(self):
        t = self.straight()
        self.win.canvas.select([t])
        self.win.text_on_arc(params(method='chord', chord=2.0, position='right'))
        arc = t.extra['arc']
        self.assertAlmostEqual(arc['center'][1], 30.0)
        self.assertLess(arc['center'][0], 20.0)

    def test_chord_changed_twice_stays_in_place(self):
        t = self.straight()
        self.win.canvas.select([t])
        self.win.text_on_arc(params(method='chord', chord=2.0))
        self.win.text_on_arc(params(method='chord', chord=4.0))
        arc = t.extra['arc']
        self.assertAlmostEqual(arc['center'][1] + arc['radius'], 34.0)
        self.assertAlmostEqual(arc['chord'], 4.0)

    def test_angles_are_kept(self):
        t = self.straight()
        self.win.canvas.select([t])
        self.win.text_on_arc(params(method='angles', start=200.0, end=100.0))
        self.assertEqual((t.extra['arc']['start'], t.extra['arc']['end']), (200.0, 100.0))

    def test_too_short_an_arc_says_so(self):
        t = self.straight()
        self.win.canvas.select([t])
        self.win.statusBar().clearMessage()
        self.win.text_on_arc(params(method='angles', start=100.0, end=80.0))
        self.assertLess(t.spacing, 0.0)
        self.assertIn('serrent', self.win.statusBar().currentMessage())

    def test_undo_brings_the_straight_text_back(self):
        t = self.straight()
        self.win.canvas.select([t])
        self.win.text_on_arc(params(method='chord'))
        self.win.undo()
        back = self.win.canvas.doc.layers[0].items[0]
        self.assertNotIn('arc', back.extra)
        self.assertAlmostEqual(back.matrix.f, 30.0)

    def test_imposed_width_is_dropped(self):
        t = self.straight()
        t.extra['fit'] = {'width': 5.0, 'mode': 'spacing'}
        t.extra['box'] = {'x0': 0, 'y0': 0, 'x1': 5, 'y1': 5}
        self.win.canvas.select([t])
        self.win.text_on_arc(params(method='circle'))
        self.assertNotIn('fit', t.extra)
        self.assertNotIn('box', t.extra)

    def test_several_lines_are_refused(self):
        t = self.straight('A\nB')
        self.win.canvas.select([t])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertIsNone(self.win.text_on_arc(params()))
        info.assert_called_once()

    def test_empty_text_does_nothing(self):
        self.assertIsNone(self.win.text_on_arc(params(text='  ')))
        self.assertEqual(self.layer.items, [])

    def test_circle_of_the_selection(self):
        s = Shape(path=Path([circle((10.0, 20.0), 15.0)]))
        self.layer.items.append(s)
        self.win.canvas.select([s])
        seen = {}

        def fake(dlg):
            seen.update(dlg.values())
            return 0
        with mock.patch('vectordrive.ui.dialogs.ArcTextDialog.exec', fake):
            self.win.text_on_arc()
        self.assertEqual(seen['method'], 'circle')
        self.assertAlmostEqual(seen['radius'], 15.0)
        self.assertAlmostEqual(seen['center'][0], 10.0)


@unittest.skipUnless(HAS_ARIAL, 'Arial absente')
class Window(Base):
    def values_with(self, target=None, ctrl=False):
        seen = {}

        def fake(dlg):
            seen.update(dlg.values())
            seen['dlg_enabled'] = {k: getattr(dlg, k).isEnabled() for k in ('chord', 'cx', 'radius', 'start', 'position', 'spacing')}
            return 0
        with mock.patch('vectordrive.ui.dialogs.ArcTextDialog.exec', fake), \
                mock.patch.object(self.MW, '_ctrl_held', return_value=ctrl):
            self.win.text_on_arc(target=target)
        return seen

    def test_existing_text_starts_by_chord(self):
        t = self.straight()
        self.win.canvas.select([t])
        got = self.values_with()
        self.assertEqual(got['method'], 'chord')
        self.assertEqual(got['text'], 'ABCDEFGH')
        self.assertTrue(got['dlg_enabled']['chord'])
        self.assertFalse(got['dlg_enabled']['radius'])
        self.assertFalse(got['dlg_enabled']['start'])

    def test_ctrl_starts_by_angles(self):
        t = self.straight()
        self.win.canvas.select([t])
        got = self.values_with(ctrl=True)
        self.assertEqual(got['method'], 'angles')
        self.assertTrue(got['dlg_enabled']['start'])
        self.assertTrue(got['dlg_enabled']['radius'])
        self.assertFalse(got['dlg_enabled']['position'])
        self.assertFalse(got['dlg_enabled']['spacing'])

    def test_new_text_starts_by_circle(self):
        self.assertEqual(self.values_with()['method'], 'circle')

    def test_reopening_shows_what_was_set(self):
        t = self.straight()
        self.win.text_on_arc(params(method='angles', start=200.0, end=100.0, radius=44.0, side='inside'), t)
        got = self.values_with(target=t)
        self.assertEqual(got['method'], 'angles')
        self.assertEqual((got['start'], got['end'], got['radius'], got['side']), (200.0, 100.0, 44.0, 'inside'))

    def test_double_click_reopens_the_arc(self):
        t = self.straight()
        self.win.text_on_arc(params(method='circle'), t)
        src = self.win.text_on_arc
        with mock.patch.object(self.win, 'text_on_arc', wraps=src) as run, \
                mock.patch('vectordrive.ui.dialogs.ArcTextDialog.exec', return_value=0):
            self.win.canvas.select([t])
            self.win._item_double_clicked(t)
        run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
