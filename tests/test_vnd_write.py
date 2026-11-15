"""Écriture VND : réécriture à l'octet, création, conservation de la fin."""
import math
import pathlib
import tempfile
import unittest

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Image, Layer, Shape
from vectordrive.core.geom import Affine
from vectordrive.io import registry, vnd, vnd_write
from tests.corpus import corpus

ROOT = pathlib.Path(__file__).resolve().parents[2]
SAMPLES = [
    corpus('vnd_datron_1'),
    corpus('vnd_datron_2'),
    corpus('vnd_verite'),
]
AVAILABLE = [p for p in SAMPLES if p.exists()]


def leaves(items):
    for it in items:
        if isinstance(it, Group):
            yield from leaves(it.children)
        else:
            yield it


def summary(doc):
    out = []
    for L in doc.layers:
        shapes = [s for s in leaves(L.items) if isinstance(s, Shape)]
        out.append((L.name, sum(len(s.path.contours) for s in shapes),
                    round(sum(s.path.length() for s in shapes), 6),
                    sum(1 for s in leaves(L.items) if isinstance(s, Image))))
    return out


class TestTemplate(unittest.TestCase):
    def test_new_document(self):
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(10, 10, 80, 40, 5)])))
        d.add(Shape(path=geom.Path([geom.circle((50, 30), 8)])))
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'n.vnd'
            registry.save_document(d, f)
            back = vnd.read(f)
        lengths = sorted(round(s.path.length(), 6) for s in leaves(back.layers[0].items))
        self.assertEqual(lengths, sorted([round(2 * math.pi * 8, 6),
                                          round(geom.rect(10, 10, 80, 40, 5).length(), 6)]))
        self.assertIsNotNone(back.plate)
        self.assertEqual(len(back.tools), 10)

    def test_points_homogeneous(self):
        c = geom.circle((0, 0), 10)
        pts = vnd_write.contour_points(c)
        segs = vnd.contour_segments(pts, closed=True)
        self.assertAlmostEqual(sum(s.length() for s in segs), 2 * math.pi * 10, places=9)

    def test_empty_document_has_a_layer(self):
        data, _ = vnd_write.write_document(Document())
        root, _ = vnd.parse(data)
        self.assertEqual(len(root.children), 1)


@unittest.skipUnless(AVAILABLE, 'aucun VND de référence')
class TestRewrite(unittest.TestCase):
    def test_byte_identical(self):
        for p in AVAILABLE:
            with self.subTest(p.name):
                data = p.read_bytes()
                self.assertEqual(vnd_write.rewrite(data), data)

    def test_moved_keeps_tail(self):
        for p in AVAILABLE:
            with self.subTest(p.name):
                raw = p.read_bytes()
                d = registry.open_document(p)
                for L in d.layers:
                    L.items = [it.transformed(Affine.translation(10, -3)) for it in L.items]
                ref = summary(d)
                out, report = vnd_write.write_document(d)
                self.assertEqual(report, [])
                self.assertEqual(out[-3000:], raw[-3000:])          # fin d'origine (FAO…)
                with tempfile.TemporaryDirectory() as tmp:
                    f = pathlib.Path(tmp) / 'm.vnd'
                    f.write_bytes(out)
                    self.assertEqual(summary(vnd.read(f)), ref)

    def test_added_object(self):
        p = AVAILABLE[0]
        d = registry.open_document(p)
        d.add(Shape(path=geom.Path([geom.circle((5, 5), 3)])))
        ref = summary(d)
        out, _ = vnd_write.write_document(d)
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'a.vnd'
            f.write_bytes(out)
            back = vnd.read(f)
        self.assertEqual(summary(back), ref)
        self.assertEqual(len(back.tools), 10)


@unittest.skipUnless(AVAILABLE, 'aucun VND de référence')
class TestTail(unittest.TestCase):
    def test_tools_and_plate(self):
        d = registry.open_document(AVAILABLE[0])
        self.assertEqual([t.color for t in d.tools[:3]], ['#000000', '#ff0000', '#00ff00'])
        self.assertAlmostEqual(d.plate.width, 210)
        self.assertAlmostEqual(d.plate.height, 297)
        self.assertAlmostEqual(d.plate.thickness, 5)


if __name__ == '__main__':
    unittest.main()
