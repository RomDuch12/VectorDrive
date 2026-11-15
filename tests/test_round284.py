"""Round 284 : balayage texturé (TypeEdit : Texturing) — coups de gouge de
longueur, profondeur et chevauchement tirés dans des bornes, même tirage =
même texture ; modèles TypeEdit SPECIALSWEEPING Texturing / TEXTURING."""
import os
import random
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
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 40, 20)]), tool=1))
    setup = M.setup_of(d)
    b = M.CamTool(name='B6', kind='boule', diameter=6, stepover=0.5)
    setup.tools = [b]
    return S.compute(d, setup, M.Operation(kind='poche', depth=1, tool_id=b.id, pocket_mode='balayage',
                                           sweep_texture=True, **kw))


class TestTexturing(unittest.TestCase):
    def test_strokes(self):
        op = M.Operation(tex_depth_min=0.2, tex_depth_max=0.4, tex_len_min=2, tex_len_max=3, tex_overlap=50)
        strokes = S.texture_strokes([[(0, 0), (30, 0)]], op, random.Random(1))
        self.assertGreater(len(strokes), 10)
        for st in strokes:
            depth = -min(z for _x, _y, z in st)
            self.assertTrue(0.2 - 1e-9 <= depth <= 0.4 + 0.02)
            self.assertAlmostEqual(st[0][2], 0.0)                                  # à fleur aux bouts
            self.assertAlmostEqual(st[-1][2], 0.0, 9)
            self.assertLessEqual(st[-1][0] - st[0][0], 3 + 1e-9)
        self.assertLess(strokes[1][0][0], strokes[0][-1][0])                      # chevauchement

    def test_pocket_and_seed(self):
        a, b = run(tex_seed=3), run(tex_seed=3)
        self.assertEqual([(m.x, m.y, m.z) for m in a.moves], [(m.x, m.y, m.z) for m in b.moves])
        c = run(tex_seed=4)
        self.assertNotEqual([m.z for m in a.moves], [m.z for m in c.moves])
        self.assertGreater(-min(m.z for m in a.moves), 0.3)

    def test_typeedit(self):
        p = tpp.Preset(name='Bal tex', kind='CP_Sweeping', sections={
            'SPECIALSWEEPING': {'Texturing': '1'},
            'TEXTURING': {'DepthMin': '1.e-003', 'DepthMax': '2.e-003', 'LengthMin': '2.5', 'LengthMax': '5.',
                          'OverlapMin': '70.', 'OverlapMax': '25.'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertEqual((o['sweep_texture'], o['tex_depth_min'], o['tex_depth_max'], o['tex_len_max']),
                         (True, 1.0, 2.0, 5.0))
        self.assertAlmostEqual(o['tex_overlap'], 47.5)


if __name__ == '__main__':
    unittest.main()
