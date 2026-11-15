"""Round 206 : projection parallèle des parcours sur une pièce (maillage)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.cam import model, strategies as S, wrap as WR
from vectordrive.cam.model import Move
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def ramp():
    """Plan incliné de 0 à 50 mm en X, Z = 10 − 0,1 x (deux triangles)."""
    p = [(0, -20, 10.0), (50, -20, 5.0), (50, 20, 5.0), (0, 20, 10.0)]
    return np.array([[p[0], p[1], p[2]], [p[0], p[2], p[3]]])


class TestProject(unittest.TestCase):
    def test_surface_map(self):
        smap = WR.SurfaceMap(ramp(), (5, -10, 45, 10), 0.1)
        self.assertAlmostEqual(smap.z(10, 0), -1.0, places=3)                     # 10 − 0,1·10 − 10
        self.assertAlmostEqual(smap.z(40, 5), -4.0, places=3)
        self.assertTrue(math.isnan(smap.z(80, 0)))

    def test_project_moves(self):
        smap = WR.SurfaceMap(ramp(), (5, -10, 45, 10), 0.1)
        moves = [Move('rapid', 10, 0, 5.0), Move('rapid', 10, 0, 1.0), Move('plunge', 10, 0, -0.2),
                 Move('feed', 40, 0, -0.2), Move('rapid', 40, 0, 5.0)]
        out, warn = WR.project(moves, smap, 5.0, 0.5)
        self.assertEqual(warn, [])
        feeds = [m for m in out if m.kind == 'feed']
        self.assertGreater(len(feeds), 50)                                         # découpé au pas
        for m in feeds:
            self.assertAlmostEqual(m.z, -0.1 * m.x - 0.2, places=3)                # 0,2 sous la surface
        self.assertEqual(out[0].z, 5.0)                                            # dégagement gardé
        bad = moves[:3] + [Move('feed', 90, 0, -0.2)]
        self.assertEqual(WR.project(bad, smap, 5.0, 0.5)[0], [])                   # hors pièce : refus

    def test_compute_refusals(self):
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.rect(10, -5, 20, 10)]), tool=0))
        s = model.CamSetup()
        t = model.CamTool(name='V', kind='conique', diameter=2.0, angle=30.0, tip=0.1, step_down=1.0)
        s.tools = [t]
        op = model.Operation(kind='gravure', tool_id=t.id, depth=0.2, wrap='surface')
        s.operations = [op]
        tp = S.compute(d, s, op)
        self.assertEqual(tp.moves, [])
        self.assertTrue(any('STEP' in w for w in tp.warnings))
        op.wrap_model = os.path.join(tempfile.mkdtemp(), 'absent.stp')
        tp = S.compute(d, s, op)
        self.assertEqual(tp.moves, [])
        self.assertTrue(any('illisible' in w for w in tp.warnings))


if __name__ == '__main__':
    unittest.main()
