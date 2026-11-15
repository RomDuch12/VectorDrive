"""Round 745 : Couper un volume par le plan vertical d'un trait du dessin
(SolidCraft, SPLIT par une ligne d'esquisse)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.core import solids as S

app = QApplication.instance() or QApplication([])


def rb(b):
    return tuple(round(v, 4) + 0.0 for v in b)


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestSplitLine(unittest.TestCase):
    def test_plane(self):
        n, d = S.line_plane((5, -1), (5, 11))                  # vers +Y : la droite est +X
        self.assertEqual(rb(n), (1, 0, 0))
        self.assertAlmostEqual(d, 5)
        right, left = S.split(S.box(0, 0, 0, 10, 10, 10), n, d)
        self.assertEqual(rb(right.bounds()), (5, 0, 0, 10, 10, 10))
        self.assertEqual(rb(left.bounds()), (0, 0, 0, 5, 10, 10))
        n, d = S.line_plane((0, 0), (10, 10))                  # en biais : deux prismes triangulaires
        a, b = S.split(S.box(0, 0, 0, 10, 10, 10), n, d)
        self.assertAlmostEqual(a.volume(), 500, places=3)
        self.assertAlmostEqual(b.volume(), 500, places=3)
        with self.assertRaises(ValueError):
            S.line_plane((1, 1), (1, 1))

    def test_window(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            box = S.make_shape(S.box(0, 0, 0, 10, 20, 5), 0)
            line = Shape(path=geom.Path([geom.Contour([geom.Line((-5, 12), (15, 12))], False)]))
            w._add_items([box, line])
            c.select([box])
            with mock.patch.object(QMessageBox, 'information') as info:                  # pas de trait
                self.assertEqual(w.solid_slice(params={'plane': 'trait', 'value': 0.0, 'keep': 'deux'}), [])
            info.assert_called_once()
            c.select([box, line])
            new = w.solid_slice(params={'plane': 'trait', 'value': 0.0, 'keep': 'deux'})
            self.assertEqual(sorted(rb(S.of_item(it).bounds()) for it in new),
                             [(0, 0, 0, 10, 12, 5), (0, 12, 0, 10, 20, 5)])
            self.assertIn(line, list(c.doc.iter_items()))         # le trait reste
            w.undo()
            c.select([it for it in c.doc.iter_items()])
            kept = w.solid_slice(params={'plane': 'trait', 'value': 0.0, 'keep': 'plus'})   # à droite : Y < 12
            self.assertEqual([rb(S.of_item(it).bounds()) for it in kept], [(0, 0, 0, 10, 12, 5)])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
