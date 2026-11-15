"""Round 596 : usiner une pièce 3D sur toutes ses faces — prise de chaque opération (face vers l'outil),
corps usiné seul, prises proposées (surface atteinte de chaque côté), automatisme pour chaque corps et
chaque prise avec un message « poser la pièce » entre deux prises."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round591 import feeds, pocket_stl
from tests.test_round595 import box_tris
from vectordrive.cam import auto3d as A
from vectordrive.cam import mill3d, model, strategies
from vectordrive.core import access3d as AC
from vectordrive.core import placement3d as P3
from vectordrive.core import solids as SO
from vectordrive.core.document import Document
from vectordrive.io import model3d

app = QApplication.instance() or QApplication([])


def two_boxes_stl():
    from vectordrive.io import stl_write
    t = np.concatenate([box_tris(0, 0, 0, 20, 10, 6), box_tris(40, 0, 0, 50, 10, 4)])
    f = pathlib.Path(tempfile.mkdtemp()) / 'deux.stl'
    stl_write.write_stl(str(f), t)
    return str(f)


class FakeDoc:
    def __init__(self, path, placement=None, plate=None):
        self.source_path = path
        self.extra = {P3.KEY: P3.to_dict(placement)} if placement is not None else {}
        self.plate = plate


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestSides(unittest.TestCase):
    def test_flipped_model(self):
        f = pocket_stl()
        doc = FakeDoc(f)
        up = mill3d.load_model(doc, f)
        down = mill3d.load_model(doc, f, '-Z')
        self.assertEqual(up.bounds()[2:6:3], (0.0, 10.0))
        b = down.bounds()
        self.assertAlmostEqual(b[2], -10.0, 5)
        self.assertAlmostEqual(b[5], 0.0, 5)
        self.assertIs(mill3d.load_model(doc, f, '-Z'), down)                # en mémoire

    def test_centered_side(self):
        from vectordrive.core.document import Plate
        f = pocket_stl()
        doc = FakeDoc(f, P3.Placement('+Z', 0.0, 'centre', 30.0, 40.0), Plate(x=0, y=0, width=100, height=100))
        pl = mill3d.side_placement(doc, f, '+X')
        m = model3d.placed(mill3d.raw_model(f), pl)
        x0, y0, _z0, x1, y1, _z1 = m.bounds()
        self.assertAlmostEqual((x0 + x1) / 2, 50.0, 5)                      # retournée, toujours centrée
        self.assertAlmostEqual((y0 + y1) / 2, 50.0, 5)

    def test_bottom_machining(self):
        f = pocket_stl()
        st = model.CamSetup(tools=[model.CamTool(kind='boule', diameter=4, stepover=0.3, step_down=20)])
        op = model.Operation(kind='surface3d', tool_id=st.tools[0].id, depth=0, resolution=0.25, model_path=f,
                             setup_face='-Z')
        tp = strategies.compute(Document(), st, op)
        fs = feeds(tp)
        self.assertAlmostEqual(min(mv.y for mv in fs), -22.0 - 0.25 * 10, 0)   # retournée : Y vers le bas
        inner = [mv.z for mv in fs if 0 <= mv.x <= 40 and -20 <= mv.y <= 0]
        self.assertTrue(inner)
        self.assertAlmostEqual(max(inner), 0.0, 6)                          # dessous plat : rien à creuser
        self.assertGreaterEqual(min(inner), -1e-6)
        self.assertAlmostEqual(min(mv.z for mv in fs), -10.0, 6)            # autour : jusqu'en bas

    def test_contours_follow_side(self):
        f = pocket_stl()
        sq = [[12, 7, 5], [28, 7, 5], [28, 13, 5], [12, 13, 5]]
        op = model.Operation(kind='surface3d', model_path=f, contours3d=[sq], setup_face='-Z')
        c = mill3d.zone_op(FakeDoc(f), op)
        self.assertIsNot(c, op)
        np.testing.assert_allclose(c.contours3d[0][0], [12, -7, -5], atol=1e-9)   # retournée autour de X
        self.assertEqual(op.contours3d[0][0], [12, 7, 5])                        # l'opération n'est pas touchée

    def test_body_alone(self):
        f = two_boxes_stl()
        m = mill3d.load_model(FakeDoc(f), f, '', 1)
        self.assertEqual(m.body_count(), 1)
        self.assertAlmostEqual(m.bounds()[0], 40.0, 5)
        st = model.CamSetup(tools=[model.CamTool(kind='fraise', diameter=2, stepover=0.4, step_down=10)])
        op = model.Operation(kind='surface3d', tool_id=st.tools[0].id, depth=0, resolution=0.25, model_path=f,
                             body3d=1)
        fs = feeds(strategies.compute(Document(), st, op))
        self.assertGreater(min(mv.x for mv in fs), 30.0)                   # rien sur l'autre corps
        self.assertAlmostEqual(min(mv.z for mv in fs), -4.0, 6)             # haut du corps à Z 0

    def test_reach_and_plan(self):
        m = mill3d.raw_model(pocket_stl())
        top = AC.reached(m, '+Z', 0.25)
        bottom = AC.reached(m, '-Z', 0.25)
        n = len(m.triangles)
        self.assertGreater(top.sum(), 0)
        self.assertTrue((top | bottom).all())                               # deux prises suffisent
        plan, left = AC.plan_sides(m, 0.25)
        self.assertEqual([s for s, _g in plan], ['+Z', '-Z'])
        self.assertAlmostEqual(left, 0.0, 9)
        self.assertEqual(len(top), n)


class TestPlanAll(unittest.TestCase):
    def test_groups(self):
        seq = A.builtin()['Ébauche et finition']
        tools = [model.CamTool(kind='fraise', diameter=6, cut_length=30)]
        info = A.PartInfo(50, 40, 10, 0, 40)
        out = A.plan_all(seq, tools, [], {-1: info, 0: info, 1: info}, groups=[(0, ['+Z', '-Z']), (1, ['+Z'])],
                         body_names={0: 'Noyau', 1: 'Tiroir'})
        kinds = [p.op.kind for p in out]
        self.assertEqual(kinds, ['instruction', 'ebauche3d', 'surface3d'] * 3)
        self.assertEqual(out[0].op.params['message'], 'Poser Noyau : dessus vers l\'outil')
        self.assertEqual(out[4].op.setup_face, '-Z')
        self.assertEqual(out[7].op.body3d, 1)
        self.assertIn('Tiroir', out[7].op.name)
        balls = {id(p.tool) for p in out if p.op.kind == 'surface3d'}
        self.assertEqual(len(balls), 1)                                     # outil créé une fois pour toutes
        self.assertTrue(all(p.origin == 'nouveau' for p in out if p.op.kind == 'surface3d'))
        single = A.plan_all(seq, tools, [], {-1: info}, groups=[(-1, [''])])
        self.assertEqual([p.op.kind for p in single], ['ebauche3d', 'surface3d'])   # une prise : sans message

    @unittest.skipUnless(SO.available(), 'manifold3d absent')
    def test_dialog_each_body_all_sides(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(two_boxes_stl())
            w._ensure_panel3d()
            p = w.panel3d
            self.assertTrue(p.refresh())
            dlg = p.auto3d(exec_dialog=False, sequence='Ébauche seule')
            dlg.body_mode.setCurrentIndex(dlg.body_mode.findData('chacun'))
            dlg.side_mode.setCurrentIndex(dlg.side_mode.findData('toutes'))
            self.assertEqual(dlg.groups(), [(0, ['+Z', '-Z']), (1, ['+Z', '-Z'])])
            self.assertIn('Corps 1', dlg.sides_text.text())
            self.assertIn('4 usinage(s)', dlg.summary.text())
            ops = w.cam_panel.apply_auto3d(dlg.planned)
            self.assertEqual([o.kind for o in ops].count('instruction'), 4)
            tps = {t.op_id for t in w.cam_panel.toolpaths}
            self.assertTrue(all((o.id in tps) == (o.kind != 'instruction') for o in ops))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
