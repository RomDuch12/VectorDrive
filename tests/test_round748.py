"""Round 748 : Comparer deux volumes (SolidCraft : inspect.compare) — écarts
des surfaces, régions de matière d'un seul des deux."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import solids as S

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestCompare(unittest.TestCase):
    def test_distance(self):
        T = np.array([[[0, 0, 0], [10, 0, 0], [0, 10, 0]]], float)
        P = np.array([[2, 2, 3], [-3, -4, 0], [10, 10, 0], [5, -2, 1], [0, 5, -2]], float)
        d, q = S.surface_distance(P, T)
        np.testing.assert_allclose(d, [3, 5, np.sqrt(50), np.sqrt(5), 2], atol=1e-12)
        np.testing.assert_allclose(q[0], [2, 2, 0])
        np.testing.assert_allclose(q[2], [5, 5, 0])                    # sur l'hypoténuse
        box = S.box(0, 0, 0, 10, 10, 10)
        pts, w = S.surface_samples(box, 1.0)
        self.assertAlmostEqual(float(w.sum()), 600, places=6)
        d, _q = S.surface_distance(pts, box.triangles())
        self.assertLess(float(d.max()), 1e-9)

    def test_compare(self):
        a = S.box(0, 0, 0, 20, 10, 10)
        b = S.hole(S.box(0, 0, 0, 20, 10, 11), 10, 5, 4)                 # plus haut de 1, percé
        r = S.compare(a, b, 0.01, 2.0, 3000)
        self.assertFalse(r['identical'])
        self.assertAlmostEqual(r['difference'], b.volume() - a.volume(), places=6)
        sides = sorted((g['side'], round(g['volume'])) for g in r['regions'])
        self.assertEqual([s for s, _v in sides], ['a', 'b'])
        va = next(g for g in r['regions'] if g['side'] == 'a')
        self.assertAlmostEqual(va['volume'], (20 * 10 * 11 - b.volume()) * 10 / 11, places=3)   # le trou dans A
        self.assertAlmostEqual(va['center'][0], 10, places=3)
        vb = next(g for g in r['regions'] if g['side'] == 'b')
        self.assertAlmostEqual(vb['bounds'][2], 10, places=6)
        self.assertAlmostEqual(vb['max_deviation'], 1.0, places=6)
        self.assertGreater(r['a_to_b']['max'], 1.0)                     # dans le trou, au plus 2 de sa paroi
        self.assertLessEqual(r['a_to_b']['max'], 2.0 + 1e-9)
        self.assertGreater(r['b_to_a']['max'], 1.0)                     # la paroi du trou, dans la matière de A
        same = S.compare(a, a.copy(), 0.01, 2.0, 3000)
        self.assertTrue(same['identical'])
        self.assertLess(same['max'], 1e-9)

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            items = [S.make_shape(S.box(0, 0, 0, 10, 10, 10), 0), S.make_shape(S.box(0, 0, 0, 10, 10, 12), 0)]
            items[0].name, items[1].name = 'V1', 'V2'
            w._add_items(items)
            c.select(items[:1])
            self.assertIsNone(w.solid_compare(params={}))
            c.select(items)
            r = w.solid_compare(params={'spacing': 2.0, 'add': True})
            self.assertIn('Différence de volume B − A : +200.000 mm³', r['text'])
            self.assertIn('1 région(s) différente(s)', r['text'])
            self.assertEqual(len(r['items']), 1)
            self.assertEqual(r['items'][0].name, 'V2 seul')
            w.undo()
            self.assertEqual(len([it for it in c.doc.iter_items() if S.is_solid(it)]), 2)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
