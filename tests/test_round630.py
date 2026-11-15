"""Round 630 : corrections de la relecture des rounds 623 à 627 — positions des
palpages décalées avec l'origine (zéro du programme) ; tore qui fait le tour
de l'axe maillé du bon côté du tube ; centres absolus des arcs G18 / G19 ;
liaison au fond de la gravure 2,5D à la profondeur sûre."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from shapely.geometry import Point, Polygon

from vectordrive.cam import model, ncread, post, strategies
from vectordrive.cam.model import Move, Toolpath
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io.neostep import step3d as ST


class TestProbeOrigin(unittest.TestCase):
    def test_positions_follow_origin(self):
        tp = Toolpath(op_id='i', tool_id='', name='i')
        tp.cycles = [{'kind': 'instruction', 'name': 'palpage_z', 'params': {'x': 30.0, 'y': 12.0}},
                     {'kind': 'instruction', 'name': 'mesure_orientation',
                      'params': {'x1': 5.0, 'y1': 5.0, 'x2': 45.0, 'y2': 5.0, 'd1': 4.0}},
                     {'kind': 'instruction', 'name': 'decalage_origine', 'params': {'x': 1.0, 'y': 2.0, 'z': -0.5}},
                     {'kind': 'instruction', 'name': 'message', 'params': {'message': 'x'}}]
        out = post.shifted([tp], (25.0, 10.0))[0].cycles
        self.assertEqual((out[0]['params']['x'], out[0]['params']['y']), (5.0, 2.0))         # palpage : suit
        p = out[1]['params']
        self.assertEqual((p['x1'], p['y1'], p['x2'], p['y2'], p['d1']), (-20.0, -5.0, 20.0, -5.0, 4.0))
        self.assertEqual(out[2]['params'], {'x': 1.0, 'y': 2.0, 'z': -0.5})                   # incrément : non
        self.assertIs(out[3], tp.cycles[3])
        self.assertEqual(tp.cycles[0]['params'], {'x': 30.0, 'y': 12.0})                     # original intact


def ring(par, a, b, v, rev):
    th = np.linspace(0, 2 * math.pi, 64, endpoint=False)
    th = th[::-1] if rev else th
    rho = a + b * math.cos(v)
    return par.c + np.outer(rho * np.cos(th), par.R[:, 0]) + np.outer(rho * np.sin(th), par.R[:, 1]) + \
        np.outer(np.full(64, b * math.sin(v)), par.R[:, 2])


class TestTorusSide(unittest.TestCase):
    def area(self, v0, v1):
        a, b = 20.0, 3.0
        par = ST._Tore(np.eye(3), np.zeros(3), a, b, 0.01)
        t = ST._trianguler(par, [(ring(par, a, b, v0, False), True), (ring(par, a, b, v1, True), False)], 0.01)
        got = 0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum()
        span = (v1 - v0) % (2 * math.pi)
        want = 2 * math.pi * b * (a * span + b * (math.sin(v0 + span) - math.sin(v0)))
        return got, want

    def test_side_from_orientation(self):
        for v0, v1 in ((-math.pi / 2, math.pi / 2), (math.radians(-100), math.radians(100)),
                       (math.radians(-60), math.radians(60)), (math.radians(100), math.radians(-100))):
            got, want = self.area(v0, v1)                # la face va de v0 à v1 dans le sens des v croissants
            self.assertAlmostEqual(got, want, delta=0.02 * want)


class TestIsoPlanes(unittest.TestCase):
    def test_g18_absolute_centre(self):
        txt = 'G90.1\nG0 X10. Y0. Z0.\nG18\nG1 X10. Y0. Z0. F100\nG2 X0. Y0. Z10. I0. K0.\n'
        tp = ncread.read(txt, 'p.nc')
        pts = [(m.x, m.z) for m in tp.moves if m.kind == 'feed']
        self.assertTrue(pts)
        self.assertTrue(all(abs(math.hypot(x, z) - 10) < 0.05 for x, z in pts))   # centre (0, 0) absolu


class TestVcarveLink(unittest.TestCase):
    def test_zigzag_channel_no_overcut(self):
        pts = [(0, 0), (2, 0.2), (4, 0), (6, 0.2), (8, 0), (8, 0.6), (6, 0.4), (4, 0.6), (2, 0.4), (0, 0.6)]
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.polyline(pts, closed=True)]), tool=0))
        s = model.CamSetup()
        t = model.CamTool(name='V60', kind='conique', diameter=3.175, angle=60, tip=0.0, number=1)
        s.tools = [t]
        s.operations = [model.Operation(kind='vcarve', tool_id=t.id, sources=[0], depth=0.5, resolution=0.05)]
        tp = strategies.compute_all(d, s)[0]
        reg = Polygon(pts)
        bnd = reg.boundary
        tan = math.tan(math.radians(30))
        worst, prev = 0.0, None
        for m in tp.moves:
            if prev is not None and m.kind != 'rapid':
                n = max(1, int(math.dist((prev.x, prev.y), (m.x, m.y)) / 0.01))
                for k in range(n + 1):
                    x, y = prev.x + (m.x - prev.x) * k / n, prev.y + (m.y - prev.y) * k / n
                    z = prev.z + (m.z - prev.z) * k / n
                    if z < -1e-6:
                        worst = max(worst, (-z) * tan - bnd.distance(Point(x, y)))
            prev = m
        self.assertLess(worst, 0.01)                     # 0,050 avant (un pas de la gravure)


if __name__ == '__main__':
    unittest.main()
