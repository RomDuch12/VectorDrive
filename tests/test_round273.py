"""Round 273 : détourage — les trous d'une pièce coupés avant son tour (la
pièce reste tenue) ; option « petites pièces d'abord »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def plunges(**kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 40, 20), geom.circle((5, 10), 3), geom.circle((35, 10), 3)]), tool=1))
    d.add(Shape(path=geom.Path([geom.rect(50, 0, 5, 5)]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F2', diameter=2)
    setup.tools = [t]
    tp = S.compute(d, setup, M.Operation(kind='contour', side='exterieur', depth=1, step_down=1, tool_id=t.id, **kw),
                   here=(0, 0))
    return [(m.x, m.y) for m in tp.moves if m.kind == 'plunge']


def in_hole(p):
    return min((p[0] - 5) ** 2, (p[0] - 35) ** 2) + (p[1] - 10) ** 2 < 9.01


class TestOrder(unittest.TestCase):
    def test_holes_before_outline(self):
        pl = plunges()
        self.assertTrue(in_hole(pl[0]) and in_hole(pl[1]))                        # les deux trous d'abord
        self.assertFalse(in_hole(pl[2]))
        self.assertLess(pl[2][0], 45)                                              # puis le tour de la plaque
        self.assertGreater(pl[3][0], 45)                                           # la petite pièce ensuite

    def test_small_first(self):
        pl = plunges(small_first=True)
        self.assertGreater(pl[0][0], 45)                                           # la petite pièce en premier
        self.assertTrue(in_hole(pl[1]) and in_hole(pl[2]))
        self.assertEqual(len(pl), 4)


if __name__ == '__main__':
    unittest.main()
