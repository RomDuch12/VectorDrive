"""Round 813 : imbrication : retournement permis, rangement des objets dans un contour."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication
from shapely.geometry import Polygon

from vectordrive.core import nest_report as NR
from vectordrive.core import nesting as N
from vectordrive.core import nesting_shape as NS
from vectordrive.core import text as TX
from vectordrive.core.document import Document, Group, Layer, Plate, Shape, Text
from vectordrive.core.geom import Path, circle, polyline, rect

app = QApplication.instance() or QApplication([])

#: un L aux bras inégaux : sa copie miroir ne se superpose à lui par aucune rotation
ELL = [(0, 0), (40, 0), (40, 10), (10, 10), (10, 25), (0, 25)]


def ell(dx=0.0, dy=0.0):
    return Shape(path=Path([polyline([(x + dx, y + dy) for x, y in ELL], closed=True)]))


def box(x, y, w, h=None):
    return Shape(path=Path([rect(x, y, w, h if h is not None else w)]))


def mirrored_ell_hole():
    """La forme juste assez grande pour le L retourné : 1 mm tout autour."""
    pts = [(40 - x, y) for x, y in ELL]
    return Path([polyline(list(Polygon(pts).buffer(1.2, join_style=2).exterior.coords)[:-1], closed=True)])


def poly_of(it):
    return Polygon(it.path.contours[0].flatten(0.01))


def det(m):
    return m.a * m.d - m.b * m.c


class Poses(unittest.TestCase):
    def poses(self, it, **kw):
        spec = N.NestSpec(shape=True, **kw)
        return NS._poses(it, spec, 0.5, 3.0)

    def test_off_by_default(self):
        self.assertFalse(N.NestSpec().allow_mirror)
        self.assertTrue(all(not p.mirror for p in self.poses(ell(), allow_rotate=True)))

    def test_a_chiral_shape_gets_twice_the_poses(self):
        plain = self.poses(ell(), allow_rotate=True)
        both = self.poses(ell(), allow_rotate=True, allow_mirror=True)
        self.assertEqual(len(plain), 4)
        self.assertEqual(len(both), 8)
        self.assertEqual(sum(p.mirror for p in both), 4)

    def test_a_symmetric_shape_gains_nothing(self):
        both = self.poses(box(0, 0, 30, 10), allow_rotate=True, allow_mirror=True)
        self.assertEqual(len(both), 2)
        self.assertTrue(all(not p.mirror for p in both))

    def test_a_disc_stays_one_pose(self):
        disc = Shape(path=Path([circle((0, 0), 10)]))
        self.assertEqual(len(self.poses(disc, allow_rotate=True, allow_mirror=True)), 1)

    def test_the_mask_is_really_mirrored(self):
        both = self.poses(ell(), allow_rotate=False, allow_mirror=True)
        self.assertEqual(len(both), 2)
        self.assertFalse((both[0].mask == both[1].mask[:, ::-1]).all() and both[0].mirror == both[1].mirror)
        self.assertTrue((both[0].mask == both[1].mask[:, ::-1]).mean() > 0.97)


class Mirror(unittest.TestCase):
    def nest_in_hole(self, **kw):
        region = mirrored_ell_hole()
        spec = N.NestSpec(shape=True, region=region, margin=0.0, gap=0.0, precision=0.25, **kw)
        return N.nest([ell(100, 100)], None, spec), region

    def test_needs_the_mirror_to_fit(self):
        res, _r = self.nest_in_hole(allow_rotate=True, allow_mirror=False)
        self.assertEqual(len(res.placed), 0)
        self.assertEqual(res.mirrored, 0)

    def test_fits_mirrored_and_really_inside(self):
        res, region = self.nest_in_hole(allow_rotate=True, allow_mirror=True)
        self.assertEqual(len(res.placed), 1)
        self.assertEqual(res.mirrored, 1)
        it, m = res.placed[0]
        self.assertLess(det(m), 0.0)
        moved = poly_of(it.transformed(m))
        zone = Polygon(region.contours[0].flatten(0.01))
        self.assertTrue(zone.buffer(1e-6).contains(moved), (moved.bounds, zone.bounds))
        self.assertAlmostEqual(moved.area, poly_of(ell()).area, delta=0.01)

    def test_mirror_with_rotation_stays_right(self):
        """Une plaque étroite oblige le L retourné ET tourné : la grille et la matrice doivent dire la même chose."""
        for corner in N.CORNERS:
            spec = N.NestSpec(shape=True, gap=2.0, margin=1.0, allow_rotate=True, allow_mirror=True, precision=0.25,
                              copies=6, corner=corner, tighten=False)
            res = N.nest([ell()], Plate(width=120, height=120), spec)
            self.assertEqual(len(res.placed), 6)
            polys = [poly_of(it.transformed(m)) for it, m in res.placed]
            for i, a in enumerate(polys):
                self.assertTrue(Polygon([(0, 0), (120, 0), (120, 120), (0, 120)]).buffer(1e-6).contains(a), corner)
                for b in polys[i + 1:]:
                    self.assertGreaterEqual(a.distance(b), 2.0 - 1e-6, corner)

    def test_tighten_keeps_the_gap(self):
        spec = N.NestSpec(shape=True, gap=1.5, margin=1.0, allow_rotate=True, allow_mirror=True, precision=0.5, copies=8)
        res = N.nest([ell()], Plate(width=150, height=150), spec)
        self.assertEqual(len(res.placed), 8)
        polys = [poly_of(it.transformed(m)) for it, m in res.placed]
        for i, a in enumerate(polys):
            for b in polys[i + 1:]:
                self.assertGreaterEqual(a.distance(b), 1.5 - 0.02)

    def test_counts_only_turned_objects(self):
        spec = N.NestSpec(shape=True, gap=1.0, margin=1.0, allow_rotate=False, allow_mirror=True, precision=0.5, copies=4)
        res = N.nest([ell()], Plate(width=200, height=200), spec)
        self.assertEqual(res.mirrored, sum(1 for _i, m in res.placed if det(m) < 0))

    def test_rectangle_mode_ignores_it(self):
        spec = N.NestSpec(shape=False, allow_mirror=True, copies=3)
        res = N.nest([ell()], Plate(width=200, height=200), spec)
        self.assertEqual(res.mirrored, 0)
        self.assertTrue(all(det(m) > 0 for _i, m in res.placed))

    def test_optimiser_keeps_it(self):
        spec = N.NestSpec(shape=True, gap=1.0, margin=1.0, allow_mirror=True, precision=1.0, copies=4, tries=3, both_ways=True)
        res = N.nest([ell()], Plate(width=200, height=200), spec)
        self.assertEqual(len(res.placed), 4)
        self.assertEqual(res.mirrored, sum(1 for _i, m in res.placed if det(m) < 0))

    def test_text_stays_a_text_when_mirrored(self):
        t = Text(text='F', font='Arial', size=20.0)
        t.outline = TX.outline_for(t)
        spec = N.NestSpec(shape=True, gap=1.0, margin=1.0, allow_rotate=False, allow_mirror=True, precision=0.25)
        spec.region = None
        p = NS._poses(t, spec, 0.25, 3.0)
        self.assertEqual(len(p), 2)
        m = NS._matrix(t, p[1], Plate(width=100, height=100), 1.0, 0.25, 0, 0, 0)
        moved = t.clone().transformed(m)
        self.assertIsInstance(moved, Text)
        self.assertLess(det(m), 0.0)
        bb = moved.bbox()
        self.assertAlmostEqual(bb[0], 1.0, delta=0.5)
        self.assertAlmostEqual(bb[3], 99.0, delta=0.5)


class Zones(unittest.TestCase):
    def test_one_contour(self):
        self.assertEqual(len(N.contours_of(box(0, 0, 10))), 1)

    def test_combination_goes_contour_by_contour_in_order(self):
        s = Shape(path=Path([rect(100, 0, 10, 10), rect(0, 0, 50, 50)]))
        z = N.contours_of(s)
        self.assertEqual(len(z), 2)
        self.assertEqual(z[0].bbox()[0], 100)
        self.assertEqual(z[1].bbox()[0], 0)

    def test_a_hole_belongs_to_its_contour(self):
        s = Shape(path=Path([rect(10, 10, 5, 5), rect(0, 0, 50, 50), rect(200, 0, 20, 20)]))
        z = N.contours_of(s)
        self.assertEqual(len(z), 2)
        self.assertEqual(len(z[0].contours), 2)
        self.assertEqual(z[0].bbox()[2], 50)
        self.assertEqual(len(z[1].contours), 1)

    def test_an_island_in_a_hole_is_a_zone(self):
        s = Shape(path=Path([rect(0, 0, 100, 100), rect(10, 10, 80, 80), rect(30, 30, 20, 20)]))
        z = N.contours_of(s)
        self.assertEqual([len(p.contours) for p in z], [2, 1])

    def test_group_keeps_its_order(self):
        g = Group(children=[box(100, 0, 10), box(0, 0, 10)])
        self.assertEqual([p.bbox()[0] for p in N.contours_of(g)], [100, 0])

    def test_open_curve_is_no_zone(self):
        s = Shape(path=Path([polyline([(0, 0), (10, 0), (10, 10)], closed=False)]))
        self.assertEqual(N.contours_of(s), [])


class Into(unittest.TestCase):
    def spec(self, **kw):
        kw.setdefault('margin', 0.5)
        kw.setdefault('gap', 1.0)
        kw.setdefault('precision', 0.25)
        return N.NestSpec(shape=True, **kw)

    def test_first_zone_first(self):
        items = [box(300 + 20 * i, 300, 10) for i in range(4)]
        z = [Path([rect(0, 0, 24, 13)]), Path([rect(100, 100, 60, 60)])]
        res = N.nest_into(items, z, self.spec())
        self.assertEqual(len(res.placed), 4)
        self.assertEqual(sorted(res.sheets), [0, 0, 1, 1])
        self.assertEqual(res.plates, 2)
        for (it, m), k in zip(res.placed, res.sheets):
            bb = it.transformed(m).bbox()
            r = z[k].bbox()
            self.assertTrue(r[0] <= bb[0] and bb[2] <= r[2] and r[1] <= bb[1] and bb[3] <= r[3], (bb, r))

    def test_second_zone_stays_free_while_the_first_has_room(self):
        items = [box(300 + 20 * i, 300, 10) for i in range(3)]
        res = N.nest_into(items, [Path([rect(0, 0, 100, 100)]), Path([rect(200, 0, 100, 100)])], self.spec())
        self.assertEqual(res.sheets, [0, 0, 0])
        self.assertEqual(res.plates, 1)

    def test_too_big_for_the_first_goes_to_the_second(self):
        big, small = box(300, 300, 50), box(400, 300, 5)
        res = N.nest_into([big, small], [Path([rect(0, 0, 20, 20)]), Path([rect(100, 0, 100, 100)])], self.spec())
        where = {id(it): k for (it, _m), k in zip(res.placed, res.sheets)}
        self.assertEqual(where[id(big)], 1)
        self.assertEqual(where[id(small)], 0)

    def test_nothing_fits(self):
        big = box(300, 300, 50)
        res = N.nest_into([big], [Path([rect(0, 0, 20, 20)])], self.spec())
        self.assertEqual(res.placed, [])
        self.assertEqual(res.unplaced, [big])
        self.assertEqual(res.usage, 0.0)

    def test_hole_of_the_zone_stays_empty(self):
        zone = N.contours_of(Shape(path=Path([rect(0, 0, 60, 60), rect(20, 20, 20, 20)])))[0]
        items = [box(300 + 20 * i, 300, 8) for i in range(10)]
        res = N.nest_into(items, [zone], self.spec())
        self.assertGreater(len(res.placed), 5)
        hole = Polygon([(20, 20), (40, 20), (40, 40), (20, 40)])
        for it, m in res.placed:
            self.assertEqual(poly_of(it.transformed(m)).intersection(hole).area, 0.0)

    def test_each_object_once_whatever_the_spec_says(self):
        items = [box(300, 300, 5)]
        res = N.nest_into(items, [Path([rect(0, 0, 100, 100)])], self.spec(copies=0, counts=[5]))
        self.assertEqual(len(res.placed), 1)

    def test_usage_counts_the_used_zones(self):
        res = N.nest_into([box(300, 300, 20)], [Path([rect(0, 0, 40, 40)]), Path([rect(100, 0, 90, 90)])], self.spec())
        self.assertAlmostEqual(res.usage, 400 / 1600, delta=0.1)


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
        self.doc.plate = Plate(width=200.0, height=200.0)
        self.doc.extra.pop('imbrication', None)
        self.win._undo.clear()

    def test_the_action_is_in_the_ribbon(self):
        self.assertIn('nest_into', self.win.A)

    def test_objects_move_into_the_first_selected(self):
        zone = box(0, 0, 60)
        a, b, far = box(100, 100, 10), box(120, 100, 10), box(140, 100, 90)
        self.layer.items.extend([zone, a, b, far])
        self.win.canvas.select([zone, a, b, far])
        res = self.win.nest_into_contour({'margin': 1.0, 'gap': 1.0, 'precision': 0.5})
        self.assertEqual(len(res.placed), 2)
        self.assertEqual(len(res.unplaced), 1)
        self.assertEqual(len(self.layer.items), 4)                        # les objets bougent, sans copie
        self.assertEqual(zone.bbox(), box(0, 0, 60).bbox())
        self.assertEqual(far.bbox(), box(140, 100, 90).bbox())            # resté où il était
        moved = [it for it in self.layer.items if it is not zone and it is not far]
        self.assertEqual(len(moved), 2)
        for it in moved:
            bb = it.bbox()
            self.assertTrue(0 <= bb[0] and bb[2] <= 60 and 0 <= bb[1] and bb[3] <= 60, bb)
        self.assertEqual(self.doc.extra['imbrication']['placed'], 2)
        self.assertIn('allow_mirror', self.doc.extra['imbrication'])

    def test_undo_brings_them_back(self):
        zone = box(0, 0, 60)
        a = box(100, 100, 10)
        self.layer.items.extend([zone, a])
        self.win.canvas.select([zone, a])
        self.win.nest_into_contour({'precision': 0.5})
        self.win.undo()
        items = self.win.canvas.doc.layers[0].items
        self.assertEqual(len(items), 2)
        self.assertEqual(items[1].bbox(), (100, 100, 110, 110))

    def test_group_fills_one_after_the_other(self):
        g = Group(children=[box(0, 0, 14), box(50, 0, 40)])
        items = [box(150, 100 + 15 * i, 10) for i in range(3)]
        self.layer.items.extend([g] + items)
        self.win.canvas.select([g] + items)
        res = self.win.nest_into_contour({'margin': 0.5, 'gap': 1.0, 'precision': 0.25, 'allow_rotate': False})
        self.assertEqual(sorted(res.sheets), [0, 1, 1])

    def test_mirror_reaches_the_command(self):
        zone = Shape(path=mirrored_ell_hole())
        it = ell(100, 100)
        self.layer.items.extend([zone, it])
        self.win.canvas.select([zone, it])
        p = {'margin': 0.0, 'gap': 0.0, 'precision': 0.25, 'allow_mirror': True}
        res = self.win.nest_into_contour(p)
        self.assertEqual(res.mirrored, 1)

    def test_first_selected_must_be_closed(self):
        line = Shape(path=Path([polyline([(0, 0), (10, 0)], closed=False)]))
        a = box(100, 100, 10)
        self.layer.items.extend([line, a])
        self.win.canvas.select([line, a])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertIsNone(self.win.nest_into_contour({}))
        info.assert_called_once()
        self.assertEqual(a.bbox(), (100, 100, 110, 110))

    def test_one_object_is_not_enough(self):
        zone = box(0, 0, 60)
        self.layer.items.append(zone)
        self.win.canvas.select([zone])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertIsNone(self.win.nest_into_contour({}))
        info.assert_called_once()

    def test_nothing_fits_says_so(self):
        zone, big = box(0, 0, 10), box(100, 100, 50)
        self.layer.items.extend([zone, big])
        self.win.canvas.select([zone, big])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            res = self.win.nest_into_contour({'precision': 0.5})
        info.assert_called_once()
        self.assertEqual(res.placed, [])
        self.assertEqual(big.bbox(), (100, 100, 150, 150))

    def test_copy_into_shape_takes_the_mirror_too(self):
        zone = Shape(path=mirrored_ell_hole())
        it = ell(100, 100)
        self.layer.items.extend([it, zone])
        self.win.canvas.select([it, zone])
        res = self.win.copy_into_shape({'count': 1, 'margin': 0.0, 'gap': 0.0, 'precision': 0.25, 'allow_mirror': True})
        self.assertEqual(res.mirrored, 1)

    def test_settings_keep_the_mirror(self):
        self.win.settings.setValue('imbrication/miroir', True)
        try:
            self.assertTrue(self.win._nest_spec().allow_mirror)
        finally:
            self.win.settings.remove('imbrication/miroir')
        self.assertFalse(self.win._nest_spec().allow_mirror)


class Dialog(unittest.TestCase):
    def test_copy_nest_dialog_has_it(self):
        from vectordrive.ui.copy_nest_dialog import CopyNestDialog
        spec = N.NestSpec(shape=True, allow_mirror=True)
        d = CopyNestDialog(None, [box(0, 0, 10)], spec, per_plane=True, count=1)
        self.assertTrue(d.mirror.isChecked())
        self.assertTrue(d.mirror.isEnabled())
        self.assertTrue(d.result_params()['spec'].allow_mirror)
        d.mirror.setChecked(False)
        self.assertFalse(d.result_params()['spec'].allow_mirror)
        d.shape.setChecked(False)
        d.deleteLater()


class Report(unittest.TestCase):
    def test_setting_is_kept_and_shown(self):
        from vectordrive.ui import nest_report as UI
        doc = Document()
        doc.layers[0].items.append(box(0, 0, 10))
        res = N.NestResult(plates=1)
        NR.remember(doc, N.NestSpec(shape=True, allow_mirror=True), res)
        self.assertTrue(doc.extra['imbrication']['allow_mirror'])
        rows = dict(UI._settings_rows(doc.extra['imbrication']))
        self.assertTrue(any('miroir' in k or 'mirror' in k for k in rows))


if __name__ == '__main__':
    unittest.main()
