"""Round 222 : parcours lourds tracés au trait fin — le contour d'un trait
de 1,2 px antialiasé coûte 100 × plus (2 millions de segments : 23 s par
rafraîchissement, 0,2 s au trait fin)."""
import os
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def zigzag(n: int):
    from vectordrive.cam.model import Move, Toolpath
    moves = [Move('rapid', 0, 0, 5)]
    for i in range(n):
        moves.append(Move('feed', (i % 200) * 0.5, (i // 200) * 0.5, -0.5))
    return Toolpath(op_id='o', tool_id='t', name='zigzag', moves=moves)


class TestHeavyPaths(unittest.TestCase):
    def test_hairline_when_heavy(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        w.resize(1200, 800)
        w.show()
        c = w.canvas
        c.set_toolpaths([(zigzag(2_000), '#e8590c')])
        self.assertFalse(c.heavy_toolpaths())                     # dessin courant : trait de 1,2 px gardé
        c.set_toolpaths([(zigzag(600_000), '#e8590c')])
        self.assertTrue(c.heavy_toolpaths())
        c.fit()
        c.repaint()                                               # construit le cache des chemins
        t0 = time.perf_counter()
        c.repaint()
        dt = time.perf_counter() - t0
        self.assertLess(dt, 3.0, f'rafraîchissement {dt:.1f} s')  # ~6,6 s au trait de 1,2 px, ~0,1 s au trait fin
        w.modified = False
        w.close()


if __name__ == '__main__':
    unittest.main()
