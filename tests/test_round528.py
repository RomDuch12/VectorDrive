"""Round 528 : programmes Heidenhain — cycles de perçage 200–205 (CYCL CALL, M99) et arcs tangents CT."""
import math
import unittest

from vectordrive.cam import ncread

PROG = '''0 BEGIN PGM TROUS MM
1 BLK FORM 0.1 Z X+0 Y+0 Z-10
2 BLK FORM 0.2 X+50 Y+50 Z+0
3 TOOL CALL 5 Z S3000
4 L Z+50 R0 FMAX
5 CYCL DEF 200 PERCAGE ~
  Q200=2 ;DISTANCE D'APPROCHE ~
  Q201=-6 ;PROFONDEUR ~
  Q206=150 ;AVANCE PLONGEE PROF. ~
  Q203=+0 ;COORD. SURFACE PIECE ~
  Q204=20 ;SAUT DE BRIDE
6 L X+10 Y+10 R0 FMAX M99
7 L X+30 Y+10 R0 FMAX
8 CYCL CALL
9 L X+0 Y+30 Z-1 F200
10 L X+20 Y+30
11 CT X+30 Y+40
12 END PGM TROUS MM
'''


class TestHeidenhain(unittest.TestCase):
    def test_cycles_and_ct(self):
        tp = ncread.read_heidenhain(PROG, 'trous')
        holes = [(m.x, m.y, m.z) for m in tp.moves if m.kind == 'plunge' and m.z < -5]
        self.assertEqual(holes, [(10, 10, -6), (30, 10, -6)])
        after = tp.moves[[m.kind for m in tp.moves].index('plunge') + 1]
        self.assertEqual(after.z, 20)                                     # retour au saut de bride
        arc = tp.moves[-1]
        self.assertEqual(arc.kind, 'arc_ccw')                            # vers la gauche : anti-horaire
        self.assertAlmostEqual(arc.cx, 20.0, 6)                          # tangent à la droite vers +X
        self.assertAlmostEqual(arc.cy, 40.0, 6)
        self.assertAlmostEqual(math.hypot(30 - arc.cx, 40 - arc.cy), math.hypot(20 - arc.cx, 30 - arc.cy), 6)
        self.assertFalse(any('non suivi' in w for w in tp.warnings))

    def test_other_cycles_signalled(self):
        tp = ncread.read_heidenhain('1 L X+0 Y+0 Z+5 FMAX\n2 CYCL DEF 251 POCHE RECTANGULAIRE\n3 CYCL CALL\n', 'p')
        self.assertTrue(any('non suivi' in w for w in tp.warnings))


if __name__ == '__main__':
    unittest.main()
