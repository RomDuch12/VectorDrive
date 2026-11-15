"""Round 346 : motifs de hachures — briques, pointillés, ondulés, nid
d'abeille ; découpés dans la région (trous vides), tournés de l'angle."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom, hatch as HT


class TestPatterns(unittest.TestCase):
    def test_patterns(self):
        src = geom.Path([geom.rect(0, 0, 20, 20), geom.rect(8, 8, 4, 4)])
        for k, _l in HT.PATTERNS:
            p = HT.hatch_path(src, HT.HatchSpec(spacing=1.0, angle=0 if k != 'nid' else 15, pattern=k))
            self.assertTrue(p.contours, k)
            for c in p.contours:                                         # rien dans le trou ni dehors
                for s in c.segments:
                    for t in (0.0, 0.5, 1.0):
                        x, y = s.point(t)
                        self.assertTrue(-1e-6 <= x <= 20 + 1e-6 and -1e-6 <= y <= 20 + 1e-6, k)
                        self.assertFalse(8 + 1e-6 < x < 12 - 1e-6 and 8 + 1e-6 < y < 12 - 1e-6, k)
        bricks = HT.hatch_path(geom.Path([geom.rect(0, 0, 10, 10)]), HT.HatchSpec(spacing=2, angle=0, pattern='briques'))
        vertical = [c for c in bricks.contours if abs(c.start[0] - c.end[0]) < 1e-9]
        self.assertTrue(vertical)                                            # joints verticaux
        self.assertEqual(HT.HatchSpec.from_dict({'pattern': 'nid'}).pattern, 'nid')


if __name__ == '__main__':
    unittest.main()
