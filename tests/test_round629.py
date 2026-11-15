"""Round 629 : maillage STEP plus robuste — boucles de bord extraites en cycles
même aux sommets où plus de deux arêtes de bord se rejoignent (deux trous qui
se touchent par un sommet : ils n'étaient pas bouchés) ; sommets ajoutés sur
le bord d'une face posés sur la corde de la voisine (voir test_round603)."""
import unittest

import numpy as np

from tests.test_round595 import box_tris
from vectordrive.core import faces3d
from vectordrive.core import watertight as WT


def pinched_box():
    """Pavé dont deux triangles de faces voisines, qui ne se touchent que par
    un sommet, sont retirés : deux trous joints en un point."""
    t = box_tris(0, 0, 0, 10, 10, 10)
    v, idx = faces3d.merged_vertices(t, 1e-6)
    for i in range(len(idx)):
        for j in range(i + 1, len(idx)):
            if len(set(idx[i]) & set(idx[j])) == 1:
                keep = [k for k in range(len(idx)) if k not in (i, j)]
                return v, idx[keep]
    raise AssertionError('aucune paire')


class TestPinchedHoles(unittest.TestCase):
    def test_two_loops_through_one_vertex(self):
        v, idx = pinched_box()
        self.assertEqual(WT.open_and_bad(idx), (6, 0))
        loops = WT.border_loops(idx)
        self.assertEqual(sorted(len(L) for L in loops), [3, 3])          # deux boucles, rien d'abandonné
        self.assertEqual(sum(len(L) for L in loops), 6)

    def test_filled_and_closed(self):
        v, idx = pinched_box()
        v2, idx2, holes = WT.fill_holes(v, idx)
        self.assertEqual(holes, 2)
        self.assertEqual(WT.open_and_bad(WT.clean(idx2)), (0, 0))

    def test_hole_found_past_a_dead_end(self):
        # trou d'un triangle (a, b, c) + un triangle de trop (a, q, d) sur une arête intérieure (a, q),
        # partagée alors par trois triangles : le chemin q → d → a → b → c → a finit en impasse ;
        # le cycle (a, b, c) doit quand même être trouvé (il était abandonné avec le chemin)
        v, idx = faces3d.merged_vertices(box_tris(0, 0, 0, 10, 10, 10), 1e-6)
        a, b, c = (int(x) for x in idx[0])
        rest = idx[1:]
        e, cnt = WT.edge_counts(rest)
        q = next(int(y) for x, y in e.tolist() if x == a and y not in (b, c))
        d = len(v)
        v = np.vstack([v, [[20.0, 20.0, 20.0]]])
        extra = np.array([[q, d, a]])                                      # ses arêtes (q, d) puis (d, a) d'abord
        idx2 = np.concatenate([extra, rest])
        loops = WT.border_loops(idx2)
        self.assertIn(sorted((a, b, c)), [sorted(L) for L in loops])

    def test_simple_hole_unchanged(self):
        v, idx = faces3d.merged_vertices(box_tris(0, 0, 0, 1, 1, 1), 1e-6)
        loops = WT.border_loops(idx[1:])
        self.assertEqual([len(L) for L in loops], [3])
        self.assertEqual(WT.border_loops(idx), [])


if __name__ == '__main__':
    unittest.main()
