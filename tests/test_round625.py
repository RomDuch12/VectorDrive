"""Round 625 : gravure 2,5D à l'outil conique — les parties plus étroites que
le premier retrait (passage de 0,341 mm entre deux motifs avec un outil 30°
pointe 0,2 et un pas de 0,1 ; pointes des angles aigus ; traits fins) sont
suivies par leur ligne médiane, la pointe descendant selon la demi-largeur
locale, comme TypeEdit — elles n'étaient pas gravées."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import Point, Polygon, box

from vectordrive.cam import advanced, model, strategies
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

GAP = 0.341
TAN = math.tan(math.radians(15))


def compute(rects, edges_only=True, depth=0.5, res=0.1):
    d = Document()
    d.plate = None
    for r in rects:
        d.add(Shape(path=geom.Path([geom.rect(*r)]), tool=0))
    s = model.CamSetup()
    t = model.CamTool(name='V30', kind='conique', diameter=3.175, angle=30, tip=0.2, number=1)
    s.tools = [t]
    s.operations = [model.Operation(kind='vcarve', tool_id=t.id, sources=[0], depth=depth,
                                    vcarve_edges_only=edges_only, resolution=res)]
    return strategies.compute_all(d, s)[0]


def cuts(tp, zone):
    """Points de coupe (échantillonnés sur les segments) dans `zone`."""
    out, prev = [], None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid':
            for k in range(11):
                x, y = prev.x + (m.x - prev.x) * k / 10, prev.y + (m.y - prev.y) * k / 10
                z = prev.z + (m.z - prev.z) * k / 10
                if zone.contains(Point(x, y)):
                    out.append((x, y, z))
        prev = m
    return out


MOTIFS = [(0, 0, 20, 10), (3, 3, 6, 4), (9 + GAP, 3, 6, 4)]       # cadre et deux motifs en relief


class TestNarrow(unittest.TestCase):
    def test_gap_between_two_motifs(self):
        gap = box(9.0, 3.5, 9 + GAP, 6.5)
        for edges_only in (True, False):
            tp = compute(MOTIFS, edges_only)
            pts = cuts(tp, gap)
            self.assertTrue(pts, f'finition={edges_only} : rien dans le passage')
            deepest = -min(z for _x, _y, z in pts)
            self.assertAlmostEqual(deepest, (GAP / 2 - 0.1) / TAN, delta=0.01)   # 0,263 : touche les deux bords
            self.assertGreaterEqual(min(m.z for m in tp.moves), -0.5 - 1e-9)

    def test_no_gouge(self):
        reg = box(0, 0, 20, 10).difference(box(3, 3, 9, 7)).difference(box(9 + GAP, 3, 6 + 9 + GAP, 7))
        tp = compute(MOTIFS)
        for x, y, z in cuts(tp, box(9.0, 3.2, 9 + GAP, 6.8)):
            if z < -1e-6:                                                  # rayon du cône en surface ≤ jeu
                self.assertLessEqual(0.1 + (-z) * TAN, reg.boundary.distance(Point(x, y)) + 2e-3)

    def test_thin_stroke_and_plain_rectangle(self):
        tp = compute([(0, 0, 5, 0.3)], edges_only=False)                    # trait de 0,3 mm
        self.assertTrue(tp.moves)
        self.assertAlmostEqual(-min(m.z for m in tp.moves), (0.15 - 0.1) / TAN, delta=0.01)
        reg = box(0, 0, 20, 10)
        qs = strategies._quad_segs(0.2, 0.01)
        self.assertEqual(advanced.narrow_axis(reg, 0.2, 0.1, TAN, 0.5, 0.1, qs), [])   # angles droits : rien
        sharp = reg.union(Polygon([(20, 4), (40, 5), (20, 6)]))                       # pointe aiguë (6°)
        chains = advanced.narrow_axis(sharp, 0.2, 0.1, TAN, 0.5, 0.1, qs)
        self.assertTrue(chains)                                           # tiré d'angle dans la pointe
        self.assertTrue(all(z >= -(0.2 - 0.1) / TAN - 1e-9 for c in chains for _x, _y, z in c))


if __name__ == '__main__':
    unittest.main()
