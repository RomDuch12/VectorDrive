"""Round 747 : Jeu entre volumes (SolidCraft : inspect.clearance) —
chevauchements, contacts, paires plus proches qu'un jeu, plus proche voisin."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import solids as S

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestClearance(unittest.TestCase):
    def test_core(self):
        a = S.box(0, 0, 0, 10, 10, 10)
        b = S.box(8, 0, 0, 10, 10, 10)            # chevauche a de 2 × 10 × 10
        c = S.box(18, 0, 0, 5, 10, 10)            # touche b
        d = S.box(23.5, 0, 0, 5, 10, 10)          # à 0,5 de c
        e = S.box(100, 0, 0, 5, 5, 5)             # loin
        r = S.clearance([a, b, c, d, e], gap=1.0)
        self.assertEqual([(i, j) for i, j, _v in r['overlaps']], [(0, 1)])
        self.assertAlmostEqual(r['overlaps'][0][2], 200, places=3)
        self.assertEqual(r['contacts'], [(1, 2)])
        self.assertEqual(len(r['near']), 1)
        i, j, dist, pa, pb = r['near'][0]
        self.assertEqual((i, j), (2, 3))
        self.assertAlmostEqual(dist, 0.5, places=6)
        self.assertAlmostEqual(pa[0], 23, places=6)                # le lieu : la face de c face à d
        self.assertAlmostEqual(pb[0], 23.5, places=6)
        self.assertEqual(r['nearest'][0], (1, 0.0))
        self.assertEqual(r['nearest'][4][0], 3)
        self.assertAlmostEqual(r['nearest'][4][1], 100 - 28.5, places=6)
        self.assertGreater(r['pruned'], 0)                          # e écarté sur les encombrements

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            items = [S.make_shape(S.box(0, 0, 0, 10, 10, 10), 0), S.make_shape(S.box(10.2, 0, 0, 10, 10, 10), 0)]
            items[0].name, items[1].name = 'Bloc', 'Couvercle'
            w._add_items(items)
            c.select(items[:1])
            self.assertIsNone(w.solid_clearance(params={'gap': 1.0}))
            c.select(items)
            r = w.solid_clearance(params={'gap': 1.0})
            self.assertEqual(len(r['near']), 1)
            self.assertIn('Bloc × Couvercle : 0.200 mm', r['text'])
            self.assertIn('Bloc → Couvercle : 0.200 mm', r['text'])
            r = w.solid_clearance(params={'gap': 0.1})
            self.assertIn('Aucun chevauchement', r['text'])
            self.assertIn(w.A['solid_clearance'], {b.defaultAction() for b in w.ribbon.findChildren(
                __import__('PySide6.QtWidgets', fromlist=['QToolButton']).QToolButton)})
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
