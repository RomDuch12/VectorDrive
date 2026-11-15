"""Round 521 : programmes ISO — cycles de perçage G81–G89 tracés (modaux, G80 / G0–G3 les arrêtent,
retour G98 à la cote de départ ou G99 au plan R)."""
import unittest

from vectordrive.cam import ncread

PROG = '''%
G21 G90
G0 Z10
G0 X0 Y0
G98 G81 X5 Y5 Z-2 R1 F100
X10 Y5
X15 Y5 Z-3
G80
G0 X30 Y30
G99 G83 X40 Y40 Z-4 R2 Q1
X45
G0 Z20
M30
'''


class TestDrillCycles(unittest.TestCase):
    def test_cycles(self):
        tp = ncread.read_iso(PROG, 'perçage')
        plunges = [m for m in tp.moves if m.kind == 'plunge']
        self.assertEqual([(m.x, m.y, m.z) for m in plunges],
                         [(5, 5, -2), (10, 5, -2), (15, 5, -3), (40, 40, -4), (45, 40, -4)])
        after_g98 = tp.moves[tp.moves.index(plunges[0]) + 1]
        self.assertEqual((after_g98.kind, after_g98.z), ('rapid', 10))          # G98 : cote de départ
        after_g99 = tp.moves[tp.moves.index(plunges[3]) + 1]
        self.assertEqual(after_g99.z, 2)                                         # G99 : plan R
        self.assertTrue(any(m.kind == 'rapid' and (m.x, m.y) == (30, 30) for m in tp.moves))   # G80 puis G0
        self.assertFalse(any('non suivi' in w for w in tp.warnings))

    def test_relative_warning(self):
        tp = ncread.read_iso('G91 G81 X5 Y5 Z-2 R1\nG80\n', 'relatif')
        self.assertTrue(any('G91' in w for w in tp.warnings))


if __name__ == '__main__':
    unittest.main()
