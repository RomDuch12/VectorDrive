"""Round 265 : FAO — découpe sur ligne commune (pièces voisines écartées
d'un diamètre d'outil : chaque pièce détourée, le bord commun coupé une
fois) ; avertissement quand des pièces trop proches sont détourées
ensemble."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape

D = 3.0


def plate(n=3):
    d = Document()
    d.plate = None
    for i in range(n):
        d.add(Shape(path=geom.Path([geom.rect(i * (10 + D), 0, 10, 10)]), tool=1))
    setup = M.setup_of(d)
    tool = M.CamTool(name='F3', diameter=D)
    setup.tools = [tool]
    return d, setup, tool


def run(common: bool):
    d, setup, tool = plate()
    op = M.Operation(name='d', kind='contour', side='exterieur', depth=1.0, step_down=1.0, tool_id=tool.id,
                     common_line=common)
    tp = S.compute(d, setup, op)
    feed = sum(math.dist((a.x, a.y), (b.x, b.y)) for a, b in zip(tp.moves, tp.moves[1:]) if b.kind == 'feed')
    return tp, feed


class TestCommonLine(unittest.TestCase):
    def test_parts_cut_once(self):
        tp, feed = run(True)
        ring = 4 * 10 + math.pi * D                                            # tour d'une pièce décalée
        self.assertAlmostEqual(feed, 3 * ring - 2 * 10, delta=1.0)             # deux bords communs en moins
        self.assertTrue(any('ligne commune' in w for w in tp.warnings))
        xs = {round(m.x, 3) for m in tp.moves if m.kind == 'feed'}
        self.assertIn(11.5, xs)                                                 # on coupe bien entre les pièces

    def test_default_warns(self):
        tp, feed = run(False)
        self.assertLess(feed, 3 * (4 * 10 + math.pi * D) - 25)                  # détourées ensemble
        self.assertTrue(any('trop proche' in w for w in tp.warnings))

    def test_single_part_unchanged(self):
        d, setup, tool = plate(1)
        a = S.compute(d, setup, M.Operation(name='a', kind='contour', side='exterieur', depth=1, step_down=1,
                                            tool_id=tool.id))
        b = S.compute(d, setup, M.Operation(name='b', kind='contour', side='exterieur', depth=1, step_down=1,
                                            tool_id=tool.id, common_line=True))
        self.assertEqual(len([m for m in a.moves if m.kind == 'feed']), len([m for m in b.moves if m.kind == 'feed']))
        self.assertFalse(any('ligne commune' in w for w in b.warnings))


if __name__ == '__main__':
    unittest.main()
