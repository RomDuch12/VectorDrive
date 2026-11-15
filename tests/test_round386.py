"""Round 386 : imbrication — remplir la plaque (exemplaires 0, TypeEdit :
copie imbriquée)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, nesting as N
from vectordrive.core.document import Plate, Shape

app = QApplication.instance() or QApplication([])


class TestFill(unittest.TestCase):
    def test_fill(self):
        plate = Plate(width=100, height=50)
        sq = Shape(path=geom.Path([geom.rect(0, 0, 18, 18)]))
        res = N.nest([sq], plate, N.NestSpec(margin=0, gap=2, copies=0))
        self.assertEqual(len(res.placed), 10)                   # 5 × 2 cases de 20 mm
        self.assertEqual(res.plates, 1)
        for _it, m in res.placed:
            b = sq.transformed(m).bbox()
            self.assertTrue(-1e-9 <= b[0] and b[2] <= 100 + 1e-9 and -1e-9 <= b[1] and b[3] <= 50 + 1e-9, b)

    def test_mixed_and_too_big(self):
        plate = Plate(width=100, height=50)
        a = Shape(path=geom.Path([geom.rect(0, 0, 38, 18)]))
        b = Shape(path=geom.Path([geom.rect(0, 0, 18, 18)]))
        big = Shape(path=geom.Path([geom.rect(0, 0, 300, 10)]))
        res = N.nest([a, b, big], plate, N.NestSpec(margin=0, gap=2, copies=0))
        kinds = [it for it, _m in res.placed]
        self.assertGreater(kinds.count(a), 0)
        self.assertGreater(kinds.count(b), 0)
        self.assertIn(big, res.unplaced)
        area = sum((it.bbox()[2] - it.bbox()[0] + 2) * (it.bbox()[3] - it.bbox()[1] + 2) for it in kinds)
        self.assertLessEqual(area, (100 + 2) * (50 + 2) + 1e-6)

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.plate = Plate(width=100, height=50)
            sq = Shape(path=geom.Path([geom.rect(0, 0, 18, 18)]))
            w.canvas.doc.add(sq)
            res = w.apply_nesting([sq], N.NestSpec(margin=0, gap=2, copies=0))
            self.assertEqual(len(res.placed), 10)
            self.assertEqual(len(w.canvas.doc.layers[0].items), 10)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
