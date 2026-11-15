"""Round 884 : un tiré d'angle s'arrête avant la paroi que le cône toucherait."""
import math
import unittest

import shapely
from shapely.geometry import Polygon

from vectordrive.cam import finish as F
from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

TAN = math.tan(math.radians(15))
RT = 0.1


def drawing(*shapes):
    doc = Document()
    layer = Layer(name='Plan 1', items=[Shape(path=geom.Path([geom.polyline(list(s), closed=True)])) for s in shapes])
    doc.layers[:] = [layer]
    doc.active = layer.id
    doc.plate = Plate(width=300, height=200)
    return doc


def wedge(bump=0.0):
    """Une pointe très fermée vers la gauche, longue de 40 mm ; sur son flanc haut, une bosse courte vers l'intérieur."""
    x_tip, y_tip = 10.0, 50.0
    slope = math.tan(math.radians(6))
    top = []
    if bump:
        # entre deux points d'essai de la distance atteinte : à 1,6 mm du bord, 8 points sur 15,3 mm, soit 11,5 puis 13,4 mm de la pointe
        x = x_tip + 12.0
        top = [(x, y_tip + slope * 12.0), (x + 0.3, y_tip + slope * 12.3 - bump), (x + 0.6, y_tip + slope * 12.6)]
    return [(x_tip, y_tip), (x_tip + 40, y_tip - slope * 40), (x_tip + 40, y_tip + slope * 40)] + top[::-1]


def run(shape, **kw):
    doc = drawing(shape)
    t = M.CamTool(name='c', kind='conique', diameter=6.0, tip=2 * RT, angle=30.0)
    setup = M.CamSetup(tools=[t])
    op = M.Operation(kind='vcarve', tool_id=t.id, depth=6.0, step_down=6.0, vcarve_step=6.0, climb=True, vcarve_edges_only=True, ramp=True, ramp_angle=15.0,
                     **kw)
    setup.operations = [op]
    tp = S.compute(doc, setup, op, (0.0, 0.0))
    return doc, setup, tp


def worst_over(doc, setup, tp):
    reg = S.region([S.item_geometry(doc.layers[0].items[0])], setup.tolerance)
    worst = -1.0
    last = None
    for m in tp.moves:
        if last is not None and m.kind != 'rapid':
            n = max(1, int(math.dist((last.x, last.y), (m.x, m.y)) / 0.05))
            for i in range(1, n + 1):
                a = i / n
                x, y, z = last.x + a * (m.x - last.x), last.y + a * (m.y - last.y), last.z + a * (m.z - last.z)
                if z < -1e-6:
                    worst = max(worst, RT - z * TAN - reg.boundary.distance(shapely.Point(x, y)))
        last = m
    return worst


class Limite(unittest.TestCase):

    def setUp(self):
        self.reg = Polygon(wedge(0.3))
        self.walls = F._walls_index(self.reg)

    def test_la_distance_atteinte_seule_ne_voit_pas_la_bosse(self):
        pulls = F._pulls(self.reg, 1.6, 135.0)
        tip = [p for p in pulls if abs(p[0][0] - 10.0) < 1e-6][0]
        self.assertAlmostEqual(tip[3], 1.6, places=6)

    def test_le_tire_s_arrete_avant_la_bosse(self):
        pulls = F._pulls(self.reg, 1.6, 135.0)
        out = F._limit_pulls(pulls, self.walls)
        tip = [p for p in out if abs(p[0][0] - 10.0) < 1e-6][0]
        full = tip[3] / tip[2]
        self.assertLess(full, 12.5)
        self.assertGreater(full, 10.0)

    def test_sans_bosse_rien_ne_change(self):
        reg = Polygon(wedge())
        pulls = F._pulls(reg, 1.6, 135.0)
        self.assertEqual(F._limit_pulls(pulls, F._walls_index(reg)), pulls)

    def test_sans_tire_ni_paroi(self):
        self.assertEqual(F._limit_pulls([], self.walls), [])
        p = [((0.0, 0.0), (1.0, 0.0), 0.5, 0.1)]
        self.assertEqual(F._limit_pulls(p, None), p)

    def test_un_seul_tire_touche_dans_la_liste(self):
        reg = Polygon(wedge(0.3))
        pulls = F._pulls(reg, 1.6, 135.0)
        out = F._limit_pulls(pulls, F._walls_index(reg))
        self.assertEqual(len(out), len(pulls))
        changed = [k for k in range(len(out)) if out[k][3] != pulls[k][3]]
        self.assertIn(next(k for k, p in enumerate(pulls) if abs(p[0][0] - 10.0) < 1e-6), changed)


class Parcours(unittest.TestCase):

    def test_le_cone_n_entre_plus_dans_la_paroi(self):
        doc, setup, tp = run(wedge(0.3))
        self.assertTrue(tp.moves)
        self.assertLess(worst_over(doc, setup, tp), 0.03)

    def test_sans_bosse_le_tire_reste_entier(self):
        doc, setup, tp = run(wedge())
        self.assertLess(worst_over(doc, setup, tp), 0.03)
        low = min(m.z for m in tp.moves if m.x < 30 and m.kind != 'rapid')
        self.assertLess(low, -1.0)


if __name__ == '__main__':
    unittest.main()
