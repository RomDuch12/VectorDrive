"""Round 333 : gravure 2,5D, nombre de passes limité (TypeEdit :
IsLimitednbStep, NbLimitedStep) — seules les n passes près du bord."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(**kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='V', kind='conique', diameter=6, angle=90, tip=0.1)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='vcarve', depth=1, tool_id=t.id, resolution=0.2, **kw))


class TestLimited(unittest.TestCase):
    def test_limit(self):
        full = run()
        lim = run(vcarve_max_steps=3)
        zf = min(m.z for m in full.moves)
        zl = min(m.z for m in lim.moves)
        self.assertLess(zf, zl)                                       # les passes profondes ne sont pas faites
        self.assertAlmostEqual(zl, -(0.05 + 3 * 0.2 - 0.05), 3)       # 3e retrait : d = 0,05 + 0,6
        self.assertTrue(any('passes limité' in w or 'limité' in w for w in lim.warnings))
        self.assertLess(len(lim.moves), len(full.moves))

    def test_typeedit(self):
        p = tpp.Preset(name='g', kind='CP_Engraving_3D', sections={'SPECIALGRAVURE': {
            'IsLimitednbStep': '1', 'NbLimitedStep': '2', 'Stepover': '0.001'}})
        self.assertEqual(tpp.to_template(p)['operations'][0]['vcarve_max_steps'], 2)


if __name__ == '__main__':
    unittest.main()
