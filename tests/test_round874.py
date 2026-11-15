"""Round 874 : l'entrée et la sortie automatiques de TE13. Les points attendus sont ceux que TE13 a calculés au départ (7, 10) d'un
contour parcouru vers le haut, chute à gauche, pour les rayons de transition R et les distances D relevés."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import Point, Polygon

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.cam import tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

RING = [(7, 10), (7, 43), (53, 43), (53, 7), (7, 7), (7, 10)]
REGION = Polygon(RING)


def leads(radius, dist):
    chain = S.with_leads(RING, REGION, True, dist, dist, keep_start=True, mode='percage', transition=radius)
    start = chain.index((7, 10))
    end = len(chain) - 1 - chain[::-1].index((7, 10))
    return chain[:start + 1], chain[end:]


class TestShape(unittest.TestCase):

    def assertPoint(self, got, want, delta=0.01):
        self.assertAlmostEqual(got[0], want[0], delta=delta)
        self.assertAlmostEqual(got[1], want[1], delta=delta)

    def assertOnCircle(self, pts, centre, radius):
        for p in pts:
            self.assertAlmostEqual(math.dist(p, centre), radius, delta=1e-6)

    def test_a_full_circle(self):
        # R = 6, D = 12 : deux demi-cercles, le perçage à (-5, 10)
        entry, exit_ = leads(6.0, 12.0)
        self.assertPoint(entry[0], (-5, 10))
        self.assertPoint(exit_[-1], (-5, 10))
        self.assertOnCircle(entry, (1, 10), 6.0)
        self.assertOnCircle(exit_, (1, 10), 6.0)
        self.assertLess(min(p[1] for p in entry), 4.1)                  # l'entrée par dessous, dans le sens du contour
        self.assertGreater(max(p[1] for p in exit_), 15.9)              # la sortie par dessus

    def test_a_smaller_circle(self):
        # R = 3, D = 6
        entry, exit_ = leads(3.0, 6.0)
        self.assertPoint(entry[0], (1, 10))
        self.assertOnCircle(entry, (4, 10), 3.0)

    def test_half_a_turn(self):
        # R = 6, D = 3 : une demi-volte, le perçage à 3 mm de corde sur le cercle de 6
        entry, exit_ = leads(6.0, 3.0)
        self.assertPoint(entry[0], (6.25, 7.10))
        self.assertPoint(exit_[-1], (6.25, 12.90))
        self.assertOnCircle(entry, (1, 10), 6.0)
        self.assertOnCircle(exit_, (1, 10), 6.0)
        self.assertAlmostEqual(math.dist(entry[0], (7, 10)), 3.0, places=6)

    def test_a_drop(self):
        # R = 3, D = 12 : le perçage à (-5, 10), une droite tangente jusqu'à (3, 7,17), l'arc
        entry, exit_ = leads(3.0, 12.0)
        self.assertPoint(entry[0], (-5, 10))
        self.assertPoint(entry[1], (3.0, 7.17))
        self.assertOnCircle(entry[1:], (4, 10), 3.0)
        self.assertPoint(exit_[-1], (-5, 10))
        self.assertPoint(exit_[-2], (3.0, 12.83))

    def test_a_narrow_drop(self):
        # R = 1, D = 12 : tangente en (5,91, 9), comme à la sortie en (5,91, 11)
        entry, exit_ = leads(1.0, 12.0)
        self.assertPoint(entry[0], (-5, 10))
        self.assertPoint(entry[1], (5.91, 9.0))
        self.assertPoint(exit_[-2], (5.91, 11.0))

    def test_it_arrives_along_the_contour(self):
        for radius, dist in ((6.0, 12.0), (3.0, 6.0), (6.0, 3.0), (3.0, 12.0), (1.0, 12.0)):
            entry, exit_ = leads(radius, dist)
            a, b = entry[-2], entry[-1]
            d = math.dist(a, b)
            self.assertGreater((b[1] - a[1]) / d, 0.95, (radius, dist))
            a, b = exit_[0], exit_[1]
            d = math.dist(a, b)
            self.assertGreater((b[1] - a[1]) / d, 0.95, (radius, dist))


class TestOldWay(unittest.TestCase):

    def test_without_a_transition_nothing_changes(self):
        chain = S.with_leads(RING, REGION, True, 6.0, 6.0, keep_start=True, mode='percage', pierce=1.5)
        self.assertAlmostEqual(chain[0][0], 1.0, places=6)              # à 6 mm, sur la normale
        self.assertAlmostEqual(chain[0][1], 10.0, places=6)
        small = S.with_leads(RING, REGION, True, 2.0, 2.0, keep_start=True, mode='percage', pierce=3.0)
        self.assertAlmostEqual(small[0][0], 5.0, places=6)              # le cercle de la distance en diamètre
        self.assertAlmostEqual(small[0][1], 10.0, places=6)


class TestOperation(unittest.TestCase):

    def path_of(self, **kw):
        doc = Document()
        doc.plate = Plate(width=120.0, height=60.0)
        doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.polyline([(10, 10), (50, 10), (50, 40), (10, 40)], closed=True)]))])]
        setup = M.setup_of(doc)
        t = M.CamTool(name='F', diameter=6.0)
        setup.tools.append(t)
        op = M.Operation(kind='contour', side='exterieur', tool_id=t.id, depth=2.0, step_down=2.0, **kw)
        setup.operations.append(op)
        M.store(doc, setup)
        return S.compute(doc, setup, op, (0.0, 0.0))

    def test_the_transition_is_used(self):
        tp = self.path_of(lead_mode='percage', lead_in=12.0, lead_out=12.0, lead_transition=6.0)
        rect = Polygon([(10, 10), (50, 10), (50, 40), (10, 40)])
        far = max(rect.distance(Point(m.x, m.y)) for m in tp.moves if abs(m.z + 2.0) < 1e-9)
        self.assertAlmostEqual(far, 3.0 + 12.0, delta=0.01)             # le perçage, à 12 mm du contour décalé de l'outil

    def test_the_check_radius_does_not_change_the_shape(self):
        # TE13 : le rayon de perçage ne change pas le parcours, il sert au contrôle
        a = self.path_of(lead_mode='percage', lead_in=12.0, lead_out=12.0, lead_transition=6.0)
        b = self.path_of(lead_mode='percage', lead_in=12.0, lead_out=12.0, lead_transition=6.0, lead_pierce=2.0)
        self.assertEqual([(m.x, m.y, m.z) for m in a.moves], [(m.x, m.y, m.z) for m in b.moves])


class TestPresets(unittest.TestCase):

    def op(self, mode):
        p = tpp.Preset(name='d', kind='CP_Cutting_3D', sections={
            'ENTRETANGENTIELLE': {'ModeIOtgt': mode},
            'FAO_NEWPARAMGLOB': {'ES_TANGEANCIELLE_RACORD': '6.e-003', 'ES_TANGEANCIELLE_DIST': '2.e-003', 'ES_TANGEANCIELLE_RAYON': '0.'}})
        return tpp.to_template(p)['operations'][0]

    def test_one_means_none(self):
        # relevé : la boîte de TE13 montre « Aucune », et ses parcours n'ont pas d'entrée
        o = self.op('1')
        self.assertEqual((o['lead_in'], o['lead_out'], o['lead_transition']), (0.0, 0.0, 0.0))

    def test_two_means_automatic(self):
        o = self.op('2')
        self.assertEqual((o['lead_mode'], o['lead_in'], o['lead_out'], o['lead_transition'], o['lead_pierce']),
                         ('percage', 2.0, 2.0, 6.0, 0.0))


class TestForm(unittest.TestCase):

    def test_the_form_offers_it(self):
        from vectordrive.ui import cam_panel as P
        for kind in ('contour', 'laser_decoupe'):
            self.assertIn('lead_transition', P.KIND_FIELDS[kind])
        self.assertIn('lead_transition', P.LABELS)


if __name__ == '__main__':
    unittest.main()
