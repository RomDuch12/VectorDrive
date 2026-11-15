"""Round 785 : enroulement d'un relief sur un autre."""
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

from vectordrive.core import galbe as GB, relief_wrap as RW
from vectordrive.core.document import Layer


def app():
    return QApplication.instance() or QApplication([])


def box_of(H, x0, y1, res):
    return (x0, y1 - H.shape[0] * res, x0 + H.shape[1] * res, y1)


def flat(w=60.0, h=60.0, z=0.0, res=0.25):
    H = np.full((int(h / res), int(w / res)), z)
    return H, 0.0, h, res


def block(w=10.0, h=10.0, z=1.0, res=0.25, x0=100.0, y1=100.0):
    return np.full((int(h / res), int(w / res)), z), x0, y1, res


def half_cylinder(R=40.0, w=60.0, h=60.0, res=0.25):
    """Un demi-cylindre d'axe Y : la hauteur varie selon X."""
    nx, ny = int(w / res), int(h / res)
    xs = 0.0 + (np.arange(nx) + 0.5) * res - w / 2
    z = np.sqrt(np.maximum(R * R - xs * xs, 0))
    return np.tile(z - z.min(), (ny, 1)), 0.0, h, res


def half_sphere(R=40.0, w=60.0, res=0.25):
    n = int(w / res)
    a = (np.arange(n) + 0.5) * res - w / 2
    X, Y = np.meshgrid(a, a)
    z = np.sqrt(np.maximum(R * R - X * X - Y * Y, 0))
    return z - z.min(), 0.0, w, res


def spread(H, x0, y1, res, floor, axis):
    """Étendue (mm) de ce qui dépasse de `floor` selon l'axe."""
    on = np.abs(H - floor) > 1e-6
    k = np.flatnonzero(on.any(axis=axis))
    return (k[-1] - k[0] + 1) * res


class Core(unittest.TestCase):
    def _run(self, base, motif, **kw):
        spec = RW.WrapSpec(**kw)
        return RW.wrap_heights(base, box_of(*base), motif, box_of(*motif), spec)

    def test_parallel_centre(self):
        H, x0, y1, res = self._run(flat(), block())
        j, i = np.nonzero(H > 0.5)
        self.assertAlmostEqual(x0 + (i.min() + i.max() + 1) / 2 * res, 30.0, delta=0.3)
        self.assertAlmostEqual(y1 - (j.min() + j.max() + 1) / 2 * res, 30.0, delta=0.3)
        self.assertAlmostEqual((i.max() - i.min() + 1) * res, 10.0, delta=0.5)

    def test_heights_add(self):
        H, *_ = self._run(flat(z=2.0), block(z=1.5))
        self.assertAlmostEqual(float(H.max()), 3.5)
        self.assertAlmostEqual(float(H.min()), 2.0)

    def test_subtract(self):
        H, *_ = self._run(flat(z=2.0), block(z=0.5), mode='soustraire')
        self.assertAlmostEqual(float(H.min()), 1.5)
        self.assertAlmostEqual(float(H.max()), 2.0)

    def test_only_the_wrapped_relief(self):
        H, *_ = self._run(flat(z=2.0), block(z=0.5), mode='seul')
        self.assertAlmostEqual(float(H.max()), 2.5)
        self.assertEqual(float(H.min()), 0.0)
        self.assertLess(float((H > 0).mean()), 0.1)

    def test_corners(self):
        for anchor, want in (('haut_gauche', (0, 0)), ('bas_droite', (-1, -1))):
            H, *_ = self._run(flat(), block(), anchor=anchor)
            self.assertGreater(float(H[want]), 0.5, anchor)

    def test_markers(self):
        base, motif = flat(), block()
        H, x0, y1, res = RW.wrap_heights(base, box_of(*base), motif, box_of(*motif), RW.WrapSpec(anchor='marqueurs'),
                                         (20.0, 40.0), (105.0, 95.0))
        j, i = np.nonzero(H > 0.5)
        self.assertAlmostEqual(x0 + (i.min() + i.max() + 1) / 2 * res, 20.0, delta=0.3)
        self.assertAlmostEqual(y1 - (j.min() + j.max() + 1) / 2 * res, 40.0, delta=0.3)

    def test_motif_keeps_its_orientation(self):
        Hm = np.zeros((40, 40))
        Hm[:20, :] = 1.0                                # la moitié haute du motif
        H, *_ = self._run(flat(), (Hm, 100.0, 100.0, 0.25), anchor='haut_gauche')
        self.assertEqual(float(H[5, 5]), 1.0)
        self.assertEqual(float(H[35, 5]), 0.0)

    def test_flat_support_all_kinds_agree(self):
        ref, *_ = self._run(flat(), block(z=1.0))
        for kind in ('spherique', 'cyl_x', 'cyl_y'):
            H, *_ = self._run(flat(), block(z=1.0), kind=kind)
            self.assertLess(float(np.abs(H - ref).max()), 1e-6, kind)

    def test_cylinder_shrinks_seen_from_above(self):
        base = half_cylinder()
        H, x0, y1, res = self._run(base, block(w=50.0, h=10.0, z=5.0), kind='cyl_y')
        d = H - base[0]
        wide = spread(d, x0, y1, res, 0.0, 0)
        want = 2 * RW.sphere_reach(40.0, 25.0)         # même rapport pour un cercle : 40·sin(25/40)
        self.assertAlmostEqual(wide, want, delta=0.8)
        self.assertLess(wide, 49.0)

    def test_cylinder_leaves_the_other_direction(self):
        base = half_cylinder()
        H, x0, y1, res = self._run(base, block(w=50.0, h=10.0, z=5.0), kind='cyl_y')
        self.assertAlmostEqual(spread(H - base[0], x0, y1, res, 0.0, 1), 10.0, delta=0.6)

    def test_cylinder_around_x(self):
        H0, x0, y1, res = half_cylinder()
        base = (H0.T, x0, y1, res)                      # l'axe devient X
        H, x, y, r = self._run(base, block(w=10.0, h=50.0, z=5.0), kind='cyl_x')
        self.assertLess(spread(H - base[0], x, y, r, 0.0, 1), 49.0)
        self.assertAlmostEqual(spread(H - base[0], x, y, r, 0.0, 0), 10.0, delta=0.6)

    def test_parallel_does_not_shrink(self):
        base = half_cylinder()
        H, x0, y1, res = self._run(base, block(w=50.0, h=10.0, z=5.0))
        self.assertAlmostEqual(spread(H - base[0], x0, y1, res, 0.0, 0), 50.0, delta=0.6)

    def test_sphere_shrinks_in_both_directions(self):
        base = half_sphere()
        H, x0, y1, res = self._run(base, block(w=40.0, h=40.0, z=5.0), kind='spherique')
        d = H - base[0]
        want = 2 * RW.sphere_reach(40.0, 20.0)
        self.assertAlmostEqual(spread(d, x0, y1, res, 0.0, 0), want, delta=1.5)
        self.assertAlmostEqual(spread(d, x0, y1, res, 0.0, 1), want, delta=1.5)

    def test_sphere_middle_is_undisturbed(self):
        base = half_sphere()
        Hm = np.zeros((160, 160))
        Hm[78:82, 78:82] = 5.0
        H, x0, y1, res = self._run(base, (Hm, 100.0, 100.0, 0.25), kind='spherique')
        j, i = np.nonzero(H - base[0] > 1.0)
        self.assertAlmostEqual((i.min() + i.max() + 1) / 2 * res, 30.0, delta=0.5)
        self.assertAlmostEqual((j.min() + j.max() + 1) / 2 * res, 30.0, delta=0.5)

    def test_copies_fill_the_galbe(self):
        Hb = np.zeros((240, 240))
        Hb[40:200, 40:200] = 1.0                        # un galbe au milieu de sa boîte
        base = (Hb, 0.0, 60.0, 0.25)
        H, *_ = self._run(base, block(w=5.0, h=5.0, z=1.0), copies_x=True, copies_y=True)
        self.assertEqual(float(H[10, 10]), 0.0)         # hors du galbe : rien
        self.assertEqual(float(H[120, 120]), 2.0)       # une copie entière dessus

    def test_copies_x_only(self):
        base = flat(z=1.0)
        H0, x0, y1, res = self._run(base, block(w=5.0, h=5.0, z=1.0))
        H, *_ = self._run((base[0] + 0.0, base[1], base[2], base[3]), block(w=5.0, h=5.0, z=1.0), copies_x=True)
        self.assertEqual(spread(H0, x0, y1, res, 1.0, 1), spread(H, x0, y1, res, 1.0, 1))
        self.assertGreater(float((H > 1.5).sum()), 5 * float((H0 > 1.5).sum()))

    def test_step_of_the_result(self):
        H, x0, y1, res = self._run(flat(), block(), resolution=0.5)
        self.assertEqual(res, 0.5)
        self.assertEqual(H.shape, (120, 120))
        self.assertAlmostEqual(float(H.max()), 1.0)


class Images(unittest.TestCase):
    def _imgs(self):
        app()
        base = flat(z=1.0)
        motif = block(z=0.5)
        spec = GB.GalbeSpec(z_max=1.0)
        return GB.encode(*base, spec, 3, 'Support'), GB.encode(*motif, GB.GalbeSpec(z_max=0.5), 0, 'Motif')

    def test_result(self):
        a, b = self._imgs()
        out = RW.wrap(a, b, RW.WrapSpec())
        self.assertEqual(out.tool, 3)
        self.assertEqual(out.name, 'Support')
        self.assertAlmostEqual(out.extra['galbe']['top'], 1.5, places=3)
        for u, v in zip(out.bbox(), a.bbox()):
            self.assertAlmostEqual(u, v, places=6)

    def test_tilted_refused(self):
        from vectordrive.core.geom import Affine
        a, b = self._imgs()
        self.assertIsNone(RW.wrap(a.transformed(Affine.rotation(10)), b, RW.WrapSpec()))
        self.assertIsNone(RW.wrap(a, b.transformed(Affine.rotation(10)), RW.WrapSpec()))

    def test_markers_missing(self):
        a, b = self._imgs()
        with self.assertRaises(ValueError):
            RW.wrap(a, b, RW.WrapSpec(anchor='marqueurs'), [(1.0, 1.0)])


class Command(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app()
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.close()

    def setUp(self):
        doc = self.win.canvas.doc
        doc.layers = [Layer(name='Plan 1')]
        doc.active = doc.layers[0].id
        self.base = GB.encode(*flat(z=1.0), GB.GalbeSpec(z_max=1.0), 0, 'Support')
        self.motif = GB.encode(*block(z=0.5), GB.GalbeSpec(z_max=0.5), 0, 'Motif')
        doc.layers[0].items = [self.base, self.motif]
        self.win.canvas.select([self.base, self.motif])
        self.patch = mock.patch('vectordrive.ui.progress.run', side_effect=lambda _p, _t, f, *a: f(*a))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    @property
    def items(self):
        return self.win.canvas.doc.layers[0].items

    def test_ribbon_once(self):
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups() for b in g.buttons()
                 if b.defaultAction() is self.win.A['relief_wrap']]
        self.assertEqual(len(found), 1)

    def test_te_link(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_WRAPPING_TARTTART'], 'relief_wrap')

    def test_replaces_both(self):
        img = self.win.relief_wrap({})
        self.assertEqual(self.items, [img])
        self.assertAlmostEqual(img.extra['galbe']['top'], 1.5, places=3)

    def test_keep_original(self):
        img = self.win.relief_wrap({'keep': True})
        self.assertEqual(self.items, [img, self.motif])

    def test_undo(self):
        self.win.relief_wrap({})
        self.win.undo()
        self.assertEqual(len(self.items), 2)

    def test_needs_two(self):
        self.win.canvas.select([self.base])
        self.assertIsNone(self.win.relief_wrap({}))

    def test_markers_missing(self):
        self.assertIsNone(self.win.relief_wrap({'anchor': 'marqueurs'}))
        self.assertEqual(len(self.items), 2)


if __name__ == '__main__':
    unittest.main()
