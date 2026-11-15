"""Round 961 : HPGL écrit — un tracé dont les points sont plus serrés que le pas du traceur ne part plus en escalier
(plus long que le tracé, et bien plus lourd) ; les tracés ordinaires ne changent pas."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r961.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402
from vectordrive.io import hpgl  # noqa: E402


def plot(path):
    """(longueur du tracé écrit en mm, nombre de points) du HPGL du tracé `path`."""
    d = Document()
    d.layers[0].items.append(Shape(path=path))
    text, _images = hpgl.write_text(d)
    total, n, pos = 0.0, 0, None
    for cmd in text.replace('\n', '').split(';'):
        if cmd[:2] not in ('PU', 'PD') or len(cmd) == 2:
            continue
        v = [int(x) for x in cmd[2:].split(',')]
        for x, y in zip(v[0::2], v[1::2]):
            if cmd[:2] == 'PD' and pos is not None:
                total += math.hypot(x - pos[0], y - pos[1]) / hpgl.UNITS
            pos = (x, y)
            n += 1
    return total, n


class Stairs(unittest.TestCase):

    def test_a_dense_line_is_not_a_staircase(self):
        a = math.radians(30)
        pts = [(10 * k / 2000 * math.cos(a), 10 * k / 2000 * math.sin(a)) for k in range(2001)]   # un point tous les 5 µm
        length, n = plot(geom.Path([geom.polyline(pts)]))
        self.assertAlmostEqual(length, 10.0, delta=0.05)                    # avant : 13,2 mm, en escalier
        self.assertEqual(n, 2)                                              # avant : 517 points

    def test_a_dense_circle_keeps_its_length(self):
        pts = [(5 + 5 * math.cos(2 * math.pi * k / 4000), 5 + 5 * math.sin(2 * math.pi * k / 4000)) for k in range(4000)]
        length, n = plot(geom.Path([geom.polyline(pts, closed=True)]))
        self.assertAlmostEqual(length, 2 * math.pi * 5, delta=0.1)          # avant : 38,5 mm (+22 %)
        self.assertLess(n, 120)                                             # avant : 1 497 points
        self.assertGreater(n, 40)                                           # reste un cercle : au demi-pas près

    def test_ordinary_shapes_are_unchanged(self):
        length, n = plot(geom.Path([geom.rect(0, 0, 40, 20, 3)]))
        self.assertAlmostEqual(length, 2 * (34 + 14) + 2 * math.pi * 3, delta=0.05)
        self.assertEqual(n, 37)
        length, n = plot(geom.Path([geom.circle((5, 5), 5)]))
        self.assertAlmostEqual(length, 2 * math.pi * 5, delta=0.05)
        self.assertEqual(n, 65)
        thin = getattr(hpgl, '_thin', None)
        self.assertIsNotNone(thin)                                                             # avant
        square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
        self.assertEqual(thin(square), square)                              # les coins d'un contour fermé restent


if __name__ == '__main__':
    unittest.main()
