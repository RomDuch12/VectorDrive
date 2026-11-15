"""Round 855 : entrée et sortie linéaires, perçage en goutte, contrôle de perçage (manuel de TE, page 661)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import LineString, Point, Polygon

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

# sens horaire : le contour part de (0, 5) vers +y ; la chute est à gauche du sens (x < 0)
SQ = [(0, 5), (0, 10), (10, 10), (10, 0), (0, 0), (0, 5)]
REGION = Polygon(SQ)
C = (0.0, 5.0)


def leads(a=0.0, b=0.0, **kw):
    return S.with_leads(SQ, REGION, True, a, b, keep_start=True, **kw)


class TestLine(unittest.TestCase):

    def test_entry(self):
        for ang in (30.0, 45.0, 90.0):
            chain = leads(3.0, mode='ligne', angle_in=ang)
            p = chain[0]
            self.assertAlmostEqual(math.dist(p, C), 3.0, places=6)
            self.assertAlmostEqual(p[1], 5.0 - 3.0 * math.cos(math.radians(ang)), places=6)  # il arrive dans le sens du contour
            self.assertLess(p[0], 0.0)                                                       # dans la chute
            self.assertEqual(chain[1], C)

    def test_exit(self):
        chain = leads(0.0, 2.0, mode='ligne', angle_out=30.0)
        p = chain[-1]
        self.assertEqual(chain[-2], C)
        self.assertAlmostEqual(math.dist(p, C), 2.0, places=6)
        self.assertAlmostEqual(p[1], 5.0 + 2.0 * math.cos(math.radians(30.0)), places=6)     # il repart dans le sens du contour
        self.assertLess(p[0], 0.0)

    def test_two_angles(self):
        chain = leads(2.0, 2.0, mode='ligne', angle_in=90.0, angle_out=30.0)
        self.assertAlmostEqual(chain[0][1], 5.0, places=6)
        self.assertGreater(chain[-1][1], 6.0)

    def test_the_angle_is_bounded(self):
        for ang in (0.0, -10.0, 500.0):
            self.assertAlmostEqual(math.dist(leads(3.0, mode='ligne', angle_in=ang)[0], C), 3.0, places=6)

    def test_inside_scrap(self):
        chain = S.with_leads(SQ, REGION, False, 2.0, 0.0, keep_start=True, mode='ligne', angle_in=90.0)
        self.assertTrue(REGION.contains(Point(chain[0])))

    def test_it_shrinks_rather_than_cut_the_piece(self):
        # un voisin à 1,5 mm : la droite de 4 mm le traverserait
        two = REGION.union(Polygon([(-5, 0), (-1.5, 0), (-1.5, 10), (-5, 10)]))
        chain = S.with_leads(SQ, two, True, 4.0, 0.0, keep_start=True, mode='ligne', angle_in=90.0)
        self.assertLess(math.dist(chain[0], C), 1.5)


class TestDrop(unittest.TestCase):

    def entry(self, d, r):
        chain = leads(d, 0.0, mode='percage', pierce=r)
        return chain[:chain.index(C) + 1]

    def exit(self, d, r):
        chain = leads(0.0, d, mode='percage', pierce=r)
        i = len(chain) - 1 - chain[::-1].index(C)
        return chain[i:]

    def test_the_hole_is_at_the_distance(self):
        for d, r in ((5.0, 1.0), (4.0, 2.0), (2.0, 2.0)):
            self.assertAlmostEqual(math.dist(self.entry(d, r)[0], (-d, 5.0)), 0.0, places=6)
            self.assertAlmostEqual(math.dist(self.exit(d, r)[-1], (-d, 5.0)), 0.0, places=6)

    def test_it_arrives_along_the_contour(self):
        pts = self.entry(5.0, 1.0)
        a, b = pts[-2], pts[-1]
        self.assertGreater(b[1] - a[1], 0)
        self.assertLess(abs(b[0] - a[0]), abs(b[1] - a[1]) * 0.3)

    def test_it_leaves_along_the_contour(self):
        pts = self.exit(5.0, 1.0)
        a, b = pts[0], pts[1]
        self.assertGreater(b[1] - a[1], 0)
        self.assertLess(abs(b[0] - a[0]), abs(b[1] - a[1]) * 0.3)

    def test_longer_than_the_diameter_a_drop(self):
        pts = self.entry(5.0, 1.0)
        tip = math.dist(pts[1], (-1.0, 5.0))                       # la droite aboutit sur le cercle
        self.assertAlmostEqual(tip, 1.0, places=6)
        length = math.dist(pts[0], pts[1])
        self.assertAlmostEqual(length, math.sqrt(4.0 ** 2 - 1.0), places=6)
        for p in pts[1:]:
            self.assertAlmostEqual(math.dist(p, (-1.0, 5.0)), 1.0, places=6)

    def test_equal_to_the_diameter_a_circle(self):
        whole = self.entry(4.0, 2.0) + self.exit(4.0, 2.0)[1:]
        for p in whole:
            self.assertAlmostEqual(math.dist(p, (-2.0, 5.0)), 2.0, places=6)
        self.assertAlmostEqual(sum(math.dist(a, b) for a, b in zip(whole, whole[1:])), 2 * math.pi * 2.0, delta=0.05)
        self.assertAlmostEqual(math.dist(whole[0], whole[-1]), 0.0, places=6)

    def test_shorter_than_the_diameter_a_half_turn(self):
        pts = self.entry(2.0, 2.0)
        for p in pts:
            self.assertAlmostEqual(math.dist(p, (-1.0, 5.0)), 1.0, places=6)
        self.assertAlmostEqual(sum(math.dist(a, b) for a, b in zip(pts, pts[1:])), math.pi, delta=0.02)

    def test_without_radius_a_circle(self):
        pts = self.entry(4.0, 0.0)
        for p in pts:
            self.assertAlmostEqual(math.dist(p, (-2.0, 5.0)), 2.0, places=6)

    def test_no_double_point(self):
        for d, r in ((5.0, 1.0), (4.0, 2.0), (2.0, 2.0)):
            for pts in (self.entry(d, r), self.exit(d, r)):
                self.assertTrue(all(math.dist(a, b) > 1e-9 for a, b in zip(pts, pts[1:])), (d, r))

    def test_the_drop_closes_on_the_contour_side(self):
        whole = self.entry(5.0, 1.0) + self.exit(5.0, 1.0)[1:]
        self.assertAlmostEqual(math.dist(whole[0], whole[-1]), 0.0, places=6)   # entrée et sortie reviennent au trou
        self.assertTrue(LineString(whole).is_valid)
        self.assertFalse(LineString(whole).intersects(REGION.buffer(-1e-3)))

    def test_inside_scrap_too(self):
        chain = S.with_leads(SQ, REGION, False, 5.0, 5.0, keep_start=True, mode='percage', pierce=1.0)
        for p in chain:
            self.assertTrue(REGION.buffer(1e-3).contains(Point(p)))


class TestCompute(unittest.TestCase):

    def path_of(self, shapes=None, **params):
        doc = Document()
        doc.plate = Plate(width=200.0, height=200.0)
        rect = Shape(path=geom.Path([geom.rect(10, 10, 40, 20)]))
        doc.layers = [Layer(name='A', items=shapes or [rect])]
        setup = M.setup_of(doc)
        tool = M.CamTool(name='F', diameter=6.0)
        setup.tools.append(tool)
        op = M.Operation(kind='contour', tool_id=tool.id, side='exterieur')
        op.depth = 1.0
        for k, v in params.items():
            setattr(op, k, v)
        setup.operations.append(op)
        M.store(doc, setup)
        return S.compute(doc, setup, op, (0.0, 0.0))

    @staticmethod
    def first(tp):
        m = next(m for m in tp.moves if m.kind != 'rapid')
        return m.x, m.y

    def test_default_is_the_quarter_circle(self):
        a = self.path_of(lead_in=2.0, ramp=False)
        b = self.path_of(lead_in=2.0, ramp=False, lead_mode='arc')
        self.assertEqual(self.first(a), self.first(b))
        self.assertEqual(len(a.moves), len(b.moves))

    def test_line(self):
        tp = self.path_of(lead_in=4.0, ramp=False, lead_mode='ligne', lead_angle=90.0)
        x, y = self.first(tp)
        self.assertLess(abs(x - 30.0), 0.5)                         # milieu du long côté
        self.assertTrue(abs(y - 3.0) < 0.2 or abs(y - 37.0) < 0.2, (x, y))    # 4 mm au-delà de l'anneau décalé de 3 mm

    def test_drop(self):
        tp = self.path_of(lead_in=6.0, lead_out=6.0, ramp=False, lead_mode='percage', lead_pierce=1.5)
        x, y = self.first(tp)
        self.assertTrue(abs(y - 1.0) < 0.2 or abs(y - 39.0) < 0.2, (x, y))
        last = [m for m in tp.moves if m.kind != 'rapid'][-1]
        self.assertAlmostEqual(x, last.x, places=6)                 # la sortie revient au trou
        self.assertAlmostEqual(y, last.y, places=6)

    def test_no_warning_when_clear(self):
        tp = self.path_of(lead_in=6.0, ramp=False, lead_mode='percage', lead_pierce=1.5)
        self.assertFalse([w for w in tp.warnings if 'perçage' in w], tp.warnings)

    def test_the_check_warns_near_a_contour(self):
        tp = self.path_of(lead_in=6.0, ramp=False, lead_mode='ligne', lead_angle=90.0, lead_pierce=12.0)
        self.assertTrue([w for w in tp.warnings if 'contrôle de perçage' in w], tp.warnings)

    def test_no_check_without_radius(self):
        tp = self.path_of(lead_in=6.0, ramp=False, lead_mode='ligne', lead_angle=90.0)
        self.assertFalse([w for w in tp.warnings if 'perçage' in w], tp.warnings)

    def test_every_pass_goes_through_the_entry(self):
        tp = self.path_of(lead_in=4.0, ramp=False, lead_mode='ligne', lead_angle=90.0, step_down=0.4)
        plunges = [m for prev, m in zip(tp.moves, tp.moves[1:]) if prev.kind == 'rapid' and m.kind != 'rapid']
        self.assertGreaterEqual(len(plunges), 2)
        x, y = self.first(tp)
        for m in plunges:
            self.assertAlmostEqual(m.x, x, places=6)
            self.assertAlmostEqual(m.y, y, places=6)

    def test_with_a_chosen_start(self):
        c = geom.rect(10, 10, 40, 20)
        s = Shape(path=geom.Path([c]))
        s.extra = {'start_xy': [[50.0, 20.0]]}
        tp = self.path_of([s], lead_in=4.0, ramp=False, lead_mode='ligne', lead_angle=90.0)
        x, y = self.first(tp)
        self.assertAlmostEqual(x, 57.0, delta=0.2)
        self.assertAlmostEqual(y, 20.0, delta=0.2)

    def test_the_form_offers_them(self):
        from vectordrive.ui import cam_panel as P
        names = ('lead_mode', 'lead_angle', 'lead_out_angle', 'lead_pierce')
        for kind in ('contour', 'laser_decoupe'):
            for n in names:
                self.assertIn(n, P.KIND_FIELDS[kind])
        for n in names:
            self.assertIn(n, P.LABELS)
        self.assertEqual(set(P.FIELD_CHOICES['lead_mode']), {'arc', 'ligne', 'percage'})


if __name__ == '__main__':
    unittest.main()
