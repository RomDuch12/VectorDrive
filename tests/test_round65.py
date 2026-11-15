"""Round 65 : fuzz géométrique des opérations de dessin, texte en colonnes."""
import os
import pathlib
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'outils'))

import fuzz_geom  # noqa: E402

from vectordrive.core import parallel, pathops  # noqa: E402
from vectordrive.core.geom import Contour, Line, Path  # noqa: E402


class TestFuzz(unittest.TestCase):
    def test_fixed_seeds(self):
        bad = {}
        for seed in range(40):
            probs = fuzz_geom.run_case(7_000_000 + seed)
            if probs:
                bad[seed] = probs
        self.assertEqual(bad, {})

    def test_small_offset_of_spikes_not_lost(self):
        # deux pics d'aire nulle : le résultat exact (vide) doit être écarté
        p = Path([Contour([Line((0, 0), (2, 1.5)), Line((2, 1.5), (0.00001, 0))], True),
                  Contour([Line((5, 5), (5.00006, 5.00014))] + [Line((5.00006, 5.00014), (5, 5))], True)])
        res, exact = parallel.offset_checked(p, 0.0104)
        self.assertGreater(pathops.area(res), 0.04)
        self.assertFalse(exact)


class TestNativeGuard(unittest.TestCase):
    def test_stuck_native_falls_back_to_shapely(self):
        import time
        from vectordrive.core import geom

        class Stuck:
            def boolean(self, *a):
                time.sleep(3)                           # rend le verrou, comme le moteur natif
                return []

            def area(self, *a):
                raise ValueError('erreur du moteur')
        old, delay = pathops._native, pathops.NATIVE_TIMEOUT
        pathops._native, pathops.NATIVE_TIMEOUT, pathops._worker = Stuck(), 0.3, None
        try:
            a = Path([geom.rect(0, 0, 10, 10)])
            b = Path([geom.rect(5, 0, 10, 10)])
            t = time.perf_counter()
            r = pathops.boolean(a, b, 'union')
            self.assertLess(time.perf_counter() - t, 2)
            self.assertAlmostEqual(pathops.area(r), 150, places=6)          # shapely, après erreur native
            self.assertIn('boolean', pathops.stuck_calls)
        finally:
            pathops._native, pathops.NATIVE_TIMEOUT, pathops._worker = old, delay, None
        self.assertAlmostEqual(pathops.area(Path([geom.rect(0, 0, 2, 2)])), 4, places=9)


class TestColumns(unittest.TestCase):
    def test_split(self):
        from vectordrive.core.text import split_columns
        self.assertEqual(split_columns(list('abcdefg'), 3), [['a', 'b', 'c'], ['d', 'e', 'f'], ['g']])
        self.assertEqual(split_columns(['a'], 4), [['a']])

    def test_columns_side_by_side(self):
        from vectordrive.core import text as TX
        from vectordrive.core.document import Text
        t = Text(text='Ligne un\nDeux\nTrois lignes\nQuatre\nCinq', font='Arial', size=5)
        t.outline = TX.outline_for(t)
        a, b = TX.columns(t, 2, 4)
        self.assertEqual((a.text, b.text), ('Ligne un\nDeux\nTrois lignes', 'Quatre\nCinq'))
        self.assertAlmostEqual(b.outline.bbox()[0] - a.outline.bbox()[2], 4, places=6)
        self.assertAlmostEqual(a.matrix.f, b.matrix.f)                  # premières lignes de base alignées


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_columns_command(self):
        from vectordrive.core import text as TX
        from vectordrive.core.document import Group, Text
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            t = Text(text='a\nb\nc\nd', font='Arial', size=5)
            t.outline = TX.outline_for(t)
            w._add_items([t])
            w.canvas.select([t])
            w._columns_dialog = lambda n, g: (2, 3.0)
            w.text_columns()
            g = w.canvas.selection[0]
            self.assertIsInstance(g, Group)
            self.assertEqual([c.text for c in g.children], ['a\nb', 'c\nd'])
            w._columns_dialog = lambda n, gg: (4, 1.0)
            w._item_double_clicked(g)
            self.assertEqual([c.text for c in w.canvas.selection[0].children], ['a', 'b', 'c', 'd'])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
