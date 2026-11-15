"""Round 335 : cotation rapide (comme QDIM en DAO) — positions en X sous la
sélection et en Y à sa gauche, en chaîne ou depuis une ligne de base."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import dims as D, geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestQuick(unittest.TestCase):
    def test_core(self):
        pts = [(10, 5), (30, 5), (60, 15)]
        dims = D.quick(pts, (0, 0, 70, 20), D.DimStyle(), 'chaine', 8)
        xs = [d for d in dims if d.kind == 'horizontale']
        ys = [d for d in dims if d.kind == 'verticale']
        self.assertEqual([round(d.value(), 6) for d in xs], [20, 30])
        self.assertEqual([round(d.value(), 6) for d in ys], [10])
        self.assertTrue(all(abs(d.points[0][1] + d.offset - (-8)) < 1e-9 for d in xs))   # ligne sous la boîte
        base = D.quick(pts, (0, 0, 70, 20), D.DimStyle(), 'base', 8)
        bx = [d for d in base if d.kind == 'horizontale']
        self.assertEqual([round(d.value(), 6) for d in bx], [20, 50])
        self.assertLess(bx[1].points[0][1] + bx[1].offset, bx[0].points[0][1] + bx[0].offset)

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            items = [Shape(path=geom.Path([geom.circle((10, 10), 2)])), Shape(path=geom.Path([geom.circle((40, 25), 2)]))]
            for it in items:
                c.doc.add(it)
            c.select(items)
            groups = w.quick_dims({'mode': 'chaine', 'gap': 6.0})
            self.assertEqual(len(groups), 2)                              # un écart en X, un en Y
            vals = sorted(round(D.dim_of(g).value(), 6) for g in groups)
            self.assertEqual(vals, [15, 30])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
