"""Round 783 : usinage d'un relief — comme une pièce 3D, angle, spirale, tranches parallèles, suivi du profil."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.cam import mill3d, model, strategies as S
from vectordrive.cam.advanced import with_stock
from vectordrive.core import galbe as GB
from vectordrive.core.document import Document


def app():
    return QApplication.instance() or QApplication([])


def dome_map(n=60, top=3.0):
    y, x = np.mgrid[0:n, 0:n]
    r = np.hypot(x - (n - 1) / 2, y - (n - 1) / 2) / ((n - 1) / 2)
    return np.clip(1 - r * r, 0, 1) * top


def relief(n=60, top=3.0, x0=0.0, y1=30.0, res=0.5, name='Dôme'):
    app()
    return GB.encode(dome_map(n, top), x0, y1, res, GB.GalbeSpec(z_max=top), 0, name)


class Recorder:
    def __init__(self):
        self.pos = None
        self.feeds = []
        self.travels = 0

    def travel(self, x, y):
        self.travels += 1
        self.pos = (x, y, 0.0)

    def plunge(self, z):
        self.pos = (self.pos[0], self.pos[1], z)

    def feed(self, x, y, z):
        self.feeds.append((x, y, z))
        self.pos = (x, y, z)

    def retract(self):
        pass


def setup_for(kind, img, tool_kind='boule', diameter=2.0, step_down=1.0, **kw):
    d = Document()
    d.plate = None
    d.add(img)
    s = model.CamSetup()
    t = model.CamTool(name='Outil', kind=tool_kind, diameter=diameter, step_down=step_down, feed=800.0)
    s.tools = [t]
    op = model.Operation(kind=kind, tool_id=t.id, depth=kw.pop('depth', 0.0), resolution=kw.pop('resolution', 0.25), **kw)
    s.operations = [op]
    return d, s, op


def compute(kind, img=None, **kw):
    d, s, op = setup_for(kind, img or relief(), **kw)
    return S.compute(d, s, op)


def feeds(tp):
    return [m for m in tp.moves if m.kind == 'feed']


def surface_at(x, y, n=60, top=3.0, res=0.5, y1=30.0):
    """Le dôme à ce point, sommet à Z = 0."""
    i, j = (x - 0.0) / res - 0.5, (y1 - y) / res - 0.5
    r = math.hypot(i - (n - 1) / 2, j - (n - 1) / 2) / ((n - 1) / 2)
    return max(0.0, 1 - r * r) * top - top


class AsAPiece(unittest.TestCase):
    def test_surface_on_a_relief(self):
        tp = compute('surface3d')
        zs = [m.z for m in feeds(tp)]
        self.assertTrue(zs)
        self.assertAlmostEqual(min(zs), -3.0, delta=0.1)
        self.assertGreater(max(zs), -0.3)
        self.assertEqual([w for w in tp.warnings if 'choisir' in w], [])

    def test_surface_stays_in_the_rectangle(self):
        tp = compute('surface3d')
        for m in feeds(tp):
            self.assertGreaterEqual(m.x, -0.01)
            self.assertLessEqual(m.x, 30.01)
            self.assertGreaterEqual(m.y, -0.01)
            self.assertLessEqual(m.y, 30.01)

    def test_surface_does_not_gouge(self):
        tp = compute('surface3d')
        for m in feeds(tp)[::7]:
            self.assertGreaterEqual(m.z, surface_at(m.x, m.y) - 0.1)

    def test_rough(self):
        tp = compute('ebauche3d', tool_kind='fraise', diameter=4.0, stock=0.2, resolution=0.25)
        ms = feeds(tp)
        self.assertTrue(ms)
        self.assertLessEqual(min(m.z for m in ms), -2.5)
        for m in ms[::11]:
            self.assertGreaterEqual(m.z, surface_at(m.x, m.y) + 0.1)

    def test_rough_levels(self):
        tp = compute('ebauche3d', tool_kind='fraise', diameter=4.0, step_down=1.0)
        levels = {round(m.z, 1) for m in feeds(tp)}
        self.assertIn(-1.0, levels)
        self.assertIn(-2.0, levels)

    def test_rest_behind_a_bigger_tool(self):
        d, s, op = setup_for('reprise3d', relief(), tool_kind='boule', diameter=1.0, stock=0.0)
        big = model.CamTool(name='Gros', kind='fraise', diameter=6.0, step_down=1.0, feed=800.0)
        s.tools.append(big)
        op.ref_tool_id = big.id
        tp = S.compute(d, s, op)
        self.assertTrue(feeds(tp))

    def test_waterline(self):
        tp = compute('niveaux3d', tool_kind='boule', diameter=1.0, step_down=0.5, resolution=0.25)
        self.assertTrue(feeds(tp))
        for m in feeds(tp)[::5]:
            self.assertGreaterEqual(m.z, surface_at(m.x, m.y) - 0.1)

    def test_depth_limits_the_relief(self):
        tp = compute('surface3d', depth=1.0)
        self.assertGreaterEqual(min(m.z for m in feeds(tp)), -1.0 - 1e-6)

    def test_tilted_relief_is_reported(self):
        from vectordrive.core.geom import Affine
        tp = compute('surface3d', img=relief().transformed(Affine.rotation(20)))
        self.assertTrue(any('posé droit' in w for w in tp.warnings))
        self.assertEqual(feeds(tp), [])

    def test_two_reliefs_share_their_top(self):
        d, s, op = setup_for('surface3d', relief())
        d.add(relief(top=1.0, x0=40.0))
        tp = S.compute(d, s, op)
        here = [m.z for m in feeds(tp) if math.hypot(m.x - 55, m.y - 15) < 4.0]      # au milieu du petit relief
        self.assertAlmostEqual(max(here), -2.0, delta=0.3)

    def test_no_relief_no_model_message(self):
        d = Document()
        d.plate = None
        s = model.CamSetup()
        t = model.CamTool(name='O', kind='boule', diameter=2.0, step_down=1.0, feed=800.0)
        s.tools = [t]
        op = model.Operation(kind='surface3d', tool_id=t.id)
        s.operations = [op]
        tp = S.compute(d, s, op)
        self.assertTrue(any('relief' in w for w in tp.warnings))

    def test_own_model_file_comes_first(self):
        d, s, op = setup_for('surface3d', relief())
        op.model_path = 'inconnu.stl'
        self.assertEqual(mill3d.relief_images(d, op), [])

    def test_volumes_come_first_unless_chosen(self):
        from unittest import mock
        d, s, op = setup_for('surface3d', relief())
        with mock.patch.object(mill3d, 'volume_items', return_value=[object()]):
            self.assertEqual(mill3d.relief_images(d, op), [])
            op.items = [d.layers[0].items[0].id]
            self.assertEqual(len(mill3d.relief_images(d, op)), 1)

    def test_a_plain_image_is_not_a_relief(self):
        d, s, op = setup_for('surface3d', relief())
        d.layers[0].items[0].extra.pop('galbe')
        self.assertEqual(mill3d.relief_images(d, op), [])


class Sample(unittest.TestCase):
    def test_bilinear(self):
        g = mill3d.Grid(0.0, 0.0, 3, 2, 1.0)
        T = np.array([[0.0, 1.0, 2.0], [10.0, 11.0, 12.0]])
        self.assertAlmostEqual(float(mill3d.sample(T, g, 0.5, 0.5)), 5.5)
        self.assertAlmostEqual(float(mill3d.sample(T, g, 2.0, 1.0)), 12.0)
        self.assertAlmostEqual(float(mill3d.sample(T, g, 99.0, -5.0)), 2.0)


class Angle(unittest.TestCase):
    def _flat(self):
        return np.full((81, 81), -1.0), mill3d.Grid(0.0, 0.0, 81, 81, 0.25)

    def _setup(self):
        return model.CamSetup()

    def test_rotation_round_trip(self):
        em = Recorder()
        t = mill3d.Turned(em, 30.0)
        t.travel(1.0, 2.0)
        u, v, _z = t.pos
        self.assertAlmostEqual(u, 1.0)
        self.assertAlmostEqual(v, 2.0)

    def test_passes_follow_the_angle(self):
        tp = compute('surface3d', scan_mode='angle', raster_angle=45.0, resolution=0.25)
        ms = feeds(tp)
        dirs = [math.degrees(math.atan2(b.y - a.y, b.x - a.x)) % 180 for a, b in zip(ms, ms[1:])
                if math.hypot(b.x - a.x, b.y - a.y) > 2.0]
        self.assertTrue(dirs)
        along = sum(1 for d in dirs if abs(d - 45) < 2)
        self.assertGreater(along / len(dirs), 0.8)

    def test_stays_in_the_rectangle(self):
        tp = compute('surface3d', scan_mode='angle', raster_angle=30.0, resolution=0.25)
        for m in feeds(tp):
            self.assertGreaterEqual(m.x, -0.3)
            self.assertLessEqual(m.x, 30.3)
            self.assertGreaterEqual(m.y, -0.3)
            self.assertLessEqual(m.y, 30.3)

    def test_covers_the_rectangle(self):
        tp = compute('surface3d', scan_mode='angle', raster_angle=30.0, resolution=0.25)
        pts = np.array([(m.x, m.y) for m in feeds(tp)])
        self.assertGreater(pts[:, 0].max() - pts[:, 0].min(), 25)
        self.assertGreater(pts[:, 1].max() - pts[:, 1].min(), 25)

    def test_every_point_is_near_a_pass(self):
        tp = compute('surface3d', scan_mode='angle', raster_angle=30.0, resolution=0.25)
        ms = feeds(tp)
        dense = []
        for a, b in zip(ms, ms[1:]):
            n = max(1, int(math.hypot(b.x - a.x, b.y - a.y) / 0.2))
            dense.extend((a.x + (b.x - a.x) * k / n, a.y + (b.y - a.y) * k / n) for k in range(n))
        pts = np.array(dense)
        so = 0.2 * 2.0                                  # recouvrement de l'outil : 20 % de 2 mm
        for x, y in ((3, 3), (15, 15), (27, 3), (3, 27), (27, 27), (8.3, 21.7)):
            self.assertLess(float(np.hypot(pts[:, 0] - x, pts[:, 1] - y).min()), so + 0.3, (x, y))

    def test_no_gouge(self):
        tp = compute('surface3d', scan_mode='angle', raster_angle=30.0, resolution=0.25)
        for m in feeds(tp)[::5]:
            self.assertGreaterEqual(m.z, surface_at(m.x, m.y) - 0.15)

    def test_cross_pass_is_added(self):
        a = len(feeds(compute('surface3d', scan_mode='angle', raster_angle=20.0, resolution=0.25)))
        b = len(feeds(compute('surface3d', scan_mode='angle', raster_angle=20.0, raster_turn=90.0, resolution=0.25)))
        self.assertGreater(b, a * 1.1)

    def test_zero_matches_x(self):
        a = feeds(compute('surface3d', scan_mode='angle', raster_angle=0.0, resolution=0.25))
        b = feeds(compute('surface3d', resolution=0.25))
        self.assertLess(abs(len(a) - len(b)) / len(b), 0.1)

    def test_on_the_relief_operation(self):
        tp = compute('relief', scan_mode='angle', raster_angle=45.0, resolution=0.25)
        self.assertTrue(feeds(tp))


class Spiral(unittest.TestCase):
    def test_path_stays_in_the_box(self):
        p = mill3d.spiral_path((0, 0, 30, 10), 1.0, 0.25)
        self.assertGreaterEqual(p[:, 0].min(), -1e-9)
        self.assertLessEqual(p[:, 0].max(), 30 + 1e-9)
        self.assertGreaterEqual(p[:, 1].min(), -1e-9)
        self.assertLessEqual(p[:, 1].max(), 10 + 1e-9)

    def test_path_is_continuous(self):
        p = mill3d.spiral_path((0, 0, 30, 10), 1.0, 0.25)
        gaps = np.hypot(*np.diff(p, axis=0).T)
        self.assertLess(float(gaps.max()), 0.8)

    def test_starts_outside_or_inside(self):
        p = mill3d.spiral_path((0, 0, 30, 10), 1.0, 0.25)
        self.assertLess(min(p[0][0], 30 - p[0][0], p[0][1], 10 - p[0][1]), 1e-6)
        q = mill3d.spiral_path((0, 0, 30, 10), 1.0, 0.25, outward=True)
        self.assertGreater(min(q[0][0], 30 - q[0][0], q[0][1], 10 - q[0][1]), 3.0)

    def test_every_point_of_the_box_is_near_a_pass(self):
        p = mill3d.spiral_path((0, 0, 30, 10), 1.0, 0.25)
        for x, y in ((1.5, 1.5), (15, 5), (29.5, 9.5), (20, 8.2), (7, 2.7)):
            self.assertLess(float(np.hypot(p[:, 0] - x, p[:, 1] - y).min()), 0.75)

    def _turning(self, p):
        x, y = p[:, 0], p[:, 1]
        return 0.5 * float(np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1]))

    def test_direction(self):
        # en avalant, la matière à droite : vers l'intérieur la matière est dedans, l'outil tourne en sens horaire
        inward_climb = mill3d.spiral_path((0, 0, 30, 10), 1.0, 0.25, climb=True)
        inward_opp = mill3d.spiral_path((0, 0, 30, 10), 1.0, 0.25, climb=False)
        self.assertLess(self._turning(inward_climb), 0)
        self.assertGreater(self._turning(inward_opp), 0)
        outward_climb = mill3d.spiral_path((0, 0, 30, 10), 1.0, 0.25, outward=True, climb=True)
        self.assertGreater(self._turning(outward_climb), 0)

    def test_square(self):
        p = mill3d.spiral_path((0, 0, 10, 10), 3.0, 0.25)
        self.assertLess(float(np.hypot(p[:, 0] - 5, p[:, 1] - 5).min()), 0.5)

    def test_operation(self):
        tp = compute('surface3d', scan_mode='spirale', resolution=0.25)
        ms = feeds(tp)
        self.assertTrue(ms)
        self.assertAlmostEqual(min(m.z for m in ms), -3.0, delta=0.15)
        for m in ms[::5]:
            self.assertGreaterEqual(m.z, surface_at(m.x, m.y) - 0.15)

    def test_one_plunge_by_level(self):
        d, s, op = setup_for('surface3d', relief(), scan_mode='spirale', resolution=0.25, step_down=10.0)
        tp = S.compute(d, s, op)
        rapids = [m for m in tp.moves if m.kind == 'plunge']
        self.assertLessEqual(len(rapids), 3)

    def test_on_the_relief_operation(self):
        tp = compute('relief', scan_mode='spirale', resolution=0.25)
        self.assertTrue(feeds(tp))


class Slices(unittest.TestCase):
    def test_parallel_to_the_profile(self):
        tp = compute('surface3d', parallel_slices=3, step_down=0.5, resolution=0.25)
        ms = feeds(tp)
        high = max(m.z for m in ms)
        self.assertAlmostEqual(high, 1.0, delta=0.1)                 # sommet : deux tranches au-dessus
        self.assertAlmostEqual(min(m.z for m in ms), -3.0, delta=0.15)

    def test_total_depth_is_stated(self):
        tp = compute('surface3d', parallel_slices=3, step_down=0.5, resolution=0.25)
        self.assertTrue(any('1.5 mm' in w for w in tp.warnings))

    def test_as_many_passes_as_slices(self):
        one = len(feeds(compute('surface3d', parallel_slices=1, step_down=0.5, resolution=0.25)))
        three = len(feeds(compute('surface3d', parallel_slices=3, step_down=0.5, resolution=0.25)))
        self.assertAlmostEqual(three / one, 3.0, delta=0.3)

    def test_last_slice_is_the_surface(self):
        tp = compute('surface3d', parallel_slices=2, step_down=0.5, resolution=0.25)
        for m in feeds(tp)[-200:]:
            self.assertGreaterEqual(m.z, surface_at(m.x, m.y) - 0.15)

    def test_on_the_relief_operation(self):
        tp = compute('relief', parallel_slices=2, step_down=0.5, resolution=0.25)
        self.assertAlmostEqual(max(m.z for m in feeds(tp)), 0.5, delta=0.1)


class Profile(unittest.TestCase):
    def test_following_keeps_cutting_time_on_the_surface(self):
        follow = compute('surface3d', step_down=1.0, resolution=0.25)
        skip = compute('surface3d', step_down=1.0, resolution=0.25, follow_profile=False)
        self.assertLess(len(feeds(skip)), len(feeds(follow)))

    def test_skip_retracts_more(self):
        follow = compute('surface3d', step_down=1.0, resolution=0.25)
        skip = compute('surface3d', step_down=1.0, resolution=0.25, follow_profile=False)
        rapid = lambda tp: sum(1 for m in tp.moves if m.kind == 'plunge')
        self.assertGreater(rapid(skip), rapid(follow))

    def test_skip_leaves_no_stair(self):
        tp = compute('surface3d', step_down=1.0, resolution=0.25, follow_profile=False)
        ms = feeds(tp)
        low = {}
        for m in ms:
            k = (round(m.x), round(m.y))
            low[k] = min(low.get(k, 9), m.z)
        far = 0
        for (x, y), z in low.items():
            if 2 < x < 28 and 2 < y < 28 and math.hypot(x - 15, y - 15) < 10:
                far = max(far, z - surface_at(x, y))
        self.assertLess(far, 0.75)

    def test_first_level_is_complete(self):
        T = np.full((41, 41), -2.0)
        g = mill3d.Grid(0.0, 0.0, 41, 41, 0.5)
        em = Recorder()
        op = model.Operation(kind='surface3d')
        tool = model.CamTool(name='O', kind='boule', diameter=2.0, step_down=1.0, feed=800.0)
        mill3d.raster(em, model.CamSetup(), op, tool, T, g, [-1.0, -2.0], None, 'x', skip_done=True)
        zs = {round(p[2], 3) for p in em.feeds}
        self.assertEqual(zs, {-1.0, -2.0})

    def test_skip_avoids_the_finished_top(self):
        T = np.full((41, 41), -2.0)
        T[:, :20] = 0.0                                 # la moitié gauche est déjà à sa cote
        g = mill3d.Grid(0.0, 0.0, 41, 41, 0.5)
        em = Recorder()
        tool = model.CamTool(name='O', kind='boule', diameter=2.0, step_down=1.0, feed=800.0)
        mill3d.raster(em, model.CamSetup(), model.Operation(kind='surface3d'), tool, T, g, [-1.0, -2.0], None, 'x', skip_done=True)
        second = [p for p in em.feeds if p[2] < -1.5]
        self.assertGreater(min(p[0] for p in second), 9.0)

    def test_spiral_skip(self):
        tp = compute('surface3d', scan_mode='spirale', step_down=1.0, resolution=0.25, follow_profile=False)
        self.assertTrue(feeds(tp))

    def test_angle_skip(self):
        tp = compute('surface3d', scan_mode='angle', raster_angle=30.0, step_down=1.0, resolution=0.25, follow_profile=False)
        self.assertTrue(feeds(tp))


class Saved(unittest.TestCase):
    def test_defaults_unchanged(self):
        op = model.Operation(kind='relief')
        self.assertEqual(op.scan_mode, 'passes')
        self.assertTrue(op.follow_profile)
        self.assertEqual(op.parallel_slices, 0)

    def test_default_relief_path_unchanged(self):
        from unittest import mock
        with mock.patch.object(mill3d, 'finish') as finish:
            compute('relief', resolution=0.5)
        finish.assert_not_called()

    def test_settings_saved(self):
        import dataclasses
        op = model.Operation(kind='relief', scan_mode='angle', raster_angle=12.5, raster_turn=90.0,
                             spiral_outward=True, parallel_slices=3, follow_profile=False)
        self.assertEqual(dataclasses.asdict(op)['raster_angle'], 12.5)
        s = model.CamSetup()
        s.operations = [op]
        back = model.CamSetup.from_dict(s.to_dict())
        o = back.operations[0]
        self.assertEqual((o.scan_mode, o.raster_angle, o.raster_turn, o.spiral_outward, o.parallel_slices, o.follow_profile),
                         ('angle', 12.5, 90.0, True, 3, False))

    def test_panel_labels(self):
        from vectordrive.ui import cam_panel as CP
        import inspect
        src = inspect.getsource(CP)
        for name in ('scan_mode', 'raster_angle', 'raster_turn', 'spiral_outward', 'parallel_slices', 'follow_profile'):
            self.assertGreaterEqual(src.count(f"'{name}'"), 3, name)


if __name__ == '__main__':
    unittest.main()
