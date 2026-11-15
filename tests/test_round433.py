"""Round 433 : passes multiples — poche par poche ou global, passes connectées en rampe."""
import unittest

from vectordrive.cam import model, strategies
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(kind, **kw):
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=1))
    d.add(Shape(path=geom.Path([geom.rect(30, 0, 10, 10)]), tool=1))
    s = model.CamSetup()
    s.tools = [model.CamTool(name='F2', diameter=2.0, step_down=0.5, number=1)]
    op = model.Operation(kind=kind, depth=1.5, step_down=0.5, tool_id=s.tools[0].id, sources=[1], **kw)
    s.operations.append(op)
    return strategies.compute(d, s, op)


def visits(tp):
    """Suite (pièce, cote) des avances au fond de chaque passe, sans doublon consécutif."""
    out = []
    for m in tp.moves:
        if m.kind != 'feed':
            continue
        key = ('A' if m.x < 20 else 'B', round(m.z, 3))
        if not out or out[-1] != key:
            out.append(key)
    return [k for k in out if k[1] in (-0.5, -1.0, -1.5)]


def compress(seq):
    out = []
    for k in seq:
        if not out or out[-1] != k:
            out.append(k)
    return out


class TestPassOrder(unittest.TestCase):
    def test_pocket_order(self):
        per = compress(visits(run('poche')))
        self.assertEqual([k[0] for k in per], ['A', 'A', 'A', 'B', 'B', 'B'])        # poche par poche
        glob = compress(visits(run('poche', pass_order='global')))
        self.assertEqual(glob, [('A', -0.5), ('B', -0.5), ('A', -1.0), ('B', -1.0), ('A', -1.5), ('B', -1.5)])

    def test_contour_order(self):
        per = compress(visits(run('contour', side='exterieur')))
        self.assertEqual([k[0] for k in per], ['A', 'A', 'A', 'B', 'B', 'B'])
        glob = compress(visits(run('contour', side='exterieur', pass_order='global')))
        self.assertEqual([k[1] for k in glob], [-0.5, -0.5, -1.0, -1.0, -1.5, -1.5])

    def test_link_passes(self):
        def rapids_inside(tp):                                       # remontées au-dessus de la pièce, dans A
            return sum(1 for m in tp.moves if m.kind == 'rapid' and m.x < 20 and m.z > 0)
        plain = run('poche')
        linked = run('poche', link_passes=True, ramp_angle=10.0)
        self.assertLess(rapids_inside(linked), rapids_inside(plain))
        zs = [m.z for m in linked.moves if m.kind == 'feed' and m.x < 20]
        self.assertTrue(any(-1.0 < z < -0.5 for z in zs))            # descente en pente entre deux passes
        self.assertAlmostEqual(min(zs), -1.5)
        def sloped(tp):                                              # avances qui descendent en avançant
            ms = tp.moves
            return sum(1 for a, b in zip(ms, ms[1:]) if b.kind == 'feed' and b.z < a.z - 1e-6
                       and abs(b.x - a.x) + abs(b.y - a.y) > 1e-6)
        self.assertEqual(sloped(run('contour', side='exterieur')), 0)
        self.assertGreaterEqual(sloped(run('contour', side='exterieur', link_passes=True)), 4)   # 2 pièces × 2 descentes


if __name__ == '__main__':
    unittest.main()
