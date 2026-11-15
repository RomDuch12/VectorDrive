"""Round 171 : entrée et sortie tangentes de la découpe laser (amorçage dans la chute)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import Point, Polygon

from vectordrive.cam import model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

SQ = [(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)]                             # sens horaire


class TestLeads(unittest.TestCase):
    def test_outside_scrap(self):
        region = Polygon(SQ)
        chain = S.with_leads(SQ, region, True, 2.0, 1.0)
        start = chain[0]
        self.assertFalse(region.contains(Point(start)))                          # perçage dans la chute
        self.assertAlmostEqual(math.dist(start, (0, 5)), 2 * math.sqrt(2), places=3)   # départ : milieu d'un côté
        i0 = chain.index((0, 5))
        self.assertEqual(chain[i0:i0 + 6], [(0, 5), (0, 10), (10, 10), (10, 0), (0, 0), (0, 5)])
        # tangente à l'arrivée : le dernier pas de l'entrée va dans le sens du 1er côté (vers +y)
        a, b = chain[i0 - 1], chain[i0]
        self.assertGreater(b[1] - a[1], 0)
        self.assertAlmostEqual(b[0] - a[0], 0, delta=abs(b[1] - a[1]) * 0.3)
        end = chain[-1]
        self.assertFalse(region.contains(Point(end)))
        self.assertAlmostEqual(math.dist(end, (0, 5)), math.sqrt(2), places=3)

    def test_inside_scrap(self):
        region = Polygon(SQ)
        chain = S.with_leads(SQ, region, False, 2.0, 0.0)
        self.assertTrue(region.contains(Point(chain[0])))                        # trou : la chute est dedans
        self.assertTrue(all(region.contains(Point(p)) or region.exterior.distance(Point(p)) < 1e-9
                            for p in chain))                                     # l'arc reste dans le trou
        self.assertEqual(chain[-1], (0, 5))                                      # sans sortie

    def test_laser_cut(self):
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)])))
        s = model.CamSetup()
        t = model.CamTool(name='Laser', kind='laser', diameter=0.1, power=80, frequency=20, feed=600)
        s.tools = [t]
        op = model.Operation(kind='laser_decoupe', tool_id=t.id, side='exterieur', lead_in=1.5, lead_out=1.0)
        s.operations = [op]
        tp = S.compute(d, s, op)
        plunge = next(m for m in tp.moves if m.kind == 'plunge')
        first = (plunge.x, plunge.y)                                             # point de perçage
        part = Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])
        self.assertGreater(part.exterior.distance(Point(first)), 0.3)            # entrée hors de la pièce
        self.assertFalse(part.contains(Point(first)))
        op.laser_passes = 2
        tp2 = S.compute(d, s, op)
        pierces = [m for m in tp2.moves if m.kind == 'plunge' and math.dist((m.x, m.y), first) < 1e-6]
        self.assertEqual(len(pierces), 2)                                         # chaque passage repart de l'entrée

    def test_degenerate(self):
        self.assertEqual(S.with_leads([(0, 0), (0, 0)], Polygon(SQ), True, 1, 1), [(0, 0), (0, 0)])


if __name__ == '__main__':
    unittest.main()
