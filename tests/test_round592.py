"""Round 592 : ébauche 3D par paliers en Z (pièce STEP, STL, 3D XML) — à chaque palier, ce que l'outil
peut enlever sans entamer la pièce ni sa surépaisseur, vidé en anneaux ; un palier juste au-dessus de
chaque fond plat ; zone limitée aux faces ou contours choisis ; courbes de niveau de la carte."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
import shapely
from PySide6.QtWidgets import QApplication

from tests.test_round591 import face_under, feeds, pocket_stl
from vectordrive.cam import mill3d, model, strategies
from vectordrive.core import solids as SO
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])


class TestIso(unittest.TestCase):
    def grid(self, n=101, res=0.1):
        return mill3d.Grid(-5.0, -5.0, n, n, res)

    def test_disk(self):
        g = self.grid()
        X, Y = np.meshgrid(g.xs, g.ys)
        reg = mill3d.iso_region(np.hypot(X, Y) - 3.0, g)
        self.assertAlmostEqual(reg.area, math.pi * 9, delta=0.05)
        self.assertEqual(reg.geom_type, 'Polygon')

    def test_ring_and_island(self):
        g = self.grid()
        X, Y = np.meshgrid(g.xs, g.ys)
        R = np.hypot(X, Y)
        F = np.where((R < 4) & (R > 2), -1.0, 1.0)            # anneau
        F[R < 1] = -1.0                                      # îlot au milieu du trou
        reg = mill3d.iso_region(F, g)
        self.assertEqual(len(reg.geoms), 2)
        self.assertFalse(reg.contains(shapely.Point(1.5, 0)))   # le trou
        self.assertTrue(reg.contains(shapely.Point(0, 0)))      # l'îlot
        self.assertTrue(reg.contains(shapely.Point(3, 0)))

    def test_edges_close(self):
        g = self.grid(11, 1.0)
        F = np.full((11, 11), -1.0)                          # tout dedans : bordée de dehors, fermée
        reg = mill3d.iso_region(F, g)
        self.assertAlmostEqual(reg.area, 11 * 11 - 0.5, delta=1e-9)   # bord à mi-chemin du dehors, coins coupés
        self.assertEqual(len(mill3d.iso_segments(np.ones((5, 5)), g)), 0)

    def test_levels_with_floors(self):
        H = np.full((50, 50), -10.0)
        H[10:40, 10:40] = 0.0
        H[20:30, 20:30] = -5.0                               # fond plat à −5 (1 mm², pas 0,1 : 100 points)
        self.assertEqual(mill3d.flat_heights(H, 0.1, 0.5), [0.0, -5.0, -10.0])
        op = model.Operation(stock=0.3, step_down=2.0)
        tool = model.CamTool(kind='fraise', diameter=0.4)
        zs = mill3d.rough_levels(op, tool, 10.0, H, 0.1)
        self.assertIn(-4.65, [round(z, 2) for z in zs])      # fond + surépaisseur + demi-pas
        self.assertIn(-9.65, [round(z, 2) for z in zs])
        self.assertEqual(zs, sorted(zs, reverse=True))


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestRough(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = pocket_stl()
        cls.setup = model.CamSetup(tools=[model.CamTool(kind='fraise', diameter=3, stepover=0.4, step_down=1.0)])

    def run_op(self, **kw):
        op = model.Operation(kind='ebauche3d', tool_id=self.setup.tools[0].id, depth=0, resolution=0.2,
                             model_path=self.f, stock=0.3, ramp=True, **kw)
        return strategies.compute(Document(), self.setup, op)

    def clearance(self, fs):
        block, pocket = shapely.box(0, 0, 40, 20), shapely.box(10, 5, 30, 15)
        out = []
        for mv in fs:
            if mv.z >= -1e-9:
                continue
            solid = block if mv.z < -5 + 1e-9 else block.difference(pocket)
            p = shapely.Point(mv.x, mv.y)
            out.append(-solid.exterior.distance(p) if solid.contains(p) else solid.distance(p))
        return min(out)

    def test_whole_piece(self):
        tp = self.run_op()
        fs = feeds(tp)
        self.assertGreaterEqual(self.clearance(fs), 1.8 - 1e-6)            # rayon + surépaisseur respectés
        inpocket = [mv.z for mv in fs if 12 < mv.x < 28 and 7 < mv.y < 13]
        self.assertAlmostEqual(min(inpocket), -4.6, 6)                    # palier au-dessus du fond de poche
        self.assertAlmostEqual(min(mv.z for mv in fs), -9.6, 6)           # autour : jusqu'au bas
        self.assertLess(min(mv.x for mv in fs), -1.8)                     # tout autour de la pièce
        self.assertTrue(any(mv.kind == 'feed' and 0 > mv.z > -1 and mv.z not in (-1.0,) for mv in fs))  # rampes

    def test_pocket_floor_only(self):
        m = mill3d.load_model(Document(), self.f)
        tp = self.run_op(faces3d=[face_under(m, 20, 10)])
        fs = feeds(tp)
        self.assertTrue(fs)
        self.assertTrue(all(10 < mv.x < 30 and 5 < mv.y < 15 for mv in fs))   # rien autour de la pièce
        self.assertAlmostEqual(min(mv.z for mv in fs), -4.6, 6)

    def test_nothing_to_remove(self):
        tp = self.run_op(contours3d=[[[50, 50, 0], [60, 50, 0], [60, 60, 0], [50, 60, 0]]])
        self.assertTrue(any('hors de la pièce' in w or 'rien à enlever' in w for w in tp.warnings), tp.warnings)

    def test_kinds(self):
        self.assertIn('ebauche3d', model.op_kinds())
        self.assertIn('ebauche3d', mill3d.KINDS)
        self.assertIn('ebauche3d', strategies.NO_CACHE_KINDS)
        from vectordrive.cam import toolprefs
        self.assertEqual(toolprefs.DEFAULTS['ebauche3d']['sort'], 'd_desc')


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestPanel(unittest.TestCase):
    def test_whole_piece_rough(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(pocket_stl())
            w._ensure_panel3d()
            p = w.panel3d
            self.assertTrue(p.refresh())
            p._fill_use_menu()
            labels = [a.text() for a in p.use_menu.actions()]
            self.assertTrue(any('Ébauche 3D de toute la pièce' in t for t in labels))
            o = p.machine_selection('ebauche3d', whole=True, exec_dialog=False)
            self.assertEqual((o.kind, o.faces3d, o.contours3d, o.stock, o.ramp), ('ebauche3d', [], [], 0.3, True))
            self.assertEqual(w.cam_panel.setup().tool(o.tool_id).kind, 'fraise')
            tp = next(t for t in w.cam_panel.toolpaths if t.op_id == o.id)
            self.assertTrue(tp.moves)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
