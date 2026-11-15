"""Round 362 : détourage trochoïdal — boucles le long du contour, rainure
plus large que l'outil, contour respecté au rayon près."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import Point, Polygon

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(side='exterieur', **kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F', kind='droite', diameter=2)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='contour', depth=1, step_down=1, tool_id=t.id, side=side, **kw))


def feeds(tp):
    return [(m.x, m.y) for m in tp.moves if m.kind == 'feed']


class TestTrochoid(unittest.TestCase):
    def test_function(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        pts = S.trochoid(sq, 1.0, 3.0, tol=0.01)
        self.assertAlmostEqual(pts[0][0], pts[-1][0], 6)            # nombre entier de boucles : retour au départ
        self.assertAlmostEqual(pts[0][1], pts[-1][1], 6)
        ring = Polygon(sq).exterior
        self.assertLessEqual(max(ring.distance(Point(p)) for p in pts), 1.0 + 1e-6)

    def test_outside(self):
        tp = run(trochoidal=True, troch_width=3.0, troch_step=0.5)   # Ø2 : boucles de rayon 0,5
        part = Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])
        F = feeds(tp)
        dmin = min(part.exterior.distance(Point(p)) for p in F)
        dmax = max(part.exterior.distance(Point(p)) for p in F)
        self.assertAlmostEqual(dmin, 1.0, 1)                        # l'outil frôle la pièce (rayon 1)
        self.assertAlmostEqual(dmax, 2.0, 1)                        # rainure de 3 : jusqu'à 1 + 2 × 0,5
        self.assertFalse(any(part.contains(Point(p)) for p in F))
        self.assertGreater(len(F), 5 * len(feeds(run())))

    def test_inside_and_too_narrow(self):
        tp = run('interieur', trochoidal=True)                     # largeur par défaut 3, pas 0,2
        part = Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])
        self.assertTrue(all(part.contains(Point(p)) for p in feeds(tp)))
        tp = run(trochoidal=True, troch_width=2.0)
        self.assertTrue(any('trochoïdal' in w for w in tp.warnings), tp.warnings)


if __name__ == '__main__':
    unittest.main()
