"""Round 182 : ordre des chaînes au plus proche voisin, en grille (mêmes résultats)."""
import math
import os
import random
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import strategies as S


def reference(chains, here=(0.0, 0.0)):
    """L'ancien ordre (balayage complet), pour comparer."""
    rest = list(chains)
    out = []
    while rest:
        def d(c):
            pts, closed = c
            if closed:
                return min(math.dist(p[:2], here[:2]) for p in pts)
            return min(math.dist(pts[0][:2], here[:2]), math.dist(pts[-1][:2], here[:2]))
        best = min(rest, key=d)
        rest.remove(best)
        pts = S._start_nearest(best[0], best[1], here)
        out.append((pts, best[1]))
        here = pts[-1]
    return out


def make(n, seed, grid_aligned=False):
    rnd = random.Random(seed)
    chains = []
    for i in range(n):
        if grid_aligned:
            cx, cy = rnd.randrange(0, 20) * 5.0, rnd.randrange(0, 12) * 5.0       # beaucoup d'égalités
        else:
            cx, cy = rnd.uniform(0, 200), rnd.uniform(0, 120)
        if i % 3:
            pts = [(cx + math.cos(2 * math.pi * k / 8), cy + math.sin(2 * math.pi * k / 8)) for k in range(8)]
            chains.append((pts + [pts[0]], True))
        else:
            chains.append(([(cx, cy), (cx + rnd.uniform(-3, 3), cy + rnd.uniform(-3, 3))], False))
    return chains


class TestOrder(unittest.TestCase):
    def test_same_as_reference(self):
        for seed in range(4):
            ch = make(300, seed)
            self.assertEqual(S.order_chains(ch, (5.0, -3.0)), reference(ch, (5.0, -3.0)), seed)

    def test_ties_and_far_start(self):
        ch = make(250, 9, grid_aligned=True)
        self.assertEqual(S.order_chains(ch), reference(ch))
        self.assertEqual(S.order_chains(ch, (1e4, -1e4)), reference(ch, (1e4, -1e4)))   # départ loin de la grille

    def test_speed(self):
        ch = make(3000, 3)
        t = time.perf_counter()
        out = S.order_chains(ch)
        self.assertEqual(len(out), 3000)
        self.assertLess(time.perf_counter() - t, 3.0)


if __name__ == '__main__':
    unittest.main()
