"""Round 323 : gomme à boucles (TypeEdit) — boucles séparées du contour au
lieu d'être supprimées ; taille mesurée en longueur ou en encombrement."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, parallel
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def looped():
    # trait ouvert avec une petite boucle (boucle de 2 × 2 au-dessus de x = 10)
    return geom.polyline([(0, 0), (12, 0), (12, 2), (10, 2), (10, -1), (20, -1)])


class TestLoops(unittest.TestCase):
    def test_separate(self):
        removed = []
        c = parallel.remove_loops(looped(), 100.0, 'longueur', removed)
        self.assertEqual(len(removed), 1)
        self.assertTrue(removed[0].closed)
        self.assertLess(len(c.segments), 5)
        b = removed[0].bbox()
        self.assertAlmostEqual(b[2] - b[0], 2, 6)

    def test_by_size(self):
        self.assertEqual(len(parallel.remove_loops(looped(), 3.0, 'encombrement').segments),
                         len(parallel.remove_loops(looped(), 100.0).segments))  # diagonale 2,83 ≤ 3
        self.assertEqual(len(parallel.remove_loops(looped(), 3.0, 'longueur').segments),
                         len(looped().segments))                              # longueur 8 > 3 : gardée

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            s = Shape(path=geom.Path([looped()]))
            w.canvas.doc.add(s)
            w.canvas.select([s])
            w.remove_loops_dialog({'max_len': 0.0, 'by': 'longueur', 'separate': True})
            new = w.canvas.doc.layers[0].items[0]
            self.assertEqual(len(new.path.contours), 2)                  # le trait + la boucle à part
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
