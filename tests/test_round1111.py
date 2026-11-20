"""Round 1111 : Reste de matière sur beaucoup de formes — la fenêtre mettait 23 s à s'ouvrir (1 500 formes, fraise Ø2) :
le nettoyage du reste (moins puis plus un quart de la tolérance) sur une multi-surface de 27 000 morceaux, que shapely
réunit à chaque pas. Même résultat, morceau par morceau."""
import os
import random
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1111.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import shapely  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.cam import model as M, strategies as S  # noqa: E402
from vectordrive.core import geom  # noqa: E402

app = QApplication.instance() or QApplication([])


def grid_region(n):
    paths = []
    for i in range(n):
        x, y = (i % 40) * 7.0, (i // 40) * 7.0
        paths.append(geom.Path([geom.rect(x, y, 5, 4) if i % 2 else geom.circle((x + 2.5, y + 2), 2)]))
    return S.region(paths, 0.01)


def blobs(n, seed):
    rng = random.Random(seed)
    gs = [shapely.Point(rng.uniform(0, 80), rng.uniform(0, 80)).buffer(rng.uniform(0.3, 4)) for _ in range(n)]
    gs += [shapely.box(x, y, x + rng.uniform(0.05, 6), y + rng.uniform(0.05, 6))
           for x, y in ((rng.uniform(0, 80), rng.uniform(0, 80)) for _ in range(n))]
    u = shapely.union_all(gs)
    return u.difference(shapely.union_all([shapely.Point(rng.uniform(0, 80), rng.uniform(0, 80)).buffer(1.5)
                                           for _ in range(n // 3)]))


def spy(calls):
    """`buffer` d'une multi-surface : le nombre de parties de chaque appel (le coût venait de là)."""
    real = shapely.MultiPolygon.buffer

    def buffer(g, distance, *a, **k):
        calls.append((len(g.geoms), distance))
        return real(g, distance, *a, **k)
    return buffer


class TestRestCleanup(unittest.TestCase):
    def test_opening_same_as_buffers(self):
        for seed, d in ((1, 0.0025), (2, 0.2), (3, 0.6)):
            g = blobs(120, seed)
            self.assertGreater(len(shapely.get_parts(g)), S.MANY_PARTS)
            want = g.buffer(-d).buffer(d)
            got = S.opening(g, d)
            self.assertAlmostEqual(got.area, want.area, delta=want.area * 1e-6)
            self.assertLess(got.symmetric_difference(want).area, want.area * 1e-6)

    def test_opening_small_and_empty(self):
        g = shapely.box(0, 0, 10, 10).union(shapely.box(20, 0, 20.1, 10))
        self.assertTrue(S.opening(g, 0.1).equals(g.buffer(-0.1).buffer(0.1)))   # peu de parties : tel quel
        self.assertIs(S.opening(g, 0.0), g)
        e = shapely.Polygon()
        self.assertIs(S.opening(e, 0.5), e)
        slivers = shapely.MultiPolygon([shapely.box(i, 0, i + 0.01, 5) for i in range(100)])
        out = S.opening(slivers, 0.05)                           # tout plus mince que 0,1 : rien ne reste
        self.assertTrue(out.is_empty)
        self.assertEqual(out.area, 0.0)

    def test_opening_overlapping_collection(self):
        boxes = [shapely.box(i * 0.5, 0, i * 0.5 + 2, 2) for i in range(60)]    # se chevauchent : réunies
        g = shapely.GeometryCollection(boxes)
        got = S.opening(g, 0.3)
        self.assertTrue(got.is_valid)
        want = shapely.union_all(boxes).buffer(-0.3).buffer(0.3)
        self.assertAlmostEqual(got.area, want.area, delta=want.area * 1e-6)
        bands = [shapely.box(i * 3.0, y, i * 3.0 + 2, y + 0.3) for i in range(40) for y in (0.0, 0.2)]
        for g in (shapely.GeometryCollection(bands), shapely.MultiPolygon(bands)):   # parties qui se chevauchent
            self.assertFalse(g.geom_type == 'MultiPolygon' and g.is_valid)
            want = g.buffer(-0.2).buffer(0.2)
            self.assertTrue(S.opening(g, 0.2).equals(want))      # tel que l'ancien calcul, pas morceau par morceau

    def test_rest_zones_not_one_big_buffer(self):
        reg = grid_region(600)
        tool = M.CamTool(name='F', kind='droite', diameter=2)
        calls = []
        with mock.patch.object(shapely.MultiPolygon, 'buffer', spy(calls)):
            rest, r = S.rest_zones(reg, tool)
        self.assertEqual(r, 1.0)
        big = [c for c in calls if abs(c[1]) < 0.01 and c[0] > S.MANY_PARTS]
        self.assertEqual(big, [], calls)                     # avant : ±0,0025 sur 10 000 parties, deux fois
        qs = S._quad_segs(1.0, 0.01)
        raw = reg.difference(S.erode(reg, 1.0, qs).buffer(1.0, quad_segs=qs))
        want = raw.buffer(-0.0025).buffer(0.0025)                # l'ancien nettoyage
        self.assertAlmostEqual(rest.area, want.area, delta=want.area * 1e-4)
        self.assertGreater(rest.area, 0.0)

    def test_thick_only_same(self):
        from vectordrive.ui import rest_preview_dialog as RP
        g = blobs(120, 4)
        for t in (0.3, 1.0):
            want = g.buffer(-t / 2).buffer(t / 2)
            got = RP.thick_only(g, t)
            self.assertAlmostEqual(got.area, want.area, delta=want.area * 1e-6)
        self.assertIs(RP.thick_only(g, 0.0), g)

    def test_dialog_on_many_shapes(self):
        from vectordrive.ui.rest_preview_dialog import RestPreviewDialog
        reg = grid_region(400)
        tool = M.CamTool(name='F', kind='droite', diameter=2)
        dlg = RestPreviewDialog(None, reg, [tool], tool=tool)
        try:
            self.assertIsNotNone(dlg.rest)
            want, _r = S.rest_zones(reg, tool)
            self.assertAlmostEqual(dlg.rest.area, want.area, places=9)
            dlg.thin.setValue(0.2)                               # zones minces ôtées : moins de reste
            self.assertLess(dlg.rest.area, want.area)
            self.assertFalse(dlg.view.rest.isEmpty())
        finally:
            dlg.deleteLater()


if __name__ == '__main__':
    unittest.main()
