"""Round 532 : correctif du 531 — une petite région sans pièce à nombreux trous garde le retrait direct,
identique au bit près ; la décomposition ne sert qu'aux pièces à nombreux trous."""
import unittest
from unittest import mock

from shapely.geometry import MultiPolygon, Polygon, box

from vectordrive.cam import strategies as S


class TestSmallDirect(unittest.TestCase):
    def test_direct_and_split(self):
        small = MultiPolygon([box(0, 0, 10, 10), box(20, 0, 25, 8)])
        self.assertTrue(S.erode(small, 1.5, 6).equals_exact(small.buffer(-1.5, quad_segs=6), 0))
        holes = [box(2 + 4 * i, 2, 4 + 4 * i, 5).exterior.coords for i in range(20)]
        plate = Polygon(box(0, 0, 90, 10).exterior.coords, holes)
        with mock.patch.object(S, '_erode_one', wraps=S._erode_one) as one:
            got = S.erode(MultiPolygon([plate, box(100, 0, 110, 10)]), 1.2, 6)
        one.assert_called()
        ref = MultiPolygon([plate, box(100, 0, 110, 10)]).buffer(-1.2, quad_segs=6)
        self.assertLess(got.symmetric_difference(ref).area, 1e-6)


if __name__ == '__main__':
    unittest.main()
