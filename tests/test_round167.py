"""Round 167 : épaisseur de trait au laser par passages parallèles (TauDrive)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def feed_length(tp):
    pos, total = None, 0.0
    for m in tp.moves:
        if m.kind == 'feed' and pos is not None:
            total += math.hypot(m.x - pos[0], m.y - pos[1])
        pos = (m.x, m.y)
    return total


class TestThicken(unittest.TestCase):
    def test_passes_both_sides(self):
        out = S.thicken([([(0, 0), (10, 0)], False)], 0.4, 0.1)
        ys = sorted(round(pts[0][1], 6) for pts, _c in out)
        self.assertEqual(ys, [-0.2, -0.1, 0.0, 0.1, 0.2])
        self.assertEqual(S.thicken([([(0, 0), (10, 0)], False)], 0.0, 0.1), [([(0, 0), (10, 0)], False)])

    def test_no_double_energy(self):
        two = [([(0, 0), (10, 0)], False), ([(0, 0.25), (10, 0.25)], False)]        # plus proches que l'épaisseur
        out = S.thicken(two, 0.6, 0.1)
        from shapely.geometry import LineString
        lines = [LineString(pts) for pts, _c in out]
        for i, a in enumerate(lines):
            for b in lines[i + 1:]:
                inter = a.buffer(0.04).intersection(b)
                self.assertLess(inter.length, 0.5, (a, b))                       # pas de passage superposé
        alone = len(S.thicken([two[0]], 0.6, 0.1)) * 2
        self.assertLess(len(out), alone)                                         # des passages retirés

    def test_closed_contour(self):
        out = S.thicken([(geom.rect(0, 0, 10, 10).flatten(0.01), True)], 0.2, 0.1)
        self.assertEqual(len(out), 3)
        self.assertTrue(all(closed for _pts, closed in out))


class TestStrategy(unittest.TestCase):
    def test_laser_op(self):
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.polyline([(0, 0), (20, 0)])])))
        s = model.CamSetup()
        t = model.CamTool(name='Laser', kind='laser', diameter=0.05, power=50, frequency=20, feed=1000)
        s.tools = [t]
        op = model.Operation(kind='laser', tool_id=t.id)
        s.operations = [op]
        one = feed_length(S.compute(d, s, op))
        op.line_width, op.line_step = 0.3, 0.05
        self.assertAlmostEqual(feed_length(S.compute(d, s, op)), 7 * one, delta=0.5)
        op.line_step = 0.0                                                        # 80 % de 0,05 = 0,04
        self.assertAlmostEqual(feed_length(S.compute(d, s, op)), 7 * one, delta=0.5)


if __name__ == '__main__':
    unittest.main()
