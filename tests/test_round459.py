"""Round 459 : programmes lus — avances programmées (F) relevées pour chaque mouvement (ISO,
Heidenhain), gardées par outil, et prises pour le temps estimé."""
import unittest

from vectordrive.cam import model, ncread, timing


class TestFeeds(unittest.TestCase):
    def test_iso(self):
        tp = ncread.read('G21\nG0 X0 Y0 Z5\nG1 Z-1 F100\nG1 X100 F1200\nG1 Y100 F60\n', 'a.nc')
        self.assertEqual(tp.feeds, [0.0, 100.0, 1200.0, 60.0])
        slow = timing.path_seconds(tp, model.CamSetup())
        tp.feeds = None                                                           # sans F : 600 mm/min
        self.assertGreater(slow, timing.path_seconds(tp, model.CamSetup()))
        inch = ncread.read('G20\nG0 X0 Y0 Z1\nG1 X1 F10\n', 'b.nc')
        self.assertAlmostEqual(inch.feeds[-1], 254.0)

    def test_heidenhain_and_split(self):
        hh = ncread.read('BEGIN PGM A MM\nTOOL CALL 1 Z\nL X+0 Y+0 Z+5 FMAX\nL Z-1 F100\nL X+100 F1200\n'
                         'TOOL CALL 2 Z\nL X+0 Y+10 Z+5 FMAX\nL Z-2 F50\nEND PGM A MM\n', 'a.h')
        self.assertEqual(hh.feeds, [0.0, 100.0, 1200.0, 1200.0, 50.0])
        self.assertEqual([p.feeds for p in hh.parts], [[0.0, 100.0, 1200.0], [1200.0, 50.0]])


if __name__ == '__main__':
    unittest.main()
