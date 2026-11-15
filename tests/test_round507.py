"""Round 507 : réunion de nombreux tracés par groupes qui se chevauchent, deux à deux en arbre — même
résultat que l'accumulation, sans son coût quadratique ; Décaler sur plusieurs processus quand c'est long
(core.workers.adaptive_map, même résultat)."""
import random
import unittest

from vectordrive.core import geom, pathops as PO


class TestUnionAll(unittest.TestCase):
    def test_same_as_accumulation(self):
        rnd = random.Random(5)
        paths = []
        for i in range(60):
            x, y = rnd.uniform(0, 80), rnd.uniform(0, 40)
            c = geom.circle((x, y), rnd.uniform(1, 6)) if i % 2 else geom.rect(x, y, rnd.uniform(1, 8), rnd.uniform(1, 5))
            paths.append(geom.Path([c]))
        paths.append(geom.Path([geom.rect(200, 200, 5, 5)]))                # isolé
        fast = PO.union_all(paths)
        acc = paths[0]
        for p in paths[1:]:
            acc = PO.boolean(acc, p, 'union')
        self.assertAlmostEqual(PO.area(fast), PO.area(acc), places=6)
        self.assertEqual(len(fast.contours), len(acc.contours))
        self.assertAlmostEqual(PO.area(PO.boolean(fast, acc, 'xor')), 0.0, places=5)

    def test_edge_cases(self):
        self.assertEqual(PO.union_all([]).contours, [])
        one = geom.Path([geom.rect(0, 0, 2, 2)])
        self.assertIs(PO.union_all([one]), one)
        two = PO.union_all([one, geom.Path([geom.rect(10, 0, 2, 2)])])        # disjoints : bout à bout
        self.assertEqual(len(two.contours), 2)
        self.assertAlmostEqual(PO.area(two), 8.0, places=6)


class TestAdaptiveOffset(unittest.TestCase):
    def test_offset_job_and_pool(self):
        from unittest import mock
        from vectordrive.core import parallel, workers
        paths = [geom.Path([geom.circle((5 * i, 0), 1.5)]) for i in range(10)]
        jobs = [(p, [0.2, 0.4], 'round') for p in paths]
        seq = [parallel.offset_job(*j) for j in jobs]
        self.assertEqual([len(r[0]) for r in seq], [2] * 10)
        self.assertEqual(sum(r[1] for r in seq), 20)
        workers.set_count(3)
        try:
            with mock.patch.object(workers, 'SWITCH_S', 0.0), mock.patch.object(workers, 'PARALLEL_MIN', 2):
                par = workers.adaptive_map(parallel.offset_job, jobs)
        finally:
            workers.set_count(0)
        for a, b in zip(seq, par):
            self.assertEqual([round(x.length(), 9) for x in a[0]], [round(x.length(), 9) for x in b[0]])
        miter = parallel.offset_job(paths[0], [0.5], 'miter')
        self.assertEqual((len(miter[0]), miter[1], miter[2]), (1, 0, 0))


if __name__ == '__main__':
    unittest.main()
