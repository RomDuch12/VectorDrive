"""Round 940 : poche — les tours ajoutés entre les passes sont visités au plus proche (moins de longues liaisons sur
une plaque à nombreuses îles)."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r940.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.cam import model, strategies  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402


def plate(n):
    side = 14.0 * n + 8.0
    contours = [geom.rect(0, 0, side, side)] + [geom.rect(8 + 14 * i, 8 + 14 * j, 6, 6)
                                                 for i in range(n) for j in range(n)]
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path(contours)))
    return d


def gap(a, b):
    """Plus courte distance entre deux tours (leurs sommets)."""
    return min(math.dist(p[:2], q[:2]) for p in a for q in b)


def tour(start, loops):
    out, here = 0.0, [start]
    for lp in loops:
        out += gap(here, lp)
        here = lp
    return out


def greedy(start, loops):
    rest, here, out = list(loops), [start], []
    while rest:
        best = min(rest, key=lambda lp: gap(here, lp))
        rest.remove(best)
        out.append(best)
        here = best
    return out


def cut_length(tp):
    out, prev = 0.0, None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid' and min(prev.z, m.z) < -1e-6:
            out += math.dist((prev.x, prev.y), (m.x, m.y))
        prev = m
    return out


class Order(unittest.TestCase):

    def test_added_loops_are_visited_nearest_first(self):
        tool = model.CamTool(name='f', diameter=3.0, step_down=1.0, stepover=0.75)
        s = model.CamSetup(tools=[tool])
        op = model.Operation(kind='poche', tool_id=tool.id, depth=0.5)
        s.operations = [op]
        seen = []
        real = strategies.spiral_leftover

        def spy(groups, *a, **k):
            out = real(groups, *a, **k)
            seen.append((groups, out))
            return out
        with mock.patch.object(strategies, 'spiral_leftover', side_effect=spy):
            tp = strategies.compute(plate(6), s, op)
        self.assertTrue(any('îlot(s) repris' in w for w in tp.warnings))
        groups, out = seen[0]
        checked = 0
        for g, more in zip(groups, out):
            if len(more) < 4:
                continue
            start = g[-1][0][-1]
            best = tour(start, greedy(start, more))
            self.assertLessEqual(tour(start, more), best * 1.1)             # avant : l'ordre où shapely les rend
            checked += 1
        self.assertGreater(checked, 0)
        self.assertLess(cut_length(tp), 4300.0)                             # avant : 4 372 mm dans la matière


if __name__ == '__main__':
    unittest.main()
