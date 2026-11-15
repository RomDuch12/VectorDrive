"""Round 749 : Aligner des volumes sur le premier choisi, axe par axe (côtés,
centres, contre, posé dessus ou dessous)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import solids as S

app = QApplication.instance() or QApplication([])


def rb(b):
    return tuple(round(v, 6) + 0.0 for v in b)


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestAlign(unittest.TestCase):
    def test_offset(self):
        ref = (0, 0, 0, 40, 20, 10)
        box = (50, 50, 5, 60, 54, 7)
        self.assertEqual(S.align_offset(box, ref, ('none', 'none', 'none')), (0, 0, 0))
        self.assertEqual(S.align_offset(box, ref, ('min', 'centre', 'max')), (-50, -42, 3))
        self.assertEqual(S.align_offset(box, ref, ('after', 'before', 'after'), 1.0), (-9, -55, 6))
        self.assertEqual(S.align_offset(box, ref, ('centre', 'centre', 'before')), (-35, -42, -7))

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            base = S.make_shape(S.box(0, 0, 0, 40, 20, 10), 0)
            lid = S.make_shape(S.box(100, 50, 3, 10, 4, 2), 0)
            pin = S.make_shape(S.cylinder(-30, -30, 0, 2, 8), 0)
            w._add_items([base, lid, pin])
            c.select([base])
            self.assertEqual(w.solid_align3d(params={}), [])
            c.select([base, lid, pin])
            new = w.solid_align3d(params={'x': 'centre', 'y': 'centre', 'z': 'after', 'gap': 0.5})
            self.assertEqual(len(new), 2)
            self.assertEqual(rb(S.of_item(new[0]).bounds()), (15, 8, 10.5, 25, 12, 12.5))   # posé sur le socle
            b = S.of_item(new[1]).bounds()
            self.assertAlmostEqual((b[0] + b[3]) / 2, 20, places=6)
            self.assertAlmostEqual(b[2], 10.5, places=6)
            self.assertEqual(rb(S.of_item(base).bounds()), (0, 0, 0, 40, 20, 10))         # la référence reste
            sh = next(it for it in c.doc.iter_items() if S.of_item(it) is not None and
                      rb(S.of_item(it).bounds()) == (15, 8, 10.5, 25, 12, 12.5))
            x0, y0, x1, y1 = sh.bbox()
            self.assertAlmostEqual(x0, 15, places=3)                                       # silhouette suivie
            self.assertAlmostEqual(y1, 12, places=3)
            w.undo()
            self.assertIn(lid, list(c.doc.iter_items()))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
