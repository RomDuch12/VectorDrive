"""Round 301 : poche concentrique en spirale et en partant de l'extérieur
(TypeEdit : Gravure 2D, options En spirale / En partant de l'extérieur)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, simulate as SIM, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(contours, **kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path(contours), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F2', diameter=2, stepover=0.4)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='poche', depth=1, step_down=1, tool_id=t.id, **kw)), setup


def uncut(tp, setup, box):
    sim = SIM.simulate([tp], setup, res=0.05)
    x0, y0, x1, y1 = box
    sub = sim.H[int((y0 - sim.y0) / sim.res):int((y1 - sim.y0) / sim.res),
                int((x0 - sim.x0) / sim.res):int((x1 - sim.x0) / sim.res)]
    return float((sub > -0.99).mean())


def plunges(tp):
    return sum(1 for m in tp.moves if m.kind == 'plunge')


class TestSpiral(unittest.TestCase):
    def test_spiral_clears(self):
        tp, setup = run([geom.rect(0, 0, 20, 12)], pocket_spiral=True)
        self.assertEqual(plunges(tp), 1)
        self.assertTrue(any('1 spirale' in w for w in tp.warnings), tp.warnings)
        self.assertEqual(uncut(tp, setup, (0.3, 0.3, 19.7, 11.7)), 0.0)
        for m in tp.moves:                                       # le centre reste à 1 mm du bord
            if m.kind == 'feed':
                self.assertTrue(1 - 1e-6 <= m.x <= 19 + 1e-6 and 1 - 1e-6 <= m.y <= 11 + 1e-6, (m.x, m.y))

    def test_outside_in(self):
        tp, _ = run([geom.rect(0, 0, 20, 12)], pocket_outside_in=True)
        first = next(m for m in tp.moves if m.kind == 'plunge')
        self.assertTrue(first.x < 1.5 or first.x > 18.5 or first.y < 1.5 or first.y > 10.5)   # au bord
        tp, _ = run([geom.rect(0, 0, 20, 12)])
        first = next(m for m in tp.moves if m.kind == 'plunge')
        self.assertTrue(3 < first.x < 17 and 3 < first.y < 9)                                # au centre
        tp, _ = run([geom.rect(0, 0, 20, 12)], pocket_spiral=True, pocket_outside_in=True)
        first = next(m for m in tp.moves if m.kind == 'plunge')
        self.assertTrue(first.x < 1.5 or first.y < 1.5 or first.x > 18.5 or first.y > 10.5)

    def test_island_keeps_rings(self):
        # îlot : retraits à trou gardés en anneaux, et tout est vidé
        tp, setup = run([geom.rect(0, 0, 30, 30), geom.rect(12, 12, 6, 6)], pocket_spiral=True)
        self.assertEqual(uncut(tp, setup, (0.3, 0.3, 11.7, 29.7)), 0.0)

    def test_typeedit(self):
        p = tpp.Preset(name='g', kind='CP_Engraving_3D', sections={'SPECIALGRAVURE': {
            'Spiraling': '1', 'OuterToInner': '1', 'Stepover': '0.001'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertTrue(o['pocket_spiral'] and o['pocket_outside_in'])


if __name__ == '__main__':
    unittest.main()
