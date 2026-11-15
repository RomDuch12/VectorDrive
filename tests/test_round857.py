"""Round 857 : gamme à plusieurs outils (manuel de TE, pages 619 à 621)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.cam import gamme
from vectordrive.cam import model as M
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape
from vectordrive.ui.gamme_dialog import GammeDialog

app = QApplication.instance() or QApplication([])


def tools():
    doc = Document()
    s = M.setup_of(doc)
    s.tools[:] = []
    out = {}
    for key, name, kind, d, ang, tip in (('c_small', 'Conique 30 0,2', 'conique', 3.0, 30.0, 0.2),
                                         ('f2', 'Fraise 2', 'fraise', 2.0, 0.0, 0.0),
                                         ('c_big', 'Conique 30 0,6', 'conique', 3.0, 30.0, 0.6),
                                         ('f6', 'Fraise 6', 'fraise', 6.0, 0.0, 0.0)):
        t = M.CamTool(name=name, diameter=d)
        t.kind, t.angle, t.tip = kind, ang, tip
        s.tools.append(t)
        out[key] = t
    return s, out


class TestOrder(unittest.TestCase):

    def test_from_the_biggest_to_the_finest(self):
        s, t = tools()
        steps = [gamme.Step(x.id) for x in t.values()]
        self.assertEqual([p[1].name for p in gamme.ranked(s, steps, 0.5)],
                         ['Fraise 6', 'Fraise 2', 'Conique 30 0,6', 'Conique 30 0,2'])

    def test_a_step_without_tool_is_left_out(self):
        s, t = tools()
        self.assertEqual(len(gamme.ranked(s, [gamme.Step('rien'), gamme.Step(t['f6'].id)], 0.5)), 1)


class TestProblem(unittest.TestCase):

    def test_no_tool(self):
        s, _t = tools()
        self.assertTrue(gamme.problem(s, [], 0.5))

    def test_no_depth(self):
        s, t = tools()
        self.assertTrue(gamme.problem(s, [gamme.Step(t['f6'].id)], 0.0))

    def test_cones_of_one_angle(self):
        s, t = tools()
        self.assertEqual(gamme.problem(s, [gamme.Step(t['c_big'].id), gamme.Step(t['c_small'].id)], 0.5), '')
        t['c_small'].angle = 45.0
        self.assertIn('angle', gamme.problem(s, [gamme.Step(t['c_big'].id), gamme.Step(t['c_small'].id)], 0.5))


class TestBuild(unittest.TestCase):

    def all_four(self, **kw):
        s, t = tools()
        return s, t, gamme.build(s, [gamme.Step(x.id) for x in t.values()], 0.5, **kw)

    def test_kinds(self):
        _s, _t, ops = self.all_four()
        self.assertEqual([o.kind for o in ops], ['poche', 'reste', 'vcarve', 'vcarve'])

    def test_named_after_the_tool(self):
        _s, _t, ops = self.all_four(label='Gamme')
        self.assertEqual(ops[0].name, 'Gamme : Fraise 6')
        self.assertEqual(ops[3].name, 'Gamme : Conique 30 0,2')

    def test_each_takes_over_from_the_previous(self):
        _s, t, ops = self.all_four()
        self.assertEqual(ops[1].ref_tool_id, t['f6'].id)
        self.assertEqual(ops[2].ref_tool_id, t['f2'].id)
        self.assertEqual(ops[3].ref_tool_id, t['c_big'].id)   # round 885 : relevé dans TE13, chacun reprend le précédent
        self.assertFalse(ops[2].link_previous)
        self.assertFalse(ops[3].link_previous)

    def test_the_milling_tools_keep_away_from_the_wall(self):
        _s, t, ops = self.all_four(stock=0.1)
        wall = t['c_big'].radius_at(0.5) - t['c_big'].tip / 2  # round 885 : relevé dans TE13, sans la pointe
        self.assertAlmostEqual(ops[0].stock, 0.1 + wall, places=6)
        self.assertAlmostEqual(ops[1].stock, 0.1 + wall, places=6)
        self.assertAlmostEqual(ops[2].stock, 0.1, places=6)

    def test_no_cone_no_wall(self):
        s, t = tools()
        ops = gamme.build(s, [gamme.Step(t['f6'].id), gamme.Step(t['f2'].id)], 0.5)
        self.assertEqual([o.stock for o in ops], [0.0, 0.0])

    def test_sweep_or_contouring(self):
        s, t = tools()
        a = gamme.build(s, [gamme.Step(t['f6'].id, 'balayage', sweep_angle=30.0)], 0.5)[0]
        self.assertEqual((a.pocket_mode, a.sweep_angle), ('balayage', 30.0))
        b = gamme.build(s, [gamme.Step(t['f6'].id, 'contournage')], 0.5)[0]
        self.assertEqual(b.pocket_mode, 'concentrique')

    def test_finish_3d_or_2d_contour(self):
        s, t = tools()
        a = gamme.build(s, [gamme.Step(t['c_big'].id, finish3d=True)], 0.5)[0]
        b = gamme.build(s, [gamme.Step(t['c_big'].id, finish3d=False)], 0.5)[0]
        self.assertEqual((a.vcarve_mode, b.vcarve_mode), ('passes', 'contour'))

    def test_a_step_can_stop_higher(self):
        s, t = tools()
        ops = gamme.build(s, [gamme.Step(t['f6'].id, depth=0.2), gamme.Step(t['f2'].id, depth=0.9)], 0.5)
        self.assertEqual([o.depth for o in ops], [0.2, 0.5])  # jamais plus bas que la gamme

    def test_stepover(self):
        s, t = tools()
        ops = gamme.build(s, [gamme.Step(t['f6'].id, stepover=1.5), gamme.Step(t['c_big'].id, stepover=0.05)], 0.5)
        self.assertEqual(ops[0].stepover_mm, 1.5)
        self.assertEqual(ops[1].stepover_mm, 0.05)

    def test_settings_for_the_whole_gamme(self):
        _s, _t, ops = self.all_four(contour_ref='fond', skip_frame=True, z_start=1.0, items=['a'], safe_z=7.0)
        for o in ops:
            self.assertEqual((o.contour_ref, o.finish_skip_frame, o.z_start, o.items, o.safe_z), ('fond', True, 1.0, ['a'], 7.0))


class TestDialog(unittest.TestCase):

    def dialog(self):
        s, t = tools()
        return s, t, GammeDialog(None, s, [gamme.Step(t['f6'].id, stepover=2.0), gamme.Step(t['c_big'].id, 'contournage', finish3d=False)], 0.4)

    def test_it_shows_the_steps(self):
        _s, t, d = self.dialog()
        self.assertEqual(d.table.rowCount(), 2)
        got = d.steps()
        self.assertEqual((got[0].tool_id, got[0].mode, got[0].stepover), (t['f6'].id, 'balayage', 2.0))
        self.assertEqual((got[1].tool_id, got[1].mode, got[1].finish3d), (t['c_big'].id, 'contournage', False))
        self.assertEqual(d.depth, 0.4)

    def test_add_and_remove(self):
        _s, _t, d = self.dialog()
        d.add_btn.click()
        self.assertEqual(d.table.rowCount(), 3)
        d.table.selectRow(0)
        d.del_btn.click()
        self.assertEqual(d.table.rowCount(), 2)
        self.assertEqual(len(d.steps()), 2)

    def test_a_bad_gamme_does_not_close(self):
        _s, t, d = self.dialog()
        t['c_big'].angle = 45.0
        d.add_step(gamme.Step(t['c_small'].id))
        with mock.patch.object(QMessageBox, 'warning') as warned:
            d.accept()
        warned.assert_called_once()
        self.assertEqual(d.result(), 0)

    def test_settings(self):
        _s, _t, d = self.dialog()
        d.w_stock.setValue(0.05)
        d.w_frame.setChecked(True)
        d.w_ref.setCurrentIndex(1)
        d.w_z.setValue(1.5)
        self.assertEqual((d.stock, d.skip_frame, d.contour_ref, d.z_start), (0.05, True, 'fond', 1.5))

    def test_no_laser_in_the_list(self):
        s, t = tools()
        laser = M.CamTool(name='Laser', diameter=0.05)
        laser.kind = 'laser'
        s.tools.append(laser)
        d = GammeDialog(None, s, [gamme.Step(t['f6'].id)], 0.4)
        names = [d.table.cellWidget(0, 0).itemText(i) for i in range(d.table.cellWidget(0, 0).count())]
        self.assertFalse([n for n in names if 'Laser' in n])


class TestCommand(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()

    def setUp(self):
        w = self.win
        doc = w.canvas.doc
        self.shape = Shape(path=geom.Path([geom.rect(10, 10, 30, 20)]))
        layer = Layer(name='Plan 1', items=[self.shape])
        doc.layers[:] = [layer]
        doc.active = layer.id
        doc.plate = Plate(width=100.0, height=100.0)
        self.panel = w.cam_panel
        s = self.panel.setup()
        s.operations[:] = []
        s.tools[:] = []
        self.t = {}
        for key, name, kind, d, ang, tip in (('f4', 'Fraise 4', 'fraise', 4.0, 0.0, 0.0), ('f1', 'Fraise 1', 'fraise', 1.0, 0.0, 0.0),
                                             ('c', 'Conique 30', 'conique', 3.0, 30.0, 0.2)):
            t = M.CamTool(name=name, diameter=d)
            t.kind, t.angle, t.tip = kind, ang, tip
            s.tools.append(t)
            self.t[key] = t
        self.panel.save(s)
        w.canvas.select([self.shape])

    def steps(self):
        return [gamme.Step(self.t[k].id) for k in ('c', 'f1', 'f4')]

    def test_three_tools_three_paths(self):
        ops = self.panel.new_gamme(exec_dialog=False, steps=self.steps(), depth=0.3)
        self.assertEqual([o.kind for o in ops], ['poche', 'reste', 'vcarve'])
        self.assertEqual([o.tool_id for o in ops], [self.t[k].id for k in ('f4', 'f1', 'c')])
        self.assertEqual([o.id for o in self.panel.setup().operations], [o.id for o in ops])
        done = {tp.op_id: tp for tp in self.panel.toolpaths}
        for o in ops:
            self.assertIn(o.id, done)
        self.assertTrue(done[ops[0].id].moves)
        self.assertTrue(done[ops[2].id].moves)

    def test_they_use_the_selection(self):
        ops = self.panel.new_gamme(exec_dialog=False, steps=self.steps(), depth=0.3)
        for o in ops:
            self.assertEqual(o.items, [self.shape.id])

    def test_nothing_selected(self):
        self.win.canvas.select([])
        self.assertIsNone(self.panel.new_gamme(exec_dialog=False, steps=self.steps(), depth=0.3))
        self.assertEqual(self.panel.setup().operations, [])

    def test_different_angles_are_refused(self):
        c2 = M.CamTool(name='Conique 60', diameter=3.0)
        c2.kind, c2.angle, c2.tip = 'conique', 60.0, 0.2
        s = self.panel.setup()
        s.tools.append(c2)
        self.panel.save(s)
        self.assertIsNone(self.panel.new_gamme(exec_dialog=False, steps=[gamme.Step(self.t['c'].id), gamme.Step(c2.id)], depth=0.3))
        self.assertEqual(self.panel.setup().operations, [])

    def test_the_window_gives_the_gamme(self):
        s = self.panel.setup()
        dlg = self.panel.gamme_dialog(s, self.steps(), 0.3)
        with mock.patch.object(dlg, 'exec', return_value=1), mock.patch.object(self.panel, 'gamme_dialog', return_value=dlg):
            ops = self.panel.new_gamme()
        self.assertEqual(len(ops), 3)

    def test_the_window_can_be_cancelled(self):
        s = self.panel.setup()
        dlg = self.panel.gamme_dialog(s, self.steps(), 0.3)
        with mock.patch.object(dlg, 'exec', return_value=0), mock.patch.object(self.panel, 'gamme_dialog', return_value=dlg):
            self.assertIsNone(self.panel.new_gamme())
        self.assertEqual(self.panel.setup().operations, [])

    def test_without_steps_it_stays_two_tools(self):
        ops = self.panel.new_gamme(exec_dialog=False, rough_id=self.t['f4'].id, finish_id=self.t['c'].id)
        self.assertEqual([o.kind for o in ops], ['poche', 'vcarve'])


if __name__ == '__main__':
    unittest.main()
