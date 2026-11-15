"""Round 190 : V-carving forme par forme."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

LETTERS = [(0, 0, 8, 5), (30, 0, 8, 5), (60, 0, 8, 5), (90, 0, 8, 5), (120, 0, 8, 5)]


def setup(rects):
    d = Document()
    d.plate = None
    for x, y, w, h in rects:
        d.add(Shape(path=geom.Path([geom.rect(x, y, w, h)]), tool=0))
    s = model.CamSetup()
    t = model.CamTool(name='V60', kind='conique', diameter=6.0, angle=60.0, tip=0.1, feed=800.0)
    s.tools = [t]
    op = model.Operation(kind='vcarve', tool_id=t.id, depth=1.0, resolution=0.2, pocket_outside_in=True, corner_pull_angle=0.0)
    s.operations = [op]
    return d, s, op


def travel(moves):
    pos, total = None, 0.0
    for m in moves:
        if m.kind == 'rapid' and pos is not None:
            total += math.hypot(m.x - pos[0], m.y - pos[1])
        pos = (m.x, m.y)
    return total


def reference(d, s, op):
    """L'ancien ordre (passe par passe sur tout le dessin), pour comparer."""
    from shapely.geometry import LineString
    tool = s.tools[0]
    reg = S.region([S.item_geometry(it) for it in S.source_items(d, op)], s.tolerance)
    tol = s.tolerance
    tan_h = math.tan(math.radians(tool.angle) / 2)
    rt = tool.tip / 2
    depth_max = abs(op.depth)
    d_flat = rt + depth_max * tan_h
    step = max(0.01, op.resolution or 0.05)
    qs = S._quad_segs(max(d_flat, tol), tol)
    rr = not op.climb
    passes = []
    dd = rt + step
    while dd < d_flat - 1e-9:
        g = S.erode(reg, dd, qs)
        if g.is_empty:
            break
        passes.append((dd, -min(depth_max, (dd - rt) / tan_h), S.rings_of(S.simplify_parts(g, tol / 2), rr)))
        dd += step
    base = S.erode(reg, d_flat, qs)
    if not base.is_empty:
        flat_step = max(0.02, 2 * (rt + 0.02 * tan_h))
        for k, g in enumerate(S.concentric(base, flat_step, tol)):
            passes.append((d_flat + k * flat_step, -depth_max, S.rings_of(g, rr)))
    em = S.Emitter(op, tool)
    cur = zcur = None
    for dd, z, rings in passes:
        inside = S.within_test(S.erode(reg, (cur if cur is not None else dd) - 1e-6, qs))
        for pts in rings:
            pts = S._start_nearest(pts, True, em.pos)
            if em.pos is not None and em.pos[2] < 0 and inside(LineString([em.pos[:2], pts[0][:2]])):
                zl = max(em.pos[2], zcur if zcur is not None else z)     # profondeur sûre (round 630)
                if zl > em.pos[2] + 1e-9:
                    em.feed(em.pos[0], em.pos[1], zl)
                em.feed(pts[0][0], pts[0][1], zl)
                em.plunge(z)
            else:
                em.travel(*pts[0][:2])
                em.plunge(z)
            for p in pts[1:]:
                em.feed(p[0], p[1], z)
        cur, zcur = dd, z
    em.retract()
    return em.moves


class TestVcarve(unittest.TestCase):
    def test_single_shape_unchanged(self):
        d, s, op = setup([(0, 0, 9, 6)])
        tp = S.compute(d, s, op)
        ref = reference(d, s, op)
        self.assertEqual([(m.kind, m.x, m.y, m.z) for m in tp.moves], [(m.kind, m.x, m.y, m.z) for m in ref])

    def test_one_shape_at_a_time(self):
        d, s, op = setup(LETTERS)
        tp = S.compute(d, s, op)
        seen, current = [], None
        for m in tp.moves:
            if m.kind != 'feed':
                continue
            k = next(i for i, (x, y, w, h) in enumerate(LETTERS) if x - 0.01 <= m.x <= x + w + 0.01)
            if k != current:
                self.assertNotIn(k, seen)
                seen.append(k)
                current = k
        self.assertEqual(seen, [0, 1, 2, 3, 4])

    def test_less_travel_same_cuts(self):
        d, s, op = setup(LETTERS)
        new, old = S.compute(d, s, op).moves, reference(d, s, op)
        self.assertLess(travel(new), travel(old) / 3)
        self.assertEqual(min(m.z for m in new), min(m.z for m in old))
        def cut(ms):                                                              # sans les liaisons au fond
            return sorted({(round(m.x, 6), round(m.y, 6), round(m.z, 6)) for i, m in enumerate(ms)
                           if m.kind == 'feed' and not (i + 1 < len(ms) and ms[i + 1].kind == 'plunge')})
        self.assertEqual(cut(new), cut(old))                                      # mêmes points usinés


if __name__ == '__main__':
    unittest.main()
