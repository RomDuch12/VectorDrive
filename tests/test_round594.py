"""Round 594 : reprise 3D (reste de l'outil d'avant), niveaux constants 3D (parois), balayage limité
aux pentes douces ; automatisme « Ébauche, reprise, finition des pentes et des parois »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
import shapely
from PySide6.QtWidgets import QApplication

from tests.test_round591 import feeds, pocket_stl
from vectordrive.cam import auto3d as A
from vectordrive.cam import mill3d, model, strategies
from vectordrive.core import solids as SO
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])


class TestHelpers(unittest.TestCase):
    def test_slopes(self):
        g = mill3d.Grid(0, 0, 50, 50, 0.1)
        X, _Y = np.meshgrid(g.xs, g.ys)
        T = -X                                               # plan à 45°
        s = mill3d.slopes(T, 0.1)
        self.assertAlmostEqual(float(np.median(s)), 45.0, 6)
        self.assertIsNone(mill3d.slope_mask(T, 0.1, 0, 90))
        self.assertFalse(mill3d.slope_mask(T, 0.1, 50, 90).any())
        self.assertTrue(mill3d.slope_mask(T, 0.1, 40, 90).all())
        a, b = np.array([True, True, False]), np.array([True, False, False])
        self.assertEqual(mill3d.combine(None, a, b).tolist(), [True, False, False])
        self.assertIsNone(mill3d.combine(None, None))

    def test_scallop_step(self):
        self.assertAlmostEqual(mill3d.scallop_step(1.0, 0.01), A.stepover_for_scallop(1.0, 0.01), 12)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestStrategies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = pocket_stl()
        cls.big = model.CamTool(kind='fraise', diameter=6, stepover=0.4, step_down=1.0)
        cls.small = model.CamTool(kind='fraise', diameter=2, stepover=0.4, step_down=1.0)
        cls.ball = model.CamTool(kind='boule', diameter=2, stepover=0.2, step_down=1.0)
        cls.setup = model.CamSetup(tools=[cls.big, cls.small, cls.ball])

    def compute(self, **kw):
        op = model.Operation(depth=0, model_path=self.f, **kw)
        return strategies.compute(Document(), self.setup, op)

    def test_rest_near_walls_only(self):
        tp = self.compute(kind='reprise3d', tool_id=self.small.id, ref_tool_id=self.big.id, resolution=0.1)
        fs = feeds(tp)
        self.assertTrue(fs)
        block, pocket = shapely.box(0, 0, 40, 20), shapely.box(10, 5, 30, 15)
        for mv in fs:                                         # à moins d'un Ø de la grosse fraise d'une paroi
            p = shapely.Point(mv.x, mv.y)
            d = min(block.exterior.distance(p), pocket.exterior.distance(p))
            self.assertLess(d, 3.0 + 0.2, (mv.x, mv.y, mv.z))
        self.assertAlmostEqual(min(mv.z for mv in fs), -5.0, 6)          # coins de la poche (r617 : reste réel)

    def test_rest_needs_previous(self):
        tp = self.compute(kind='reprise3d', tool_id=self.small.id, resolution=0.2)
        self.assertTrue(any('outil passé avant' in w for w in tp.warnings))
        tp = self.compute(kind='reprise3d', tool_id=self.big.id, ref_tool_id=self.small.id, resolution=0.2)
        self.assertTrue(any('rien à reprendre' in w for w in tp.warnings))

    def test_waterline_walls(self):
        tp = self.compute(kind='niveaux3d', tool_id=self.ball.id, resolution=0.05, slope_min=40, step_down=1.0)
        fs = feeds(tp)
        zs = sorted({round(mv.z, 6) for mv in fs})
        self.assertEqual(zs[-1], -1.0)
        self.assertEqual(zs[0], -10.0)
        at3 = [mv for mv in fs if abs(mv.z + 3) < 1e-9]
        outer = [mv for mv in at3 if mv.x < 5]
        inner = [mv for mv in at3 if 9 < mv.x < 12]
        self.assertTrue(outer and inner)                      # tour de la pièce et tour de la poche
        self.assertAlmostEqual(min(mv.x for mv in outer), -1.0, 1)      # boule Ø2 contre la paroi x 0
        self.assertAlmostEqual(min(mv.x for mv in inner), 11.0, 1)      # contre la paroi de poche x 10
        self.assertFalse(any(abs(mv.y - 10) < 2 and 13 < mv.x < 27 and abs(mv.z + 3) < 1e-9 for mv in fs))

    def test_waterline_no_walls(self):
        flat = model.Operation(kind='niveaux3d', tool_id=self.ball.id, depth=0, resolution=0.1, model_path=self.f,
                               contours3d=[[[14, 8, 5], [26, 8, 5], [26, 12, 5], [14, 12, 5]]], slope_min=40)
        tp = strategies.compute(Document(), self.setup, flat)
        self.assertTrue(any('aucune paroi' in w for w in tp.warnings), tp.warnings)

    def test_raster_gentle_slopes(self):
        tp = self.compute(kind='surface3d', tool_id=self.ball.id, resolution=0.1, slope_max=30, step_down=100)
        fs = feeds(tp)
        self.assertTrue(fs)
        steep = [mv for mv in fs if -9.5 < mv.z < -1.0 and not (11 < mv.x < 29 and 6 < mv.y < 14)]   # pente estimée : à 1 mm près aux coins
        self.assertEqual(steep, [])                           # pas de passes à mi-hauteur des parois
        tp = self.compute(kind='surface3d', tool_id=self.ball.id, resolution=0.2, slope_min=89.9, slope_max=90)
        self.assertTrue(tp.warnings or not feeds(tp))


class TestAuto(unittest.TestCase):
    def test_sequence(self):
        seq = A.all_sequences()['Ébauche, reprise, finition des pentes et des parois'][1]
        tools = [model.CamTool(kind='fraise', diameter=d, cut_length=30) for d in (2, 4, 10)] + \
            [model.CamTool(kind='boule', diameter=d, cut_length=30) for d in (1, 2)]
        out = A.plan(seq, tools, [], A.PartInfo(80, 60, 15, 1.0, 60), depth=15)
        self.assertEqual([p.op.kind for p in out], ['ebauche3d', 'reprise3d', 'surface3d', 'niveaux3d'])
        self.assertEqual(out[0].tool.diameter, 10)
        self.assertEqual(out[1].tool.diameter, 4)                     # moitié de Ø10
        self.assertEqual(out[1].op.ref_tool_id, out[0].tool.id)       # reprend le reste de l'ébauche
        self.assertEqual(out[2].op.slope_max, 50.0)
        self.assertEqual(out[3].op.slope_min, 40.0)
        self.assertAlmostEqual(out[3].op.step_down, round(A.stepover_for_scallop(1.0, 0.01), 3), 9)
        for k in ('reprise3d', 'niveaux3d'):
            self.assertIn(k, model.op_kinds())
            self.assertIn(k, mill3d.KINDS)
            self.assertIn(k, strategies.NO_CACHE_KINDS)

    @unittest.skipUnless(SO.available(), 'manifold3d absent')
    def test_apply_remaps_previous_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(pocket_stl())
            w._ensure_panel3d()
            p = w.panel3d
            p.refresh()
            dlg = p.auto3d(exec_dialog=False, sequence='Ébauche, reprise, finition des pentes et des parois')
            self.assertEqual(dlg.table.rowCount(), 4)
            ops = w.cam_panel.apply_auto3d(dlg.planned)
            s = w.cam_panel.setup()
            rough, rest = ops[0], ops[1]
            self.assertEqual(rest.ref_tool_id, rough.tool_id)          # l'outil copié dans le document
            self.assertIsNotNone(s.tool(rest.ref_tool_id))
            names = [t.name for t in w.cam_panel.toolpaths]
            self.assertEqual(len(names), 4)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
