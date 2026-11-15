"""Round 504 : traitement par lots sur plusieurs processus quand le reste du lot s'annonce long (même
résultat qu'à la suite, dans l'ordre) ; deux sources pour une même sortie : la seconde ignorée."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom, workers
from vectordrive.core.document import Document, Shape
from vectordrive.io import batch, registry


def make(folder: pathlib.Path, n: int) -> list:
    out = []
    for i in range(n):
        doc = Document()
        doc.add(Shape(path=geom.Path([geom.circle((0, 0), 1 + i)])))
        f = folder / f'rond{i:02d}.dxf'
        registry.save_document(doc, f)
        out.append(f)
    return out


class TestBatchProcesses(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.files = make(self.dir, 6)
        svg = Document()
        svg.add(Shape(path=geom.Path([geom.rect(0, 0, 3, 3)])))
        registry.save_document(svg, self.dir / 'rond00.svg')          # même nom que rond00.dxf

    def tearDown(self):
        workers.set_count(0)

    def test_pool_same_as_sequential(self):
        files = self.files + [self.dir / 'rond00.svg']
        seq = batch.convert(files, self.dir / 'seq', 'vnd')
        workers.set_count(3)
        with mock.patch.object(workers, 'SWITCH_S', 0.0), mock.patch.object(workers, 'PARALLEL_MIN', 2):
            par = batch.convert(files, self.dir / 'par', 'vnd')
            rows = batch.check(files)
        self.assertEqual(len(par.done), 6)
        self.assertEqual([pathlib.Path(s).name for s, _d in par.done], [f.name for f in self.files])
        self.assertEqual(par.skipped, seq.skipped)
        self.assertIn('même fichier de sortie', par.skipped[0][1])
        for (_s, a), (_t, b) in zip(seq.done, par.done):
            la = list(registry.open_document(a).iter_leaves())
            lb = list(registry.open_document(b).iter_leaves())
            self.assertEqual([x.bbox() for x in la], [x.bbox() for x in lb])
        self.assertEqual([r['fichier'] for r in rows], [str(f) for f in files])
        self.assertTrue(all(r['lu'] for r in rows))

    def test_small_lot_stays_sequential(self):
        workers.set_count(4)
        with mock.patch.object(workers, 'run_pool', side_effect=AssertionError('processus pour un petit lot')):
            res = batch.convert(self.files, self.dir / 'out', 'svg')
        self.assertEqual(len(res.done), 6)
        self.assertEqual(batch.processes(3), 1)
        self.assertGreater(batch.processes(40), 1)


if __name__ == '__main__':
    unittest.main()
