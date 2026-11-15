"""Round 815 : lignes de découpe de la matière restante ; imbrication : liste d'angles."""
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
from shapely.geometry import LineString, box as sbox

from vectordrive.core import nest_report as NR
from vectordrive.core import nesting as N
from vectordrive.core import nesting_shape as NS
from vectordrive.core import remnant as RE
from vectordrive.core.document import Document, Layer, Plate, Shape
from vectordrive.core.geom import Path, circle, polyline, rect

app = QApplication.instance() or QApplication([])


def box(x, y, w, h=None):
    return Shape(path=Path([rect(x, y, w, h if h is not None else w)]))


def segments(path):
    return [(c.segments[0].start, c.segments[-1].end) for c in path.contours]


class Scrap(unittest.TestCase):
    def setUp(self):
        self.plate = Plate(width=100.0, height=50.0)

    def test_whole_plate_grid(self):
        p = RE.scrap_lines(self.plate, [], 10.0, 10.0)
        seg = segments(p)
        self.assertEqual(len(seg), 9 + 4)                                 # le bord de la plaque n'est pas une ligne
        self.assertFalse(any(c.closed for c in p.contours))
        xs = sorted({a[0] for a, b in seg if a[0] == b[0]})
        self.assertEqual(xs, [10.0 * k for k in range(1, 10)])

    def test_grid_starts_from_the_plate(self):
        plate = Plate(x=-50.0, y=-25.0, width=100.0, height=50.0)
        seg = segments(RE.scrap_lines(plate, [], 40.0, 0.0))
        self.assertEqual(sorted(a[0] for a, _b in seg), [-10.0, 30.0])
        self.assertEqual({round(a[1]) for a, _b in seg} | {round(b[1]) for _a, b in seg}, {-25, 25})

    def test_zero_means_no_line_in_that_direction(self):
        self.assertEqual(len(segments(RE.scrap_lines(self.plate, [], 0.0, 10.0))), 4)
        self.assertEqual(len(segments(RE.scrap_lines(self.plate, [], 10.0, 0.0))), 9)
        self.assertEqual(RE.scrap_lines(self.plate, [], 0.0, 0.0).contours, [])

    def test_negative_step_is_no_line(self):
        self.assertEqual(RE.scrap_lines(self.plate, [], -5.0, -5.0).contours, [])

    def test_lines_stop_before_the_objects(self):
        it = box(30, 10, 30, 30)
        p = RE.scrap_lines(self.plate, [it], 10.0, 10.0, gap=2.0)
        keep_out = sbox(28, 8, 62, 42)
        for a, b in segments(p):
            self.assertLess(LineString([a, b]).intersection(keep_out.buffer(-1e-6)).length, 1e-6)
        # une verticale au milieu de l'objet est coupée en deux
        at_40 = [s for s in segments(p) if s[0][0] == 40.0 and s[1][0] == 40.0]
        self.assertEqual(len(at_40), 2)

    def test_round_object_with_its_hole(self):
        it = Shape(path=Path([circle((50, 25), 20), circle((50, 25), 10)]))
        p = RE.scrap_lines(self.plate, [it], 10.0, 0.0, gap=1.0)
        at_50 = [s for s in segments(p) if abs(s[0][0] - 50.0) < 1e-9]
        self.assertEqual(len(at_50), 2)                                   # le trou tombe avec l'objet

    def test_lines_stay_on_a_round_cornered_plate(self):
        plate = Plate(width=100.0, height=50.0, corner_radius=20.0)
        for a, b in segments(RE.scrap_lines(plate, [], 5.0, 0.0)):
            if a[0] < 5.5:
                self.assertGreater(min(a[1], b[1]), 5.0)

    def test_nothing_left(self):
        self.assertEqual(RE.scrap_lines(self.plate, [box(-10, -10, 200)], 10.0, 10.0).contours, [])

    def test_step_larger_than_the_plate(self):
        self.assertEqual(RE.scrap_lines(self.plate, [], 500.0, 500.0).contours, [])

    def test_tiny_step_is_capped(self):
        with mock.patch.object(RE, 'MAX_LINES', 7):
            self.assertEqual(len(segments(RE.scrap_lines(self.plate, [], 0.001, 0.0))), 7)


class Angles(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(N.parse_angles('0;90;180'), [0.0, 90.0, 180.0])
        self.assertEqual(N.parse_angles('0 ; 45,5 ; 450'), [0.0, 45.5, 90.0])
        self.assertEqual(N.parse_angles('360;0;-90'), [0.0, 270.0])
        self.assertEqual(N.parse_angles('a;;nan'), [])
        self.assertEqual(N.parse_angles(''), [])
        self.assertEqual(N.parse_angles(None), [])

    def tall(self):
        return Shape(path=Path([polyline([(0, 0), (40, 0), (40, 10), (10, 10), (10, 25), (0, 25)], closed=True)]))

    def poses(self, **kw):
        return NS._poses(self.tall(), N.NestSpec(shape=True, **kw), 0.5, 3.0)

    def test_list_replaces_the_step(self):
        self.assertEqual([p.angle for p in self.poses(angles='0;45')], [0.0, 45.0])

    def test_empty_or_bad_list_keeps_the_step(self):
        self.assertEqual(len(self.poses(angles='')), 4)
        self.assertEqual(len(self.poses(angles='abc')), 4)

    def test_no_rotation_wins(self):
        self.assertEqual([p.angle for p in self.poses(angles='0;45', allow_rotate=False)], [0.0])

    def test_a_listed_angle_is_used_and_right(self):
        """Une bande de 70 mm ne passe qu'en diagonale, à 45°, dans une plaque de 60 × 60."""
        it = box(200, 200, 70, 5)
        spec = N.NestSpec(shape=True, gap=0.0, margin=0.0, angles='0;45', precision=0.25, tighten=False)
        res = N.nest([it], Plate(width=60, height=60), spec)
        self.assertEqual(len(res.placed), 1)
        moved = it.transformed(res.placed[0][1])
        bb = moved.bbox()
        self.assertGreaterEqual(bb[0], -1e-6)
        self.assertLessEqual(bb[2], 60.0 + 1e-6)
        self.assertGreaterEqual(bb[1], -1e-6)
        self.assertLessEqual(bb[3], 60.0 + 1e-6)
        a = moved.path.contours[0].segments[0]
        self.assertAlmostEqual(abs(math.atan2(a.end[1] - a.start[1], a.end[0] - a.start[0])), math.pi / 4, places=6)
        self.assertEqual(res.rotated, 1)

    def test_kept_for_the_report(self):
        doc = Document()
        NR.remember(doc, N.NestSpec(shape=True, angles='0;180'), N.NestResult())
        self.assertEqual(doc.extra['imbrication']['angles'], '0;180')
        from vectordrive.ui import nest_report as UI
        self.assertIn('0;180', dict(UI._settings_rows(doc.extra['imbrication'])).values())

    def test_dialog_field(self):
        from vectordrive.ui.copy_nest_dialog import CopyNestDialog
        d = CopyNestDialog(None, [box(0, 0, 10)], N.NestSpec(shape=True, angles='0;90'), per_plane=True, count=1)
        self.assertEqual(d.angles.text(), '0;90')
        d.angles.setText(' 0;180 ')
        self.assertEqual(d.result_params()['spec'].angles, '0;180')
        self.assertTrue(d.angles.isEnabled())
        d.shape.setChecked(False)
        self.assertFalse(d.angles.isEnabled())
        d.deleteLater()


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
        self.doc.plate = Plate(width=100.0, height=50.0)
        self.win._undo.clear()

    def test_action_exists(self):
        self.assertIn('scrap_lines', self.win.A)

    def test_lines_join_the_objects_layer(self):
        it = box(30, 10, 30, 30)
        other = Layer(name='Plan 2')
        self.doc.layers.append(other)
        other.items.append(it)
        self.win.canvas.select([it])
        shape = self.win.scrap_lines({'step_x': 20.0, 'step_y': 0.0, 'tool': 1})
        self.assertIs(other.items[-1], shape)
        self.assertEqual(shape.tool, 1)
        self.assertEqual(self.win.canvas.selection, [shape])

    def test_without_selection_the_active_layer_counts(self):
        it = box(30, 10, 30, 30)
        self.layer.items.append(it)
        self.win.canvas.select([])
        shape = self.win.scrap_lines({'step_x': 40.0, 'step_y': 0.0, 'gap': 0.0})
        self.assertEqual(len(shape.path.contours), 3)                     # x = 40 coupée : deux morceaux, x = 80 entière

    def test_undo(self):
        self.win.scrap_lines({})
        self.assertEqual(len(self.layer.items), 1)
        self.win.undo()
        self.assertEqual(sum(len(L.items) for L in self.win.canvas.doc.layers), 0)

    def test_no_plate(self):
        self.doc.plate = None
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertIsNone(self.win.scrap_lines({}))
        info.assert_called_once()

    def test_no_step(self):
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertIsNone(self.win.scrap_lines({'step_x': 0.0, 'step_y': 0.0}))
        info.assert_called_once()
        self.assertEqual(self.layer.items, [])

    def test_bad_tool_is_brought_back(self):
        shape = self.win.scrap_lines({'tool': 999})
        self.assertLess(shape.tool, len(self.doc.tools))

    def test_settings_keep_the_angles(self):
        self.win.settings.setValue('imbrication/angles', '0;180')
        try:
            self.assertEqual(self.win._nest_spec().angles, '0;180')
        finally:
            self.win.settings.remove('imbrication/angles')
        self.assertEqual(self.win._nest_spec().angles, '')


if __name__ == '__main__':
    unittest.main()
