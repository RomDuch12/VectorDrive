"""Round 1104 : un PDF de devis (textes vectorisés) mettait 60 s à s'ouvrir — la surface en règle non nulle normalisait
chaque tracé quatre fois (`pathops.area` normalise déjà) ; l'aire d'une forme peinte était recalculée pour chaque aplat
blanc posé dessus. Mêmes formes, deux fois moins de calcul."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1104.ini'))

from vectordrive.core import geom, pathops  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402


def square(x, y, s, ccw=True):
    c = geom.rect(x, y, s, s)
    return c if ccw else c.reversed()


class TestAreas(unittest.TestCase):
    def test_area_fill_rule(self):
        # deux carrés de 10 qui se recouvrent de moitié, même sens : pair-impair 100, non nulle 150
        p = geom.Path([square(0, 0, 10), square(5, 0, 10)])
        self.assertAlmostEqual(pathops.area(p), 100.0, places=3)
        self.assertAlmostEqual(pathops.area(p, evenodd=True), 100.0, places=3)
        self.assertAlmostEqual(pathops.area(p, evenodd=False), 150.0, places=3)
        eo, nz = pathops.fill_areas(p)
        self.assertAlmostEqual(eo, 100.0, places=3)
        self.assertAlmostEqual(nz, 150.0, places=3)

    def test_fill_areas_converts_once(self):
        p = geom.Path([square(0, 0, 10), square(20, 0, 10)])
        if pathops._native is None:
            self.skipTest('moteur natif absent')
        with mock.patch.object(pathops, 'to_ops', wraps=pathops.to_ops) as conv:
            eo, nz = pathops.fill_areas(p)
        self.assertEqual(conv.call_count, 1)
        self.assertAlmostEqual(eo, nz, places=3)

    def test_without_native_engine(self):
        p = geom.Path([square(0, 0, 10), square(5, 0, 10)])
        with mock.patch.object(pathops, '_native', None):
            eo, nz = pathops.fill_areas(p)
            self.assertAlmostEqual(pathops.area(p, evenodd=False), nz, places=1)
        self.assertAlmostEqual(eo, 100.0, places=1)
        self.assertAlmostEqual(nz, 150.0, places=1)


    def test_native_failure_no_second_try(self):
        # moteur en défaut (délai dépassé…) : repli shapely direct, sans retenter le moteur par `normalize`
        p = geom.Path([square(0, 0, 10), square(5, 0, 10)])

        def failing(*a, **k):
            raise pathops._NativeFailed('délai')
        with mock.patch.object(pathops, '_call', side_effect=failing) as call, \
                mock.patch.object(pathops, 'normalize', wraps=pathops.normalize) as norm:
            eo, nz = pathops.fill_areas(p)
            a = pathops.area(p, evenodd=False)
        self.assertEqual(norm.call_count, 0)
        self.assertLessEqual(call.call_count, 2)
        self.assertAlmostEqual(nz, 150.0, places=1)
        self.assertAlmostEqual(a, nz, places=6)
        self.assertAlmostEqual(eo, 100.0, places=1)


class TestPdfSurfaces(unittest.TestCase):
    def test_nonzero_same_result_fewer_passes(self):
        from vectordrive.io import pdf
        over = geom.Path([square(0, 0, 10), square(5, 0, 10)])          # recouvrement même sens : réuni
        got = pdf._nonzero(over, [10, False])
        self.assertIsNot(got, over)
        self.assertAlmostEqual(pathops.area(got), 150.0, places=3)
        hole = geom.Path([square(0, 0, 10), square(3, 3, 4, ccw=False)])  # trou en sens inverse : courbes d'origine
        with mock.patch.object(pathops, 'normalize', wraps=pathops.normalize) as norm:
            self.assertIs(pdf._nonzero(hole, [10, False]), hole)
        self.assertEqual(norm.call_count, 0)                              # avant : deux normalisations (+ deux dans area)

    def test_knock_out_area_once_per_shape(self):
        from vectordrive.io import pdf
        painted = Shape(path=geom.Path([square(0, 0, 30)]))
        painted.filled = True
        items = [painted]
        for x in (2, 12, 22):                                              # trois aplats blancs posés dessus
            w = Shape(path=geom.Path([square(x, 2, 4)]))
            w.extra['pdf_blanc'] = 'aplat'
            items.append(w)
        report = []
        with mock.patch.object(pathops, 'area', wraps=pathops.area) as ar:
            masks = pdf._knock_out(items, report)
        self.assertEqual(len(masks), 3)
        self.assertEqual(items, [painted])
        self.assertAlmostEqual(pathops.area(painted.path), 900.0 - 3 * 16.0, places=2)
        self.assertEqual(ar.call_count, 4)                                 # avant : 6 (l'aire de départ à chaque aplat)
        self.assertTrue(any('recoupée' in r for r in report))


if __name__ == '__main__':
    unittest.main()
