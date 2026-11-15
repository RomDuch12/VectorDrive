"""Round 403 : lire un programme ISO (G-code) en parcours (TypeEdit :
Simulations NC)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import ncread

app = QApplication.instance() or QApplication([])

PROG = """%
(carré et arc)
N10 G21 G90 G17
N20 G0 X0 Y0 Z5
N30 G1 Z-1 F300
N40 X10
N50 Y10 ; commentaire
N60 G2 X20 Y10 I5 J0
N70 G3 X10 Y10 R5
N80 G91 G1 X-10
N90 G90 G0 Z5
M30
%"""


class TestNC(unittest.TestCase):
    def test_read(self):
        tp = ncread.read(PROG)
        kinds = [m.kind for m in tp.moves]
        self.assertEqual(kinds, ['rapid', 'plunge', 'feed', 'feed', 'arc_cw', 'arc_ccw', 'feed', 'rapid'])
        arc = tp.moves[4]
        self.assertEqual((arc.cx, arc.cy), (15.0, 10.0))
        r = tp.moves[5]
        self.assertAlmostEqual(math.hypot(r.x - r.cx, r.y - r.cy), 5.0, 6)
        self.assertAlmostEqual(r.cx, 15.0, 6)                       # G3 de (20,10) à (10,10), R5 : centre (15,10)
        self.assertEqual((tp.moves[6].x, tp.moves[6].y), (0.0, 10.0))   # G91 : relatif
        self.assertEqual(tp.warnings, [])

    def test_inch_and_cycles(self):
        tp = ncread.read('G20 G90\nG0 X1 Y1 Z0.1\nG81 X2 Y2 Z-0.1 R0.1\n')
        self.assertAlmostEqual(tp.moves[0].x, 25.4, 6)
        drill = [m for m in tp.moves if m.kind == 'plunge']          # cycle tracé depuis le round 521
        self.assertEqual([(round(m.x, 6), round(m.z, 6)) for m in drill], [(50.8, -2.54)])
        self.assertTrue(ncread.read('M30').warnings)

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            path = os.path.join(tempfile.mkdtemp(), 'essai.nc')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(PROG)
            tp = w.open_nc_program(path)
            self.assertIn(tp, w.cam_panel.toolpaths)
            self.assertEqual(tp.name, 'essai.nc')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
