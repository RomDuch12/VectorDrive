"""Round 779 : mode prismatique, facettes au bord, éclairage, ordre dans les groupes, commandes reliées."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

import numpy as np
from PySide6.QtWidgets import QApplication
from shapely.geometry import box

from vectordrive.core import galbe as GB
from vectordrive.core import relief_ops as R
from vectordrive.core import typeart as TA
from vectordrive.core.document import Group, Image, Layer, Shape, Text
from vectordrive.core.geom import Path, polyline, rect
from vectordrive.ui import shortcuts as S
from vectordrive.ui import view3d as V3


def heights(img):
    H, x0, y1, res = GB.decode(img)
    return H, x0, y1, res


def z_at(img, x, y):
    return R.z_at(img, x, y)


class Prism(unittest.TestCase):
    def setUp(self):
        self.spec = TA.PrismSpec(resolution=0.1, margin=1.0)
        self.region = box(0, 0, 20, 20)
        self.slope = [(0, 0), (2, 3)]                    # 2 mm de large, 3 mm de haut

    def test_plateau_in_the_centre(self):
        img = TA.prism(self.region, self.slope, self.spec)
        self.assertAlmostEqual(z_at(img, 10, 10), 3.0, delta=0.02)
        self.assertAlmostEqual(z_at(img, 7, 13), 3.0, delta=0.02)

    def test_profile_on_the_edge(self):
        img = TA.prism(self.region, self.slope, self.spec)
        self.assertAlmostEqual(z_at(img, 1, 10), 1.5, delta=0.1)
        self.assertAlmostEqual(z_at(img, 19, 10), 1.5, delta=0.1)
        self.assertAlmostEqual(z_at(img, 0.5, 10), 0.75, delta=0.1)

    def test_outside_stays_at_zero(self):
        img = TA.prism(self.region, self.slope, self.spec)
        self.assertAlmostEqual(z_at(img, -0.5, 10), 0.0, delta=1e-6)

    def test_profile_may_be_drawn_either_way(self):
        a = heights(TA.prism(self.region, [(0, 0), (2, 3)], self.spec))[0]
        b = heights(TA.prism(self.region, [(50, 3), (48, 0)], self.spec))[0]
        self.assertLess(float(np.abs(a - b).max()), 1e-3)

    def test_curved_profile(self):
        pts = [(2 * (1 - math.cos(t * math.pi / 40)), 2 * math.sin(t * math.pi / 40)) for t in range(21)]
        img = TA.prism(self.region, pts, self.spec)
        self.assertAlmostEqual(z_at(img, 10, 10), 2.0, delta=0.02)
        self.assertGreater(z_at(img, 0.5, 10), 1.0)      # quart de rond : monte vite au bord

    def test_step_in_the_profile(self):
        img = TA.prism(self.region, [(0, 0), (1, 1), (1, 2), (3, 2)], self.spec)
        self.assertAlmostEqual(z_at(img, 10, 10), 2.0, delta=0.02)

    def test_flat_profile_refused(self):
        with self.assertRaises(ValueError):
            TA.prism(self.region, [(5, 0), (5, 3)], self.spec)
        with self.assertRaises(ValueError):
            TA.prism(self.region, [(5, 0)], self.spec)

    def test_empty_region(self):
        self.assertIsNone(TA.prism(None, self.slope, self.spec))

    def test_combined_with_a_relief(self):
        base = TA.extrude(box(-5, -5, 25, 25), TA.ExtrudeSpec(z=1.0))
        img = TA.prism(self.region, self.slope, TA.PrismSpec(mode='ajouter'), onto=base)
        self.assertAlmostEqual(z_at(img, 10, 10), 4.0, delta=0.02)
        self.assertAlmostEqual(z_at(img, 23, 10), 1.0, delta=0.02)

    def test_narrow_stroke_stays_below_the_plateau(self):
        img = TA.prism(box(0, 0, 2, 40), self.slope, self.spec)
        self.assertLess(z_at(img, 1, 20), 1.6)


class Facets(unittest.TestCase):
    def _block(self):
        H = np.zeros((60, 60))
        H[20:40, 20:40] = 2.0
        return H

    def test_slope_around_the_relief(self):
        out = R.edge_facets(self._block(), 0.5, 4.0)
        self.assertEqual(out[30, 30], 2.0)
        row = out[30, 20 - 9:20]
        self.assertTrue((np.diff(row) > 0).all(), row)
        self.assertLess(row[0], 0.4)
        self.assertGreater(row[-1], 1.5)

    def test_beyond_the_distance_nothing_changes(self):
        out = R.edge_facets(self._block(), 0.5, 4.0)
        self.assertEqual(out[30, 5], 0.0)
        self.assertEqual(out[3, 30], 0.0)

    def test_relief_itself_is_kept(self):
        H = self._block()
        out = R.edge_facets(H, 0.5, 4.0)
        self.assertTrue((out[20:40, 20:40] == H[20:40, 20:40]).all())

    def test_follows_the_height_of_the_nearest_edge(self):
        H = np.zeros((40, 80))
        H[10:30, 20:40] = 1.0
        H[10:30, 40:60] = 3.0
        out = R.edge_facets(H, 0.5, 2.0)
        self.assertGreater(out[20, 61], 1.5)
        self.assertLess(out[20, 18], 1.0)

    def test_nothing_to_do(self):
        H = np.zeros((10, 10))
        self.assertTrue((R.edge_facets(H, 0.1, 1.0) == 0).all())
        full = np.ones((10, 10))
        self.assertTrue((R.edge_facets(full, 0.1, 1.0) == 1).all())
        self.assertTrue((R.edge_facets(self._block(), 0.5, 0.0) == self._block()).all())

    def test_input_is_left_alone(self):
        H = self._block()
        R.edge_facets(H, 0.5, 4.0)
        self.assertEqual(H[30, 15], 0.0)


class Light(unittest.TestCase):
    def tearDown(self):
        V3.LIGHT.update(V3.LIGHT_DEFAULT)

    def test_default_is_the_former_light(self):
        for yaw in (0.0, 45.0, 200.0):
            a = math.radians(yaw - 30)
            for got, want in zip(V3.light_vector(yaw), (math.sin(a), -math.cos(a), 1.4)):
                self.assertAlmostEqual(got, want, places=9)

    def test_azimuth_turns_it(self):
        V3.LIGHT['azimuth'] = 120.0
        self.assertAlmostEqual(V3.light_vector(120.0)[1], -1.0)

    def test_elevation(self):
        V3.LIGHT['elevation'] = 45.0
        self.assertAlmostEqual(V3.light_vector(0.0)[2], 1.0)
        V3.LIGHT['elevation'] = 90.0
        self.assertLess(V3.light_vector(0.0)[2], 12.0)


class Commands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        for k in ('cad/view_light', 'vue3d/lumiere', 'typeart/prism'):
            cls.win.settings.remove(k)
        V3.LIGHT.update(V3.LIGHT_DEFAULT)
        cls.win.close()

    def setUp(self):
        doc = self.win.canvas.doc
        doc.layers = [Layer(name='Plan 1')]
        doc.active = doc.layers[0].id

    def _ribbon(self, key):
        return [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups() for b in g.buttons()
                if b.defaultAction() is self.win.A[key]]

    def test_ribbon(self):
        for k in ('relief_prism', 'relief_facets', 'view_light', 'group_reverse'):
            self.assertEqual(len(self._ribbon(k)), 1, k)

    def test_te_names(self):
        want = {'ID_TART_METNONDEF': 'relief_keep', 'ID_TART_EXTRACTTART': 'relief_extract', 'ID_TART_DEPOSE': 'relief_place',
                'ID_TROITOIR': 'relief_border', 'ID_TART_ISO_LETTER': 'relief_prism', 'ID_TART_FACETSONEDGES': 'relief_facets',
                'ID_SETLIGHTPOS': 'view_light', 'ID_INVERT_GROUP': 'group_reverse', 'ID_TART_RECALAGE_POINT': 'relief_z_align'}
        for te, key in want.items():
            self.assertEqual(S.TE_ACTIONS[te], key)
            self.assertIn(key, self.win.A)

    # --- mode prismatique
    def _select(self, *items):
        self.win.canvas.doc.layers[0].items = list(items)
        self.win.canvas.select(list(items))

    def test_prism_on_a_shape(self):
        form = Shape(path=Path([rect(0, 0, 20, 20)]))
        prof = Shape(path=Path([polyline([(100, 0), (102, 3)], False)]))
        self._select(form, prof)
        img = self.win.relief_prism(TA.PrismSpec())
        self.assertIsInstance(img, Image)
        self.assertAlmostEqual(z_at(img, 10, 10), 3.0, delta=0.02)
        self.assertIn(img, self.win.canvas.doc.layers[0].items)

    def test_prism_on_a_text_not_converted(self):
        t = Text(text='H', font='Arial', size=20.0)
        prof = Shape(path=Path([polyline([(100, 0), (100.5, 1)], False)]))
        self._select(t, prof)
        img = self.win.relief_prism(TA.PrismSpec())
        self.assertIsInstance(img, Image)
        H = heights(img)[0]
        self.assertAlmostEqual(float(H.max()), 1.0, delta=0.02)

    def test_prism_profile_is_the_last_open_curve(self):
        form = Shape(path=Path([rect(0, 0, 20, 20)]))
        first = Shape(path=Path([polyline([(100, 0), (102, 9)], False)]))
        prof = Shape(path=Path([polyline([(100, 0), (102, 3)], False)]))
        self._select(form, first, prof)
        img = self.win.relief_prism(TA.PrismSpec())
        self.assertAlmostEqual(z_at(img, 10, 10), 3.0, delta=0.02)

    def test_prism_needs_a_profile(self):
        self._select(Shape(path=Path([rect(0, 0, 20, 20)])))
        self.assertIsNone(self.win.relief_prism(TA.PrismSpec()))
        self.assertIn('profil', self.win.statusBar().currentMessage())

    def test_prism_needs_an_object(self):
        self._select(Shape(path=Path([polyline([(100, 0), (102, 3)], False)])))
        self.assertIsNone(self.win.relief_prism(TA.PrismSpec()))

    def test_prism_vertical_profile(self):
        self._select(Shape(path=Path([rect(0, 0, 20, 20)])), Shape(path=Path([polyline([(5, 0), (5, 3)], False)])))
        self.assertIsNone(self.win.relief_prism(TA.PrismSpec()))
        self.assertIn('largeur', self.win.statusBar().currentMessage())

    def test_prism_undo(self):
        form = Shape(path=Path([rect(0, 0, 20, 20)]))
        prof = Shape(path=Path([polyline([(100, 0), (102, 3)], False)]))
        self._select(form, prof)
        self.win.relief_prism(TA.PrismSpec())
        self.win.undo()
        self.assertFalse(any(isinstance(i, Image) for i in self.win.canvas.doc.layers[0].items))

    # --- facettes
    def test_facets_command(self):
        img = TA.extrude(box(0, 0, 20, 20), TA.ExtrudeSpec(z=2.0, margin=5.0))
        self._select(img)
        new = self.win.relief_op('relief_facets', {'distance': 2.0})
        self.assertIsInstance(new, Image)
        self.assertAlmostEqual(z_at(new, 10, 10), 2.0, delta=0.02)
        self.assertAlmostEqual(z_at(new, -1, 10), 1.0, delta=0.15)
        self.assertAlmostEqual(z_at(new, -4, 10), 0.0, delta=1e-6)

    # --- éclairage
    def test_light_command(self):
        got = self.win.view_light({'azimuth': 400.0, 'elevation': 200.0})
        self.assertAlmostEqual(got['azimuth'], 40.0)
        self.assertAlmostEqual(got['elevation'], 85.0)
        self.assertAlmostEqual(float(self.win.settings.value('vue3d/lumiere')[0]), 40.0)

    def test_light_cancel(self):
        before = dict(V3.LIGHT)
        with mock.patch.object(self.win, '_ask', return_value=None):
            self.assertIsNone(self.win.view_light())
        self.assertEqual(V3.LIGHT, before)

    def test_light_restored(self):
        self.win.settings.setValue('vue3d/lumiere', [12.0, 33.0])
        self.win._restore_light()
        self.assertEqual(V3.LIGHT, {'azimuth': 12.0, 'elevation': 33.0})
        self.win.settings.remove('vue3d/lumiere')
        self.win._restore_light()
        self.assertEqual(V3.LIGHT, V3.LIGHT_DEFAULT)

    def test_light_bad_setting(self):
        self.win.settings.setValue('vue3d/lumiere', 'abîmé')
        self.win._restore_light()
        self.win.settings.remove('vue3d/lumiere')
        self.assertEqual(V3.LIGHT, V3.LIGHT_DEFAULT)

    # --- ordre dans les groupes
    def test_group_reverse(self):
        a, b, c = (Shape(path=Path([rect(i, 0, 1, 1)])) for i in range(3))
        g = Group(children=[a, b, c])
        self._select(g)
        self.assertEqual(self.win.group_reverse(), 1)
        self.assertEqual(g.children, [c, b, a])

    def test_group_reverse_subgroups(self):
        a, b = (Shape(path=Path([rect(i, 0, 1, 1)])) for i in range(2))
        sub = Group(children=[a, b])
        c = Shape(path=Path([rect(9, 0, 1, 1)]))
        g = Group(children=[c, sub])
        self._select(g)
        self.assertEqual(self.win.group_reverse(), 2)
        self.assertEqual(g.children, [sub, c])
        self.assertEqual(sub.children, [b, a])

    def test_group_reverse_needs_a_group(self):
        self._select(Shape(path=Path([rect(0, 0, 1, 1)])))
        self.assertEqual(self.win.group_reverse(), 0)
        self.assertIn('groupe', self.win.statusBar().currentMessage())

    def test_group_reverse_undo(self):
        a, b = (Shape(path=Path([rect(i, 0, 1, 1)])) for i in range(2))
        g = Group(children=[a, b])
        self._select(g)
        self.win.group_reverse()
        self.win.undo()
        kept = self.win.canvas.doc.layers[0].items[0]
        self.assertEqual(kept.children[0].bbox()[0], 0.0)


if __name__ == '__main__':
    unittest.main()
