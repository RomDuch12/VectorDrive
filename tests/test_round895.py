"""Round 895 : la Finition et le cône de la Gamme sans calcul refait, même parcours. Les contours aplatis et la région une fois (le cône
les passe à la Finition), les cadres une fois par cône, les angles à tirer une fois par Finition, leur portée pour tous les angles à la
fois. L'ancienne portée, angle par angle, est recopiée ici pour comparer."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from vectordrive.cam import finish as F
from vectordrive.cam import gamme
from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape


# --- la version d'avant (round 894), pour comparer -----------------------------------------------------------------------------------

def old_pull_reach(edge, v, b, s, d):
    from shapely.geometry import Point

    def ok(t, eps):
        return abs(edge.distance(Point(v[0] + b[0] * t, v[1] + b[1] * t)) - t * s) <= eps
    t1 = d / s
    lo, hi = 0.0, None
    for k in range(1, 9):
        t = t1 * k / 8
        if ok(t, 1e-4):
            lo = t
        else:
            hi = t
            break
    if hi is None:
        return d
    for _ in range(14):
        m = (lo + hi) / 2
        if ok(m, 1e-5):
            lo = m
        else:
            hi = m
    return lo * s


def old_pulls(reg, d, max_angle):
    out = []
    if max_angle <= 0:
        return out
    for poly in getattr(reg, 'geoms', [reg]):
        if poly.geom_type != 'Polygon' or poly.is_empty:
            continue
        edge = poly.boundary
        for v, b, ang in S.corner_pulls(poly, False, max_angle):
            s = math.sin(ang / 2)
            if s > 1e-6:
                out.append((v, b, s, old_pull_reach(edge, v, b, s, d)))
    return out


# --- dessins -------------------------------------------------------------------------------------------------------------------------

def square(x0, y0, x1, y1):
    return geom.polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True)


def poly(pts):
    return geom.polyline(pts, closed=True)


def drawing(*paths):
    doc = Document()
    layer = Layer(name='Plan 1', items=[Shape(path=geom.Path([p])) for p in paths])
    doc.layers[:] = [layer]
    doc.active = layer.id
    doc.plate = Plate(width=300, height=200)
    return doc


def letters():
    """Un cadre, des formes à angles vifs, une branche étroite, une île dans un trou : tirés d'angle, axes et anneaux."""
    return drawing(square(0, 0, 60, 40),
                   poly([(5, 5), (25, 5), (25, 9), (9, 9), (9, 30), (5, 30)]),
                   poly([(30, 5), (55, 5), (42, 35)]),
                   square(8, 32, 28, 37),
                   square(10, 33, 26, 36),
                   poly([(33, 10), (37, 10), (37.6, 25), (33.4, 25)]))


def regions():
    """Angles dont la bissectrice est barrée avant le bout (V étroit, peigne), et d'autres libres."""
    comb = box(0, 0, 30, 4).union(unary_union([box(2 + 4 * i, 4, 3 + 4 * i, 12) for i in range(7)]))
    v = Polygon([(40, 0), (60, 0), (50.4, 30), (50, 3), (49.6, 30)])
    star = Polygon([(70 + 6 * math.cos(math.pi * k / 5) * (1 if k % 2 == 0 else 0.4), 6 * math.sin(math.pi * k / 5) * (1 if k % 2 == 0 else 0.4))
                    for k in range(10)])
    frame = box(90, 0, 130, 30).difference(box(95, 5, 125, 25))
    return [comb, v, star, frame, unary_union([comb, v, star, frame])]


def cone(tip=0.2, angle=30.0):
    return M.CamTool(name='k', kind='conique', diameter=6.0, tip=tip, angle=angle)


def finition(doc, **kw):
    k = cone()
    setup = M.CamSetup(tools=[k])
    op = M.Operation(kind='vcarve', tool_id=k.id, depth=1.0, climb=True)
    op.vcarve_step = 0.5
    op.vcarve_edges_only = True
    op.finish_rule = 877
    for key, v in kw.items():
        setattr(op, key, v)
    setup.operations = [op]
    return S.compute(doc, setup, op, (0.0, 0.0))


def gamme_cone(doc):
    c, k = M.CamTool(name='c', kind='fraise', diameter=2.0), cone(0.2)
    setup = M.CamSetup(tools=[c, k])
    ops = gamme.build(setup, [gamme.Step(c.id, 'contournage', stepover=1.0, step_down=0.5),
                              gamme.Step(k.id, finish3d=True, stepover=0.2, step_down=0.5)],
                      1.5, climb=True, ramp=True, ramp_angle=10.0, pass_order='global', skip_frame=True, stock=0.1)
    setup.operations = list(ops)
    return S.compute(doc, setup, ops[1], (0.0, 0.0))


def moves(tp):
    return [(m.kind, m.x, m.y, m.z) for m in tp.moves]


# --- essais --------------------------------------------------------------------------------------------------------------------------

class Portee(unittest.TestCase):

    def test_same_reach_as_corner_by_corner(self):
        for reg in regions():
            for d in (0.3, 1.0, 2.5, 6.0):
                want = old_pulls(reg, d, 135.0)
                self.assertEqual(F._pulls(reg, d, 135.0), want)                 # mêmes valeurs, au bit près
                corners = F._pull_corners(reg, 135.0)
                self.assertEqual(F._pulls(reg, d, 135.0, corners), want)

    def test_some_reaches_are_cut_short(self):
        reach = [p[3] for p in F._pulls(regions()[-1], 2.5, 135.0)]
        self.assertTrue(any(r < 2.5 for r in reach))
        self.assertTrue(any(r == 2.5 for r in reach))

    def test_no_corner(self):
        self.assertEqual(F._pulls(box(0, 0, 5, 5), 1.0, 0.0), [])
        self.assertEqual(F._pull_reaches([], 1.0), [])


class Region(unittest.TestCase):

    def test_from_lines_is_region(self):
        doc = letters()
        paths = [S.item_geometry(it) for it in doc.layers[0].items]
        self.assertTrue(S.region_from_lines(S.polylines(paths, 0.01)).equals(S.region(paths, 0.01)))


class Parcours(unittest.TestCase):

    def test_finition_same_moves(self):
        with mock.patch.object(F, '_pulls', lambda reg, d, a, corners=None: old_pulls(reg, d, a)):
            old = moves(finition(letters()))
        new = moves(finition(letters()))
        self.assertGreater(len(new), 100)
        self.assertEqual(new, old)

    def test_gamme_cone_same_moves(self):
        with mock.patch.object(F, '_pulls', lambda reg, d, a, corners=None: old_pulls(reg, d, a)):
            old = moves(gamme_cone(letters()))
        new = moves(gamme_cone(letters()))
        self.assertGreater(len(new), 100)
        self.assertEqual(new, old)


class UneFois(unittest.TestCase):
    """Ce qui ne dépend pas de la passe n'est calculé qu'une fois (trois passes ici)."""

    def test_gamme_cone(self):
        with mock.patch.object(S, 'polylines', wraps=S.polylines) as lines, \
                mock.patch.object(S, 'frames_of', wraps=S.frames_of) as frames, \
                mock.patch.object(S, 'corner_pulls', wraps=S.corner_pulls) as corners:
            gamme_cone(letters())
        self.assertEqual(lines.call_count, 1)                                   # avant : 3
        self.assertEqual(frames.call_count, 1)                                  # avant : 1 + 1 par passe
        self.assertLessEqual(corners.call_count, 6)                             # avant : une fois par forme et par passe

    def test_finition(self):
        with mock.patch.object(S, 'polylines', wraps=S.polylines) as lines:
            finition(letters())
        self.assertEqual(lines.call_count, 1)                                   # avant : 2


if __name__ == '__main__':
    unittest.main()
