"""Round 998 : FAO, la matière restante entre les opérations (retour de l'atelier du 12/11 : « les restes matières entre
chaque opé ») — dans la simulation, « Matière après » une opération : la matière laissée aux suivantes, ce que cette
opération enlève en vert (sans ce que celles d'avant ont déjà enlevé) ; au clic droit d'une opération, « Matière restante
après cette opération… »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, simulate
from vectordrive.cam.model import Move, Toolpath
from vectordrive.core import progress as P

app = QApplication.instance() or QApplication([])


def line(st, op_id, y, z, name=''):
    """Un trait de 20 mm à la fraise de 2 mm, à la cote z."""
    tp = Toolpath(op_id=op_id, tool_id=st.tools[0].id, name=name)
    tp.moves = [Move('rapid', 0, y, 5), Move('plunge', 0, y, z), Move('feed', 20, y, z), Move('rapid', 20, y, 5)]
    return tp


def job(zb=-1.0):
    """Ébauche (deux traits à 0,5), Finition (sur le premier trait, à zb), un détourage plus loin, un parcours sans
    opération (TypeEdit), un parcours vide."""
    st = model.CamSetup(tools=[model.CamTool(name='F2', diameter=2.0)])
    a = model.Operation(kind='poche', tool_id=st.tools[0].id, name='Ébauche')
    b = model.Operation(kind='poche', tool_id=st.tools[0].id, name='Finition')
    c = model.Operation(kind='contour', tool_id=st.tools[0].id)
    st.operations = [a, b, c]
    tps = [line(st, a.id, 0, -0.5), line(st, a.id, 1.5, -0.5), line(st, b.id, 0, zb), line(st, c.id, 10, -0.5),
           line(st, '', 20, -0.3, 'TE 1'), Toolpath(op_id=c.id, tool_id=st.tools[0].id)]
    return st, (a, b, c), tps


class Above:
    """Brut plus haut que la pièce de 1 mm, partout."""
    top = 1.0

    def inside(self, x, y):
        return (x > -1e9) & (y > -1e9)

    def __repr__(self):
        return 'Above()'


def green(c):
    return c.green() > 140 and c.red() < 110 and c.blue() < 120


def count(image, test, step=4):
    return sum(1 for y in range(0, image.height(), step) for x in range(0, image.width(), step)
               if test(image.pixelColor(x, y)))


def row_of(sim, y):
    return round((y - sim.y0) / sim.res)


class TestSpans(unittest.TestCase):

    def test_operations_in_machining_order(self):
        st, (a, b, c), tps = job()
        self.assertEqual(simulate.op_spans(tps), [(a.id, 0, 2, 0, 8), (b.id, 2, 3, 8, 12), (c.id, 3, 4, 12, 16),
                                                  (None, 4, 5, 16, 20)])

    def test_an_operation_split_by_another_counts_twice(self):
        st, (a, b, _c), tps = job()
        spans = simulate.op_spans([tps[0], tps[2], tps[1]])
        self.assertEqual([s[0] for s in spans], [a.id, b.id, a.id])


class TestRemaining(unittest.TestCase):

    def setUp(self):
        simulate._SIM_CACHE.clear()

    def states(self, zb=-1.0, stock=None):
        st, ops, tps = job(zb)
        full = simulate.simulate(tps, st, res=0.1, stock=stock)
        return st, tps, full, [simulate.remaining(tps, st, full, s[3], s[4]) for s in simulate.op_spans(tps)]

    def test_after_the_last_is_the_full_simulation(self):
        _st, _tps, full, states = self.states()
        before, after = states[-1]
        self.assertTrue(np.allclose(after.H, full.H))
        self.assertAlmostEqual(after.removed, full.removed, places=6)
        self.assertEqual(float(np.abs(states[0][0].H).max()), 0.0)   # avant la première : rien d'enlevé
        self.assertEqual(states[0][0].removed, 0.0)

    def test_each_operation_counts_only_what_is_left(self):
        st, tps, full, states = self.states(zb=-1.0)
        before, after = states[1]
        gone = after.removed - before.removed
        rough = simulate.simulate(tps[:2], st, res=0.1).removed      # l'ébauche seule, puis avec la finition
        both = simulate.simulate(tps[:3], st, res=0.1).removed
        self.assertAlmostEqual(gone, both - rough, delta=0.03 * (both - rough))
        alone = simulate.simulate([tps[2]], st, res=0.1).removed     # la finition seule : tout le trait sur 1 mm
        self.assertLess(gone, 0.6 * alone)                           # avec l'ébauche avant : le demi-millimètre restant

    def test_an_operation_with_nothing_left_removes_nothing(self):
        _st, _tps, _full, states = self.states(zb=-0.4)            # la finition passe moins bas que l'ébauche
        before, after = states[1]
        self.assertEqual(after.removed - before.removed, 0.0)
        self.assertFalse((before.H - after.H > 1e-6).any())

    def test_with_the_stock_above_the_part(self):
        _st, _tps, full, states = self.states(stock=Above())
        self.assertEqual(float(states[0][0].H.min()), 1.0)          # avant la première : le haut du brut
        self.assertTrue(np.allclose(states[-1][1].H, full.H))

    def test_simulated_in_pieces_the_same_arcs_included(self):
        st = model.CamSetup(tools=[model.CamTool(name='F2', diameter=2.0)])
        tp = Toolpath(op_id='a', tool_id=st.tools[0].id)
        tp.moves = [Move('rapid', 0, 0, 5), Move('plunge', 0, 0, -0.5), Move('arc_ccw', 10, 0, -0.5, 5, 0),
                    Move('feed', 10, 5, -0.5), Move('arc_cw', 0, 5, -0.8, 5, 5), Move('rapid', 0, 5, 5)]
        full = simulate.simulate([tp], st, res=0.1)
        whole = simulate.advance([tp], st, simulate.blank(full), 0, 6)
        with mock.patch.object(simulate, 'CHUNK', 1):                # une limite de bloc à chaque mouvement, arcs compris
            pieces = simulate.advance([tp], st, simulate.blank(full), 0, 6)
        self.assertTrue(np.allclose(whole.H, full.H))
        self.assertTrue(np.allclose(pieces.H, full.H))

    def test_cancel_stops_it_inside_a_block(self):
        st, _ops, tps = job()
        full = simulate.simulate(tps, st, res=0.1)
        task = P.Task('essai')
        task.cancel()
        token = P.attach(task)
        try:
            with mock.patch.object(simulate, '_stamp_batch') as b, mock.patch.object(simulate, '_stamp_segment') as g:
                with self.assertRaises(P.Cancelled):
                    simulate.remaining(tps, st, full, 0, 16)
            self.assertEqual(b.call_count + g.call_count, 0)        # rien de creusé après Annuler
        finally:
            P.detach(token)


class TestRender(unittest.TestCase):

    def test_marked_points_in_green(self):
        sim = simulate.SimResult(H=np.zeros((50, 50)), x0=0.0, y0=0.0, res=0.1)
        mark = np.zeros((50, 50), dtype=bool)
        mark[10:20, 10:40] = True
        self.assertGreater(count(simulate.render(sim, mark=mark), green), 0)
        self.assertEqual(count(simulate.render(sim), green), 0)
        self.assertEqual(count(simulate.render(sim, mark=mark[:10]), green), 0)   # pas la forme de la grille : ignoré


class TestDialog(unittest.TestCase):

    def setUp(self):
        simulate._SIM_CACHE.clear()
        self.st, self.ops, self.tps = job()

    def dialog(self, tps=None, **kw):
        from vectordrive.ui.sim_dialog import SimDialog
        d = SimDialog(None, self.tps if tps is None else tps, self.st, **kw)
        self.addCleanup(d.done, 0)
        return d

    def test_the_operations_listed(self):
        d = self.dialog()
        self.assertEqual([d.after.itemText(i) for i in range(d.after.count())],
                         ['Toutes les opérations', '1. Ébauche', '2. Finition', '3. Détourage (contour décalé)', '4. TE 1'])
        self.assertEqual(d.after.currentIndex(), 0)
        self.assertTrue(d.after.isVisibleTo(d) and d.after_label.isVisibleTo(d) and d.show_cut.isVisibleTo(d))
        self.assertFalse(d.show_cut.isEnabled())
        self.assertIs(d.result, d.full)
        self.assertNotIn('après', d.info.text())

    def test_after_an_operation(self):
        d = self.dialog()
        d.after.setCurrentIndex(2)
        self.assertIn('après « 2. Finition » : volume enlevé', d.info.text())
        self.assertIn('par cette opération', d.info.text())
        self.assertTrue(d.show_cut.isEnabled())
        self.assertGreater(count(d.image, green), 0)
        r, f = d.result, d.full
        row = row_of(f, 10)                                         # le trait du détourage, fait après
        self.assertLess(float(f.H[row].min()), -0.4)
        self.assertEqual(float(r.H[row].min()), 0.0)
        self.assertEqual(len(d._tool_lines()), 3)                   # le chemin de l'outil : jusqu'à la finition
        d.show_cut.setChecked(False)
        self.assertEqual(count(d.image, green), 0)
        d.show_cut.setChecked(True)
        d.after.setCurrentIndex(0)
        self.assertIs(d.result, d.full)
        self.assertFalse(d.show_cut.isEnabled())
        self.assertEqual(count(d.image, green), 0)
        self.assertEqual(len(d._tool_lines()), len(self.tps))

    def test_opened_on_an_operation(self):
        a, b, _c = self.ops
        self.assertEqual(self.dialog(upto=b.id).after.currentIndex(), 2)
        self.assertEqual(self.dialog(upto=a.id).after.currentIndex(), 1)
        self.assertEqual(self.dialog(upto='inconnue').after.currentIndex(), 0)

    def test_a_single_operation(self):
        d = self.dialog(self.tps[:2])
        self.assertFalse(d.after.isVisibleTo(d) or d.after_label.isVisibleTo(d) or d.show_cut.isVisibleTo(d))
        self.assertIs(d.result, d.full)
        d = self.dialog(self.tps[:2], upto=self.ops[0].id)          # ouverte sur elle : le choix et le vert
        self.assertTrue(d.after.isVisibleTo(d) and d.show_cut.isEnabled())
        self.assertEqual(d.after.currentIndex(), 1)
        self.assertAlmostEqual(d.gone, d.full.removed, places=6)

    def test_an_operation_in_two_places(self):
        st, (a, b, _c) = self.st, self.ops
        tps = [line(st, a.id, 0, -0.5), line(st, b.id, 10, -0.5), line(st, a.id, 20, -0.5)]
        d = self.dialog(tps, upto=a.id)
        self.assertEqual(d.after.currentIndex(), 3)                 # après son dernier endroit
        self.assertAlmostEqual(d.gone, d.full.removed * 2 / 3, delta=0.02 * d.full.removed)   # ses deux traits
        f = d.full
        self.assertTrue(d.cut[row_of(f, 0)].any() and d.cut[row_of(f, 20)].any())
        self.assertFalse(d.cut[row_of(f, 10)].any())                # pas celui de l'autre opération

    def test_cancelled_back_to_all_and_said(self):
        d = self.dialog()
        with mock.patch.object(simulate, 'advance', side_effect=P.Cancelled()):
            d.after.setCurrentIndex(2)
        self.assertEqual(d.after.currentIndex(), 0)
        self.assertIs(d.result, d.full)
        self.assertFalse(d.show_cut.isEnabled())
        self.assertTrue(d.info.text().startswith('Simulation annulée — Pas '))

    def test_from_one_operation_to_the_next(self):
        d = self.dialog()
        real = simulate.advance
        with mock.patch.object(simulate, 'advance', side_effect=real) as m:
            d.after.setCurrentIndex(2)                              # l'ébauche puis la finition
            self.assertEqual(m.call_count, 2)
            d.after.setCurrentIndex(1)
            d.after.setCurrentIndex(3)                              # le détourage seul en plus
            self.assertEqual(m.call_count, 3)
            d.after.setCurrentIndex(4)                              # la dernière : la simulation complète
            self.assertEqual(m.call_count, 3)
            self.assertIs(d.result, d.full)
            d.run()                                                 # « Recalculer » : la grille peut changer
            self.assertEqual(m.call_count, 3 + 3)

    def test_little_memory_same_result(self):
        from vectordrive.ui.sim_dialog import SimDialog
        d = self.dialog()
        d.after.setCurrentIndex(3)
        want = d.result.H.copy()
        with mock.patch.object(SimDialog, 'STATES_BYTES', 1):
            d2 = self.dialog()
            d2.after.setCurrentIndex(2)
            d2.after.setCurrentIndex(3)
            self.assertLessEqual(len(d2._states), 1)
            self.assertTrue(np.allclose(d2.result.H, want))

    def test_depth_follows_the_operation(self):
        d = self.dialog()
        self.assertAlmostEqual(d.level.minimum(), -1.0, places=2)
        d.level.setValue(-0.5)
        self.assertEqual(d.level_slider.value(), 500)
        d.after.setCurrentIndex(1)                                  # après l'ébauche : 0,5 mm
        self.assertAlmostEqual(d.level.minimum(), -0.5, places=2)
        self.assertEqual(d.level_slider.value(), 1000)              # avant : 500, le curseur en retard sur la valeur

    def test_the_relief_once_per_state(self):
        got = []
        d = self.dialog(on_relief=got.append)
        d.after.setCurrentIndex(1)
        d.lay_relief()
        self.assertFalse(d.relief_button.isEnabled())
        d.after.setCurrentIndex(3)
        self.assertTrue(d.relief_button.isEnabled())                # un autre état : un autre relief
        d.after.setCurrentIndex(1)
        self.assertFalse(d.relief_button.isEnabled())               # celui-là est déjà posé
        d.run()
        self.assertTrue(d.relief_button.isEnabled())
        self.assertEqual(len(got), 1)

    def test_memory_freed_when_closed(self):
        d = self.dialog()
        d.after.setCurrentIndex(3)
        self.assertTrue(d._states)
        d.done(0)
        self.assertEqual(d._states, {})


class TestOpMenu(unittest.TestCase):

    def setUp(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        simulate._SIM_CACHE.clear()
        self.w = MainWindow()
        self.c = self.w.canvas
        self.cp = self.w.cam_panel
        self.a = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
        self.b = Shape(path=geom.Path([geom.rect(40, 0, 20, 10)]))
        self.c.doc.add(self.a)
        self.c.doc.add(self.b)
        self.c.select([self.a])
        self.op1 = self.cp.new_operation('gravure', exec_dialog=False)
        self.c.select([self.b])
        self.op2 = self.cp.new_operation('gravure', exec_dialog=False)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def opened(self, row):
        self.cp.ops.selectRow(row)
        d = self.cp.simulate_after_op(exec_dialog=False)
        if d is not None:
            self.addCleanup(d.done, 0)
        return d

    def ops_of(self, d):
        return [t.op_id for t in d.toolpaths]

    def test_the_menu_offers_it(self):
        self.cp.ops.selectRow(1)
        m = self.cp.op_menu(exec_menu=False)
        a = next(a for a in m.actions() if a.text() == 'Matière restante après cette opération…')
        self.assertIn('matière laissée aux suivantes', a.toolTip())
        m.deleteLater()

    def test_opened_after_the_chosen_operation(self):
        d = self.opened(1)
        self.assertEqual(d.after.count(), 3)
        self.assertEqual(d.after.currentIndex(), 2)
        self.assertEqual(set(self.ops_of(d)), {self.op1.id, self.op2.id})
        d0 = self.opened(0)
        self.assertEqual(d0.after.currentIndex(), 1)
        self.assertIn('après « 1. ', d0.info.text())

    def test_unchecked_paths_left_out_but_those_of_the_operation(self):
        for tp in self.cp.toolpaths:
            tp.shown = tp.op_id == self.op2.id                      # « Simuler en 2D » de la seconde : la première décochée
        self.assertEqual(set(self.ops_of(self.opened(1))), {self.op2.id})      # le programme : sans la première
        self.assertEqual(set(self.ops_of(self.opened(0))), {self.op1.id, self.op2.id})   # la première, choisie

    def test_disabled_operation_left_out(self):
        s = self.cp.setup()
        s.operations[0].enabled = False
        self.cp.save(s)
        self.assertEqual(set(self.ops_of(self.opened(1))), {self.op2.id})

    def test_other_face_left_out(self):
        from vectordrive.core import workspace as WS
        real = WS.op_setup
        with mock.patch.object(WS, 'op_setup', side_effect=lambda op, doc=None: (
                ('-Z', 0) if op is not None and op.id == self.op1.id else real(op, doc))):
            self.assertEqual(set(self.ops_of(self.opened(1))), {self.op2.id})

    def test_nothing_recomputed_when_nothing_is_checked(self):
        for tp in self.cp.toolpaths:
            tp.shown = False
        with mock.patch.object(self.cp, 'compute', side_effect=AssertionError('tout recalculé')):
            d = self.opened(1)
        self.assertEqual(set(self.ops_of(d)), {self.op2.id})

    def test_cancelled_recompute_gives_nothing(self):
        with mock.patch.object(self.cp, 'current_paths', return_value=[]), \
                mock.patch.object(self.cp, 'outdated', return_value=True):
            self.assertIsNone(self.opened(1))


if __name__ == '__main__':
    unittest.main()
