"""Round 617 : reprise 3D sur la matière vraiment laissée — surfaces atteintes par les deux outils (enveloppes),
pas leurs cotes de pointe (toute une bande au pied des parois passait pour du reste) ; un point repris une seule
fois à sa cote ; fentes où l'outil entre tout juste (segments d'un point) ; zones l'une après l'autre, segments
enchaînés au plus proche (round 619 : déplacements rapides de toujours, sûrs). Suite « Ébauche, finition,
reprise des angles » (grosse boule puis petite boule)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from tests.test_round591 import feeds, pocket_stl
from vectordrive.cam import auto3d as A
from vectordrive.cam import mill3d, model, strategies
from vectordrive.cam.advanced import envelope
from vectordrive.core import solids as SO
from vectordrive.core.document import Document


class TestHelpers(unittest.TestCase):
    def test_envelope(self):
        flat = model.CamTool(kind='fraise', diameter=2)
        ball = model.CamTool(kind='boule', diameter=2)
        T = np.zeros((21, 21))
        T[:, 11:] = -5.0                                                  # une marche à x 1,1
        E = envelope(T, 0.1, flat)
        self.assertEqual(float(E[10, 0]), 0.0)
        self.assertEqual(float(E[10, 20]), -5.0)
        self.assertEqual(float(E[10, 10]), -5.0)                          # la fraise plate rase le pied de marche
        Eb = envelope(T, 0.1, ball)
        self.assertGreater(float(Eb[10, 10]), -5.0)                       # la boule y laisse un arrondi
        self.assertTrue(np.all(Eb <= T + 1e-12))                          # au plus bas, là où passait la pointe

    def test_label(self):
        m = np.zeros((6, 8), bool)
        m[0:2, 0:2] = True
        m[4, 3:7] = True
        m[2:4, 6] = True
        m[5, 0] = True
        lab, n = mill3d.label(m)
        self.assertEqual(n, 3)
        self.assertEqual(lab[4, 3], lab[2, 6])
        self.assertEqual(int(lab[3, 3]), 0)

    def test_sequence(self):
        seq = A.builtin()['Ébauche, finition, reprise des angles']
        tools = [model.CamTool(kind='fraise', diameter=8, cut_length=60)] + \
            [model.CamTool(kind='boule', diameter=d, cut_length=60) for d in (3, 12)]
        out = A.plan(seq, tools, [], A.PartInfo(80, 96, 40, 1.5, 80), depth=40)
        self.assertEqual([(p.op.kind, p.tool.diameter) for p in out],
                         [('ebauche3d', 8), ('surface3d', 12), ('reprise3d', 3)])
        self.assertEqual(out[2].op.ref_tool_id, out[1].tool.id)           # le reste de la grosse boule
        self.assertAlmostEqual(out[2].op.stepover_mm, round(A.stepover_for_scallop(1.5, A.CRETE), 3), 9)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestRest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = pocket_stl()                                              # bloc 40 × 20 × 10, poche 20 × 10 de 5

    def rest(self, small, big, **kw):
        st = model.CamSetup(tools=[big, small])
        op = model.Operation(kind='reprise3d', tool_id=small.id, ref_tool_id=big.id, depth=0, model_path=self.f,
                             resolution=0.1, **kw)
        return strategies.compute(Document(), st, op)

    def test_only_the_pocket_corners(self):
        big = model.CamTool(kind='fraise', diameter=6, stepover=0.4, step_down=1.0)
        small = model.CamTool(kind='fraise', diameter=2, stepover=0.4, step_down=1.0)
        fs = feeds(self.rest(small, big))
        P = np.array([(m.x, m.y, m.z) for m in fs])
        corners = np.array([(10, 5), (30, 5), (10, 15), (30, 15)])
        d = np.min(np.linalg.norm(P[:, None, :2] - corners[None], axis=2), axis=1)
        self.assertLess(d.max(), 4.0)                                     # rien le long des parois droites
        self.assertAlmostEqual(P[:, 2].min(), -5.0, 6)                    # jusqu'au fond de la poche
        for c in corners:                                                 # chaque coin repris
            self.assertTrue((np.linalg.norm(P[:, :2] - c, axis=1) < 2.5).any(), c)   # lignes sur la grille : pas au ras
        keys = {(round(m.x, 3), round(m.y, 3), round(m.z, 3)) for m in fs}
        self.assertGreater(len(keys), 0.9 * len(fs))                      # pas le même trajet palier après palier

    def test_rapids_stay_clear(self):
        big = model.CamTool(kind='boule', diameter=6, step_down=1.0)
        small = model.CamTool(kind='boule', diameter=2, step_down=1.0)
        tp = self.rest(small, big, stepover_mm=0.3)
        self.assertTrue(feeds(tp))
        m = mill3d.load_model(Document(), self.f)
        for mv in tp.moves:
            if mv.kind != 'rapid':
                continue
            inside = 0 < mv.x < 40 and 0 < mv.y < 20
            pocket = 10 < mv.x < 30 and 5 < mv.y < 15
            floor = -5.0 if pocket else (0.0 if inside else -10.0)
            self.assertGreaterEqual(mv.z, floor - 1e-6, (mv.x, mv.y, mv.z))   # jamais dans la pièce
        ups = [b.z - a.z for a, b in zip(tp.moves, tp.moves[1:]) if b.kind == 'rapid' and b.z > a.z + 1e-9]
        self.assertLess(len(ups), 150)                                    # avant : 1 184 remontées, 3 188 mm
        self.assertLess(sum(ups), 400.0)
        self.assertIsNotNone(m)

    def test_narrow_slot(self):
        from vectordrive.io import stl_write
        import pathlib
        s = SO.boolean('subtract', [SO.box(0, 0, 0, 40, 30, 10), SO.box(10, 5, 4, 4.3, 20, 10)])   # fente de 4,3
        f = pathlib.Path(tempfile.mkdtemp()) / 'fente.stl'
        stl_write.write_stl(str(f), s.triangles())
        big = model.CamTool(kind='fraise', diameter=8, step_down=2.0)
        small = model.CamTool(kind='fraise', diameter=4, step_down=2.0, stepover=0.4)
        st = model.CamSetup(tools=[big, small])
        op = model.Operation(kind='reprise3d', tool_id=small.id, ref_tool_id=big.id, depth=0, model_path=str(f),
                             resolution=0.1)
        fs = feeds(strategies.compute(Document(), st, op))
        inslot = [mv for mv in fs if 10 < mv.x < 14.3 and 5 < mv.y < 25]
        self.assertTrue(inslot)                                           # la Ø4 entre dans la fente de 4,3
        self.assertAlmostEqual(min(mv.z for mv in inslot), -6.0, 6)
        ys = sorted({round(mv.y, 1) for mv in inslot})
        self.assertGreater(len(ys), 8)                                    # tout le long de la fente
        self.assertLess(max(np.diff(ys)), 2.0 + 1e-9)


if __name__ == '__main__':
    unittest.main()
