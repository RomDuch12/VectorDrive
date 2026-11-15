"""Round 635 : brut de la pièce 3D (core.stock3d : bloc, barre ronde, plaque,
marges) — l'ébauche 3D part du haut du brut et vide tout le brut autour de
la pièce, rien hors de lui ; contrôles (pièce qui dépasse, brut trop mince) ;
automatisme 3D (longueur d'outil depuis le haut du brut) ; fenêtre Brut… ;
arêtes du brut dans la vue 3D."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from tests.test_round591 import pocket_stl
from vectordrive.cam import auto3d as A
from vectordrive.cam import mill3d, model, strategies
from vectordrive.core import solids as SO
from vectordrive.core import stock3d
from vectordrive.core.document import Document, Plate

app = QApplication.instance() or QApplication([])
PART = (0.0, 0.0, 0.0, 40.0, 20.0, 10.0)                 # bloc 40 × 20 × 10 de pocket_stl


class TestStock(unittest.TestCase):
    def test_kinds(self):
        b = stock3d.resolve(stock3d.Stock3D('marges', side=2, top=1, bottom=3), PART)
        self.assertEqual((b.x0, b.y0, b.x1, b.y1, b.top, b.bottom), (-2, -2, 42, 22, 1, -13))
        b = stock3d.resolve(stock3d.Stock3D('bloc', sx=50, sy=30, sz=15, top=2), PART)
        self.assertEqual((b.x0, b.y0, b.x1, b.y1, b.top, b.bottom), (-5, -5, 45, 25, 2, -13))
        b = stock3d.resolve(stock3d.Stock3D('bloc', sx=50, sy=30, top=2), PART)
        self.assertEqual(b.bottom, -10)                                      # hauteur 0 : la pièce et le dessus
        b = stock3d.resolve(stock3d.Stock3D('rond', diameter=50, sz=12, dx=1), PART)
        self.assertTrue(b.round)
        self.assertEqual(b.center, (21, 10))
        plate = Plate(x=-10, y=-10, width=60, height=40, thickness=12)
        b = stock3d.resolve(stock3d.Stock3D('plaque'), PART, plate)
        self.assertEqual((b.x0, b.y1, b.bottom), (-10, 30, -12))
        self.assertIsNone(stock3d.resolve(stock3d.Stock3D('plaque'), PART, None))
        self.assertIsNone(stock3d.resolve(stock3d.Stock3D('bloc'), PART))    # sans dimensions
        self.assertIsNone(stock3d.resolve(stock3d.Stock3D(), PART))

    def test_checks(self):
        ok = stock3d.resolve(stock3d.Stock3D('bloc', sx=40, sy=20, sz=10), PART)
        self.assertEqual(stock3d.check(ok, PART), [])                        # au plus juste : rien à dire
        w = stock3d.check(stock3d.resolve(stock3d.Stock3D('bloc', sx=30, sy=20, sz=8), PART), PART)
        self.assertTrue(any('dépasse du brut de 5 mm' in x for x in w), w)
        self.assertTrue(any('il manque 2 mm' in x for x in w), w)
        w = stock3d.check(stock3d.resolve(stock3d.Stock3D('rond', diameter=40), PART), PART)
        self.assertTrue(any('dépasse' in x for x in w))                      # diagonale 44,7 > 40
        self.assertEqual(stock3d.check(stock3d.resolve(stock3d.Stock3D('rond', diameter=45), PART), PART), [])

    def test_dict_and_inside(self):
        s = stock3d.Stock3D('bloc', sx=50, sy=30, top=2, material='Laiton')
        self.assertEqual(stock3d.from_dict(stock3d.to_dict(s)), s)
        self.assertEqual(stock3d.from_dict({'kind': 'pyramide', 'sx': 'x'}).kind, '')
        b = stock3d.StockBox(0, 0, 10, 10, 0, -5)
        self.assertEqual(list(b.inside([5, 11, 10.9], [5, 5, 10.9], 1.0)), [True, True, False])   # coin arrondi
        self.assertEqual(list(b.inside([0.5, 5], [5, 5], -1.0)), [False, True])                 # rétréci
        s2 = model.CamSetup.from_dict(model.CamSetup(stock3d=stock3d.to_dict(s)).to_dict())
        self.assertEqual(stock3d.of_setup(s2), s)
        self.assertEqual(model.CamSetup.from_dict({'stock3d': 'x'}).stock3d, {})

    def test_levels_above(self):
        self.assertEqual(mill3d.levels_above(2.0, 1.0), [1.0, 0.0])
        self.assertEqual(mill3d.levels_above(2.0, 0.8), [2 * (1 - 1 / 3), 2 * (1 - 2 / 3), 0.0])
        self.assertEqual(mill3d.levels_above(0.0, 1.0), [])


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestRough(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = pocket_stl()

    def run_op(self, stock=None, **kw):
        setup = model.CamSetup(tools=[model.CamTool(kind='fraise', diameter=4, stepover=0.5, step_down=1.0)],
                               stock3d=stock3d.to_dict(stock) if stock else {})
        op = model.Operation(kind='ebauche3d', tool_id=setup.tools[0].id, depth=0, resolution=0.25,
                             model_path=self.f, stock=0.3, ramp=False, **kw)
        return op, strategies.compute(Document(), setup, op)

    def test_from_stock_top(self):
        op, tp = self.run_op(stock3d.Stock3D('bloc', sx=56, sy=36, top=2))
        cut = [m for m in tp.moves if m.kind != 'rapid']
        self.assertTrue(cut, tp.warnings)
        self.assertAlmostEqual(max(m.z for m in cut if m.kind == 'feed'), 1.0, places=6)    # palier dans le dessus
        self.assertTrue(any(abs(m.z) < 1e-9 for m in cut if m.kind == 'feed'))
        r = 2.0
        box = stock3d.StockBox(-8, -8, 48, 28, 2, -10)
        self.assertTrue(all(box.inside([m.x], [m.y], 0.9 * r + 0.3)[0] for m in cut))       # jamais hors du brut
        self.assertTrue(any((m.x < -4 or m.x > 44) and m.z < -5 for m in cut))             # le brut vidé autour
        rapids = [m for m in tp.moves if m.kind == 'rapid']
        self.assertGreaterEqual(min(m.z for m in rapids), 2.0 + op.clear_z - 1e-9)        # approche au-dessus du brut
        self.assertFalse([w for w in tp.warnings if 'brut' in w])

    def test_without_stock_unchanged(self):
        _op, tp = self.run_op()
        cut = [m for m in tp.moves if m.kind == 'feed']
        self.assertLessEqual(max(m.z for m in cut), 1e-9)                     # rien au-dessus de la pièce

    def test_tight_and_small(self):
        _op, tp = self.run_op(stock3d.Stock3D('marges'))
        cut = [m for m in tp.moves if m.kind != 'rapid']
        self.assertTrue(all(-1.8 - 0.3 <= m.x <= 41.8 + 0.3 and -1.8 - 0.3 <= m.y <= 21.8 + 0.3 for m in cut))
        _op, tp = self.run_op(stock3d.Stock3D('bloc', sx=30, sy=20, sz=10))
        self.assertTrue(any('dépasse du brut' in w for w in tp.warnings), tp.warnings)

    def test_second_setup_ignores_stock(self):
        _op, tp = self.run_op(stock3d.Stock3D('bloc', sx=56, sy=36, top=2), setup_face='-Z')
        self.assertLessEqual(max(m.z for m in tp.moves if m.kind == 'feed'), 1e-9)    # retournée : brut inconnu


class TestAuto(unittest.TestCase):
    def test_tool_reach_from_stock_top(self):
        tools = [model.CamTool(kind='fraise', diameter=8, cut_length=10), model.CamTool(kind='fraise', diameter=6,
                                                                                        cut_length=15)]
        step = A.Step(kind='ebauche3d', tool_kind='fraise', rule='gros')
        info = A.PartInfo(40, 40, 10, 0, 40)
        self.assertEqual(A.pick_tool(step, tools, info).diameter, 8)
        info.stock_top = 2.0
        self.assertEqual(A.pick_tool(step, tools, info).diameter, 6)          # 10 + 2 mm à atteindre
        seq = A.Sequence(steps=[A.Step(kind='ebauche3d', tool_kind='fraise', rule='outil', tool_id=tools[0].id)])
        pl = A.plan(seq, tools, [], info)[0]
        self.assertEqual((pl.op.depth, pl.limited), (8.0, 8.0))              # le porte-outil au haut du brut


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestUi(unittest.TestCase):
    def test_dialogs_and_view(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(pocket_stl())
            w._ensure_panel3d()
            p = w.panel3d
            self.assertTrue(p.refresh())
            cp = w.cam_panel
            dlg = cp.stock_dialog(exec_dialog=False, model=p.view.model)
            dlg.kind.setCurrentIndex(dlg.kind.findData('bloc'))
            dlg.spins['top'].setValue(1.5)
            dlg.fit_to_part()
            s = dlg.value()
            self.assertEqual((s.kind, s.sx, s.sy, s.sz), ('bloc', 40, 20, 12))   # 10 + 1,5 arrondi
            self.assertIn('40 × 20 × 12 mm', dlg.info.text())
            dlg.spins['sx'].setValue(30)
            self.assertIn('dépasse', dlg.info.text())
            dlg.spins['sx'].setValue(50)
            cp.set_stock(dlg.value())
            self.assertEqual(w.canvas.doc.extra['fao']['stock3d']['sx'], 50)
            self.assertIsNotNone(p.view.stock_lines)
            self.assertEqual(len(p.view.stock_lines), 24)                     # 12 arêtes du pavé
            top = float(p.view.stock_lines[:, 2].max()) - p.view.model_dz
            self.assertAlmostEqual(top, 1.5, places=5)
            a3 = p.auto3d(exec_dialog=False, sequence='Ébauche, demi-finition, finition')
            self.assertIn('Brut : 50 × 20 × 12 mm', a3.stock_text.text())
            self.assertAlmostEqual(a3.info.stock_top, 1.5)
            cp.set_stock(stock3d.Stock3D())
            self.assertFalse(w.canvas.doc.extra['fao'].get('stock3d'))
            self.assertIsNone(p.view.stock_lines)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
