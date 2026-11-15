"""Round 647 : la simulation part du haut du brut 3D (plus haut que la
pièce) dans son emprise — surfaçage simulé, rapide et porte-outil contrôlés
dans cette matière ; lecture pas à pas et relief étendu de même ; brut
ignoré pour les parcours d'une autre prise (autre repère)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.cam import model, relief
from vectordrive.cam import simulate as SIM
from vectordrive.core import stock3d

SB = stock3d.StockBox(0.0, 0.0, 20.0, 10.0, 1.0, -11.0)          # 1 mm au-dessus de la pièce


def path(tool, pts, op='x'):
    return model.Toolpath(op, tool.id, [model.Move(k, x, y, z) for k, x, y, z in pts])


def facing(tool):
    pts = [('rapid', -3, -1, 5), ('feed', -3, -1, 0)]
    for k, y in enumerate(np.arange(-1.0, 11.5, 3.0)):
        xa, xb = (-3, 23) if k % 2 == 0 else (23, -3)
        pts += [('feed', xa, float(y), 0), ('feed', xb, float(y), 0)]
    return path(tool, pts + [('rapid', pts[-1][1], pts[-1][2], 5)])


class TestStart(unittest.TestCase):
    def test_initial(self):
        H = SIM.initial_heights(SB, -1.0, -1.0, 0.5, (25, 45))
        self.assertEqual(H[12, 12], 1.0)                                       # X 5 Y 5 : haut du brut
        self.assertEqual(H[0, 0], 0.0)                                         # hors du brut : Z 0
        self.assertEqual(float(H.max()), 1.0)
        rnd = stock3d.StockBox(0.0, 0.0, 10.0, 10.0, 2.0, -5.0, True)
        H = SIM.initial_heights(rnd, 0.0, 0.0, 0.5, (21, 21))
        self.assertEqual((H[10, 10], H[1, 1]), (2.0, 0.0))                     # barre ronde : le disque
        self.assertEqual(float(SIM.initial_heights(None, 0, 0, 1, (3, 3)).max()), 0.0)
        flush = stock3d.StockBox(0.0, 0.0, 10.0, 10.0, 0.0, -5.0)
        self.assertEqual(float(SIM.initial_heights(flush, 0, 0, 1, (3, 3)).max()), 0.0)


class TestChecks(unittest.TestCase):
    def setUp(self):
        self.mill = model.CamTool(kind='fraise', diameter=2.0, name='Fraise 2')
        self.s = model.CamSetup(tools=[self.mill])

    def test_rapid_in_stock(self):
        tp = path(self.mill, [('rapid', -5, 5, 10), ('rapid', -5, 5, 0.5), ('rapid', 25, 5, 0.5)])
        self.assertEqual(SIM.simulate([tp], self.s, res=0.1).rapid_hits, [])     # Z 0,5 : au-dessus de la pièce
        hit = SIM.simulate([tp], self.s, res=0.1, stock=SB).rapid_hits
        self.assertEqual(len(hit), 1)
        self.assertAlmostEqual(hit[0]['depth'], 0.5, places=6)                  # dans le brut
        self.assertTrue(-1.0 - 0.1 <= hit[0]['x'] <= 21.0)                      # bord de l'outil sur le brut

    def test_facing(self):
        big = model.CamTool(kind='fraise', diameter=4.0, name='Fraise 4')
        s = model.CamSetup(tools=[big])
        tp = facing(big)
        self.assertEqual(SIM.simulate([tp], s, res=0.1, margin=1.0).removed, 0.0)
        sim = SIM.simulate([tp], s, res=0.1, margin=1.0, stock=SB)
        self.assertAlmostEqual(sim.removed, 200.0, delta=8.0)                   # 20 × 10 × 1 mm surfacés
        self.assertLessEqual(float(sim.H.max()), 1e-9)
        self.assertIs(sim.stock, SB)
        base = SIM.SimResult(SIM.initial_heights(SB, sim.x0, sim.y0, sim.res, sim.H.shape), sim.x0, sim.y0,
                             sim.res, stock=SB)
        half = SIM.simulate_range([tp], s, base, 0, len(tp.moves) // 2)        # lecture pas à pas : même matière
        step = SIM.simulate_range([tp], s, half, len(tp.moves) // 2, len(tp.moves))
        self.assertLess(float(np.abs(step.H - sim.H).max()), 1e-9)
        self.assertAlmostEqual(step.removed, sim.removed, places=6)
        self.assertGreater(float(half.H.max()), 0.5)                           # à mi-chemin : brut pas fini

    def test_holder(self):
        t = model.CamTool(kind='fraise', diameter=2.0, name='Courte', stickout=1.5, holder_diameter=20.0)
        s = model.CamSetup(tools=[t])
        tp = path(t, [('rapid', 5, 5, 5), ('feed', 5, 5, -1), ('feed', 8, 5, -1), ('rapid', 8, 5, 5)])
        self.assertEqual(SIM.simulate([tp], s, res=0.1).collisions, [])          # porte-outil à Z 0,5
        hit = SIM.simulate([tp], s, res=0.1, stock=SB).collisions
        self.assertTrue(hit)
        self.assertAlmostEqual(hit[0]['depth'], 0.5 - SIM.HOLDER_TOL, places=6)

    def test_pad(self):
        sim = SIM.simulate([facing(self.mill)], self.s, res=0.5, margin=0.5, stock=SB)
        big = relief.pad_to(sim, (-40.0, -40.0, 60.0, 50.0))
        self.assertIs(big.stock, SB)
        j, i = int(round((5 - big.y0) / big.res)), int(round((-30 - big.x0) / big.res))
        self.assertEqual(big.H[j, i], 0.0)                                      # hors du brut
        self.assertLessEqual(float(big.H.max()), 1.0)


class TestStockOf(unittest.TestCase):
    def test_setups(self):
        from tests.test_round596 import FakeDoc, two_boxes_stl
        p = two_boxes_stl()
        doc = FakeDoc(p)
        s = model.CamSetup()
        self.assertIsNone(SIM.stock_of(doc, s))                                 # aucun brut donné
        s.stock3d = stock3d.to_dict(stock3d.Stock3D('bloc', sx=60, sy=20, sz=8, top=1))
        box = SIM.stock_of(doc, s)
        self.assertEqual((box.x0, box.y0, box.x1, box.y1, box.top), (-5.0, -5.0, 55.0, 15.0, 1.0))
        top = model.Operation(kind='surface3d')
        down = model.Operation(kind='surface3d', setup_face='-Z')
        alone = model.Operation(kind='surface3d', body3d=1)
        s.operations = [top, down, alone]
        mill = model.CamTool()
        self.assertIsNotNone(SIM.stock_of(doc, s, [path(mill, [], top.id)]))
        self.assertIsNone(SIM.stock_of(doc, s, [path(mill, [], top.id), path(mill, [], down.id)]))  # retournée
        self.assertIsNone(SIM.stock_of(doc, s, [path(mill, [], alone.id)]))     # corps seul : autre repère
        self.assertIsNone(SIM.stock_of(None, s))


class TestWindow(unittest.TestCase):
    def test_dialog_relief_player(self):
        from tests.test_round596 import two_boxes_stl
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(two_boxes_stl())
            cp = w.cam_panel
            cp.set_stock(stock3d.Stock3D('bloc', sx=60, sy=20, sz=8, top=1))
            s = cp.setup()
            mill = model.CamTool(kind='fraise', diameter=4.0, name='Fraise 4')
            s.tools.append(mill)
            op = model.Operation(kind='surface3d', tool_id=mill.id)
            s.operations.append(op)
            cp.save(s)
            tp = facing(mill)
            tp.op_id = op.id
            cp.toolpaths = [tp]
            tp.shown = True
            cp.checked_paths = lambda: [tp]
            dlg = cp.simulate(exec_dialog=False)
            self.assertIsNotNone(dlg.stock)
            self.assertEqual(dlg.stock.top, 1.0)
            self.assertGreater(dlg.result.removed, 100.0)                       # le surfaçage du brut
            r = relief.from_paths(w.canvas.doc, [tp], cut=True)
            self.assertIsNotNone(r.sim.stock)
            w._ensure_panel3d()
            pl = w.panel3d.player
            pl.load([tp], r)
            self.assertEqual(float(pl.base.H.max()), 1.0)                       # lecture : départ au haut du brut
            down = model.Operation(kind='surface3d', tool_id=mill.id, setup_face='-Z')
            s = cp.setup()
            s.operations.append(down)
            cp.save(s)
            tp2 = facing(mill)
            tp2.op_id = down.id
            cp.checked_paths = lambda: [tp, tp2]
            self.assertIsNone(cp.simulate(exec_dialog=False).stock)             # autre prise mêlée : sans brut
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
