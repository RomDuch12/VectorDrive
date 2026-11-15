"""Round 189 : poches usinées forme par forme."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def setup(rects, depth=3.0):
    d = Document()
    d.plate = None
    for x, y, w, h in rects:
        d.add(Shape(path=geom.Path([geom.rect(x, y, w, h)]), tool=0))
    s = model.CamSetup()
    t = model.CamTool(name='F2', kind='fraise', diameter=2.0, stepover=0.4, step_down=1.0, feed=800.0)
    s.tools = [t]
    op = model.Operation(kind='poche', tool_id=t.id, depth=depth, step_down=1.0)
    s.operations = [op]
    return d, s, op


def shells_of(reg, r, step, tol, stock=0.0):
    qs = S._quad_segs(max(r, tol), tol)
    out, g = [], S.erode(reg, r + stock, qs)
    while not g.is_empty:
        out.append(S.simplify_parts(g, tol / 2))
        g = S.erode(reg, r + stock + len(out) * step, qs)
    return out


def travel(tp):
    pos, total = None, 0.0
    for m in tp.moves:
        if m.kind == 'rapid' and pos is not None:
            total += math.hypot(m.x - pos[0], m.y - pos[1])
        pos = (m.x, m.y)
    return total


LETTERS = [(0, 0, 20, 10), (30, 0, 20, 10), (60, 0, 20, 10), (90, 0, 20, 10), (120, 0, 20, 10)]


class TestPocket(unittest.TestCase):
    def test_groups_cover_same_rings(self):
        d, s, op = setup(LETTERS)
        reg = S.region([S.item_geometry(it) for it in S.source_items(d, op)], s.tolerance)
        shells = shells_of(reg, 1.0, 0.8, s.tolerance)
        old = [pts for sh in reversed(shells) for pts in S.rings_of(sh, True)]
        groups = S.shape_groups(reg, shells, True)
        self.assertEqual(len(groups), 5)
        self.assertEqual(sorted(map(tuple, map(tuple, (p for g in groups for p in g)))),
                         sorted(map(tuple, map(tuple, old))))
        single = S.region([geom.Path([geom.rect(0, 0, 20, 10)])], s.tolerance)
        sh1 = shells_of(single, 1.0, 0.8, s.tolerance)
        self.assertEqual(S.shape_groups(single, sh1, True),
                         [[pts for sh in reversed(sh1) for pts in S.rings_of(sh, True)]])

    def test_one_shape_at_a_time(self):
        d, s, op = setup(LETTERS)
        tp = S.compute(d, s, op)
        seen, current = [], None
        for m in tp.moves:
            if m.kind != 'feed':
                continue
            k = next(i for i, (x, y, w, h) in enumerate(LETTERS) if x - 0.01 <= m.x <= x + w + 0.01)
            if k != current:
                self.assertNotIn(k, seen)                                         # jamais de retour
                seen.append(k)
                current = k
        self.assertEqual(seen, [0, 1, 2, 3, 4])                                   # au plus proche, depuis l'origine
        for k, (x, _y, w, _h) in enumerate(LETTERS):
            zs = {round(m.z, 6) for m in tp.moves if m.kind == 'feed' and x <= m.x <= x + w}
            self.assertEqual(zs, {-1.0, -2.0, -3.0})                              # toutes les passes de la forme

    def test_less_travel(self):
        d, s, op = setup(LETTERS)
        tp = S.compute(d, s, op)
        reg = S.region([S.item_geometry(it) for it in S.source_items(d, op)], s.tolerance)
        shells = shells_of(reg, 1.0, 0.8, s.tolerance)
        em = S.Emitter(op, s.tools[0])
        old = [pts for sh in reversed(shells) for pts in S.rings_of(sh, not op.climb)]
        S.mill_rings(em, old, S.levels(op.depth, 1.0), S.erode(reg, 1.0 - 1e-6, 8))
        em.retract()
        before = model.Toolpath(op_id=op.id, tool_id=op.tool_id)
        before.moves = em.moves
        self.assertLess(travel(tp), travel(before) / 3)
        ups = lambda t: sum(1 for m in t.moves if m.kind == 'rapid' and m.z >= op.safe_z - 1e-9)
        self.assertLess(ups(tp), ups(before))                                     # moins de remontées

    def test_single_shape_unchanged(self):
        d, s, op = setup([(0, 0, 30, 18)])
        tp = S.compute(d, s, op)
        reg = S.region([S.item_geometry(it) for it in S.source_items(d, op)], s.tolerance)
        shells = shells_of(reg, 1.0, 0.8, s.tolerance)
        em = S.Emitter(op, s.tools[0])
        old = [pts for sh in reversed(shells) for pts in S.rings_of(sh, not op.climb)]
        S.mill_rings(em, old, S.levels(op.depth, 1.0), S.erode(reg, 1.0 - 1e-6, 8))
        em.retract()
        self.assertEqual([(m.kind, m.x, m.y, m.z) for m in tp.moves], [(m.kind, m.x, m.y, m.z) for m in em.moves])


if __name__ == '__main__':
    unittest.main()
