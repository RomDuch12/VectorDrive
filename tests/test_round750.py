"""Round 750 : Coque ouverte d'un ou de plusieurs côtés, parois dedans,
dehors ou des deux côtés (SolidCraft : solid.shell)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import solids as S

app = QApplication.instance() or QApplication([])


def rb(b):
    return tuple(round(v, 3) + 0.0 for v in b)


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestShellSides(unittest.TestCase):
    def test_core(self):
        b = S.box(0, 0, 0, 20, 10, 10)
        closed = S.shell(b, 1.0)
        self.assertAlmostEqual(closed.volume(), 2000 - 18 * 8 * 8, places=3)
        tube = S.shell(b, 1.0, open_sides=('-x', '+x'))                 # un tube : ouvert aux deux bouts
        self.assertAlmostEqual(tube.volume(), 20 * (100 - 64), delta=0.1)
        self.assertEqual(rb(tube.bounds()), (0, 0, 0, 20, 10, 10))
        self.assertEqual(S.top_at(tube, 10, 5), 10)                      # le dessus reste fermé
        tray = S.shell(b, 1.0, open_sides=('+z', '-y'))
        self.assertAlmostEqual(tray.volume(), 2000 - 18 * 8 * 8 - 18 * 8 * 1 - 18 * 1 * 8, delta=0.1)  # l'arête reste
        same = S.shell(b, 1.0, open_top=True)
        self.assertAlmostEqual(same.volume(), S.shell(b, 1.0, open_sides=('+z',)).volume(), places=6)
        out = S.shell(b, 1.0, direction='outside')
        self.assertEqual(rb(out.bounds()), (-1, -1, -1, 21, 11, 11))    # le volume devient le vide
        both = S.shell(b, 2.0, direction='both', open_sides=('+z',))
        self.assertEqual(rb(both.bounds()), (-1, -1, -1, 21, 11, 11))
        with self.assertRaises(S.SolidError):
            S.shell(b, 10.0, direction='both')                            # 5 mm vers l'intérieur : plus rien à évider
        with self.assertRaises(S.SolidError):
            S.shell(b, 0.0)

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            box = S.make_shape(S.box(0, 0, 0, 20, 10, 10), 0)
            w._add_items([box])
            c.select([box])
            new = w.solid_shell(params={'thickness': 1.0, 'open_xmin': True, 'open_xmax': True})
            self.assertAlmostEqual(S.of_item(new[0]).volume(), 720, delta=0.1)
            w.undo()
            c.select([it for it in c.doc.iter_items()])
            new = w.solid_shell(params={'thickness': 1.0, 'direction': 'outside', 'open_top': True})
            self.assertEqual(rb(S.of_item(new[0]).bounds()), (-1, -1, -1, 21, 11, 11))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
