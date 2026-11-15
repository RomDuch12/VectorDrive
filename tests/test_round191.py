"""Round 191 : découpe 3D, forme suivante au plus près par arbre STRtree (même ordre)."""
import os
import random
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import Point, box

from vectordrive.cam import model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def naive(geoms, here, step):
    """L'ancien choix : toutes les formes restantes comparées."""
    rest, out, pos = list(range(len(geoms))), [], here
    while rest:
        i = min(rest, key=lambda k: geoms[k].distance(Point(pos)))
        rest.remove(i)
        out.append(i)
        pos = step(geoms[i])
    return out


def picked(geoms, here, step):
    p, out, pos = S.NearestPicker(geoms), [], here
    index = {id(g): k for k, g in enumerate(geoms)}
    for _ in geoms:
        g = p.pop(pos)
        out.append(index[id(g)])
        pos = step(g)
    return out


class TestPicker(unittest.TestCase):
    def test_same_order_random(self):
        for seed in range(4):
            rnd = random.Random(seed)
            geoms = [Point(rnd.uniform(0, 200), rnd.uniform(0, 120)).buffer(rnd.uniform(0.5, 3)) for _ in range(300)]
            a = naive(geoms, (0.0, 0.0), lambda g: g.exterior.coords[3])
            b = picked(geoms, (0.0, 0.0), lambda g: g.exterior.coords[3])
            self.assertEqual(a, b, seed)

    def test_ties_inside_and_far(self):
        geoms = [box(x * 10, y * 10, x * 10 + 4, y * 10 + 4) for x in range(12) for y in range(8)]   # égalités
        a = naive(geoms, (55.0, 35.0), lambda g: (g.centroid.x, g.centroid.y))
        b = picked(geoms, (55.0, 35.0), lambda g: (g.centroid.x, g.centroid.y))
        self.assertEqual(a, b)
        a = naive(geoms, (-5000.0, 9000.0), lambda g: g.exterior.coords[0])
        b = picked(geoms, (-5000.0, 9000.0), lambda g: g.exterior.coords[0])
        self.assertEqual(a, b)
        p = S.NearestPicker([box(0, 0, 1, 1)])
        p.pop((0, 0))
        with self.assertRaises(IndexError):
            p.pop((0, 0))

    def test_decoupe3d_fast(self):
        rnd = random.Random(1)
        d = Document()
        d.plate = None
        for _ in range(1500):
            d.add(Shape(path=geom.Path([geom.circle((rnd.uniform(0, 300), rnd.uniform(0, 200)), rnd.uniform(0.8, 2.5))]),
                        tool=0))
        s = model.CamSetup()
        v = model.CamTool(name='V', kind='conique', diameter=6.0, angle=60.0, tip=0.1, feed=1000.0, step_down=0.5)
        s.tools = [v]
        op = model.Operation(tool_id=v.id, kind='decoupe3d', side='exterieur', depth=1.0)
        s.operations = [op]
        t = time.perf_counter()
        tp = S.compute(d, s, op)
        self.assertLess(time.perf_counter() - t, 30.0)
        self.assertGreater(len(tp.moves), 10000)


if __name__ == '__main__':
    unittest.main()
