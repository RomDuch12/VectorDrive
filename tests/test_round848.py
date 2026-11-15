"""Round 848 : reprise d'usinage. Reprendre un parcours en cours de route, sans jamais reprendre à une mauvaise place."""
import dataclasses
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model as M, restart as RS, strategies as S
from vectordrive.cam.model import Move, Toolpath
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape
from vectordrive.ui.main_window import MainWindow


def job(n=4, **kw):
    """`n` carrés gravés côte à côte, un seul passage chacun."""
    d = Document()
    d.plate = None
    for k in range(n):
        d.add(Shape(path=geom.Path([geom.rect(k * 20.0, 0, 10, 10)]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F', diameter=1.0)
    setup.tools = [t]
    kw.setdefault('kind', 'gravure')
    kw.setdefault('side', 'sur')
    kw.setdefault('depth', 0.5)
    kw.setdefault('step_down', 0.5)
    op = M.Operation(tool_id=t.id, **kw)
    setup.operations = [op]
    return d, setup, op


def path(**kw):
    d, setup, op = job(**kw)
    tp = S.compute(d, setup, op)
    return d, setup, op, tp


class TestPoints(unittest.TestCase):

    def test_entries(self):
        _d, _s, _o, tp = path()
        self.assertEqual(len(RS.entries(tp.moves)), 4)

    def test_a_laser_enters_at_the_surface(self):
        _d, _s, _o, tp = path(depth=0.0, step_down=0.0)
        self.assertEqual(len(RS.entries(tp.moves)), 4)

    def test_rapids_are_not_points(self):
        _d, _s, _o, tp = path()
        self.assertTrue(all(tp.moves[i].kind != 'rapid' for i in RS.rows(tp.moves)))

    def test_a_ramp_counts_once(self):
        _d, _s, _o, tp = path(ramp=True)
        self.assertEqual(len(RS.entries(tp.moves)), 4)


class TestCut(unittest.TestCase):

    def setUp(self):
        _d, _s, self.op, self.tp = path()
        self.moves = self.tp.moves
        self.entries = RS.entries(self.moves)

    def test_it_starts_above_the_point_and_ends_at_the_clearance(self):
        at = self.entries[2]
        out = RS.cut(self.moves, at, len(self.moves) - 1, self.op.safe_z, self.op.clear_z)
        m = self.moves[at]
        self.assertEqual((out[0].kind, out[0].x, out[0].y, out[0].z), ('rapid', m.x, m.y, self.op.safe_z))
        self.assertEqual((out[1].kind, out[1].z), ('rapid', self.op.clear_z))
        self.assertEqual((out[2].kind, out[2].x, out[2].y, out[2].z), ('plunge', m.x, m.y, m.z))
        self.assertEqual((out[-1].kind, out[-1].z), ('rapid', self.op.safe_z))

    def test_it_machines_only_what_comes_after(self):
        at = self.entries[2]
        out = RS.cut(self.moves, at, len(self.moves) - 1, self.op.safe_z, self.op.clear_z)
        cutting = [m for m in out if m.z < -1e-9 and m.kind == 'feed']
        self.assertTrue(cutting)
        self.assertTrue(all(m.x >= 40.0 - 1e-9 for m in cutting), [m.x for m in cutting])
        self.assertEqual(len(RS.entries(out)), 2)

    def test_resuming_in_the_middle_of_a_contour(self):
        """Un point en plein contour : l'outil y redescend, puis finit le contour."""
        at = next(i for i in RS.rows(self.moves) if i > self.entries[1] + 1)
        out = RS.cut(self.moves, at, self.entries[2] - 1, self.op.safe_z, self.op.clear_z)
        self.assertEqual(out[2].kind, 'plunge')
        self.assertEqual((out[2].x, out[2].y), (self.moves[at].x, self.moves[at].y))
        self.assertTrue(all(m.x < 40.0 for m in out))

    def test_stopping_early(self):
        out = RS.cut(self.moves, self.entries[0], self.entries[2] - 1, self.op.safe_z, self.op.clear_z)
        self.assertEqual(len(RS.entries(out)), 2)
        self.assertEqual(out[-1].z, self.op.safe_z)

    def test_an_arc_keeps_its_start(self):
        moves = [Move('rapid', 0, 0, 5), Move('plunge', 0, 0, -1), Move('feed', 10, 0, -1),
                 Move('arc_ccw', 10, 10, -1, cx=10, cy=5), Move('rapid', 10, 10, 5)]
        out = RS.cut(moves, 2, 3, 5.0, 1.0)
        self.assertEqual((out[2].x, out[2].y), (10, 0))
        self.assertTrue(out[3].is_arc)
        self.assertEqual((out[3].cx, out[3].cy), (10, 5))


class TestOperation(unittest.TestCase):

    def test_the_program_is_cut_with_a_message(self):
        d, setup, op, tp = path()
        at = RS.entries(tp.moves)[2]
        RS.choose(op, tp.moves, at, len(tp.moves) - 1)
        out = S.compute_all(d, setup)[0]
        self.assertEqual(len(RS.entries(out.moves)), 2)
        self.assertTrue(any(w.startswith(RS.NOTE) and '2 entrée(s) dans la matière sur 4' in w for w in out.warnings), out.warnings)

    def test_the_choice_survives_a_save(self):
        d, setup, op, tp = path()
        at = RS.entries(tp.moves)[2]
        RS.choose(op, tp.moves, at, len(tp.moves) - 1)
        M.store(d, setup)
        back = M.setup_of(d).operations[0]
        self.assertEqual((back.restart_from, back.restart_to, back.restart_sig), (op.restart_from, op.restart_to, op.restart_sig))

    def test_a_changed_path_is_machined_in_full_and_says_so(self):
        d, setup, op, tp = path()
        RS.choose(op, tp.moves, RS.entries(tp.moves)[2], len(tp.moves) - 1)
        d.add(Shape(path=geom.Path([geom.rect(100.0, 0, 10, 10)]), tool=1))
        out = S.compute_all(d, setup)[0]
        self.assertEqual(len(RS.entries(out.moves)), 5)
        self.assertTrue(any('ignorée' in w for w in out.warnings), out.warnings)

    def test_choosing_all_is_no_restart(self):
        _d, _s, op, tp = path()
        keep = RS.rows(tp.moves)
        RS.choose(op, tp.moves, keep[0], keep[-1])
        self.assertEqual(op.restart_sig, '')

    def test_applying_twice_is_the_same(self):
        d, setup, op, tp = path()
        RS.choose(op, tp.moves, RS.entries(tp.moves)[1], len(tp.moves) - 1)
        tps = S.compute_all(d, setup)
        once = list(tps[0].moves)
        S.apply_faced_all(setup, tps)
        self.assertEqual(tps[0].moves, once)
        self.assertEqual(sum(1 for w in tps[0].warnings if w.startswith(RS.NOTE)), 1)

    def test_forgetting_gives_the_whole_path_back(self):
        d, setup, op, tp = path()
        n = len(tp.moves)
        RS.choose(op, tp.moves, RS.entries(tp.moves)[1], n - 1)
        tps = S.compute_all(d, setup)
        self.assertLess(len(tps[0].moves), n)
        RS.forget(op)
        S.apply_faced_all(setup, tps)
        self.assertEqual(len(tps[0].moves), n)
        self.assertFalse(any(w.startswith(RS.NOTE) for w in tps[0].warnings))

    def test_cycles_do_not_bring_every_hole_back(self):
        tp = Toolpath(op_id='a', tool_id='t', moves=[Move('rapid', 0, 0, 5), Move('plunge', 0, 0, -1), Move('rapid', 0, 0, 5),
                                                     Move('rapid', 9, 0, 5), Move('plunge', 9, 0, -1), Move('rapid', 9, 0, 5)],
                      cycles=[{'kind': 'percage', 'x': 0, 'y': 0}, {'kind': 'percage', 'x': 9, 'y': 0}])
        op = M.Operation(safe_z=5.0, clear_z=1.0)
        RS.choose(op, tp.moves, 4, 4)
        self.assertTrue(RS.apply(op, tp))
        self.assertEqual(tp.cycles, [])
        RS.restore(tp)
        self.assertEqual(len(tp.cycles), 2)
        self.assertEqual(len(tp.moves), 6)

    def test_the_next_operation_starts_from_the_full_path(self):
        """Le suivant part de là où le parcours complet s'arrête : sa reprise ne doit pas le changer."""
        d, setup, op, tp = path()
        other = dataclasses.replace(op, id='autre')
        setup.operations.append(other)
        ref = S.compute_all(d, setup)[1]
        RS.choose(op, S.compute_all(d, setup)[0].moves, RS.entries(tp.moves)[2], RS.entries(tp.moves)[3] - 1)
        now = S.compute_all(d, setup)
        self.assertEqual(now[1].moves, ref.moves)

    def test_a_restart_does_not_force_a_new_calculation(self):
        d, setup, op, tp = path()
        S.clear_toolpath_cache()
        full = S.compute_all(d, setup)[0]
        RS.choose(op, full.moves, RS.entries(full.moves)[2], len(full.moves) - 1)
        S.compute_all(d, setup)
        self.assertEqual(S.LAST_RUN['computed'], 0)
        self.assertEqual(S.LAST_RUN['reused'], 1)


class TestPanel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.doc = self.win.canvas.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = None
        self.doc.extra.pop('fao', None)
        for k in range(3):
            self.layer.items.append(Shape(path=geom.Path([geom.rect(k * 20.0, 0, 10, 10)]), tool=1))
        self.panel = self.win.cam_panel
        s = self.panel.setup()
        t = M.CamTool(name='F', diameter=1.0)
        s.tools = [t]
        s.operations = [M.Operation(name='Gravure', kind='gravure', side='sur', depth=0.5, step_down=0.5, tool_id=t.id)]
        self.panel.save(s)
        self.panel.refresh() if hasattr(self.panel, 'refresh') else None
        self.panel.toolpaths = []
        self.panel._select_row(self.panel.ops, 0)

    def test_the_menu_offers_it(self):
        m = self.panel.op_menu(exec_menu=False)
        self.assertIn('Reprise d\'usinage…', [a.text() for a in m.actions()])
        m.deleteLater()

    def test_choosing_cuts_the_shown_path(self):
        self.panel.compute_op(self.panel._current_op()[2])
        tp = next(t for t in self.panel.toolpaths if t.op_id)
        at = RS.entries(tp.moves)[1]
        got = self.panel.restart_op(params={'start': at, 'end': len(tp.moves) - 1})
        self.assertIsNotNone(got)
        tp = next(t for t in self.panel.toolpaths if t.op_id)
        self.assertEqual(len(RS.entries(tp.moves)), 2)
        self.assertEqual(self.panel._current_op()[2].restart_from, at)

    def test_the_dialog(self):
        from vectordrive.ui.restart_dialog import RestartDialog
        d, s, op, tp = path(n=3)
        dlg = RestartDialog(self.win, 'x', tp.moves, op)
        self.assertEqual(dlg.model.rowCount(), 3)
        dlg.only_entries.setChecked(False)
        self.assertEqual(dlg.model.rowCount(), len(RS.rows(tp.moves)))
        keep = RS.rows(tp.moves)
        self.assertEqual((dlg.start, dlg.end), (keep[0], keep[-1]))
        dlg.set_point('start', keep[5])
        dlg.set_point('end', keep[2])
        self.assertEqual((dlg.start, dlg.end), (keep[0], keep[2]))
        dlg.set_point('start', keep[4])
        self.assertEqual((dlg.start, dlg.end), (keep[4], keep[-1]))
        self.assertIn(str(keep[4] + 1), dlg.summary.text())
        dlg.reset()
        self.assertEqual((dlg.start, dlg.end), (keep[0], keep[-1]))
        for r in range(dlg.model.rowCount()):
            dlg.model.index(r, 2).data()
        dlg.deleteLater()

    def test_the_dialog_is_used_by_the_command(self):
        self.panel.compute_op(self.panel._current_op()[2])
        with mock.patch('vectordrive.ui.restart_dialog.RestartDialog.exec', return_value=0):
            self.assertIsNone(self.panel.restart_op())
        self.assertEqual(self.panel._current_op()[2].restart_sig, '')

    def test_the_row_shows_it(self):
        o = M.Operation(name='Gravure', kind='gravure', restart_sig='12:abc')
        self.assertNotEqual(self.panel.op_label(o), 'Gravure')
        self.assertIn('Gravure', self.panel.op_label(o))


if __name__ == '__main__':
    unittest.main()
