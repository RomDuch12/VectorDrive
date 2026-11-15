"""Round 297 : découpe (TypeEdit : onglets FAO et Boucles) — boucles aux
angles extérieurs (angles vifs, collisions gérées), angles arrondis en plus
de l'outil, décalage supplémentaire ; reprise des réglages TypeEdit."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(contours, **kw):
    d = Document()
    d.plate = None
    for c in contours:
        d.add(Shape(path=geom.Path([c]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F', kind='droite', diameter=2)
    setup.tools = [t]
    kw.setdefault('side', 'exterieur')
    return S.compute(d, setup, M.Operation(kind='contour', depth=1, step_down=1, tool_id=t.id, **kw))


def feeds(tp):
    return [(m.x, m.y) for m in tp.moves if m.kind == 'feed']


class TestCutting(unittest.TestCase):
    def test_loops_outside(self):
        tp = run([geom.rect(0, 0, 20, 20)], corner_loops=True, loop_length=3, loop_radius=1)
        self.assertTrue(any('4 boucle' in w for w in tp.warnings), tp.warnings)
        pts = feeds(tp)
        self.assertTrue(any(abs(x - 24) < 1e-6 and abs(y + 1) < 1e-6 for x, y in pts))   # arête prolongée
        for x, y in pts:                                                              # jamais dans la pièce
            dx, dy = max(0 - x, 0, x - 20), max(0 - y, 0, y - 20)
            self.assertGreaterEqual(math.hypot(dx, dy), 1 - 1e-6)
        plain = run([geom.rect(0, 0, 20, 20)])
        self.assertLess(max(x for x, _ in feeds(plain)), 21 + 1e-6)

    def test_collision(self):
        # deux pièces proches : les boucles qui les toucheraient sont réduites ou omises
        tp = run([geom.rect(0, 0, 20, 20), geom.rect(24, 0, 20, 20)], corner_loops=True, loop_length=5, loop_radius=2)
        for x, y in feeds(tp):
            for x0 in (0, 24):
                dx, dy = max(x0 - x, 0, x - x0 - 20), max(0 - y, 0, y - 20)
                self.assertGreaterEqual(math.hypot(dx, dy), 1 - 1e-3)

    def test_inside_loops(self):
        # découpe intérieure d'un L : seul l'angle rentrant du trou est extérieur à la matière gardée
        L = geom.polyline([(0, 0), (20, 0), (20, 8), (8, 8), (8, 20), (0, 20)], closed=True)
        tp = run([L], side='interieur', corner_loops=True, loop_length=2, loop_radius=0.5)
        self.assertTrue(any('1 boucle' in w for w in tp.warnings), tp.warnings)

    def test_round_offset(self):
        tp = run([geom.rect(0, 0, 20, 20)], corner_round=3)
        pts = feeds(tp)
        # coin arrondi de 3 mm + rayon 1 : le parcours passe à 4 mm du centre d'arrondi (3, 3)
        d = min(math.hypot(x - 23, y - 23) for x, y in pts)
        self.assertAlmostEqual(min(math.hypot(x - 17, y - 17) for x, y in pts), 4, 1)
        self.assertGreater(d, 4.4)                                            # sans : 3,24
        tp = run([geom.rect(0, 0, 20, 20)], offset_add=0.5)
        self.assertAlmostEqual(max(x for x, _ in feeds(tp)), 21.5, 6)

    def test_typeedit(self):
        from vectordrive.cam import tpp
        p = tpp.Preset(name='d', kind='CP_Cutting_3D', sections={'SPECIALDECOUPE': {
            'DecInternal': '2', 'm_AddLoop': '1', 'm_LoopRadius': '0.0025', 'm_LoopLength': '0.0055',
            'm_AngleMin': '0.0872664625997165', 'm_AngleMax': '2.87979326579064', 'm_LengthMini': '0.0001',
            'm_CheckCollision': '1', 'Anglearrondi': '0.001', 'OffsetAdd': '-0.0002'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertTrue(o['corner_loops'] and o['loop_check'])
        self.assertAlmostEqual(o['loop_radius'], 2.5)
        self.assertAlmostEqual(o['loop_length'], 5.5)
        self.assertAlmostEqual(o['loop_angle_min'], 5.0)
        self.assertAlmostEqual(o['loop_angle_max'], 165.0)
        self.assertAlmostEqual(o['corner_round'], 1.0)
        self.assertAlmostEqual(o['offset_add'], -0.2)

if __name__ == '__main__':
    unittest.main()
