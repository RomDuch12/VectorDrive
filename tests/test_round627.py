"""Round 627 : programmes ISO — centres d'arcs I J absolus (comme la Cielle :
fiche TypeEdit Ijki=0) reconnus arc par arc, G90.1 / G91.1 lus ; les arcs
n'étaient plus que des cercles énormes reliant les passes."""
import math
import unittest

from vectordrive.cam import ncread

ABS = """T6
G0 X35.868 Y-106.495 Z100.
G1 X35.868 Y-106.495 Z-1. F200
G1 X47.627 Y-106.495 Z-1. F2000
G2 X49.627 Y-108.475 I41.747 J-114.435
G1 X33.867 Y-108.475 Z-1.
G3 X33.138 Y-109.587 I41.747 J-114.435
M30
"""
REL = """G0 X10. Y0. Z1.
G1 X10. Y0. Z-1. F100
G2 X0. Y-10. I-10. J0.
G3 X-10. Y0. I0. J10.
"""


def far(tp, cx, cy):
    return max(math.hypot(x - cx, y - cy) for kind, pl in tp.polylines(0.01) if kind == 'feed' for x, y, _z in pl)


class TestArcCentres(unittest.TestCase):
    def test_absolute(self):
        tp = ncread.read(ABS, 'b.iso')
        arcs = [m for m in tp.moves if m.is_arc]
        self.assertEqual(len(arcs), 2)
        self.assertTrue(all((round(m.cx, 3), round(m.cy, 3)) == (41.747, -114.435) for m in arcs))
        self.assertLess(far(tp, 41.747, -114.435), 10.1)                 # dans la poche, pas de cercle énorme
        self.assertTrue(any('absolues' in w for w in tp.warnings))

    def test_relative_unchanged(self):
        tp = ncread.read(REL, 'r.nc')
        self.assertTrue(all((round(m.cx, 6), round(m.cy, 6)) == (0, 0) for m in tp.moves if m.is_arc))
        self.assertFalse(any('absolues' in w for w in tp.warnings))

    def test_explicit_modes_and_full_circle_first(self):
        tp = ncread.read('G91.1\n' + ABS, 'x.nc')                       # imposé : relatifs
        first = next(m for m in tp.moves if m.is_arc)
        self.assertEqual((round(first.cx, 3), round(first.cy, 3)), (round(47.627 + 41.747, 3), -220.93))
        tp = ncread.read('G90.1\n' + REL.replace('I-10. J0.', 'I0. J0.').replace('I0. J10.', 'I0. J0.'), 'y.nc')
        self.assertTrue(all((round(m.cx, 6), round(m.cy, 6)) == (0, 0) for m in tp.moves if m.is_arc))
        circle_first = ABS.replace('G2 X49.627', 'G2 X47.627 Y-106.495 I41.747 J-114.435\nG2 X49.627')
        tp = ncread.read(circle_first, 'c.iso')                          # cercle entier avant le 1er arc tranché
        self.assertTrue(all((round(m.cx, 3), round(m.cy, 3)) == (41.747, -114.435) for m in tp.moves if m.is_arc))

    def test_arc_center(self):
        self.assertEqual(ncread.arc_center(10, 0, 0, -10, -10, 0)[2:], (False, True))
        self.assertEqual(ncread.arc_center(47.627, -106.495, 49.627, -108.475, 41.747, -114.435)[2:], (True, True))
        self.assertEqual(ncread.arc_center(1, 0, 1, 0, 0, 0)[3], False)  # cercle entier : non tranché


if __name__ == '__main__':
    unittest.main()
