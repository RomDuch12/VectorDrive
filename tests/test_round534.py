"""Round 534 : intersections › Couper aux intersections — segments de coupe filtrés une fois par leurs
cadres (avant : comparés un à un à chaque contour) ; mêmes morceaux."""
import random
import unittest

from vectordrive.core import geom, intersect as I
from vectordrive.core.document import Shape
from vectordrive.core.trim import cut_params, piece


def old_split(path, cutters):
    out = []
    for c in path.contours:
        if not c.segments:
            continue
        others = [s for s in cutters if all(s is not t for t in c.segments)]
        gs = cut_params(c, others, self_cut=True)
        n = float(len(c.segments))
        if not gs:
            out.append(c)
            continue
        if c.closed:
            for k, g in enumerate(gs):
                out.append(piece(c, g, gs[(k + 1) % len(gs)] if len(gs) > 1 else g + n))
        else:
            bounds = [0.0] + gs + [n]
            out += [piece(c, a, b) for a, b in zip(bounds, bounds[1:]) if b - a > 1e-9]
    return geom.Path([c for c in out if c.segments])


class TestSplit(unittest.TestCase):
    def test_same_pieces(self):
        rnd = random.Random(4)
        shapes = [Shape(path=geom.Path([geom.circle((rnd.uniform(0, 40), rnd.uniform(0, 30)), rnd.uniform(1, 6))]))
                  for _ in range(25)]
        shapes += [Shape(path=geom.Path([geom.rect(rnd.uniform(0, 40), rnd.uniform(0, 30), 8, 3)])) for _ in range(10)]
        new = I.apply('split', shapes)
        segs = [seg for s in shapes for c in s.path.contours for seg in c.segments]
        old = [old_split(s.path, segs) for s in shapes]
        sig = lambda paths: [[(round(c.length(), 9), len(c.segments), c.closed) for c in p.contours] for p in paths]  # noqa: E731
        self.assertEqual(sig([s.path for s in new]), sig(old))
        self.assertGreater(sum(len(s.path.contours) for s in new), len(shapes))     # vraiment coupés


if __name__ == '__main__':
    unittest.main()
