"""Round 413 : volumes 3D — primitives, extrusion (dépouille), révolution, booléens, masse."""
import math
import unittest

from vectordrive.core import geom
from vectordrive.core import solids as S


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestSolids(unittest.TestCase):
    def test_primitives(self):
        self.assertAlmostEqual(S.box(0, 0, 0, 10, 20, 30).volume(), 6000, places=6)
        self.assertAlmostEqual(S.box(10, 0, 0, -10, 20, 30).bounds()[0], 0)       # côtés signés
        self.assertAlmostEqual(S.wedge(0, 0, 0, 10, 20, 30).volume(), 3000, places=6)
        self.assertAlmostEqual(S.cylinder(0, 0, 0, 5, 10).volume(), math.pi * 250, delta=math.pi * 250 * 0.01)
        self.assertAlmostEqual(S.cone(0, 0, 0, 5, 10).volume(), math.pi * 250 / 3, delta=3)
        self.assertAlmostEqual(S.sphere(0, 0, 0, 5).volume(), 4 / 3 * math.pi * 125, delta=5)
        self.assertAlmostEqual(S.pyramid(0, 0, 0, 4, 10, 10).volume(), 2000 / 3, places=6)
        self.assertAlmostEqual(S.torus(0, 0, 0, 20, 5).volume(), 2 * math.pi ** 2 * 500, delta=100)
        with self.assertRaises(S.SolidError):
            S.box(0, 0, 0, 0, 1, 1)

    def test_wedge_shape(self):
        w = S.wedge(0, 0, 0, 10, 20, 30)
        top = w.verts[w.verts[:, 2] > 29.9]
        self.assertTrue(len(top) and abs(top[:, 0]).max() < 1e-6)            # pleine hauteur sur x0

    def test_extrude(self):
        r = geom.Path([geom.rect(0, 0, 40, 30), geom.rect(10, 10, 10, 10)])       # un trou
        e = S.extrude(r, 10, z0=5)
        self.assertAlmostEqual(e.volume(), (1200 - 100) * 10, places=4)
        self.assertAlmostEqual(e.bounds()[2], 5)
        down = S.extrude(geom.Path([geom.rect(0, 0, 40, 30)]), -10)
        self.assertAlmostEqual(down.bounds()[5], 0)
        t = math.tan(math.radians(10)) * 10
        exact = 10 * (40 * 30) - 10 * t * (40 + 30) + 4 / 3 * t * t * 10      # tronc de pyramide rectangulaire
        tap = S.extrude(geom.Path([geom.rect(0, 0, 40, 30)]), 10, taper_deg=10)
        self.assertAlmostEqual(tap.volume(), exact, delta=exact * 0.01)
        out = S.extrude(geom.Path([geom.rect(0, 0, 40, 30)]), 10, taper_deg=-10)
        self.assertAlmostEqual(out.bounds()[0], -t, delta=0.01)
        with self.assertRaises(S.SolidError):
            S.extrude(geom.Path([geom.polyline([(0, 0), (10, 0)])]), 5)        # rien de fermé

    def test_revolve(self):
        prof = geom.Path([geom.rect(10, 0, 5, 20)])
        full = S.revolve(prof, ((0, 0), (0, 1)))
        self.assertAlmostEqual(full.volume(), math.pi * 125 * 20, delta=math.pi * 125 * 20 * 0.01)
        b = full.bounds()
        self.assertAlmostEqual(b[1], 0)
        self.assertAlmostEqual(b[4], 20)                                           # le long de l'axe Y
        half = S.revolve(geom.Path([geom.rect(0, 10, 20, 5)]), ((0, 0), (1, 0)), 180)
        self.assertGreater(half.bounds()[5], 14.9)                                 # main droite : +Y vers +Z
        self.assertAlmostEqual(half.bounds()[2], 0, places=6)
        q = S.revolve(geom.Path([geom.rect(0, -15, 20, 5)]), ((0, 0), (1, 0)), 90)
        self.assertLess(q.bounds()[2], -14.9)                                      # −Y vers −Z
        with self.assertRaises(S.SolidError):
            S.revolve(geom.Path([geom.rect(-5, 0, 10, 10)]), ((0, 0), (0, 1)))     # traverse l'axe

    def test_booleans_massprop(self):
        a = S.box(0, 0, 0, 10, 20, 30)
        hole = S.cylinder(5, 10, -1, 3, 40)
        sub = S.boolean('subtract', [a, hole])
        self.assertAlmostEqual(sub.volume(), 6000 - math.pi * 9 * 30, delta=5)
        uni = S.boolean('union', [a, S.box(5, 0, 0, 10, 20, 30)])
        self.assertAlmostEqual(uni.volume(), 9000, places=4)
        inter = S.boolean('intersect', [a, S.box(5, 0, 0, 10, 20, 30)])
        self.assertAlmostEqual(inter.volume(), 3000, places=4)
        mp = S.massprop(a, density=2.7)
        self.assertAlmostEqual(mp['mass'], 16.2)
        self.assertEqual(tuple(round(v, 6) for v in mp['centroid']), (5, 10, 15))
        self.assertAlmostEqual(mp['area'], 2200)

    def test_transform_and_save(self):
        a = S.box(0, 0, 0, 10, 20, 30)
        m = [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]              # symétrie
        b = a.transformed(m)
        self.assertAlmostEqual(b.volume(), 6000, places=6)                       # faces toujours dehors
        b.manifold()
        c = S.Solid.from_dict(a.to_dict())
        self.assertEqual((c.id, c.name), (a.id, a.name))
        self.assertTrue((c.verts == a.verts).all())


if __name__ == '__main__':
    unittest.main()
