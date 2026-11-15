"""Round 318 : mise en page du texte sur la plaque (TypeEdit) — lignes
réparties, volume du texte, marges automatiques, décalage, poids."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import platetext as PT
from vectordrive.core.document import Plate

app = QApplication.instance() or QApplication([])


class TestLayout(unittest.TestCase):
    def test_equal_lines(self):
        pl = Plate(100, 50)
        rows = PT.layout(pl, PT.PlateTextSpec(lines=2, volume=40, margin_factor=1, h_margin=10))
        self.assertEqual(len(rows), 2)
        (x1, b1, h1, L1), (x2, b2, h2, L2) = rows
        self.assertEqual((x1, h1, L1), (50, 10, 80))
        # reste 30 mm : 2 marges + 1 interligne = 3 × 10
        self.assertAlmostEqual(b1, 50 - 10 - 10)                       # haut : marge 10, capitales 10
        self.assertAlmostEqual(b2, b1 - 10 - 10)
        self.assertAlmostEqual(b2, 10)                                 # marge du bas : 10

    def test_offset_weights_margins(self):
        pl = Plate(100, 50, margins=[0, 0, 0, 10])
        rows = PT.layout(pl, PT.PlateTextSpec(lines=2, volume=50, weights='3 1', offset=50))
        self.assertAlmostEqual(rows[0][2], 15)                         # 40 × 50 % = 20 ; 3/4 et 1/4
        self.assertAlmostEqual(rows[1][2], 5)
        self.assertLess(40 - (rows[0][1] + rows[0][2]), 20 / 3)        # le texte remonte (marge du haut réduite)

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.plate = Plate(120, 40)
            texts = w.plate_text({'lines': 3, 'volume': 50, 'margin_factor': 1, 'offset': 0, 'h_margin': 5,
                                  'weights': '', 'font': 'Arial'})
            self.assertEqual(len(texts), 3)
            self.assertTrue(all(t.align == 'center' for t in texts))
            self.assertAlmostEqual(texts[0].extra['max_length']['length'], 108)
            ys = [t.matrix.f for t in texts]
            self.assertEqual(ys, sorted(ys, reverse=True))
            w.undo()
            self.assertEqual(sum(len(L.items) for L in w.canvas.doc.layers), 0)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
