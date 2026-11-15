"""Round 348 : engrenage en développante — rayons de tête et de pied, nombre
de dents, épaisseur de dent au primitif, alésage, mise à l'échelle."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import forms as F, geom


class TestGear(unittest.TestCase):
    def test_profile(self):
        g = F.Gear(module=2, teeth=20, bore=10)
        p = g.build()
        self.assertEqual(len(p.contours), 2)
        pts = [s.start for s in p.contours[0].segments]
        radii = [math.hypot(x, y) for x, y in pts]
        self.assertAlmostEqual(max(radii), 22.0, 6)                     # tête : r + m
        self.assertAlmostEqual(min(radii), 17.5, 6)                     # pied : r − 1,25 m
        tips = [math.atan2(y, x) for (x, y), r in zip(pts, radii) if abs(r - 22.0) < 1e-6]
        self.assertEqual(len(tips), 40)                                 # 2 points de tête par dent
        # épaisseur au primitif (r = 20) : π m / 2 = 3,1416 mm (corde ≈ arc)
        c = p.contours[0]
        ring = geom.circle((0, 0), 20)
        from vectordrive.core.pathops import _to_shapely
        inter = _to_shapely(geom.Path([c])).boundary.intersection(_to_shapely(geom.Path([ring])).boundary)
        angs = sorted(math.atan2(q.y, q.x) for q in inter.geoms)
        widths = sorted(b - a for a, b in zip(angs, angs[1:]))
        self.assertAlmostEqual(widths[len(widths) // 2] * 20, math.pi * 2 / 2, 1)

    def test_scale(self):
        d = F.to_dict(F.Gear(module=1, teeth=12))
        m = geom.Affine(2, 0, 0, 2, 0, 0)
        out = F.transformed(d, m, F.Gear(module=1, teeth=12).build().transformed(m))
        self.assertAlmostEqual(out['module'], 2.0)
        self.assertEqual(out['teeth'], 12)


if __name__ == '__main__':
    unittest.main()
