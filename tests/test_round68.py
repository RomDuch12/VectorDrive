"""Round 68 : boucles sans fin du moteur natif corrigées à la source
(linesweeper modifié : bornes de sûreté, panique → repli shapely)."""
import os
import pathlib
import sys
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'outils'))

import fuzz_geom  # noqa: E402

from vectordrive.core import pathops  # noqa: E402


@unittest.skipIf(pathops._native is None, 'moteur natif absent')
class TestNativeNoHang(unittest.TestCase):
    def test_former_hangs_finish_fast(self):
        delay = pathops.NATIVE_TIMEOUT
        pathops.NATIVE_TIMEOUT = 10
        before = list(pathops.stuck_calls)
        try:
            for seed in (3000299, 3001958):          # bouclaient sans fin dans linesweeper
                t = time.perf_counter()
                self.assertEqual(fuzz_geom.run_case(seed), [])
                self.assertLess(time.perf_counter() - t, 5)
        finally:
            pathops.NATIVE_TIMEOUT = delay
        self.assertEqual(pathops.stuck_calls, before)            # aucun appel abandonné

    def test_engine_still_works_after_panic(self):
        from vectordrive.core import geom
        from vectordrive.core.geom import Path
        fuzz_geom.run_case(3001958)
        a = pathops.boolean(Path([geom.rect(0, 0, 10, 10)]), Path([geom.rect(5, 0, 10, 10)]), 'union')
        self.assertAlmostEqual(pathops.area(a), 150, places=9)


if __name__ == '__main__':
    unittest.main()
