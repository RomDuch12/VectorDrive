"""Round 683 : générateurs STEP « Vé de bridage » (Bridage : profil extrudé posé par sa matrice, vé à 90 ou
120°, gorge au fond) et « Plaque de moule » (Moule : quatre alésages de guidage aux coins dont un décalé,
lamés au besoin, empreinte en poche au besoin) ; volumes, encombrements, solides fermés et bien tournés,
refus dits ; alésages de la plaque reconnus par « Pièce dans ce trou », la douille proposée dans les quatre,
collerette dans le lamage ; fenêtre."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import holefit as H
from vectordrive.core import stepgen as G
from tests.test_round676 import hole_face, part
from tests.test_round677 import _Case, mesh_volume, placed_bounds

app = QApplication.instance() or QApplication([])


def v_area(v):
    """Aire du profil du vé : le bloc moins le vé (jusqu'à la gorge) et la gorge."""
    W, Hh, b, g, gd = (float(v[k]) for k in ('width', 'height', 'opening', 'relief', 'relief_depth'))
    t = math.tan(math.radians(float(v['angle']) / 2))
    depth = b / 2 / t
    if g <= 0:
        return W * Hh - b * depth / 2
    y_g = Hh - depth + g / 2 / t
    return W * Hh - (b + g) / 2 * (Hh - y_g) - g * (y_g - (Hh - depth - gd))


def rounded_area(length, width, r):
    return length * width - (4 - math.pi) * r * r


class TestVBlock(_Case):
    def test_default(self):
        v = G.values('ve')
        b, _p = self.assertSolid('ve', v)
        self.assertEqual(b.name, 'Ve 90 60x60x40')
        self.assertEqual(placed_bounds(b), [-30, -30, 0, 30, 30, 40])      # centré, long de Y, dessous à Z = 0
        self.assertAlmostEqual(mesh_volume(b) / (v_area(v) * 60), 1.0, delta=1e-6)
        self.assertFalse(B.contains(b, (0, 0, 39)))                         # ouvert en haut, sur toute la longueur
        self.assertFalse(B.contains(b, (0, 29, 39)))
        self.assertTrue(B.contains(b, (25, 0, 39)) and B.contains(b, (0, 0, 10)))
        self.assertFalse(B.contains(b, (0, 0, 18)))                         # la gorge sous la pointe (17 à 22)
        self.assertTrue(B.contains(b, (0, 0, 16.5)))
        for side in (1, -1):                                                # flancs à 45° : à Z = 30, x = 10
            self.assertTrue(B.contains(b, (side * 10.1, 0, 30)))
            self.assertFalse(B.contains(b, (side * 9.9, 0, 30)))

    def test_angle_and_plain(self):
        v = G.values('ve', angle=120.0, relief=0.0, length=100.0)
        b, _p = self.assertSolid('ve', v)
        self.assertEqual(G.file_name('ve', v), 'Ve_120_100x60x40_o40')
        self.assertAlmostEqual(mesh_volume(b) / (v_area(v) * 100), 1.0, delta=1e-6)
        tip = 40 - 20 / math.tan(math.radians(60))                          # pointe du vé
        self.assertTrue(B.contains(b, (0, 0, tip - 0.05)))
        self.assertFalse(B.contains(b, (0, 0, tip + 0.05)))
        self.assertEqual(len(b.slabs[0].loops[0].pts), 7)

    def test_refusals(self):
        for over in ({'opening': 58.0}, {'height': 20.0}, {'relief': 40.0}, {'relief_depth': 0.0},
                     {'relief_depth': 18.0}):
            with self.assertRaises(G.GenError, msg=over):
                G.build('ve', G.values('ve', **over))
        self.assertIn('ve', [k for k, f in G.FAMILIES.items() if f.category == 'Bridage'])


class TestMouldPlate(_Case):
    def test_default(self):
        v = G.values('plaque_moule')
        b, _p = self.assertSolid('plaque_moule', v)
        self.assertEqual(b.name, 'Plaque de moule 196x196x36')
        self.assertEqual(placed_bounds(b), [0, 0, 0, 196, 196, 36])          # coin à l'origine
        bores = 4 * (math.pi * 10 ** 2 * 36 + math.pi * (13 ** 2 - 10 ** 2) * 5)
        expect = 196 * 196 * 36 - bores - rounded_area(80, 60, 5) * 15
        self.assertAlmostEqual(mesh_volume(b) / expect, 1.0, delta=0.002)
        self.assertFalse(B.contains(b, (33.5, 174, 18)))                    # le 4e alésage décalé de 2 en X
        self.assertTrue(B.contains(b, (11, 174, 18)))
        self.assertFalse(B.contains(b, (34, 22, 34)))                       # lamage Ø26 sur 5
        self.assertTrue(B.contains(b, (34, 22, 20)))
        self.assertFalse(B.contains(b, (98, 98, 30)))                       # empreinte de 15
        self.assertTrue(B.contains(b, (98, 98, 10)))

    def test_variants(self):
        for over, n in (({'counterbore': 0}, 2), ({'cavity_length': 0}, 2), ({'offset': 0}, 3),
                        ({'counterbore': 0, 'cavity_length': 0}, 1), ({'cavity_corner': 0}, 3),
                        ({'cavity_corner': 100}, 3), ({'counterbore_depth': 15}, 2), ({'offset': -4}, 3),
                        ({'cavity_length': 160}, 3)):                     # longue, entre les alésages
            b, _p = self.assertSolid('plaque_moule', G.values('plaque_moule', **over))
            self.assertEqual(len(b.slabs), n, over)
        self.assertNotEqual(G.file_name('plaque_moule', G.values('plaque_moule')),
                            G.file_name('plaque_moule', G.values('plaque_moule', bore=16.0)))

    def test_refusals(self):
        for over in ({'inset': 10.0}, {'counterbore': 18.0}, {'counterbore_depth': 36.0},
                     {'cavity_depth': 36.0}, {'cavity_length': 160.0, 'cavity_width': 160.0}, {'offset': 150.0},
                     {'length': 50.0}, {'cavity_width': 196.0}):
            with self.assertRaises(G.GenError, msg=over):
                G.build('plaque_moule', G.values('plaque_moule', **over))
        self.assertEqual([k for k, f in G.FAMILIES.items() if f.category == 'Moule'][-1], 'plaque_moule')

    def test_bores_take_bushings(self):
        p = self.path('plaque.step')
        G.write('plaque_moule', G.values('plaque_moule'), p)
        T, fo, infos = part(p)
        b = H.bore(T, fo, infos, hole_face(infos, 10.0))
        self.assertEqual((b.diameter, b.depth, b.through), (20.0, 31.0, True))   # sous le lamage
        self.assertEqual(len(H.same_bores(T, fo, infos, b)), 4)
        v = H.propose(b, 'douille')
        self.assertEqual((v['D'], v['length'], v['D2'], v['h']), (20.0, 36.0, 25.0, 5.0))
        bs = H.parts(b, 'douille', v)
        P = np.concatenate([B.mesh(x).reshape(-1, 3) for x in bs])
        self.assertAlmostEqual(float(P[:, 2].min()), 0.0, 6)               # au ras du dessous
        self.assertAlmostEqual(float(P[:, 2].max()), 36.0, 6)              # collerette dans le lamage, au ras
        top = P[np.isclose(P[:, 2], 36.0)]
        self.assertLessEqual(float(np.hypot(top[:, 0] - b.entry[0], top[:, 1] - b.entry[1]).max()), 12.5 + 1e-6)
        c = H.bore(T, fo, infos, hole_face(infos, 13.0))                   # le lamage : borgne de 5
        self.assertEqual((c.diameter, c.depth, c.through), (26.0, 5.0, False))


class TestWindow(_Case):
    def test_dialog(self):
        from vectordrive.ui.stepgen_dialog import StepGenDialog
        for cat, key in (('Bridage', 've'), ('Moule', 'plaque_moule')):
            d = StepGenDialog(None, cat, folder=self.d)
            d.select_family(key)
            self.assertEqual(d.key, key)
            self.assertLessEqual(d.sizeHint().height(), 1000, key)                 # 12 réglages : tient en Full HD
            out = d.save(confirm=False)
            self.assertTrue(os.path.isfile(out) and out.endswith(G.file_name(key, G.values(key)) + '.step'), out)
            d.deleteLater()


if __name__ == '__main__':
    unittest.main()
