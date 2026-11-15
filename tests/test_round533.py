"""Round 533 : intersections — objets qui se touchent regroupés par un arbre (STRtree) au lieu de toutes les
paires (10 000 objets : 2 min → 1 s) ; mêmes groupes, même ordre ; « Réunir » et « Contour extérieur »."""
import random
import unittest

from vectordrive.core import geom, intersect as I
from vectordrive.core.document import Shape


def old_groups(shapes):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    geo = []
    for s in shapes:
        polys = [Polygon(p).buffer(0) for p in s.path.flatten(0.05) if len(p) >= 4]
        geo.append(unary_union(polys) if polys else None)
    parent = list(range(len(shapes)))

    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for i in range(len(shapes)):
        for j in range(i + 1, len(shapes)):
            if geo[i] is not None and geo[j] is not None and geo[i].intersects(geo[j]):
                parent[root(j)] = root(i)
    groups: dict = {}
    for i, s in enumerate(shapes):
        groups.setdefault(root(i), []).append(s)
    return list(groups.values())


class TestTouchingGroups(unittest.TestCase):
    def test_same_groups(self):
        rnd = random.Random(11)
        shapes = [Shape(path=geom.Path([geom.circle((rnd.uniform(0, 100), rnd.uniform(0, 60)), rnd.uniform(0.5, 4))]))
                  for _ in range(150)]
        shapes.append(Shape(path=geom.Path([geom.Contour([geom.Line((0, 0), (5, 5))])])))   # ouvert : à part
        new, old = I._touching_groups(shapes), old_groups(shapes)
        self.assertEqual([[id(s) for s in g] for g in new], [[id(s) for s in g] for g in old])
        out = I.apply('union', shapes)
        self.assertEqual(len(out), len(new))


if __name__ == '__main__':
    unittest.main()
