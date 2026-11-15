"""Round 686 : générateur STEP « Bride ronde » (Brut et profilés) — disque à
trous sur un cercle (passage, lamés, fraisés, taraudés, le premier à l'angle
donné), alésage et centrage en saillie au besoin ; volumes, encombrements,
solides fermés et bien tournés, refus dits ; trous reconnus par « Vis dans
ce trou », tous ensemble ; alésage par « Pièce dans ce trou » ; fenêtre."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import brep as B
from vectordrive.core import stepgen as G
from tests.test_round676 import hole_face, part
from tests.test_round677 import _Case, mesh_volume, placed_bounds

app = QApplication.instance() or QApplication([])


class TestFlange(_Case):
    def test_default(self):
        v = G.values('bride_ronde')
        b, _p = self.assertSolid('bride_ronde', v)
        self.assertEqual(b.name, 'Bride ronde 120x15')
        self.assertEqual(placed_bounds(b), [-60, -60, 0, 60, 60, 15])
        r = G.CLEARANCE['M8'] / 2
        expect = math.pi * (60 ** 2 - 20 ** 2 - 6 * r * r) * 15
        self.assertAlmostEqual(mesh_volume(b) / expect, 1.0, delta=0.002)
        for k in range(6):                                                # premier trou sur +X, tous les 60°
            a = math.radians(60 * k)
            self.assertFalse(B.contains(b, (45 * math.cos(a), 45 * math.sin(a), 7)))
        self.assertTrue(B.contains(b, (45 * math.cos(math.radians(30)), 45 * math.sin(math.radians(30)), 7)))
        self.assertFalse(B.contains(b, (0, 0, 7)))                        # l'alésage

    def test_variants(self):
        for over, n in (({'hole': 'lamage'}, 2), ({'hole': 'fraisure', 'spigot': 60.0}, 3), ({'n': 0}, 1),
                        ({'n': 1}, 1), ({'hole': 'taraude', 'bore': 0.0, 'n': 3, 'start': 90.0}, 1),
                        ({'spigot': 60.0, 'spigot_height': 5.0, 'hole': 'lamage'}, 3)):
            b, _p = self.assertSolid('bride_ronde', G.values('bride_ronde', **over))
            self.assertEqual(len(b.slabs), n, over)
        b = G.build('bride_ronde', G.values('bride_ronde', spigot=60.0, spigot_height=5.0))[0]
        self.assertEqual(placed_bounds(b)[2::3], [0, 20])                  # centrage dessus, de 15 à 20
        self.assertTrue(B.contains(b, (25, 0, 18)) and not B.contains(b, (35, 0, 18)))
        b = G.build('bride_ronde', G.values('bride_ronde', n=3, start=90.0))[0]
        self.assertFalse(B.contains(b, (0, 45, 7)))                       # premier trou à 90°
        self.assertTrue(B.contains(b, (45, 0, 7)))
        names = {G.file_name('bride_ronde', G.values('bride_ronde', **o)) for o in
                 ({}, {'start': 15.0}, {'spigot': 60.0}, {'hole': 'lamage'}, {'n': 8})}
        self.assertEqual(len(names), 5)                                   # tout dans le nom
        self.assertTrue(all(c.isalnum() or c in '_.-' for nm in names for c in nm))

    def test_refusals(self):
        for over in ({'pcd': 115.0}, {'n': 40}, {'bore': 130.0}, {'spigot': 30.0}, {'pcd': 45.0},
                     {'spigot': 82.0}):
            with self.assertRaises(G.GenError, msg=over):
                G.build('bride_ronde', G.values('bride_ronde', **over))
        self.assertEqual([k for k, f in G.FAMILIES.items() if f.category == 'Brut'][-1], 'bride_ronde')

    def test_holes_take_screws_and_bore_a_bearing(self):
        from vectordrive.core import holefit as H
        from vectordrive.core import screwfit as F
        p = self.path('bride.step')
        G.write('bride_ronde', G.values('bride_ronde', hole='lamage'), p)
        T, fo, infos = part(p)
        fit = F.analyse(T, fo, infos, hole_face(infos, G.CLEARANCE['M8'] / 2))
        self.assertEqual((fit.kind, fit.through), ('lamage', True))
        self.assertTrue(np.allclose(fit.axis, (0, 0, 1)))
        pr = F.propose(fit)
        self.assertEqual((pr['family'], pr['size']), ('chc', 'M8'))
        self.assertEqual(len(F.same_holes(T, fo, infos, fit)), 6)
        b = H.bore(T, fo, infos, hole_face(infos, 20.0))                   # l'alésage Ø40 : un roulement
        self.assertEqual((b.diameter, b.depth, b.through), (40.0, 15.0, True))
        v = H.propose(b, 'roulement')
        self.assertEqual(v, {'ref': '6203'})                               # 17 × 40 × 12
        self.assertEqual(H.outside(b, H.parts(b, 'roulement', v)), (0.0, 0.0))


class TestWindow(_Case):
    def test_dialog(self):
        from vectordrive.ui.stepgen_dialog import StepGenDialog
        d = StepGenDialog(None, 'Brut', folder=self.d)
        d.select_family('bride_ronde')
        self.assertLessEqual(d.sizeHint().height(), 1000)
        out = d.save(confirm=False)
        self.assertTrue(out.endswith(G.file_name('bride_ronde', G.values('bride_ronde')) + '.step'), out)
        d.deleteLater()


if __name__ == '__main__':
    unittest.main()
