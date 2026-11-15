"""Round 505 : axe médian (gravure 2,5D en ligne médiane) filtré sur tableaux — extrémités dans la région
et distance au bord par un arbre de ses segments : même résultat que le test point par point, 3 × plus vite."""
import random
import unittest

import shapely
from shapely.geometry import MultiPoint, Point, box

from vectordrive.cam import advanced as A


def reference_edges(reg, step, min_dist):
    """Arêtes gardées par l'ancien filtre (point par point), avant chaînage."""
    pts = []
    for poly in getattr(reg, 'geoms', [reg]):
        for ring in [poly.exterior] + list(poly.interiors):
            pts += list(shapely.segmentize(ring, step).coords)[:-1]
    edges = shapely.voronoi_polygons(MultiPoint(pts), only_edges=True)
    bound = reg.boundary
    keep = set()
    for e in getattr(edges, 'geoms', [edges]):
        c = list(e.coords)
        a, b = c[0], c[-1]
        if not (shapely.contains_xy(reg, *a) and shapely.contains_xy(reg, *b)):
            continue
        if bound.distance(shapely.points(a)) < min_dist or bound.distance(shapely.points(b)) < min_dist:
            continue
        ka, kb = tuple(round(v, 5) for v in a), tuple(round(v, 5) for v in b)
        if ka != kb:
            keep.add(frozenset((ka, kb)))
    return keep


class TestMedialAxis(unittest.TestCase):
    def test_same_edges_as_reference(self):
        rnd = random.Random(3)
        parts = [box(0, 0, 30, 8).difference(box(5, 2, 9, 6))]
        parts += [Point(40 + 6 * i, rnd.uniform(0, 10)).buffer(rnd.uniform(1, 2.5), 12) for i in range(6)]
        reg = shapely.union_all(parts)
        chains = A.medial_axis(reg, 0.2, 0.2)
        got = {frozenset((c[i], c[i + 1])) for c in chains for i in range(len(c) - 1)}
        self.assertEqual(got, reference_edges(reg, 0.2, 0.2))
        self.assertTrue(got)

    def test_rectangle_axis(self):
        chains = A.medial_axis(box(0, 0, 20, 4), 0.1, 0.5)
        ys = [p[1] for c in chains for p in c]
        self.assertTrue(ys)
        self.assertTrue(all(0.5 < y < 3.5 for y in ys))
        self.assertTrue(any(abs(y - 2.0) < 1e-6 for y in ys))        # l'axe du milieu
        self.assertEqual(A.medial_axis(box(0, 0, 0.01, 0.01), 0.1, 0.5), [])


if __name__ == '__main__':
    unittest.main()
