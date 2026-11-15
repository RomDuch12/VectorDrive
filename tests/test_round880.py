"""Round 880 : la région d'un grand groupe de contours qui se croisent ne lève plus d'exception."""
import unittest
from unittest import mock

import shapely
from shapely.geometry import Polygon, box

from vectordrive.cam import strategies as S


def crossing():
    """Assez de contours qui se croisent pour passer par les faces du réseau des bords (sans contours simplement imbriqués)."""
    return [box(i, 0, i + 1.5, 10) for i in range(0, 40, 1)]


class Region(unittest.TestCase):
    def test_le_calcul_normal(self):
        a = S._even_odd(crossing())
        self.assertTrue(a)
        self.assertTrue(all(p.is_valid for p in a))

    def test_faces_qui_se_chevauchent(self):
        normal = sum(p.area for p in S._even_odd(crossing()))
        with mock.patch.object(shapely, 'coverage_union_all', side_effect=shapely.errors.GEOSException('CoverageUnion cannot process overlapping inputs.')):
            got = S._even_odd(crossing())
        self.assertAlmostEqual(sum(p.area for p in got), normal, places=6)

    def test_meme_la_reunion_ordinaire_refuse(self):
        normal = sum(p.area for p in S._even_odd(crossing()))
        real = shapely.union_all
        calls = []

        def once(geoms, *a, **kw):
            if not kw.get('grid_size') and len(calls) == 1:
                calls.append('refus')
                raise shapely.errors.GEOSException('side location conflict')
            calls.append('ok')
            return real(geoms, *a, **kw)
        with mock.patch.object(shapely, 'coverage_union_all', side_effect=shapely.errors.GEOSException('x')), \
                mock.patch.object(shapely, 'union_all', side_effect=once):
            got = S._even_odd(crossing())
        self.assertIn('refus', calls)
        self.assertAlmostEqual(sum(p.area for p in got), normal, places=3)

    def test_la_region_entiere(self):
        from vectordrive.core import geom
        paths = [geom.Path([geom.polyline([(i, 0), (i + 1.5, 0), (i + 1.5, 10), (i, 10)], closed=True)]) for i in range(0, 100)]
        with mock.patch.object(shapely, 'coverage_union_all', side_effect=shapely.errors.GEOSException('x')):
            reg = S.region(paths, 0.01)
        self.assertFalse(reg.is_empty)

    def test_une_partie_non_valide_est_reparee(self):
        bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2)])
        self.assertFalse(bowtie.is_valid)
        good = box(10, 0, 11, 1)
        got = S._valid_parts([good, bowtie])
        self.assertIs(got[0], good)
        self.assertTrue(all(p.is_valid and p.geom_type == 'Polygon' for p in got))
        self.assertAlmostEqual(sum(p.area for p in got), 1.0 + 2.0, places=6)    # les deux ailes

    def test_un_trait_repasse_sur_lui_meme_n_est_pas_une_forme(self):
        good = box(0, 0, 10, 10)
        trait = Polygon([(2, 2), (5, 3), (5.00001, 3.00001), (2.00001, 2.00001)])
        self.assertTrue(trait.is_valid)
        self.assertEqual(S._valid_parts([good, trait]), [good])
        fin = box(20, 0, 30, 0.01)                                 # un centième de millimètre : une forme, même si aucun outil n'y entre
        self.assertEqual(len(S._valid_parts([good, fin])), 2)

    def test_tout_valide_rien_ne_change(self):
        parts = [box(0, 0, 1, 1), box(2, 0, 3, 1)]
        got = S._valid_parts(parts)
        self.assertIs(got[0], parts[0])
        self.assertIs(got[1], parts[1])
        self.assertEqual(S._valid_parts([]), [])

    def test_la_region_d_un_dessin_touffu_est_valide(self):
        from vectordrive.core import geom
        paths = [geom.Path([geom.polyline([(i, 0), (i + 1.5, 0), (i + 1.5, 10), (i, 10)], closed=True)]) for i in range(0, 100)]
        self.assertTrue(S.region(paths, 0.01).is_valid)


if __name__ == '__main__':
    unittest.main()
