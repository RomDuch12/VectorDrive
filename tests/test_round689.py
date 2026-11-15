"""Round 689 : générateur STEP « Plateau à rainures en T » (Bridage : profil
extrudé posé par sa matrice, rainures ISO 299 ouvertes dessus, centrées, à
l'entraxe donné) ; volume, encombrement, solide fermé et bien tourné, la
rainure creuse et sa tête, l'écrou en T par défaut y entre ; refus dits ;
nom ; rangé dans Bridage ; faces parallèles et semblables sur le plateau."""
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


def area(v):
    W, H, n, a, b, c, h = (float(v[k]) for k in ('width', 'height', 'n', 'a', 'b', 'c', 'h'))
    return W * H - n * (a * (h - c) + b * c)


class TestBuild(_Case):
    def test_default(self):
        v = G.values('plateau_rainures')
        b, p = self.assertSolid('plateau_rainures', v)
        self.assertEqual(b.name, 'Plateau rainures 3x14 300x200x50')
        self.assertEqual(placed_bounds(b), [-100, -150, 0, 100, 150, 50])
        self.assertAlmostEqual(B.volume(b) / (area(v) * 300), 1.0, delta=1e-9)
        for x in (-63, 0, 63):                                            # trois rainures, centrées
            self.assertFalse(B.contains(b, (x, 0, 45)))                   # le col
            self.assertFalse(B.contains(b, (x + 10, 0, 30)))              # la tête, plus large
            self.assertTrue(B.contains(b, (x + 10, 0, 45)))               # au-dessus de la tête : matière
            self.assertTrue(B.contains(b, (x, 0, 20)))                    # sous la rainure
        nut = G.values('ecrou_t')
        self.assertEqual(float(nut['a']), float(v['a']))                  # l'écrou en T par défaut y entre
        self.assertLess(float(nut['e']), float(v['b']))
        self.assertLess(float(nut['k']), float(v['c']))
        self.assertLess(float(nut['h']), float(v['h']))

    def test_variants_and_name(self):
        v = G.values('plateau_rainures', n=1, length=120, width=60, height=30, a=8, b=13, c=6, h=13, pitch=5)
        b, _p = self.assertSolid('plateau_rainures', v)
        self.assertAlmostEqual(B.volume(b) / (area(v) * 120), 1.0, delta=1e-9)
        self.assertFalse(B.contains(b, (0, 0, 25)))
        v = G.values('plateau_rainures', n=6, pitch=50, width=320)
        b, _p = self.assertSolid('plateau_rainures', v)
        self.assertFalse(B.contains(b, (125, 0, 45)) or B.contains(b, (-125, 0, 45)))
        name = G.file_name('plateau_rainures', v)
        self.assertEqual(name, 'Plateau_rainures_6x14_p50_300x320x50_b23_c9_h23')
        self.assertIn('plateau_rainures', [k for k, f in G.FAMILIES.items() if f.category == 'Bridage'])

    def test_refusals(self):
        for over in ({'b': 14}, {'c': 23}, {'h': 46}, {'pitch': 25}, {'width': 150}, {'n': 0}):
            with self.assertRaises(G.GenError, msg=over):
                G.build('plateau_rainures', G.values('plateau_rainures', **over))

    def test_selection_on_the_table(self):
        p = self.path('plateau.step')
        v = G.values('plateau_rainures')
        G.write('plateau_rainures', v, p)
        m = model3d.from_step(p)
        up = [f for f in range(m.face_count()) if S.props(m, f)['kind'] == 'plan' and S.props(m, f)['normal'][2] > 0.999]
        offsets = sorted({round(S.props(m, f)['offset'], 6) for f in up})
        self.assertEqual(offsets, [27, 50])                               # fond des rainures, dessus
        self.assertEqual(S.parallel(m, up[:1]), up)
        top = [f for f in up if abs(S.props(m, f)['offset'] - 50) < 1e-6]
        self.assertEqual(len(top), 4)                                     # le dessus, coupé par 3 rainures
        self.assertEqual(S.similar(m, top[:1]), top)


if __name__ == '__main__':
    unittest.main()
