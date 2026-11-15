"""Aller-retour des formats et vérité terrain TypeEdit.

Les fichiers réels (corpus, voir tests/corpus.py) restent hors du dépôt :
les tests correspondants sont sautés s'ils sont absents.
"""
import math
import pathlib
import tempfile
import unittest

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Shape
from vectordrive.core.geom import bbox_union
from vectordrive.io import registry, vnd
from tests.corpus import corpus



def leaves(items):
    for it in items:
        if isinstance(it, Group):
            yield from leaves(it.children)
        else:
            yield it


def layer_stats(L):
    shapes = [s for s in leaves(L.items) if getattr(s, 'path', None)]
    return (sum(len(s.path.contours) for s in shapes),
            sum(s.path.length() for s in shapes),
            bbox_union(s.bbox() for s in shapes))


def sample_doc() -> Document:
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 80, 40, 5)])))
    d.add(Shape(path=geom.Path([geom.circle((40, 20), 8)])))
    d.add(Shape(path=geom.Path([geom.Contour([geom.Cubic((10, 10), (20, 30), (40, -10), (60, 10))])])))
    return d


class TestRoundTrip(unittest.TestCase):
    def test_round_trips(self):
        d = sample_doc()
        L0 = d.layers[0]
        n0, len0, _ = layer_stats(L0)
        with tempfile.TemporaryDirectory() as tmp:
            for ext in ('vdz', 'svg', 'dxf', 'pdf'):
                with self.subTest(ext=ext):
                    f = pathlib.Path(tmp) / f'a.{ext}'
                    registry.save_document(d, f)
                    back = registry.open_document(f)
                    n = sum(layer_stats(L)[0] for L in back.layers)
                    ln = sum(layer_stats(L)[1] for L in back.layers)
                    self.assertEqual(n, n0)
                    self.assertAlmostEqual(ln, len0, delta=0.01)

    def test_vdz_exact(self):
        d = sample_doc()
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'a.vdz'
            registry.save_document(d, f)
            back = registry.open_document(f)
            a = d.layers[0].items[1].path.contours[0].segments
            b = back.layers[0].items[1].path.contours[0].segments
            self.assertEqual(a, b)


@unittest.skipUnless(corpus('vnd_verite').exists(), 'dessin de référence absent')
class TestReference(unittest.TestCase):
    """Le même dessin lu dans le VND et dans le DXF exporté par TypeEdit."""

    @classmethod
    def setUpClass(cls):
        cls.vnd = registry.open_document(corpus('vnd_verite'))
        cls.dxf = registry.open_document(corpus('dxf_verite'))

    def test_structure(self):
        self.assertEqual([L.name for L in self.vnd.layers], ['Plan 1', 'Plan 2'])
        self.assertEqual(self.vnd.stats()['contours'], 572)

    def test_plan2_matches_typeedit_dxf(self):
        n, length, bb = layer_stats(self.vnd.layers[1])
        n2, length2, bb2 = layer_stats(self.dxf.layers[0])
        self.assertEqual(n, 113)
        self.assertEqual(n2, 113)
        for a, b in zip(bb, bb2):
            self.assertAlmostEqual(a, b, places=3)
        self.assertAlmostEqual(length, length2, delta=0.5)   # DXF aplati par TypeEdit


@unittest.skipUnless(corpus('vnd_datron_1').exists(), 'corpus absent')
class TestOtherVnd(unittest.TestCase):
    def test_vnd_datron_1(self):
        d = registry.open_document(corpus('vnd_datron_1'))
        self.assertEqual(d.stats()['contours'], 65)

    def test_bpm_layers(self):
        p = corpus('vnd_datron_2')
        if not p.exists():
            self.skipTest('BPM absent')
        d = registry.open_document(p)
        self.assertEqual(len(d.layers), 5)
        self.assertEqual(d.layers[0].name, '100 vers 70')


class TestVndPoints(unittest.TestCase):
    def test_homogeneous_quarter_circle(self):
        # quart de cercle de rayon 10 mm, contrôle stocké × w (homogène), en mètres
        w = math.sqrt(0.5)
        pts = [(0.010, 0.0, 0, 1.0, 0x0D), (0.010 * w, 0.010 * w, 0, w, 0x0C), (0.0, 0.010, 0, 1.0, 0x0D)]
        segs = vnd.contour_segments(pts, closed=False)
        self.assertEqual(len(segs), 1)
        self.assertAlmostEqual(segs[0].length(), math.pi * 10 / 2, places=6)


if __name__ == '__main__':
    unittest.main()
