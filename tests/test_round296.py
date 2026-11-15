"""Round 296 : couteau flottant à boucles (TypeEdit : Vinyle, onglet Avancé)
— boucle tangente hors matière à chaque angle vif entre les angles latéraux
mini et maxi, côtés trop courts ignorés, boucles qui entrent dans la matière
ou touchent le dessin refusées."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(contours, **kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path(contours), tool=1))
    setup = M.setup_of(d)
    k = M.CamTool(name='K', kind='couteau', diameter=1, tip=0.25)
    setup.tools = [k]
    return S.compute(d, setup, M.Operation(kind='vinyle', depth=0.2, tool_id=k.id, knife_mode='boucles', **kw))


class TestLoops(unittest.TestCase):
    def test_corner_loops(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        path, n = S.corner_loops(sq, True, 30, 165, 2.0, 1.0)
        self.assertEqual(n, 4)
        self.assertIn((12.0, 0.0), path)                       # dépasse le coin de 2 mm
        self.assertIn((10.0, -2.0), path)                      # revient sur le côté suivant prolongé
        self.assertTrue(all(not (0 < x < 10 and 0 < y < 10) for x, y in path))   # boucles dehors
        self.assertEqual(S.corner_loops(sq, True, 30, 80, 2.0, 1.0)[1], 0)         # 90° > maxi
        self.assertEqual(S.corner_loops(sq, True, 30, 165, 2.0, 1.0, min_side=20)[1], 0)
        self.assertEqual(S.corner_loops(sq, False, 30, 165, 2.0, 1.0)[1], 3)       # ouvert : sommets intérieurs

    def test_strategy(self):
        tp = run([geom.rect(0, 0, 10, 10)], loop_length=2.0, loop_radius=1.0)
        self.assertTrue(any('4 boucle' in w for w in tp.warnings))
        self.assertEqual(sum(1 for m in tp.moves if m.kind == 'plunge'), 1)       # sans remonter
        xs = [m.x for m in tp.moves if m.kind == 'feed']
        self.assertGreater(max(xs), 11.5)

    def test_checked(self):
        # L : l'angle rentrant ferait sa boucle dans la matière — refusée
        L = geom.polyline([(0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10)], closed=True)
        tp = run([L], loop_length=1.0, loop_radius=0.5)
        self.assertTrue(any('5 boucle' in w for w in tp.warnings))
        tp = run([L], loop_length=1.0, loop_radius=0.5, loop_check=False)
        self.assertTrue(any('6 boucle' in w for w in tp.warnings))


if __name__ == '__main__':
    unittest.main()
