"""Round 691 : générateur STEP « Cale pentée » (Bridage : profil extrudé posé
par sa matrice, dessus en pente du bout mince au bout épais le long de X) ;
volume, encombrement, pente, solide fermé et bien tourné ; refus dits ; nom
avec l'angle ; rangée dans Bridage ; le dessus lu comme un plan incliné."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import facesel as S
from vectordrive.core import stepgen as G
from vectordrive.io import model3d
from tests.test_round677 import _Case, placed_bounds

app = QApplication.instance() or QApplication([])


class TestBuild(_Case):
    def test_default(self):
        v = G.values('cale_pentee')
        b, p = self.assertSolid('cale_pentee', v)
        self.assertEqual(b.name, 'Cale pentee 100x50 5-15')
        self.assertEqual(placed_bounds(b), [-25, -50, 0, 25, 50, 15])
        self.assertAlmostEqual(B.volume(b) / (100 * 50 * 10), 1.0, delta=1e-9)
        self.assertFalse(B.contains(b, (-24, 0, 6)))                      # bout mince en X bas
        self.assertTrue(B.contains(b, (24, 0, 14)))                       # bout épais en X haut
        self.assertTrue(B.contains(b, (0, 0, 9.9)) and not B.contains(b, (0, 0, 10.1)))   # mi-pente : 10
        self.assertEqual(G.file_name('cale_pentee', v), 'Cale_pentee_100x50_h5-15_11.31deg')
        m = model3d.from_step(p)
        tops = [S.props(m, f) for f in range(m.face_count()) if S.props(m, f)['kind'] == 'plan'
                and 0.5 < S.props(m, f)['normal'][2] < 0.999]
        self.assertEqual(len(tops), 1)                                    # le dessus incliné
        self.assertAlmostEqual(math.degrees(math.acos(tops[0]['normal'][2])), math.degrees(math.atan2(10, 50)), 6)

    def test_refusals_and_place(self):
        for over in ({'h1': 0.2}, {'h2': 5}, {'h2': 4}):
            with self.assertRaises(G.GenError, msg=over):
                G.build('cale_pentee', G.values('cale_pentee', **over))
        self.assertEqual([k for k, f in G.FAMILIES.items() if f.category == 'Bridage'][-1], 'cale_pentee')


if __name__ == '__main__':
    unittest.main()
