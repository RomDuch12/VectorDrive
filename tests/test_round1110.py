"""Round 1110 : booléens et Détourer sur beaucoup de formes — Exclusion pliée (le carré du nombre d'objets : 1 500
formes, des minutes), Différence d'une plaque moins ses trous soustraits un à un (1 000 trous : 76 s), Détourer réunissant
tout le dessus à chaque forme. Mêmes résultats, en arbre / en une fois / par voisinage."""
import os
import random
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1110.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom, pathfinder as PF, pathops as P  # noqa: E402

app = QApplication.instance() or QApplication([])


def grid(n, x0=0.0, y0=0.0):
    out = []
    for i in range(n):
        x, y = x0 + (i % 40) * 7.0, y0 + (i // 40) * 7.0
        out.append(geom.Path([geom.rect(x, y, 5, 4) if i % 2 else geom.circle((x + 2.5, y + 2), 2)]))
    return out


def blobs(n, seed):
    rng = random.Random(seed)
    return [geom.Path([geom.circle((rng.uniform(0, 30), rng.uniform(0, 30)), rng.uniform(2, 7)) if i % 2 else
                       geom.rect(rng.uniform(0, 30), rng.uniform(0, 30), rng.uniform(2, 9), rng.uniform(2, 9))])
            for i in range(n)]


class Counted:
    """`pathops.boolean` compté : appels par opération et contours passés (le coût d'un pli grandit avec eux)."""

    def __init__(self):
        self.calls, self.contours = {}, 0
        self.real = P.boolean

    def __call__(self, a, b, op):
        self.calls[op] = self.calls.get(op, 0) + 1
        self.contours += len(a.contours) + len(b.contours)
        return self.real(a, b, op)


class TestManyShapes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.show()
        app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        for t in getattr(cls.w, 'docs', []):
            t.modified = False
        cls.w.close()
        cls.w.deleteLater()

    def run_bool(self, paths, op):
        from vectordrive.core.document import Shape
        c = self.w.canvas
        c.doc.layers[0].items.clear()
        shapes = [Shape(path=p) for p in paths]
        for s in shapes:
            c.doc.add(s)
        c.selection = list(shapes)
        k = Counted()
        with mock.patch.object(P, 'boolean', k):
            self.w.boolean(op)
        return c.doc.layers[0].items, k

    def test_xor_same_region_as_fold(self):
        for seed in (1, 2, 3):
            ps = blobs(9, seed)
            fold = ps[0]
            for p in ps[1:]:
                fold = P.boolean(fold, p, 'xor')
            self.assertAlmostEqual(P.area(P.xor_all(ps)), P.area(fold), places=6)
            self.assertAlmostEqual(P.area(P.boolean(P.xor_all(ps), fold, 'xor')), 0.0, places=6)

    def test_xor_many_not_squared(self):
        items, k = self.run_bool(grid(600), 'xor')            # avant : le carré (600 formes : ~180 000 contours passés)
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0].path.contours), 600)
        self.assertLess(k.contours, 600 * 6, k.contours)

    def test_difference_plate_once(self):
        holes = grid(300, 5.0, 5.0)
        plate = geom.Path([geom.rect(0, 0, 300, 70)])
        items, k = self.run_bool([plate] + holes, 'difference')
        self.assertEqual(k.calls.get('difference'), 1, k.calls)  # avant : 300 soustractions, le tracé grossissant
        want = P.area(plate) - sum(P.area(h) for h in holes)
        self.assertAlmostEqual(P.area(items[0].path), want, places=4)
        self.assertEqual(len(items[0].path.contours), 301)

    def test_intersect_stops_when_empty(self):
        ps = grid(50)
        items, k = self.run_bool(ps, 'intersect')              # les deux premières ne se touchent pas
        self.assertEqual(k.calls.get('intersect'), 1, k.calls)
        self.assertEqual(items, [])

    def test_intersect_and_union_unchanged(self):
        ps = [geom.Path([geom.rect(0, 0, 20, 20)]), geom.Path([geom.rect(10, 5, 20, 20)]), geom.Path([geom.circle((15, 15), 6)])]
        items, _k = self.run_bool(ps, 'intersect')
        fold = P.boolean(P.boolean(ps[0], ps[1], 'intersect'), ps[2], 'intersect')
        self.assertAlmostEqual(P.area(items[0].path), P.area(fold), places=6)

    def test_trim_same_as_before(self):
        import shapely

        def old_trim(items):
            regs = PF._regions(items)
            out, above = [], None
            for g, t in reversed(regs):
                out.append((g if above is None else shapely.difference(g, above), t))
                above = g if above is None else shapely.union(above, g)
            return PF._out(reversed(out))
        for seed in (4, 5, 6):
            items = [(p, i % 3) for i, p in enumerate(blobs(14, seed))]
            new, old = PF.trim(items), old_trim(items)
            self.assertEqual([t for _p, t in new], [t for _p, t in old])
            for (a, _t), (b, _u) in zip(new, old):
                self.assertAlmostEqual(P.area(a), P.area(b), places=6)
                self.assertAlmostEqual(P.area(P.boolean(a, b, 'xor')), 0.0, places=5)

    def test_mass_properties_same_region(self):
        import shapely
        from shapely.geometry import Polygon
        from vectordrive.core import cadtools as C
        for seed in (7, 8, 9):
            cs = [p.contours[0] for p in blobs(11, seed)]
            m = C.mass_properties(geom.Path(cs))
            region = Polygon(C._polyline(cs[0], 0.005))           # l'ancien pli, pair-impair
            for c in cs[1:]:
                region = shapely.symmetric_difference(region, Polygon(C._polyline(c, 0.005)))
            self.assertAlmostEqual(m['area'], region.area, places=6)
            self.assertAlmostEqual(m['centroid'][0], region.centroid.x, places=6)
            self.assertAlmostEqual(m['centroid'][1], region.centroid.y, places=6)
        cs = [p.contours[0] for p in grid(800)]                  # avant : le carré (1 500 formes : 13 s)
        m = C.mass_properties(geom.Path(cs))
        self.assertAlmostEqual(m['area'], sum(Polygon(C._polyline(c, 0.005)).area for c in cs), places=4)

    def test_trim_disjoint_untouched(self):
        items = [(p, 0) for p in grid(200)]
        out = PF.trim(items)
        self.assertEqual(len(out), 200)
        same = PF._out(PF._regions(items))                       # (les cercles passés par shapely sont aplatis)
        for (a, _t), (b, _u) in zip(out, same):
            self.assertAlmostEqual(P.area(a), P.area(b), places=6)


    def test_xor_overlapping_groups(self):
        ps = grid(40) + grid(40, 1.0, 1.0) + grid(40, 2.0, 0.5) + grid(15, 3.0, 1.5)   # groupes de 3 et de 4 : arbre
        fold = ps[0]                                             # à plusieurs niveaux, niveaux impairs
        for p in ps[1:]:
            fold = P.boolean(fold, p, 'xor')
        a = P.area(fold)
        self.assertAlmostEqual(P.area(P.xor_all(ps)), a, delta=a * 1e-6)

    def test_xor_single_is_normalized(self):
        p = geom.Path([geom.rect(0, 0, 10, 10), geom.rect(5, 5, 10, 10)])   # deux carrés qui se chevauchent
        got = P.xor_all([p, geom.Path()])                        # pair-impair : deux L (avant : les carrés bruts)
        self.assertEqual(sorted(len(c.segments) for c in got.contours), [6, 6])
        self.assertAlmostEqual(P.area(got), 150.0, places=6)
        self.assertIs(P.union_all([p]), p)                       # la réunion d'un seul tracé : inchangée

    def test_single_groups_report_progress(self):
        from vectordrive.core import progress
        seen = []
        with mock.patch.object(progress, 'step', lambda i, n, text='': seen.append((i, n))):
            P.union_all(grid(30))                                # 30 formes disjointes : avant, aucun pas (ni annulation)
        self.assertEqual(len(seen), 30, seen)
        self.assertTrue(all(i < n for i, n in seen), seen)

    def test_agent_difference_once(self):
        from vectordrive.agent.tools import ToolSet
        import json
        c = self.w.canvas
        c.doc.layers[0].items.clear()
        tools = ToolSet(self.w)
        call = lambda name, **a: json.loads(tools.call(name, a)[0]['text'])
        ids = [call('add_rectangle', x=0, y=0, width=300, height=70)['ids'][0]]
        for i in range(40):
            ids += call('add_ellipse', cx=10 + i * 7.0, cy=10, rx=2)['ids']
        k = Counted()
        with mock.patch.object(P, 'boolean', k):
            out = call('boolean', operation='difference', ids=ids)
        self.assertEqual(k.calls.get('difference'), 1, k.calls)  # avant : 40 soustractions
        items = c.doc.layers[0].items
        self.assertEqual([it.id for it in items], out['ids'])
        self.assertEqual(len(items[0].path.contours), 41)
        k = Counted()
        ids = [call('add_rectangle', x=0, y=100, width=5, height=5)['ids'][0]]
        ids += [call('add_rectangle', x=50 + i * 10, y=100, width=5, height=5)['ids'][0] for i in range(10)]
        with mock.patch.object(P, 'boolean', k):
            out = call('boolean', operation='intersect', ids=ids)
        self.assertEqual(k.calls.get('intersect'), 1, k.calls)
        self.assertTrue(out['empty'])

    def test_carve_same_as_fold(self):
        from vectordrive.core import textflow as TF
        region = geom.Path([geom.rect(0, 0, 60, 40)])
        for seed, gap in ((10, 0.0), (11, 1.5)):
            obs = blobs(12, seed) + [geom.Path([geom.rect(200, 200, 5, 5)])]   # (une hors de la forme)
            zone = TF.region_of(region)
            for o in obs:
                cut = TF.region_of(o)
                zone = zone.difference(cut.buffer(gap) if gap > 0 else cut)
            got = TF.region_of(TF.carve(region, obs, gap))
            self.assertAlmostEqual(got.area, zone.area, delta=zone.area * 1e-4)
            self.assertLess(got.symmetric_difference(zone).area, zone.area * 1e-3)

if __name__ == '__main__':
    unittest.main()
