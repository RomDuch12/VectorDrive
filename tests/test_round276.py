"""Round 276 : découpe au couteau (TypeEdit : Vinyle) — tracé, couteau
asservi (remonte aux angles vifs), couteau flottant (axe en avance du
déport de la lame, pivot en arc aux angles)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(mode, shape=None):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([shape or geom.rect(0, 0, 10, 10)]), tool=1))
    setup = M.setup_of(d)
    k = M.CamTool(name='K', kind='couteau', diameter=1, tip=0.5)
    setup.tools = [k]
    return S.compute(d, setup, M.Operation(kind='vinyle', depth=0.2, tool_id=k.id, knife_mode=mode))


class TestKnife(unittest.TestCase):
    def test_modes(self):
        self.assertEqual(sum(1 for m in run('trace').moves if m.kind == 'plunge'), 1)
        self.assertEqual(sum(1 for m in run('asservi').moves if m.kind == 'plunge'), 4)    # une par angle
        fl = run('flottant')
        feeds = [(m.x, m.y) for m in fl.moves if m.kind == 'feed']
        self.assertIn((10.5, 0.0), [(round(x, 6), round(y, 6)) for x, y in feeds])           # axe en avance
        arc = [p for p in feeds if 10 < p[0] < 10.5 and 0 < p[1] < 0.5]
        self.assertTrue(arc)
        self.assertTrue(all(abs(math.hypot(x - 10, y) - 0.5) < 1e-6 for x, y in arc))       # pivot autour du coin
        self.assertTrue(all(m.z == -0.2 for m in fl.moves if m.kind == 'feed'))

    def test_smooth_curve_no_pivot(self):
        tp = run('asservi', geom.circle((0, 0), 10))
        self.assertEqual(sum(1 for m in tp.moves if m.kind == 'plunge'), 1)                  # pas d'angle vif

    def test_typeedit(self):
        self.assertEqual(tpp.TYPES['CP_Vinyl'][1], 'vinyle')
        self.assertIn('couteau', M.TOOL_KINDS)


if __name__ == '__main__':
    unittest.main()
