"""Round 487 : Finition 2,5D sur plusieurs formes séparées."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import box

from vectordrive.cam import advanced as A, model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


class TestMultiPart(unittest.TestCase):
    def test_surface(self):
        cone = model.CamTool(kind='conique', diameter=3.175, angle=90.0, tip=0.0)
        reg = box(0, 0, 10, 10).union(box(20, 0, 30, 10))
        H = A.engraving_surface(reg, cone, 2.0, -1.0, -1.0, 321, 121, 0.1)
        self.assertAlmostEqual(H[60, 15], -0.5, places=6)                   # premier morceau
        self.assertAlmostEqual(H[60, 215], -0.5, places=6)                  # second morceau

    def test_compute(self):
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.rect(10, 10, 30, 20), geom.rect(18, 15, 8, 10)])))
        d.add(Shape(path=geom.Path([geom.circle((60, 20), 9)])))
        s = model.CamSetup()
        cone = model.CamTool(kind='conique', diameter=6.0, angle=60.0, tip=0.1)
        ball = model.CamTool(kind='boule', diameter=1.0, step_down=0.3, stepover=0.3)
        s.tools = [cone, ball]
        op = model.Operation(kind='finition25d', tool_id=ball.id, ref_tool_id=cone.id, depth=1.0, resolution=0.1)
        s.operations = [op]
        tp = S.compute(d, s, op)
        self.assertTrue(tp.moves)
        self.assertAlmostEqual(min(m.z for m in tp.moves if m.kind != 'rapid'), -1.0, places=2)
        cuts = [m for m in tp.moves if m.kind != 'rapid']
        across = [min(a.z, b.z) for a, b in zip(cuts, cuts[1:])            # segments qui passent entre les formes
                  if abs(a.y - b.y) < 1e-9 and 12 < a.y < 28 and min(a.x, b.x) < 45 < max(a.x, b.x)]
        self.assertTrue(across and min(across) >= 0.4, across[:5])        # au-dessus de la pièce


if __name__ == '__main__':
    unittest.main()
