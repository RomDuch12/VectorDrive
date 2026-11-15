"""Round 888 : la Finition et le cône de la Gamme plus rapides, même parcours. Chaque sommet d'anneau cherché une fois
(`_Graph.chain`), les contours de tous les tours d'une passe en une requête (`_owners`), les cadres trouvés sans comparer chaque forme
à toutes les autres (`frames_of`). Les anciennes versions sont recopiées ici pour comparer."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.ops import unary_union

from vectordrive.cam import finish as F
from vectordrive.cam import gamme
from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape


# --- les versions d'avant (round 887), pour comparer ---------------------------------------------------------------------------------

def old_edges(g, path, kind):
    for a, b in zip(path, path[1:]):
        g.edge([a, b], kind)


def old_owner(g, cycle, tree, wall_right, rt, tan_h, stock):
    votes: dict = {}
    every = max(1, len(cycle) // 24)
    for h in cycle[::every] + [c for c in cycle if g.he[c][4] == 'axe'][:8]:
        e = g.he[h]
        if e[4] == 'tire':
            continue
        path = e[2]
        for a, b in zip(path, path[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            n = math.hypot(dx, dy)
            if n < 1e-9:
                continue
            nx, ny = (dy / n, -dx / n) if wall_right else (-dy / n, dx / n)
            zm = (a[2] + b[2]) / 2
            dist = rt + max(0.0, -zm) * tan_h + stock
            q = shapely.points((a[0] + b[0]) / 2 + nx * dist, (a[1] + b[1]) / 2 + ny * dist)
            i = int(tree.nearest(q))
            votes[i] = votes.get(i, 0) + 1
            break
    if votes:
        return max(votes, key=votes.get)
    x, y = g.he[cycle[0]][2][0][:2]
    return int(tree.nearest(shapely.points(x, y)))


def old_owners(g, cycles, tree, wall_right, rt, tan_h, stock):
    return [old_owner(g, c, tree, wall_right, rt, tan_h, stock) for c in cycles]


def old_frames_of(reg):
    polys = [p for p in getattr(reg, 'geoms', [reg]) if p.geom_type == 'Polygon' and not p.is_empty]
    shells = [Polygon(p.exterior) for p in polys]
    out = [p for i, p in enumerate(polys) if p.interiors and not any(
        j != i and shells[j].contains(p.representative_point()) for j in range(len(polys)))]
    return unary_union(out) if out else None


# --- dessins d'essai -----------------------------------------------------------------------------------------------------------------

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
                   poly([(5, 5), (25, 5), (25, 9), (9, 9), (9, 30), (5, 30)]),                 # un L étroit
                   poly([(30, 5), (55, 5), (42, 35)]),                                         # un triangle aigu
                   square(8, 32, 28, 37),
                   square(10, 33, 26, 36),                                                     # une île dans le trou
                   poly([(33, 10), (37, 10), (37.6, 25), (33.4, 25)]))


def cone(tip=0.2, angle=30.0):
    return M.CamTool(name='k', kind='conique', diameter=6.0, tip=tip, angle=angle)


def fraise(d):
    return M.CamTool(name=f'c{d}', kind='fraise', diameter=d)


def finition(doc, **kw):
    k = cone()
    setup = M.CamSetup(tools=[k])
    op = M.Operation(kind='vcarve', tool_id=k.id, depth=1.0, climb=True)      # la Finition de TypeEdit : passes, contours seuls
    op.vcarve_step = 0.5
    op.vcarve_edges_only = True
    op.finish_rule = 877
    for key, v in kw.items():
        setattr(op, key, v)
    setup.operations = [op]
    return S.compute(doc, setup, op, (0.0, 0.0))


def gamme_cone(doc):
    c, k = fraise(2.0), cone(0.2)
    setup = M.CamSetup(tools=[c, k])
    ops = gamme.build(setup, [gamme.Step(c.id, 'contournage', stepover=1.0, step_down=0.5), gamme.Step(k.id, finish3d=True, stepover=0.2,
                                                                                                       step_down=0.5)],
                      1.5, climb=True, ramp=True, ramp_angle=10.0, pass_order='global', skip_frame=True, stock=0.1)
    setup.operations = list(ops)
    return S.compute(doc, setup, ops[1], (0.0, 0.0))


def moves(tp):
    return [(m.kind, round(m.x, 9), round(m.y, 9), round(m.z, 9)) for m in tp.moves]


# --- essais --------------------------------------------------------------------------------------------------------------------------

class Graphe(unittest.TestCase):

    def ring(self, z=-0.5):
        return [(0, 0, z), (10, 0, z), (10, 0, z), (10, 5, z), (10.00004, 5.00003, z), (0, 5, z), (0, 0, z)]

    def test_chain_builds_the_graph_edge_does(self):
        for wall_right in (True, False):
            a, b = F._Graph(wall_right, 0.06), F._Graph(wall_right, 0.06)
            for g, add in ((a, lambda g, p, k: g.chain(p, k)), (b, old_edges)):
                add(g, self.ring(), 'anneau')
                add(g, [(10, 5, -0.5), (12, 8, -0.5), (0, 5, -0.5)], 'anneau')            # partage des nœuds avec le premier
                add(g, [(3, 3, -0.2), (3, 3, -0.2)], 'anneau')                            # rien qu'un point : aucune arête
            self.assertEqual(a.pos, b.pos)
            self.assertEqual(a.he, b.he)
            self.assertEqual(a.out, b.out)
            self.assertEqual([[a.he[h][:2] for h in c] for c in a.faces()], [[b.he[h][:2] for h in c] for c in b.faces()])

    def test_a_point_within_the_snap_joins_the_existing_node(self):
        g = F._Graph(True, 0.06)
        g.chain([(0, 0, 0), (1, 0, 0)], 'anneau')
        g.chain([(1.00005, 0, 0), (2, 0, 0)], 'anneau')
        self.assertEqual(len(g.pos), 3)


class Contours(unittest.TestCase):

    def level(self, doc, z, wall_right=True):
        k = cone()
        op = M.Operation(kind='finition', tool_id=k.id, depth=1.0, climb=wall_right)
        geoms = [g for it in S.source_items(doc, op) if (g := S.item_geometry(it))]
        reg = S.region(geoms, 0.01)
        tan_h = math.tan(math.radians(15))
        qs = S._quad_segs(0.2, 0.01)
        g, _short = F._level_graph(reg, z, 0.1, tan_h, op, 0.05, qs, wall_right)
        closed = [pts for pts, c in S.polylines(geoms, 0.01) if c and len(pts) >= 4]
        tree = shapely.STRtree([LineString([p[:2] for p in pts]) for pts in closed])
        return g, tree, tan_h

    def test_same_owner_for_every_tour(self):
        for z, wall_right, stock in ((-0.3, True, 0.0), (-1.0, True, 0.1), (-0.6, False, 0.0)):
            g, tree, tan_h = self.level(letters(), z, wall_right)
            cycles = g.faces()
            self.assertGreater(len(cycles), 5)
            self.assertEqual(F._owners(g, cycles, tree, wall_right, 0.1, tan_h, stock), old_owners(g, cycles, tree, wall_right, 0.1, tan_h,
                                                                                                    stock))

    def test_a_tour_of_angle_pulls_only_takes_the_nearest(self):
        g, tree, tan_h = self.level(letters(), -0.5)
        cycles = g.faces()
        lone = [[h for h in cycles[0] if g.he[h][4] == 'tire'] or cycles[0][:1]]
        for c in lone:
            for h in c:
                g.he[h][4] = 'tire'
        self.assertEqual(F._owners(g, lone, tree, True, 0.1, tan_h, 0.0), old_owners(g, lone, tree, True, 0.1, tan_h, 0.0))

    def test_no_tour_no_request(self):
        g, tree, tan_h = self.level(letters(), -0.5)
        with mock.patch.object(type(tree), 'nearest', side_effect=AssertionError('demandé')):
            self.assertEqual(F._owners(g, [], tree, True, 0.1, tan_h, 0.0), [])


class Cadres(unittest.TestCase):

    def region(self, n=12):
        frame = box(0, 0, 200, 100)
        holes, islands = [], []
        for i in range(n):
            x = 5 + i * 16
            holes.append(box(x, 10, x + 12, 90))
            islands.append(box(x + 2, 20, x + 10, 80).difference(box(x + 4, 30, x + 8, 70)))   # une île à trou dans chaque trou
        other = box(300, 0, 340, 40).difference(box(310, 10, 330, 30))                          # un second cadre, à part
        lone = box(400, 0, 410, 10)                                                             # une forme sans trou
        return unary_union([frame.difference(unary_union(holes)), *islands, other, lone])

    def test_same_frames(self):
        for reg in (self.region(), self.region(1), box(0, 0, 5, 5), MultiPolygon()):
            want, got = old_frames_of(reg), S.frames_of(reg)
            if want is None:
                self.assertIsNone(got)
            else:
                self.assertTrue(got.equals(want))
                self.assertEqual(shapely.to_wkb(got), shapely.to_wkb(want))

    def test_a_shape_inside_another_shape_s_hole_is_not_a_frame(self):
        frames = S.frames_of(self.region(3))
        self.assertEqual(len(getattr(frames, 'geoms', [frames])), 2)                            # le grand cadre et le second

    def test_one_point_per_holed_shape(self):
        reg = self.region(40)
        holed = sum(1 for p in reg.geoms if p.interiors)
        calls = []
        real = Polygon.representative_point

        def count(self):
            calls.append(1)
            return real(self)
        with mock.patch.object(Polygon, 'representative_point', count):
            S.frames_of(reg)
        self.assertEqual(len(calls), holed)                                                     # avant : une fois par paire de formes


class Parcours(unittest.TestCase):
    """Le parcours calculé avec les nouvelles fonctions, puis avec les anciennes à leur place : les mêmes coups."""

    def both(self, run):
        new = moves(run())
        with mock.patch.object(F, '_owners', old_owners), \
                mock.patch.object(F._Graph, 'chain', lambda g, p, k, radius=1e-4: old_edges(g, p, k)), \
                mock.patch.object(S, 'frames_of', old_frames_of):
            old = moves(run())
        return new, old

    def test_finition_by_passes(self):
        new, old = self.both(lambda: finition(letters()))
        self.assertGreater(len(new), 100)
        self.assertEqual(new, old)

    def test_finition_3d_only_other_side(self):
        new, old = self.both(lambda: finition(letters(), climb=False, finish_3d_only=True))
        self.assertGreater(len(new), 20)
        self.assertEqual(new, old)

    def test_gamme_cone_frame_skipped(self):
        new, old = self.both(lambda: gamme_cone(letters()))
        self.assertGreater(len(new), 100)
        self.assertEqual(new, old)


if __name__ == '__main__':
    unittest.main()
