"""Round 440 : pièces au plus proche calculées d'un coup (détourage, remplissage forme par forme) —
même ordre que le calcul pas à pas, en bien moins de temps."""
import random
import time
import unittest

import shapely
from shapely.geometry import Point

from vectordrive.cam import model, strategies
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def brute(polys, here):
    rest, out, pos = list(polys), [], here
    while rest:
        k = min(range(len(rest)), key=lambda i: rest[i].exterior.distance(Point(pos)))
        out.append(rest.pop(k))
        c = out[-1].centroid
        pos = (c.x, c.y)
    return out


class TestNearest(unittest.TestCase):
    def test_same_order(self):
        rnd = random.Random(4)
        polys = [shapely.box(x, y, x + rnd.uniform(0.5, 3), y + rnd.uniform(0.5, 3))
                 for x, y in ((rnd.uniform(0, 100), rnd.uniform(0, 100)) for _ in range(150))]
        for here in ((0.0, 0.0), (50.0, 50.0), (120.0, -5.0)):
            self.assertEqual([id(p) for p in strategies._nearest_first(polys, here)],
                             [id(p) for p in brute(polys, here)])

    def test_contour_speed(self):
        d = Document()
        for i in range(20):
            for j in range(20):
                d.add(Shape(path=geom.Path([geom.star((i * 12, j * 12), 5, 2.5, 7)]), tool=0))
        s = model.CamSetup()
        s.tools = [model.CamTool(name='F1', kind='fraise', diameter=1.0, number=1)]
        op = model.Operation(kind='contour', depth=1.0, step_down=0.5, tool_id=s.tools[0].id, sources=[0],
                             side='exterieur')
        t = time.time()
        tp = strategies.compute(d, s, op)
        self.assertTrue(tp.moves)
        self.assertLess(time.time() - t, 3.0)                       # 400 pièces : ≈ 4 s auparavant


if __name__ == '__main__':
    unittest.main()
