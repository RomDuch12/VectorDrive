"""Round 186 : enroulement des parcours sur un cylindre ou un cône (3 axes)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, strategies as S, wrap as WR
from vectordrive.cam.model import Move
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def line(x0, x1, y=5.0, z=-0.2, safe=5.0):
    return [Move('rapid', x0, y, safe), Move('rapid', x0, y, 1.0), Move('plunge', x0, y, z),
            Move('feed', x1, y, z), Move('rapid', x1, y, safe)]


class TestMath(unittest.TestCase):
    def test_cylinder_surface(self):
        w = WR.Wrap('cylindre_y', 20.0, origin=3.0)
        self.assertEqual(w.surface(3.0, 7.0), (3.0, 7.0, 0.0))                     # génératrice du dessus
        s = 20.0 * math.pi / 4                                                        # un huitième de tour
        x, y, z = w.surface(3.0 + s, 7.0)
        self.assertAlmostEqual(x, 3.0 + 20.0 * math.sin(math.pi / 4))
        self.assertAlmostEqual(z, 20.0 * math.cos(math.pi / 4) - 20.0)
        self.assertEqual(y, 7.0)
        wx = WR.Wrap('cylindre_x', 20.0, origin=0.0)                                   # axe selon X
        x, y, z = wx.surface(7.0, s)
        self.assertEqual(x, 7.0)
        self.assertAlmostEqual(y, 20.0 * math.sin(math.pi / 4))

    def test_apply_follows_surface(self):
        w = WR.Wrap('cylindre_y', 15.0)
        out, warn = WR.apply(line(-10.0, 10.0), w, safe_z=5.0, tol=0.01)
        self.assertEqual(warn, [])
        feeds = [m for m in out if m.kind in ('feed', 'plunge') and m.z < 0.5]
        self.assertGreater(len(feeds), 10)                                           # découpé
        for m in feeds:
            t = math.asin(m.x / 15.0)
            self.assertAlmostEqual(m.z, 15.0 * math.cos(t) - 15.0 - 0.2, places=9)   # 0,2 sous la surface
        self.assertAlmostEqual(feeds[-1].x, 15.0 * math.sin(10.0 / 15.0))          # longueur d'arc gardée
        angles = [math.asin(m.x / 15.0) for m in feeds]
        sag = max(15.0 * (1 - math.cos((b - a) / 2)) for a, b in zip(angles, angles[1:]))
        self.assertLessEqual(sag, 0.01 + 1e-12)
        self.assertEqual([m.z for m in out if m.kind == 'rapid' and m.z > 4], [5.0, 5.0])   # dégagement gardé

    def test_cone(self):
        w = WR.Wrap('cone_y', 10.0, radius2=20.0, length=50.0)
        self.assertEqual(w.radius_at(25.0), 15.0)
        out, warn = WR.apply(line(-5.0, 5.0, y=50.0), w, safe_z=5.0)
        self.assertEqual(warn, [])
        self.assertTrue(all(m.z == 5.0 + 10.0 for m in out if m.kind == 'rapid' and m.z > 10))   # au-dessus du haut
        cut = [m for m in out if m.kind == 'feed']
        t = 5.0 / 10.0                                                               # angle donné par le 1er rayon
        self.assertAlmostEqual(cut[-1].x, 20.0 * math.sin(t))
        self.assertAlmostEqual(cut[-1].z, 20.0 * math.cos(t) - 10.0 - 0.2)

    def test_refusals(self):
        self.assertEqual(WR.apply(line(0, 5), WR.Wrap('cylindre_y', 0.0), 5.0)[0], [])
        self.assertEqual(WR.apply(line(0, 5), WR.Wrap('cone_y', 10.0), 5.0)[0], [])           # cône incomplet
        out, warn = WR.apply(line(0, 30), WR.Wrap('cylindre_y', 10.0), 5.0)                    # plus de 85°
        self.assertEqual(out, [])
        self.assertIn('85°', warn[0])
        out, warn = WR.apply(line(0, 12), WR.Wrap('cylindre_y', 10.0), 5.0)                    # 69° : prévenu
        self.assertTrue(out)
        self.assertIn('biais', warn[0])
        out, _w = WR.apply(line(0, 5, y=-60.0), WR.Wrap('cone_y', 10.0, radius2=20.0, length=50.0), 5.0)
        self.assertEqual(out, [])                                                                # au-delà de la pointe
        arcs = line(0, 5)[:3] + [Move('arc_cw', 5, 5, -0.2, 2.5, 5)]
        self.assertEqual(WR.apply(arcs, WR.Wrap('cylindre_y', 10.0), 5.0)[0], [])


def doc_setup(kind='gravure', tool_kind='conique', **wrap):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(-8, 0, 16, 10)]), tool=0))
    s = model.CamSetup()
    t = model.CamTool(name='T', kind=tool_kind, diameter=2.0, angle=30.0, tip=0.1, step_down=1.0)
    s.tools = [t]
    op = model.Operation(kind=kind, tool_id=t.id, depth=0.3, **wrap)
    s.operations = [op]
    return d, s, op


class TestCompute(unittest.TestCase):
    def test_engraving_wrapped(self):
        d, s, op = doc_setup(wrap='cylindre_y', wrap_radius=12.0)
        flat = S.compute(d, s, model.Operation.from_dict({**op.to_dict(), 'wrap': 'none'}))
        tp = S.compute(d, s, op)
        self.assertLess(min(m.z for m in tp.moves), min(m.z for m in flat.moves) - 0.5)    # plus bas sur les côtés
        self.assertLess(max(abs(m.x) for m in tp.moves), 8.0)                             # serré par l'enroulement
        self.assertTrue(any('à simuler' in w for w in tp.warnings))
        self.assertEqual(model.Operation.from_dict(op.to_dict()).wrap_radius, 12.0)

    def test_cycles_and_refusals(self):
        d, s, op = doc_setup(kind='contour', tool_kind='fraise', wrap='cylindre_y', wrap_radius=30.0, side='exterieur')
        flat = S.compute(d, s, model.Operation.from_dict({**op.to_dict(), 'wrap': 'none'}))
        tp = S.compute(d, s, op)
        if flat.cycles:
            self.assertTrue(any('cycles machine remplacés' in w for w in tp.warnings))
        self.assertEqual(tp.cycles, [])
        self.assertTrue(tp.moves)
        d, s, op = doc_setup(kind='laser', tool_kind='laser', wrap='cylindre_y', wrap_radius=30.0)
        tp = S.compute(d, s, op)
        self.assertEqual(tp.moves, [])
        self.assertTrue(any('laser' in w for w in tp.warnings))
        d, s, op = doc_setup(wrap='cylindre_y')                                                     # rayon manquant
        tp = S.compute(d, s, op)
        self.assertEqual(tp.moves, [])


class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_form_action_and_mapping(self):
        from vectordrive.ui import cam_panel
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_CMDFAO_CYL_MAPPING'], 'cam_wrap_cylinder')
        self.assertEqual(TE_ACTIONS['ID_CMDFAO_CON_MAPPING'], 'cam_wrap_cone')
        _d, s, op = doc_setup()
        dlg = cam_panel.FieldsDialog(None, 'Opération', op, Document(), s.tools)
        w = dlg.widgets['wrap']
        self.assertEqual([w.itemData(i) for i in range(w.count())], list(WR.MODES))
        w.setCurrentIndex(w.findData('cone_x'))
        dlg.widgets['wrap_radius'].setValue(8.0)
        dlg.apply()
        self.assertEqual((op.wrap, op.wrap_radius), ('cone_x', 8.0))

    def test_wrap_op(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            self.assertIn('cam_wrap_cylinder', w.A)
            panel = w.cam_panel
            doc = w.canvas.doc
            d, s, _op = doc_setup()
            model.store(doc, s)
            panel.refresh()
            self.assertIsNone(panel.wrap_op('cylindre', exec_dialog=False))                # rien de choisi
            panel.ops.selectRow(0)
            op = panel.wrap_op('cylindre', exec_dialog=False)
            self.assertEqual(op.wrap, 'cylindre_y')
            op = panel.wrap_op('cone', exec_dialog=False)
            self.assertEqual(op.wrap, 'cone_y')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
