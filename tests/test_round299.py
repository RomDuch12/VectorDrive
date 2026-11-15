"""Round 299 : découpe en chaîne (TypeEdit : chainMode) — d'une pièce à la
suivante sans relever l'outil quand la liaison reste dans la chute."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(contours, **kw):
    d = Document()
    d.plate = None
    for cs in contours:
        d.add(Shape(path=geom.Path(cs), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F', kind='droite', diameter=2)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='contour', depth=2, step_down=1, tool_id=t.id, side='exterieur', **kw))


def rapids_down(tp):
    return sum(1 for m in tp.moves if m.kind == 'plunge')


class TestChain(unittest.TestCase):
    def test_three_parts(self):
        parts = [[geom.rect(i * 15, 0, 10, 10)] for i in range(3)]
        plain = run(parts)
        self.assertEqual(rapids_down(plain), 6)                     # 3 pièces × 2 passes
        tp = run(parts, chain_cut=True)
        self.assertEqual(rapids_down(tp), 2)                        # une plongée par passe
        self.assertTrue(any('2 liaison' in w or '4 liaison' in w for w in tp.warnings), tp.warnings)
        for m in tp.moves:                                          # jamais dans une pièce
            if m.kind == 'feed':
                inside = any(i * 15 + 0.99 < m.x < i * 15 + 9.01 and 0.99 < m.y < 9.01 for i in range(3))
                self.assertFalse(inside, (m.x, m.y))

    def test_hole_lifts(self):
        # trou puis pourtour : la liaison traverserait la pièce — l'outil remonte
        cs = [geom.rect(0, 0, 20, 20), geom.rect(8, 8, 4, 4)]
        tp = run([cs], chain_cut=True)
        self.assertEqual(rapids_down(tp), 4)

    def test_typeedit(self):
        p = tpp.Preset(name='d', kind='CP_Cutting_3D', sections={'SPECIALDECOUPE': {'DecInternal': '2',
                                                                                 'chainMode': '1'}})
        self.assertTrue(tpp.to_template(p)['operations'][0]['chain_cut'])


if __name__ == '__main__':
    unittest.main()
