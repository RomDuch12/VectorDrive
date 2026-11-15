"""Formats du round 4 : EPS / AI ancien, SimPl, CLJOB + ISO, STEP."""
import math
import pathlib
import tempfile
import unittest

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import postscript, registry
from tests.corpus import corpus

STEP = corpus('step')


def sample():
    d = Document()
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 40, 20, 5)])))
    d.add(Shape(path=geom.Path([geom.circle((20, 10), 4)])))
    return d


def total_length(doc):
    return sum(it.path.length() for it in doc.iter_leaves() if getattr(it, 'path', None))


class TestRoundTrips(unittest.TestCase):
    def test_eps(self):
        with tempfile.TemporaryDirectory() as t:
            f = pathlib.Path(t) / 'a.eps'
            postscript.write(sample(), f)
            back = registry.open_document(f)
        self.assertEqual(back.stats()['contours'], 2)
        self.assertAlmostEqual(total_length(back), total_length(sample()), delta=1e-3)


@unittest.skipUnless(STEP.is_dir(), 'pièces STEP absentes')
class TestStep(unittest.TestCase):
    def test_wall_mount(self):
        f = next(STEP.rglob('base_wall_mount_vc.stp'), None)
        if f is None:
            self.skipTest('pièce absente')
        d = registry.open_document(f)
        bb = d.bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 34, places=3)
        self.assertAlmostEqual(bb[3] - bb[1], 19, places=3)
        self.assertTrue(any('trou' in r for r in d.report))


if __name__ == '__main__':
    unittest.main()
