"""Round 798 : historique des volumes (d'après la frise des opérations de SolidCraft)."""
import json
import math
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

from vectordrive.core import history3d as HI
from vectordrive.core import sketch as SK
from vectordrive.core import solids as SO
from vectordrive.core.document import Shape
from vectordrive.core.geom import Affine, Path, circle, rect
from vectordrive.io import native

app = QApplication.instance() or QApplication([])


def plain(x, y, w, h, name='p'):
    return Shape(path=Path([rect(x, y, w, h)]), name=name)


def disc(x, y, r, name='d'):
    return Shape(path=Path([circle((x, y), r)]), name=name)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.doc = self.win.canvas.doc
        self.doc.layers[0].items = []
        self.doc.active = 0
        self.win.canvas.selection = []
        self.win._undo.clear()
        self.win._redo.clear()

    def put(self, *items):
        for it in items:
            self.doc.add(it)
        self.win.canvas.select(list(items))
        return items[0] if len(items) == 1 else items

    def block(self, height=10.0):
        self.put(plain(0, 0, 40, 30))
        return self.win.solid_extrude(params={'height': height})[0]

    def holed(self, height=10.0, r=5.0):
        """Un pavé percé de part en part : deux étapes."""
        b = self.block(height)
        c = disc(20, 15, r)
        self.doc.add(c)
        self.win.canvas.select([b, c])
        return self.win.solid_extrude(params={'operation': 'subtract', 'through': True})[0]

    def only(self):
        out = [it for it in self.doc.layers[0].items if SO.is_solid(it)]
        self.assertEqual(len(out), 1)
        return out[0]

    def replay(self, it):
        """Le même historique, recalculé : la commande rejouée donne-t-elle le même volume ?"""
        new = self.win._hist_apply(it, json.loads(json.dumps(HI.history_of(it))), 'x')
        self.assertIsNotNone(new, self.win.history_error)
        return new

    def assertBounds(self, it, expected, places=2):
        for a, b in zip(SO.of_item(it).bounds(), expected):
            self.assertAlmostEqual(a, b, places=places)


class Recording(Base):
    def test_extrude_keeps_its_step(self):
        it = self.block(10.0)
        step = HI.root_of(it)
        self.assertEqual(step['cmd'], 'solid_extrude')
        self.assertEqual(step['params']['height'], 10.0)
        self.assertEqual(step['title'], 'Extrusion')
        self.assertIn('10', step['shown'])
        self.assertEqual([e['kind'] for e in step['inputs']], ['item'])
        self.assertEqual(len(HI.history_of(it)['steps']), 1)

    def test_two_steps_hold_the_first_by_its_rank(self):
        it = self.holed()
        hist = HI.history_of(it)
        self.assertEqual([s['cmd'] for s in hist['steps']], ['solid_extrude', 'solid_extrude'])
        inputs = hist['steps'][-1]['inputs']
        self.assertEqual([e['kind'] for e in inputs], ['solid', 'item'])
        self.assertEqual(inputs[0]['step'], 0)
        self.assertNotIn('mesh', inputs[0])                       # le pavé par ses étapes : pas de maillage
        self.assertNotIn('solide', json.dumps(hist['steps'][0]))

    def test_two_histories_are_put_end_to_end(self):
        a = self.block()
        self.put(plain(30, 0, 40, 30, 'q'))
        b = self.win.solid_extrude(params={'height': 10.0})[0]
        self.win.canvas.select([b])
        b = self.win.solid_move_z(params={'dz': 1.0})[0]
        self.win.canvas.select([a, b])
        it = self.win.solid_boolean('union')[0]
        hist = HI.history_of(it)
        self.assertEqual(len(hist['steps']), 4)
        self.assertEqual([e['step'] for e in hist['steps'][-1]['inputs']], [0, 2])
        self.assertEqual(hist['steps'][2]['inputs'][0]['step'], 1)    # l'étape déplacée suit son volume
        root = hist['steps'][-1]
        self.assertEqual(root['kw'], {'op': 'union'})
        self.assertIsNone(root['params'])
        self.assertEqual(self.win.history_title(root), self.win.A['solid_union'].text().replace('&', '').rstrip('…'))
        new = self.win.history_set_params(it, 1, {'height': 20.0})
        self.assertBounds(new, (0, 0, 0, 70, 30, 21))

    def test_primitive_keeps_its_place(self):
        self.doc.plate.x, self.doc.plate.y = 0.0, 0.0
        it = self.win.solid_primitive('box', params={'dx': 10.0, 'dy': 10.0, 'dz': 5.0})[0]
        was = SO.of_item(it).bounds()
        self.doc.plate.x += 100.0                                  # la plaque bouge : le volume ne suit pas
        self.addCleanup(setattr, self.doc.plate, 'x', 0.0)
        new = self.win.history_set_params(it, -1, {'dz': 8.0})
        b = SO.of_item(new).bounds()
        self.assertAlmostEqual(b[0], was[0], places=3)
        self.assertAlmostEqual(b[1], was[1], places=3)
        self.assertAlmostEqual(b[5] - b[2], 8.0, places=3)

    def test_failed_command_notes_nothing(self):
        self.put(plain(0, 0, 10, 10))
        self.assertEqual(self.win.solid_boolean('union'), [])
        self.assertEqual(self.win._undo, [])

    def test_too_many_objects(self):
        with mock.patch.object(HI, 'MAX_INPUTS', 1):
            self.put(plain(0, 0, 10, 10), plain(20, 0, 10, 10, 'q'))
            out = self.win.solid_extrude(params={'height': 5.0})
        self.assertEqual(len(out), 2)
        self.assertFalse(HI.has_history(out[0]))

    def test_every_recorded_command_exists(self):
        import inspect
        from vectordrive.ui.main_window import MainWindow
        for name in HI.RECORDED:
            self.assertTrue(callable(getattr(MainWindow, name)), name)
            self.assertTrue(hasattr(getattr(MainWindow, name), '__wrapped__'), name)
            inspect.signature(getattr(MainWindow, name))

    def test_inspections_note_nothing(self):
        from vectordrive.ui.main_window import MainWindow
        for name in ('solid_massprop', 'solid_section', 'solid_import', 'solid_bounding'):
            self.assertFalse(hasattr(getattr(MainWindow, name), '__wrapped__'), name)

    def test_inner_command_has_no_step_of_its_own(self):
        it = self.block()
        self.win.canvas.select([it])
        self.win._hist_busy = True
        try:
            out = self.win.solid_move_z(params={'dz': 1.0})
        finally:
            self.win._hist_busy = False
        self.assertEqual(self.win._last_ask['values']['dz'], 1.0)
        self.assertFalse(HI.has_history(out[0]))                    # la commande qui l'appelle notera

    def test_a_command_is_not_stopped_by_its_history(self):
        self.put(plain(0, 0, 10, 10))
        with mock.patch.object(HI, 'gather', side_effect=ValueError('cassé')):
            out = self.win.solid_extrude(params={'height': 5.0})
        self.assertEqual(len(out), 1)
        self.assertFalse(HI.has_history(out[0]))

    def test_settings_that_do_not_save_are_not_kept(self):
        self.put(plain(0, 0, 10, 10))
        real = self.win._ask

        def odd(*a, **k):
            out = real(*a, **k)
            self.win._last_ask = dict(self.win._last_ask, values={'x': object()})
            return out
        with mock.patch.object(self.win, '_ask', odd):
            out = self.win.solid_extrude(params={'height': 5.0})
        self.assertEqual(len(out), 1)
        self.assertFalse(HI.has_history(out[0]))

    def test_describe_is_safe(self):
        spec = [('h', float, 10.0, 'Hauteur (mm)'), ('op', str, 'a', 'Opération'), ('b', bool, False, 'À travers (tout)'),
                ('s', str, 'x', 'Style')]
        text = HI.describe({'h': 2.5, 'op': 'b', 'b': True, 's': 'y'}, spec, {'op': [('a', 'Un'), ('b', 'Deux')], 's': ['xy', 'ab']})
        self.assertEqual(text, 'Hauteur : 2.5 ; Opération : Deux ; À travers ; Style : y')
        self.assertEqual(HI.describe({}, spec), 'Hauteur : 10')


class Rebuild(Base):
    def test_change_height(self):
        it = self.block(10.0)
        new = self.win.history_set_params(it, -1, {'height': 25.0})
        self.assertBounds(new, (0, 0, 0, 40, 30, 25))
        self.assertIs(self.only(), new)
        self.assertEqual(new.id, it.id)
        self.assertEqual(HI.root_of(new)['params']['height'], 25.0)
        self.assertEqual(self.win.canvas.selection, [new])

    def test_change_first_step_redoes_the_rest(self):
        it = self.holed(10.0, 5.0)
        new = self.win.history_set_params(it, 0, {'height': 30.0})
        self.assertBounds(new, (0, 0, 0, 40, 30, 30))
        expected = (40 * 30 - math.pi * 25) * 30               # le trou va toujours de part en part
        self.assertAlmostEqual(SO.of_item(new).volume() / expected, 1.0, places=2)
        self.assertEqual(HI.history_of(new)['steps'][0]['params']['height'], 30.0)

    def test_change_last_step_of_two(self):
        it = self.block(10.0)
        c = disc(20, 15, 5)
        self.doc.add(c)
        self.win.canvas.select([it, c])
        it = self.win.solid_extrude(params={'operation': 'subtract', 'height': 4.0, 'z0': 6.0})[0]
        whole = SO.of_item(it).volume()
        new = self.win.history_set_params(it, -1, {'height': 2.0, 'z0': 8.0})
        self.assertGreater(SO.of_item(new).volume(), whole)

    def test_moved_volume_stays_where_it_is(self):
        it = self.block(10.0)
        moved = it.transformed(Affine.translation(100.0, 50.0))
        self.doc.layers[0].items[0] = moved
        self.assertTrue(HI.has_history(moved))
        new = self.win.history_set_params(moved, -1, {'height': 20.0})
        self.assertBounds(new, (100, 50, 0, 140, 80, 20))
        box = new.path.bbox()
        self.assertAlmostEqual(box[0], 100.0, places=2)
        self.assertAlmostEqual(box[3], 80.0, places=2)
        again = self.win.history_set_params(new, -1, {'height': 5.0})        # et encore une fois
        self.assertBounds(again, (100, 50, 0, 140, 80, 5))

    def test_moved_input_is_kept(self):
        """Un volume déplacé avant de servir d'entrée : le déplacement fait partie de l'étape."""
        b = self.block(10.0)
        m = b.transformed(Affine.translation(100.0, 0.0))
        self.doc.layers[0].items[0] = m
        c = disc(120, 15, 5)
        self.doc.add(c)
        self.win.canvas.select([m, c])
        it = self.win.solid_extrude(params={'operation': 'subtract', 'through': True})[0]
        new = self.win.history_set_params(it, 0, {'height': 20.0})
        self.assertBounds(new, (100, 0, 0, 140, 30, 20))
        expected = (40 * 30 - math.pi * 25) * 20
        self.assertAlmostEqual(SO.of_item(new).volume() / expected, 1.0, places=2)

    def test_changed_outside_is_frozen(self):
        it = self.block(10.0)
        other = SO.box(0, 0, 0, 5, 5, 5)
        new = self.win._swap_solids([(it, [other])])[0]             # une opération qui ne se note pas
        self.assertIn(HI.KEY, new.extra)
        self.assertFalse(HI.has_history(new))
        self.assertIsNone(self.win.history_set_params(new, -1, {'height': 3.0}))
        self.assertIn('hors de son historique', self.win.history_error)
        self.win.canvas.select([new])
        with mock.patch.object(self.win, 'statusBar') as bar:
            self.assertIsNone(self.win.solid_history())
        self.assertIn('historique', bar.return_value.showMessage.call_args[0][0])
        self.win.canvas.select([new])
        lifted = self.win.solid_move_z(params={'dz': 2.0})[0]        # ce qui suit part de ce volume figé
        step = HI.root_of(lifted)
        self.assertEqual(step['inputs'][0]['kind'], 'item')
        self.assertNotIn(HI.KEY, step['inputs'][0]['item']['extra'])
        up = self.win.history_set_params(lifted, -1, {'dz': 3.0})
        self.assertBounds(up, (0, 0, 3, 5, 5, 8))

    def test_suspend_and_resume(self):
        it = self.holed()
        full = 40 * 30 * 10
        off = self.win.history_set_off(it, -1, True)
        self.assertAlmostEqual(SO.of_item(off).volume(), full, places=1)
        self.assertTrue(HI.root_of(off)['off'])
        on = self.win.history_set_off(off, -1, False)
        self.assertLess(SO.of_item(on).volume(), full - 100)

    def test_first_step_cannot_be_suspended(self):
        it = self.block()
        self.assertFalse(HI.can_suspend(HI.root_of(it)))
        self.assertIsNone(self.win.history_set_off(it, -1, True))
        self.assertIn('crée le volume', self.win.history_error)

    def test_suspended_step_may_still_be_changed(self):
        it = self.holed()
        off = self.win.history_set_off(it, -1, True)
        new = self.win.history_set_params(off, 0, {'height': 20.0})
        self.assertAlmostEqual(SO.of_item(new).volume(), 40 * 30 * 20, places=1)

    def test_nothing_left_behind(self):
        """Un recalcul ne touche ni à l'annulation, ni aux autres objets, ni à l'état de la fenêtre."""
        it = self.holed()
        other = plain(200, 0, 10, 10, 'autre')
        self.doc.add(other)
        layers, active = self.doc.layers, self.doc.active
        undo = len(self.win._undo)
        new = self.win.history_set_params(it, 0, {'height': 12.0})
        self.assertEqual(len(self.win._undo), undo + 1)
        self.assertIs(self.doc.layers, layers)
        self.assertEqual(self.doc.active, active)
        names = [o.name for o in self.doc.layers[0].items]
        self.assertEqual(len(names), 2)
        self.assertIn('autre', names)
        self.assertIn(new, self.doc.layers[0].items)
        self.assertFalse(self.win._replaying)
        self.assertTrue(self.win.canvas.updatesEnabled())
        self.assertFalse(self.win.canvas.signalsBlocked())

    def test_undo_and_redo(self):
        it = self.block(10.0)
        new = self.win.history_set_params(it, -1, {'height': 25.0})
        self.assertTrue(HI.has_history(new))
        self.win.undo()
        back = self.only()
        self.assertBounds(back, (0, 0, 0, 40, 30, 10))
        self.assertEqual(HI.root_of(back)['params']['height'], 10.0)
        self.win.redo()
        self.assertBounds(self.only(), (0, 0, 0, 40, 30, 25))
        self.assertEqual(HI.root_of(self.only())['params']['height'], 25.0)

    def test_failure_changes_nothing(self):
        it = self.holed()
        undo = len(self.win._undo)
        was = it.extra[HI.KEY]
        with mock.patch.object(SO, 'extrude_between', side_effect=SO.SolidError('impossible')):
            self.assertIsNone(self.win.history_set_params(it, 0, {'height': 30.0}))
        self.assertTrue(self.win.history_error)
        self.assertIs(self.only(), it)
        self.assertEqual(len(self.win._undo), undo)
        self.assertIs(it.extra[HI.KEY], was)
        self.assertEqual(HI.history_of(it)['steps'][0]['params']['height'], 10.0)    # l'historique du dessin reste juste
        self.assertFalse(self.win._replaying)
        self.assertTrue(self.win.canvas.updatesEnabled())

    def test_replay_opens_no_window(self):
        it = self.block()
        hist = json.loads(json.dumps(HI.history_of(it)))
        hist['steps'][-1]['params'] = None
        with mock.patch('vectordrive.ui.dialogs.ParamsDialog') as dlg:
            self.assertIsNone(self.win._hist_apply(it, hist, 'x'))
        dlg.assert_not_called()
        self.assertTrue(self.win.history_error)

    def test_lost_output_is_said(self):
        it = self.block()
        hist = json.loads(json.dumps(HI.history_of(it)))
        hist['steps'][-1]['index'] = 5
        self.assertIsNone(self.win._hist_apply(it, hist, 'x'))
        self.assertIn('Extrusion', self.win.history_error)

    def test_cap_on_steps(self):
        with mock.patch.object(HI, 'MAX_STEPS', 3):
            it = self.block()
            for _ in range(6):
                self.win.canvas.select([it])
                it = self.win.solid_move_z(params={'dz': 1.0})[0]
            self.assertLessEqual(len(HI.history_of(it)['steps']), 3)
            new = self.win.history_set_params(it, -1, {'dz': 2.0})
        self.assertBounds(new, (0, 0, 7, 40, 30, 17))

    def test_long_history(self):
        """Une longue suite d'étapes s'enregistre, se relit et se recalcule : rien ne s'imbrique."""
        it = self.block()
        n = 150
        for _ in range(n):
            self.win.canvas.select([it])
            it = self.win.solid_move_z(params={'dz': 1.0})[0]
        self.assertEqual(len(HI.history_of(it)['steps']), n + 1)
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'long.vdz'
            native.write(self.doc, p)
            back = native.read(p).layers[0].items[0]
        self.assertTrue(HI.has_history(back))
        new = self.win.history_set_params(it, 0, {'height': 20.0})
        self.assertBounds(new, (0, 0, n, 40, 30, n + 20))

    def test_volumes_are_let_go_on_the_way(self):
        steps = [{'inputs': []}, {'inputs': [{'kind': 'solid', 'step': 0}]},
                 {'inputs': [{'kind': 'solid', 'step': 1}, {'kind': 'solid', 'step': 0}, {'kind': 'item'}]}]
        self.assertEqual([sorted(x) for x in HI.last_uses(steps)], [[], [], [0, 1]])

    def test_each_command_replays_to_the_same_volume(self):
        cases = [('solid_move_z', {'dz': 3.0}), ('solid_rotate3d', {}), ('solid_scale3d', {'factor': 1.5}),
                 ('solid_mirror_z', {}), ('solid_shell', {'thickness': 1.0}), ('solid_round', {}),
                 ('solid_offset', {}), ('solid_smooth', {}), ('solid_array_z', {}), ('solid_slice', {}),
                 ('solid_align3d', {}), ('solid_rest', {})]
        done = 0
        for name, params in cases:
            with self.subTest(name):
                self.setUp()
                it = self.block()
                self.win.canvas.select([it])
                with mock.patch('vectordrive.ui.main_window.QMessageBox'):
                    out = getattr(self.win, name)(params=params)
                sols = [o for o in out if SO.is_solid(o) and HI.has_history(o)] if isinstance(out, list) else []
                if not sols:
                    continue
                done += 1
                a = SO.of_item(sols[-1])
                b = SO.of_item(self.replay(sols[-1]))
                self.assertAlmostEqual(a.volume(), b.volume(), places=3)
                for u, v in zip(a.bounds(), b.bounds()):
                    self.assertAlmostEqual(u, v, places=3)
        self.assertGreaterEqual(done, 8)

    def test_creating_commands_replay_to_the_same_volume(self):
        cases = [('solid_primitive', ('cylinder',), {'r': 5.0, 'h': 8.0}), ('solid_primitive', ('wedge',), {}),
                 ('solid_revolve', (), {})]
        done = 0
        for name, args, params in cases:
            with self.subTest(f'{name} {args}'):
                self.setUp()
                self.put(plain(10, 0, 10, 20))
                out = getattr(self.win, name)(*args, params=params)
                sols = [o for o in out if SO.is_solid(o) and HI.has_history(o)]
                if not sols:
                    continue
                done += 1
                self.assertAlmostEqual(SO.of_item(sols[0]).volume(), SO.of_item(self.replay(sols[0])).volume(), places=3)
        self.assertGreaterEqual(done, 2)

    def test_permute_keeps_the_shift_choice(self):
        it = self.block()
        self.win.canvas.select([it])
        out = self.win.solid_permute(keep=True)
        self.assertEqual(len(out), 2)
        step = HI.root_of(out[1])
        self.assertEqual(step['kw']['keep'], True)
        self.assertEqual(step['index'], 1)
        self.assertAlmostEqual(SO.of_item(self.replay(out[1])).volume(), SO.of_item(out[1]).volume(), places=3)

    def test_permute_notes_the_key_state(self):
        it = self.block()
        self.win.canvas.select([it])
        out = self.win.solid_permute()
        self.assertEqual(HI.root_of(out[0])['kw']['keep'], False)

    def test_separate_keeps_the_rank(self):
        a = self.block()
        self.put(plain(100, 0, 10, 10, 'q'))
        b = self.win.solid_extrude(params={'height': 5.0})[0]
        self.win.canvas.select([a, b])
        one = self.win.solid_boolean('union')[0]
        self.win.canvas.select([one])
        parts = self.win.solid_separate()
        self.assertEqual(len(parts), 2)
        vols = sorted(SO.of_item(p).volume() for p in parts)
        small = next(p for p in parts if SO.of_item(p).volume() == vols[0])
        self.assertAlmostEqual(SO.of_item(self.replay(small)).volume(), vols[0], places=3)

    def test_two_results_change_one_at_a_time(self):
        self.put(plain(0, 0, 10, 10), plain(50, 0, 10, 10, 'q'))
        a, b = self.win.solid_extrude(params={'height': 5.0})
        new = self.win.history_set_params(b, -1, {'height': 8.0})
        self.assertBounds(new, (50, 0, 0, 60, 10, 8))
        self.assertBounds(a, (0, 0, 0, 10, 10, 5))


class Sketches(Base):
    def sketched(self, width=40.0):
        sk = SK.Sketch()
        ls = sk.add_rect(0, 0, width, 30)
        sk.add_constraint('fix', sk.lines[ls[0]]['p'])
        sk.add_constraint('length', ls[0], value=width)
        sk.add_constraint('length', ls[1], value=30.0)
        self.assertTrue(sk.solve().ok)
        return self.win.sketch_done(sk), sk

    def test_extrude_keeps_the_sketch(self):
        shape, _sk = self.sketched()
        self.win.canvas.select([shape])
        it = self.win.solid_extrude(params={'height': 10.0})[0]
        entry = HI.at(HI.history_of(it), (0, 0))
        self.assertFalse(HI.is_step(entry))
        self.assertIsNotNone(HI.sketch_of(entry))

    def test_new_dimension_changes_the_volume(self):
        shape, _sk = self.sketched(40.0)
        self.win.canvas.select([shape])
        it = self.win.solid_extrude(params={'height': 10.0})[0]
        c = disc(20, 15, 5)
        self.doc.add(c)
        self.win.canvas.select([it, c])
        it = self.win.solid_extrude(params={'operation': 'subtract', 'through': True})[0]
        sk2 = SK.Sketch.from_dict(HI.sketch_of(HI.at(HI.history_of(it), (0, 0))))
        rule = next(c for c in sk2.constraints if c.kind == 'length' and abs(float(c.value) - 40.0) < 1e-6)
        rule.value = 70.0
        self.assertTrue(sk2.solve().ok)
        new = self.win.history_set_sketch(it, (0, 0), sk2)
        self.assertIsNotNone(new, self.win.history_error)
        self.assertBounds(new, (0, 0, 0, 70, 30, 10))
        entry = HI.at(HI.history_of(new), (0, 0))
        again = SK.Sketch.from_dict(HI.sketch_of(entry))
        self.assertTrue(any(c.kind == 'length' and abs(float(c.value) - 70.0) < 1e-6 for c in again.constraints))
        self.assertEqual(entry['item']['extra']['sketch_box'][2], 70.0)

    def test_sketch_window(self):
        shape, _sk = self.sketched(40.0)
        self.win.canvas.select([shape])
        it = self.win.solid_extrude(params={'height': 10.0})[0]

        class Answer:
            def __init__(self, parent, sketch, ignored=0):
                self.sketch = sketch
                rule = next(c for c in sketch.constraints if c.kind == 'length' and abs(float(c.value) - 40.0) < 1e-6)
                rule.value = 55.0
                sketch.solve()

            def exec(self):
                return 1
        with mock.patch('vectordrive.ui.sketch_editor.SketchEditor', Answer):
            new = self.win.history_edit_sketch(it, (0, 0))
        self.assertBounds(new, (0, 0, 0, 55, 30, 10))

    def test_sketch_window_closed(self):
        shape, _sk = self.sketched()
        self.win.canvas.select([shape])
        it = self.win.solid_extrude(params={'height': 10.0})[0]

        class Answer:
            def __init__(self, parent, sketch, ignored=0):
                self.sketch = sketch

            def exec(self):
                return 0
        with mock.patch('vectordrive.ui.sketch_editor.SketchEditor', Answer):
            self.assertIsNone(self.win.history_edit_sketch(it, (0, 0)))
        self.assertIs(self.only(), it)

    def test_moved_sketch_keeps_its_place(self):
        """La reprise d'une esquisse déplacée, en dessin comme dans l'historique."""
        shape, _sk = self.sketched(40.0)
        moved = shape.transformed(Affine.translation(10.0, 5.0))
        self.doc.layers[0].items[0] = moved
        sk = SK.Sketch.from_dict(moved.extra['sketch'])
        new = self.win._sketch_shape(moved, sk)
        box = new.path.bbox()
        self.assertAlmostEqual(box[0], 10.0, places=3)
        self.assertAlmostEqual(box[1], 5.0, places=3)


class Files(Base):
    def test_rebuild_after_reopening(self):
        it = self.holed(10.0, 5.0)
        self.assertTrue(HI.has_history(it))
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'piece.vdz'
            native.write(self.doc, p)
            doc = native.read(p)
        back = doc.layers[0].items[0]
        self.assertTrue(HI.has_history(back))
        self.doc.layers[0].items = [back]
        new = self.win.history_set_params(back, 0, {'height': 22.0})
        self.assertIsNotNone(new, self.win.history_error)
        self.assertBounds(new, (0, 0, 0, 40, 30, 22))
        self.assertAlmostEqual(SO.of_item(new).volume() / ((40 * 30 - math.pi * 25) * 22), 1.0, places=2)

    def test_old_file_without_history(self):
        it = SO.make_shape(SO.box(0, 0, 0, 5, 5, 5))
        self.assertFalse(HI.has_history(it))
        self.assertIsNone(HI.history_of(it))
        self.assertIsNone(HI.root_of(it))
        self.assertIsNone(HI.history_of(plain(0, 0, 1, 1)))

    def test_damaged_history_is_ignored(self):
        it = self.block()
        for odd in ('n’importe quoi', {'result': HI.mesh_hash(it)}, {'steps': [], 'result': HI.mesh_hash(it)}):
            it.extra[HI.KEY] = odd
            self.assertFalse(HI.has_history(it))

    def test_broken_step_is_refused_not_fatal(self):
        it = self.block()
        hist = json.loads(json.dumps(HI.history_of(it)))
        del hist['steps'][-1]['inputs'][0]['item']['path']
        self.assertIsNone(self.win._hist_apply(it, hist, 'x'))
        self.assertTrue(self.win.history_error)
        self.assertIs(self.only(), it)


class Dialog(Base):
    def box(self, item):
        from vectordrive.ui.history3d_dialog import HistoryDialog
        dlg = HistoryDialog(self.win, item)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def test_steps_are_listed_in_order(self):
        dlg = self.box(self.holed())
        self.assertEqual(dlg.tree.topLevelItemCount(), 2)
        first, last = dlg.tree.topLevelItem(0), dlg.tree.topLevelItem(1)
        self.assertEqual(first.text(0), '1. Extrusion')
        self.assertEqual(last.text(0), '2. Extrusion')
        self.assertIn('Soustraire', last.text(1))
        self.assertEqual(first.child(0).text(0), 'Tracé')
        self.assertEqual(last.child(0).text(0), 'Volume de l’étape 1')
        self.assertEqual(dlg.current_ref(), 1)                         # la dernière étape est choisie

    def test_buttons_follow_the_line(self):
        dlg = self.box(self.holed())
        first, last = dlg.tree.topLevelItem(0), dlg.tree.topLevelItem(1)
        self.assertTrue(dlg.edit_button.isEnabled())
        self.assertTrue(dlg.suspend_button.isEnabled())
        dlg.tree.setCurrentItem(first.child(0))                        # le tracé
        self.assertEqual(dlg.current_ref(), (0, 0))
        self.assertFalse(dlg.edit_button.isEnabled())
        self.assertFalse(dlg.suspend_button.isEnabled())
        dlg.tree.setCurrentItem(first)                                 # la première extrusion : elle crée le volume
        self.assertTrue(dlg.edit_button.isEnabled())
        self.assertFalse(dlg.suspend_button.isEnabled())
        dlg.tree.setCurrentItem(last.child(0))                         # une entrée qui est un volume d'une étape
        self.assertFalse(dlg.edit_button.isEnabled())

    def test_suspend_button(self):
        dlg = self.box(self.holed())
        dlg.suspend_button.click()
        self.assertTrue(HI.root_of(dlg.item)['off'])
        self.assertIn('suspendue', dlg.tree.topLevelItem(1).text(0))
        self.assertEqual(dlg.suspend_button.text(), 'Reprendre')
        dlg.suspend_button.click()
        self.assertFalse(HI.root_of(dlg.item)['off'])

    def test_edit_fills_the_window_with_the_values_of_the_step(self):
        from dataclasses import replace
        import vectordrive.ui.dialogs as D
        it = self.holed(10.0)
        self.win.settings.setValue('cad/solide_extrusion', {'height': 99.0})
        self.addCleanup(self.win.settings.remove, 'cad/solide_extrusion')
        dlg = self.box(it)
        dlg.tree.setCurrentItem(dlg.tree.topLevelItem(0))
        seen = {}

        class Answer:
            def __init__(self, parent, title, params, labels, warning='', choices=None):
                seen['height'] = params.height
                self.params = params

            def exec(self):
                return 1

            def result_params(self):
                return replace(self.params, height=33.0)
        with mock.patch.object(D, 'ParamsDialog', Answer):
            dlg.edit_button.click()
        self.assertEqual(seen['height'], 10.0)                         # pas la dernière valeur retenue
        self.assertBounds(dlg.item, (0, 0, 0, 40, 30, 33))
        self.assertEqual(self.win.settings.value('cad/solide_extrusion')['height'], 99.0)
        self.assertIn('33', dlg.tree.topLevelItem(0).text(1))
        self.assertEqual(dlg.current_ref(), 0)                         # la ligne reste choisie
        self.assertIn('recalculé', dlg.status.text())

    def test_edit_cancelled(self):
        import vectordrive.ui.dialogs as D
        it = self.holed()
        dlg = self.box(it)

        class Answer:
            def __init__(self, *a, **k):
                pass

            def exec(self):
                return 0
        undo = len(self.win._undo)
        with mock.patch.object(D, 'ParamsDialog', Answer):
            dlg.edit_button.click()
        self.assertIs(dlg.item, it)
        self.assertIs(self.only(), it)
        self.assertEqual(len(self.win._undo), undo)
        self.assertEqual(self.win.history_error, '')
        self.assertFalse(self.win._replaying)

    def test_sketch_button_label(self):
        sk = SK.Sketch()
        sk.add_rect(0, 0, 10, 10)
        shape = self.win.sketch_done(sk)
        self.win.canvas.select([shape])
        it = self.win.solid_extrude(params={'height': 10.0})[0]
        dlg = self.box(it)
        dlg.tree.setCurrentItem(dlg.tree.topLevelItem(0).child(0))
        self.assertEqual(dlg.tree.currentItem().text(0), 'Esquisse')
        self.assertTrue(dlg.edit_button.isEnabled())
        self.assertIn('esquisse', dlg.edit_button.text())

    def test_failure_is_said_in_the_window(self):
        from dataclasses import replace
        import vectordrive.ui.dialogs as D
        dlg = self.box(self.holed())
        dlg.tree.setCurrentItem(dlg.tree.topLevelItem(0))

        class Answer:
            def __init__(self, parent, title, params, labels, warning='', choices=None):
                self.params = params

            def exec(self):
                return 1

            def result_params(self):
                return replace(self.params, height=33.0)
        was = dlg.item
        with mock.patch.object(D, 'ParamsDialog', Answer), \
                mock.patch.object(SO, 'extrude_between', side_effect=SO.SolidError('impossible')):
            dlg.edit_button.click()
        self.assertIs(dlg.item, was)
        self.assertTrue(dlg.status.text())

    def test_frozen_volume_opens_no_window(self):
        self.doc.add(SO.make_shape(SO.box(0, 0, 0, 5, 5, 5)))
        self.win.canvas.select(self.doc.layers[0].items)
        self.assertIsNone(self.win.solid_history())

    def test_several_volumes_open_no_window(self):
        a = self.block()
        self.put(plain(50, 0, 10, 10, 'q'))
        b = self.win.solid_extrude(params={'height': 5.0})[0]
        self.win.canvas.select([a, b])
        self.assertIsNone(self.win.solid_history())

    def test_double_click(self):
        it = self.block()
        with mock.patch.object(self.win, 'solid_history') as opened:
            self.win._item_double_clicked(it)
        opened.assert_called_once_with(it)
        frozen = SO.make_shape(SO.box(0, 0, 0, 5, 5, 5))
        with mock.patch.object(self.win, 'solid_history') as opened:
            self.win._item_double_clicked(frozen)
        opened.assert_not_called()

    def test_ribbon(self):
        action = self.win.A['solid_history']
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups()
                 for b in g.buttons() if b.defaultAction() is action]
        self.assertEqual(len(found), 1)
        self.assertEqual(action.text(), 'Historique…')


if __name__ == '__main__':
    unittest.main()
