"""Round 280 : finition TypeEdit (bords et tirés d'angle) — gravure 2,5D
sans vidage du fond ; cadre englobant ignoré en gravure en relief ;
modèles TypeEdit « Finition » (CP_Finishing) repris ainsi."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def setup_of(paths):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path(paths), tool=1))
    setup = M.setup_of(d)
    v = M.CamTool(name='V30', kind='conique', diameter=3, angle=30, tip=0.2)
    setup.tools = [v]
    return d, setup, v


class TestFinition(unittest.TestCase):
    def test_edges_only(self):
        d, setup, v = setup_of([geom.rect(0, 0, 20, 10)])
        full = S.compute(d, setup, M.Operation(kind='vcarve', depth=0.5, tool_id=v.id))
        edge = S.compute(d, setup, M.Operation(kind='vcarve', depth=0.5, tool_id=v.id, vcarve_edges_only=True))
        self.assertLess(len(edge.moves), len(full.moves) / 3)
        xs = [m.x for m in edge.moves if m.kind == 'feed']
        self.assertGreaterEqual(min(xs), 0.05 - 1e-6)                              # le tiré d'angle touche les bords à la pointe
        self.assertLess(max(x for x in xs if x < 10), 1.0)                         # près des bords seulement
        self.assertAlmostEqual(min(m.z for m in edge.moves), -0.5, 6)

    def test_skip_frame(self):
        # gravure en relief : un cadre et une lettre (carré) laissée en relief au milieu
        d, setup, v = setup_of([geom.rect(0, 0, 30, 20), geom.rect(10, 5, 10, 10)])
        op = M.Operation(kind='vcarve', depth=0.5, tool_id=v.id, vcarve_edges_only=True, finish_skip_frame=True)
        tp = S.compute(d, setup, op)
        feeds = [(m.x, m.y) for m in tp.moves if m.kind == 'feed']
        self.assertTrue(feeds)
        self.assertTrue(all(9 < x < 21 and 4 < y < 16 for x, y in feeds))          # seulement autour de la lettre

    def test_typeedit(self):
        p = tpp.Preset(name='Finit 30 0.2', kind='CP_Finishing', sections={
            'SPECIALFINITION': {'Allowance': '0.', 'SkipExternal': '1'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertEqual((o['kind'], o['vcarve_edges_only'], o['finish_skip_frame']), ('vcarve', True, True))


if __name__ == '__main__':
    unittest.main()
