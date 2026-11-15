"""Round 79 : décalage exact dans le tampon, l'ombrage et les hachures."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom, hatch, pathops, shadow, stamp
from vectordrive.core.geom import Path


class TestExactInternalOffsets(unittest.TestCase):
    def test_stamp_shoulder(self):
        sq = Path([geom.rect(0, 0, 10, 10)])
        a = pathops.area(stamp.region(sq, stamp.StampSpec(margin=2, radius=0, border=1, shoulder=0.5)))
        self.assertAlmostEqual(a, 144 - (121 - (4 - math.pi) * 0.25), places=6)

    def test_hatch_inset(self):
        disc = Path([geom.circle((0, 0), 10)])
        lines = hatch.hatch_path(disc, hatch.HatchSpec(spacing=0.5, angle=30, inset=1.0))
        rmax = max(math.hypot(*q) for c in lines.contours for q in (c.start, c.end))
        self.assertAlmostEqual(rmax, 9, places=6)

    def test_shadow_gap(self):
        sq = Path([geom.rect(0, 0, 10, 10)])
        sp = shadow.shadow_path(sq, shadow.ShadowSpec('portee', 0, 3, gap=1))
        self.assertAlmostEqual(pathops.area(sp), 20, places=6)          # (13 − 11) × 10


if __name__ == '__main__':
    unittest.main()
