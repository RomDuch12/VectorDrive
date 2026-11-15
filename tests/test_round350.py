"""Round 350 : découpe 3D, tirés d'angle au sommet (TypeEdit : P25D_AngleMax)
— dans les angles rentrants (côté chute), l'outil conique remonte sur la
bissectrice jusqu'à ce que le cône touche l'angle à la surface."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

L = [(0, 0), (20, 0), (20, 8), (8, 8), (8, 20), (0, 20)]               # angle rentrant en (8, 8)


def run(contour, **kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([contour]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='V90', kind='conique', diameter=6, angle=90, tip=0.2)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='decoupe3d', depth=1, step_down=0.5, tool_id=t.id, **kw))


class TestPulls(unittest.TestCase):
    def test_exterior(self):
        tp = run(geom.polyline(L, closed=True), side='exterieur', corner_pull=True)
        self.assertTrue(any("1 tiré(s) d'angle" in w for w in tp.warnings), tp.warnings)
        top = [m for m in tp.moves if m.kind == 'feed' and abs(m.z) < 1e-9]
        self.assertTrue(top)
        end = top[-1]
        d = math.dist((end.x, end.y), (8, 8))
        self.assertAlmostEqual(d, 0.1 / math.sin(math.radians(45)), 3)       # pointe : 0,1 / sin 45°
        self.assertGreater(end.x, 8)                                            # dans la chute (coin rentrant)
        self.assertGreater(end.y, 8)
        plain = run(geom.polyline(L, closed=True), side='exterieur')
        self.assertFalse(any('tiré' in w for w in plain.warnings))

    def test_interior(self):
        tp = run(geom.rect(0, 0, 20, 10), side='interieur', corner_pull=True)
        self.assertTrue(any("4 tiré(s) d'angle" in w for w in tp.warnings), tp.warnings)
        tp = run(geom.rect(0, 0, 20, 10), side='interieur', corner_pull=True, corner_pull_angle=80)
        self.assertFalse(any('tiré' in w for w in tp.warnings))             # 90° n'est pas sous 80°

    def test_typeedit(self):
        import math as m
        p = tpp.Preset(name='d3', kind='CP_Cutting_3D', sections={'SPECIALDECOUPE': {'DecInternal': '2',
                                                                                    'Mode3DOnly': '1'},
                                                                  'FAO_NEWPARAMGLOB': {'P25D_AngleMax': str(m.radians(120))}})
        o = tpp.to_template(p)['operations'][0]
        self.assertEqual(o['kind'], 'decoupe3d')
        self.assertTrue(o['corner_pull'])
        self.assertAlmostEqual(o['corner_pull_angle'], 120.0, 3)


if __name__ == '__main__':
    unittest.main()
