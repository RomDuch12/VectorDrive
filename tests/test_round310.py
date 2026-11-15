"""Round 310 : taraudage / filetage (TypeEdit) — filetage extérieur, angle
de départ, entrée et sortie en arc tangent ou radiales."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(r_circle, **kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.circle((10, 10), r_circle)]), tool=0))
    s = model.CamSetup()
    tool = model.CamTool(name='Fraise à fileter', diameter=2.5)
    s.tools = [tool]
    op = model.Operation(kind='taraudage', tool_id=tool.id, depth=3, thread='M4', climb=True, **kw)
    s.operations = [op]
    return S.compute(d, s, op)


def feeds(tp):
    return [m for m in tp.moves if m.kind == 'feed']


class TestThreadLeads(unittest.TestCase):
    def test_start_angle(self):
        tp = run(1.65, thread_start_angle=90)
        first = next(m for m in feeds(tp) if math.hypot(m.x - 10, m.y - 10) > 0.7)
        self.assertAlmostEqual(first.x, 10, 6)
        self.assertAlmostEqual(first.y, 10.75, 6)                      # r = 2 − 1,25 à 90°

    def test_internal_arc(self):
        tp = run(1.65, thread_lead='arc')
        pts = [(m.x, m.y) for m in feeds(tp)]
        self.assertTrue(all(math.hypot(x - 10, y - 10) <= 0.75 + 1e-6 for x, y in pts))   # jamais dans le filet
        arc = [p for p in pts if 0.05 < math.hypot(p[0] - 10, p[1] - 10) < 0.74]
        self.assertGreater(len(arc), 10)                                # entrée et sortie arrondies

    def test_external(self):
        tp = run(2.0, thread_external=True, thread_lead_dist=1.5)
        pts = [(m.x, m.y) for m in feeds(tp)]
        r = 2.0 + 1.25
        self.assertTrue(all(math.hypot(x - 10, y - 10) >= r - 1e-6 for x, y in pts))      # toujours dehors
        self.assertAlmostEqual(min(math.hypot(x - 10, y - 10) for x, y in pts), r, 6)
        self.assertFalse(any('avant-trou' in w for w in tp.warnings))
        tp = run(2.0, thread_external=True, thread_lead='arc', thread_lead_dist=1.5)
        pts = [(m.x, m.y) for m in feeds(tp)]
        self.assertTrue(all(math.hypot(x - 10, y - 10) >= r - 1e-6 for x, y in pts))

    def test_tangent_arc(self):
        pts = S.tangent_arc((1, 0), (0, 1), (0, 0), 90, True)          # arrive en (1, 0) en montant
        self.assertAlmostEqual(pts[0][0], 0, 6)
        self.assertAlmostEqual(pts[0][1], -1, 6)
        pts = S.tangent_arc((1, 0), (0, 1), (0, 0), 90, False)         # part de (1, 0) en montant
        self.assertAlmostEqual(pts[-1][1], 1, 6)


if __name__ == '__main__':
    unittest.main()
