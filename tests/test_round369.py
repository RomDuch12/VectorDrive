"""Round 369 : gravure laser — orientation automatique : les lignes de
chaque forme dans le sens de sa longueur."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import strategies as S
from vectordrive.core import geom
from tests.test_round368 import run


class TestAutoOrientation(unittest.TestCase):
    def test_axis(self):
        reg = S.region([geom.Path([geom.rect(0, 0, 4, 20)])], 0.01)
        self.assertAlmostEqual(S.long_axis_angle(reg) % 180, 90.0, 6)

    def test_fill(self):
        tall = geom.rect(0, 0, 4, 20)                    # haute : lignes verticales
        plain = run([tall])
        auto = run([tall], hatch_auto=True)
        n = lambda tp: sum(1 for m in tp.moves if m.kind == 'plunge')
        self.assertLess(n(auto), n(plain) / 3)           # 8 lignes au lieu de 40
        for a, b in zip(auto.moves, auto.moves[1:]):
            if a.kind == 'plunge' and b.kind == 'feed':
                self.assertAlmostEqual(a.x, b.x, 6)       # chaque ligne verticale

    def test_per_shape(self):
        shapes = [geom.rect(0, 0, 4, 20), geom.rect(10, 0, 20, 4)]
        tp = run(shapes, hatch_auto=True, fill_order='forme')
        n = sum(1 for m in tp.moves if m.kind == 'plunge')
        self.assertLessEqual(n, 20)


if __name__ == '__main__':
    unittest.main()
