"""Round 285 : Pathfinder — diviser, détourer, fusionner, recadrer,
soustraire l'arrière (formes empilées dans l'ordre du dessin)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, pathfinder as PF
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])
A = (geom.Path([geom.rect(0, 0, 10, 10)]), 1)                 # en bas
B = (geom.Path([geom.rect(5, 5, 10, 10)]), 2)                 # au-dessus


def area(p):
    return sum(abs(c.signed_area()) for c in p.contours)


class TestPathfinder(unittest.TestCase):
    def test_divide(self):
        out = PF.divide([A, B])
        self.assertEqual(len(out), 3)
        self.assertEqual(sorted(round(area(p)) for p, _t in out), [25, 75, 75])
        overlap = next(t for p, t in out if round(area(p)) == 25)
        self.assertEqual(overlap, 2)                                              # la forme visible au-dessus

    def test_trim_merge_crop_minus(self):
        tr = PF.trim([A, B])
        self.assertEqual([(round(area(p)), t) for p, t in tr], [(75, 1), (100, 2)])
        same = PF.merge([A, (B[0], 1)])
        self.assertEqual([(round(area(p)), t) for p, t in same], [(175, 1)])
        cr = PF.crop([A, B])
        self.assertEqual([(round(area(p)), t) for p, t in cr], [(25, 1)])
        mb = PF.minus_back([A, B])
        self.assertEqual([(round(area(p)), t) for p, t in mb], [(75, 2)])

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            a, b = Shape(path=A[0], tool=0), Shape(path=B[0], tool=1)
            c.doc.add(a)
            c.doc.add(b)
            c.select([b, a])                                                       # ordre de sélection inversé
            new = w.pathfinder('trim')
            self.assertEqual(sorted(round(area(s.path)) for s in new), [75, 100])
            self.assertEqual(next(s.tool for s in new if round(area(s.path)) == 75), 0)   # A, sous B, rognée
            w.undo()
            self.assertEqual(len(c.doc.layers[0].items), 2)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
