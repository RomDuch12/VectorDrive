"""Round 322 : projection locale (TypeEdit) — le dessin posé le long d'une
courbe guide sur la surface d'une pièce, longueurs mesurées sur la surface,
profondeur reprise à la verticale."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.cam import model as M, strategies as S, wrap as WR
from vectordrive.cam.model import Move
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def plane(slope=0.0):
    # plan z = slope·x sur [0, 100] × [0, 40]
    a, b, c, d = (0, 0, 0), (100, 0, 100 * slope), (100, 40, 100 * slope), (0, 40, 0)
    return np.array([(a, b, c), (a, c, d)], float)


def square(z=-0.5):
    pts = [(0, 0), (10, 0), (10, 2), (0, 2), (0, 0)]
    return [Move('rapid', 0, 0, 5)] + [Move('feed', x, y, z) for x, y in pts]


class TestLocal(unittest.TestCase):
    def test_flat(self):
        smap = WR.SurfaceMap(plane(), (0, 0, 100, 40), 0.1)
        out, w = WR.local_project(square(), smap, [(10, 5), (60, 5)], 2.0, 0.5)
        cut = [(round(m.x, 4), round(m.y, 4), round(m.z, 4)) for m in out if m.z < 0]
        self.assertIn((20.0, 5.0, -0.5), cut)
        self.assertIn((20.0, 7.0, -0.5), cut)

    def test_slope_and_curve(self):
        smap = WR.SurfaceMap(plane(0.5), (0, 0, 100, 40), 0.05)
        out, w = WR.local_project(square(), smap, [(10, 5), (60, 5)], 99.0, 0.5)
        far = max(m.x for m in out)
        self.assertAlmostEqual(far, 10 + 10 / math.sqrt(1.25), 1)      # 10 mm mesurés sur la pente
        top = smap.top
        m = next(m for m in out if abs(m.x - far) < 1e-6)
        self.assertAlmostEqual(m.z, 0.5 * m.x - top - 0.5, 1)           # profondeur sous la surface
        smap = WR.SurfaceMap(plane(), (0, 0, 100, 40), 0.1)
        arc = [(30 + 20 * math.cos(t), 5 + 20 * math.sin(t)) for t in np.linspace(math.pi, 0, 60)]
        out, w = WR.local_project(square(), smap, arc, 2.0, 0.5)
        self.assertTrue(out)
        for m in out:
            if m.z < 0 and abs(m.y - 5) > 1e-6:
                self.assertGreaterEqual(math.dist((m.x, m.y), (30, 5)), 20 - 0.05)   # sens horaire : la gauche est dehors

    def test_refusals(self):
        smap = WR.SurfaceMap(plane(), (0, 0, 100, 40), 0.1)
        self.assertEqual(WR.local_project(square(), smap, [(10, 5), (15, 5)], 2.0, 0.5)[0], [])  # guide trop courte
        self.assertEqual(WR.local_project(square(), smap, [(10, 5), (200, 5)], 2.0, 0.5)[0], [])  # hors pièce
        self.assertTrue(WR.local_project(square(), smap, [], 2.0, 0.5)[1])

    def test_operation(self):
        from vectordrive.io.stl_write import write_stl
        path = os.path.join(tempfile.mkdtemp(), 'plan.stl')
        write_stl(path, plane())
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.polyline([(0, 0), (10, 0)])]), tool=1))
        setup = M.setup_of(d)
        t = M.CamTool(name='V', kind='conique', diameter=3, angle=90)
        setup.tools = [t]
        op = M.Operation(kind='gravure', depth=0.2, tool_id=t.id, wrap='locale', wrap_model=path,
                         wrap_guide=[[20, 10], [80, 10]])
        tp = S.compute(d, setup, op)
        cut = [m for m in tp.moves if m.z < 0]
        self.assertTrue(cut, tp.warnings)
        self.assertAlmostEqual(min(m.x for m in cut), 20, 3)
        self.assertAlmostEqual(cut[0].y, 10, 3)


if __name__ == '__main__':
    unittest.main()
