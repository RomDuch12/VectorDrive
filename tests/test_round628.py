"""Round 628 : arcs G2 / G3 dans les programmes — les suites de segments d'un
parcours (avances à Z constant) qui suivent un cercle à la tolérance près
deviennent des arcs (cam.arcfit), pour les post-processeurs qui écrivent des
arcs ; écart garanti, plongées / rampes / rapides inchangés."""
import math
import os
import random
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import shapely
from shapely.geometry import LineString

from vectordrive.cam import arcfit, model, post, strategies
from vectordrive.cam.model import Move, Toolpath, arc_points
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def trace(moves):
    pts, prev = [], None
    for m in moves:
        if prev is not None and m.kind != 'rapid':
            if not pts or pts[-1] != prev:
                pts.append(prev)
            pts.extend(arc_points(prev, m, 0.0005) if m.is_arc else [(m.x, m.y, m.z)])
        prev = (m.x, m.y, m.z)
    return LineString([p[:2] for p in pts])


def circle_moves(cx, cy, r, n, z=-1.0, start=0.0, sweep=2 * math.pi):
    out = [Move('rapid', cx + r * math.cos(start), cy + r * math.sin(start), 5.0),
           Move('plunge', cx + r * math.cos(start), cy + r * math.sin(start), z)]
    for k in range(1, n + 1):
        a = start + sweep * k / n
        out.append(Move('feed', cx + r * math.cos(a), cy + r * math.sin(a), z))
    return out


class TestFit(unittest.TestCase):
    def test_circle_becomes_arcs_within_tolerance(self):
        moves = circle_moves(10, 5, 6, 120)
        fitted = arcfit.fit_moves(moves, 0.01)
        arcs = [m for m in fitted if m.is_arc]
        self.assertTrue(1 <= len(arcs) <= 3, len(arcs))                   # moins d'un tour par arc
        self.assertTrue(all(m.kind == 'arc_ccw' for m in arcs))
        self.assertTrue(all(abs(math.hypot(m.cx - 10, m.cy - 5) < 0.01) for m in arcs))
        self.assertEqual(fitted[:2], moves[:2])                            # rapide et plongée gardés
        self.assertEqual((fitted[-1].x, fitted[-1].y), (moves[-1].x, moves[-1].y))
        self.assertLessEqual(shapely.hausdorff_distance(trace(moves), trace(fitted), densify=0.05), 0.0101)
        cw = arcfit.fit_moves(circle_moves(0, 0, 4, 60, sweep=-math.pi), 0.01)
        self.assertTrue(all(m.kind == 'arc_cw' for m in cw if m.is_arc) and any(m.is_arc for m in cw))

    def test_guarantee_on_random_polylines(self):
        rnd = random.Random(7)
        for _ in range(60):
            moves = [Move('rapid', 0, 0, 2), Move('plunge', 0, 0, -0.5)]
            x = y = 0.0
            heading = rnd.uniform(0, 2 * math.pi)
            for _k in range(rnd.randint(5, 80)):                           # virages doux, droites, cassures
                heading += rnd.choice([0.0, rnd.uniform(-0.3, 0.3), rnd.uniform(-2, 2)])
                step = rnd.uniform(0.05, 2.0)
                x, y = x + step * math.cos(heading), y + step * math.sin(heading)
                moves.append(Move('feed', x, y, -0.5))
            tol = rnd.choice([0.005, 0.01, 0.02])
            fitted = arcfit.fit_moves(moves, tol)
            hd = shapely.hausdorff_distance(trace(moves), trace(fitted), densify=0.02)
            self.assertLessEqual(hd, tol + 2e-4)
            self.assertEqual((fitted[-1].x, fitted[-1].y), (moves[-1].x, moves[-1].y))

    def test_untouched(self):
        line = [Move('rapid', 0, 0, 1), Move('plunge', 0, 0, -1)] + [Move('feed', k, 0, -1) for k in range(1, 9)]
        self.assertEqual(arcfit.fit_moves(line, 0.01), line)               # droite : segments
        ramp = circle_moves(0, 0, 5, 40)
        ramp = ramp[:2] + [Move('feed', m.x, m.y, -1 - 0.01 * k) for k, m in enumerate(ramp[2:])]
        self.assertEqual(arcfit.fit_moves(ramp, 0.01), ramp)                # Z qui varie : hélice gardée
        tps = [Toolpath(op_id='o', tool_id='t', moves=circle_moves(0, 0, 5, 40))]
        self.assertIs(arcfit.fit_toolpaths(tps, 0)[0], tps[0])


class TestPost(unittest.TestCase):
    def setUp(self):
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 40, 20, 5)]), tool=0))
        s = model.CamSetup()
        t = model.CamTool(name='F2', diameter=2, number=1, cut_length=10, step_down=1.0)
        s.tools = [t]
        s.operations = [model.Operation(kind='contour', tool_id=t.id, sources=[0], depth=1.0)]
        self.s, self.tps = s, strategies.compute_all(d, s)

    def run_post(self, arcs, machine=None):
        from vectordrive.plugins import REGISTRY
        seen = {}

        def write(toolpaths, setup, *, title='', machine=None, stem='', box_mm=None):
            seen['moves'] = [m for tp in toolpaths for m in tp.moves]
            return post.PostResult('G0', [], '.nc')
        if arcs:
            write.arcs = True
        REGISTRY.posts['essai628'] = ('Essai', write)
        try:
            post.run('essai628', self.tps, self.s, machine=machine)
        finally:
            REGISTRY.posts.pop('essai628', None)
        return seen['moves']

    def test_only_posts_that_write_arcs(self):
        self.assertTrue(any(m.is_arc for m in self.run_post(True)))       # coins arrondis : arcs
        self.assertFalse(any(m.is_arc for m in self.run_post(False)))     # post sans arcs : segments
        self.assertFalse(any(m.is_arc for m in self.tps[0].moves))         # le parcours affiché : inchangé
        self.assertFalse(any(m.is_arc for m in self.run_post(True, machine={'Mset40': '1'})))   # axe rotatif
        self.s.arc_fit = 0.0
        self.assertFalse(any(m.is_arc for m in self.run_post(True)))       # réglé à 0 : segments

    def test_setting_saved(self):
        self.assertEqual(model.CamSetup().arc_fit, 0.01)
        s = model.CamSetup(arc_fit=0.005)
        self.assertEqual(model.CamSetup.from_dict(s.to_dict()).arc_fit, 0.005)
        self.assertEqual(model.CamSetup.from_dict({}).arc_fit, 0.01)


if __name__ == '__main__':
    unittest.main()
