"""Round 664 : relecture des ajouts de 663. Le recalcul avant l'écriture
rejoue le dernier calcul — ses objets en mode sélection, tous les objets en
mode couleur — quel que soit le mode du moment ; sans calcul complet, seules
les opérations refaites depuis leur formulaire sont refaites. Objets du
dernier calcul disparus, ou calcul annulé : rien n'est écrit, la liste
d'avant reste et le recalcul sera retenté. Fusion ou annulation : seules les
opérations qui ont changé de place emmènent leurs parcours."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(tempfile.mkdtemp(), 'modeles_fao'))

from PySide6.QtWidgets import QApplication

from tests import test_round657 as R657
from vectordrive.cam import model
from vectordrive.core import placement3d as P3

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    setUp, names = R657.TestWindow.setUp, R657.TestWindow.names

    def tearDown(self):
        self.cp.set_selection_mode(False)                                         # réglage gardé : remis
        R657.TestWindow.tearDown(self)

    def move_part(self, dx=3.0):
        P3.set_body(self.doc, 1, P3.Placement('+Z', 0.0, 'libre', dx, 0.0))       # la pièce a bougé

    def written(self):
        return self.names([tp for tp in self.cp.current_paths(dates=False) if tp.moves])

    def test_selection_replayed_in_colour_mode(self):
        cp = self.cp
        cp.set_selection_mode(True)
        self.w.canvas.selection = [self.m1]
        cp.compute()
        cp.set_selection_mode(False)                                              # changé pour un autre onglet
        self.move_part()
        self.assertEqual(self.written(), ['Un'])                                  # pas « Deux » en plus

    def test_colour_replayed_in_selection_mode(self):
        cp = self.cp                                                              # calculé en mode couleur
        cp.set_selection_mode(True)
        self.w.canvas.selection = [self.m2]
        self.move_part()
        self.assertEqual(self.written(), ['Un', 'Deux'])

    def test_only_form_ops_redone(self):
        cp = self.cp
        cp._remember('_only', None)                                               # rien de calculé en entier
        cp._remember('_whole', {o.id for o in cp.setup().operations})                # liste toute des formulaires
        cp.set_selection_mode(True)
        self.w.canvas.selection = [self.m1]
        self.move_part()
        self.assertEqual(self.written(), ['Un', 'Deux'])
        self.assertEqual(cp._memo('_placement_states'), cp._placement_state())  # pas refaits à chaque appel

    def test_objects_gone(self):
        cp = self.cp
        cp.set_selection_mode(True)
        self.w.canvas.selection = [self.m1]
        cp.compute()
        before = list(cp.toolpaths)
        self.m1.id = 'remplace'                                                   # pièce replacée : autre objet
        self.move_part()
        self.assertEqual(cp.current_paths(dates=False), [])
        self.assertIn('remplacés ou supprimés', cp.info.text())
        self.assertEqual(cp.toolpaths, before)
        self.assertEqual(cp._memo('_placement_states'), '')                       # retenté au prochain appel

    def test_cancel_writes_nothing(self):
        from vectordrive.ui import progress
        cp = self.cp
        cp.set_selection_mode(True)
        self.w.canvas.selection = [self.m1]
        cp.compute()
        cp.compute_op(cp.setup().operations[1])                                   # « Deux » sur tous ses objets
        real = progress.run

        def run(win, title, *a, **k):
            if title == 'Calcul du parcours':
                raise progress.Cancelled()
            return real(win, title, *a, **k)
        self.move_part()
        with mock.patch('vectordrive.ui.progress.run', run):
            self.assertEqual(cp.current_paths(dates=False), [])
        self.assertEqual(self.written(), ['Un', 'Deux'])                          # retenté, sans annuler

    def test_manual_order_kept_on_merge(self):
        cp = self.cp
        s = cp.setup()
        s.operations += [model.Operation(kind='gravure', name=n, tool_id=self.t.id, items=[m.id], depth=0.1)
                         for n, m in (('Trois', self.m1), ('Quatre', self.m2))]
        cp.save(s)
        un, deux, trois, quatre = [tp for tp in cp.compute() if tp.moves]
        cp.display([un, deux, quatre, trois])                                     # réglé à la main
        before = [o.id for o in cp.setup().operations]
        s = cp.setup()
        s.operations = s.operations[1:] + s.operations[:1]                        # « Un » passe en dernier
        cp.save(s)
        cp.follow_order(before)
        self.assertEqual([tp.op_id for tp in cp.toolpaths], [deux.op_id, quatre.op_id, trois.op_id, un.op_id])

    def forget(self):
        cp = self.cp                                                              # rien de su de leur calcul
        cp._remember('_only', None)                                               # (665 : une session garde
        cp._remember('_whole', set())                                             # ce qu'on en savait)
        cp._remember('_computed', None)
        cp._remember('_placement_states', '')
        cp._remember('_surface_states', ('?',))

    def test_session_then_form_redoes_all(self):
        cp = self.cp
        self.forget()
        un = next(tp for tp in cp.toolpaths if tp.moves)
        cp.compute_op(cp.setup().operations[1])                                   # « Deux » seul refait
        self.move_part()
        tps = cp.current_paths(dates=False)
        self.assertEqual(self.names([tp for tp in tps if tp.moves]), ['Un', 'Deux'])
        self.assertIsNot(next(tp for tp in tps if tp.moves), un)                  # « Un » refait aussi

    def test_session_in_selection_mode_asks(self):
        cp = self.cp
        self.forget()
        cp.set_selection_mode(True)
        self.w.canvas.selection = [self.m2]
        self.assertEqual(cp.current_paths(dates=False), [])
        self.assertIn('session reprise', cp.info.text())

    def test_disabled_ops_ignored_by_follow(self):
        cp = self.cp
        s = cp.setup()
        x, y = [model.Operation(kind='gravure', name=n, tool_id=self.t.id, items=[self.m1.id], enabled=False)
                for n in ('X', 'Y')]
        s.operations[1:1] = [x, y]
        cp.save(s)
        un, deux = [tp for tp in cp.toolpaths if tp.moves]
        cp.display([deux, un])                                                    # découpe en dernier, à la main
        before = [o.id for o in cp.setup().operations]
        s = cp.setup()
        s.operations = [s.operations[0], s.operations[3], s.operations[1], s.operations[2]]
        cp.save(s)
        cp.follow_order(before)
        self.assertEqual([tp.op_id for tp in cp.toolpaths], [deux.op_id, un.op_id])

    def test_dates_by_form_redo_others(self):
        cp = self.cp
        with mock.patch.object(cp, 'refresh_dates', lambda: 1):                  # textes datés changés
            cp.compute_op(cp.setup().operations[1])
        self.assertEqual(cp._memo('_placement_states'), '')

    def test_removed_form_path_stays_out(self):
        cp = self.cp
        self.forget()
        cp._remember('_placement_states', None)
        cp.display([])
        for o in cp.setup().operations:
            cp.compute_op(o)
        cp.display([tp for tp in cp.toolpaths if tp.op_id == cp.setup().operations[0].id])   # « Deux » retiré
        self.move_part()
        self.assertEqual(self.written(), ['Un'])

    def test_typeedit_list_kept(self):
        cp = self.cp
        self.forget()
        cp._remember('_whole', {cp.setup().operations[1].id})
        cp._remember('_computed', {o.id for o in cp.setup().operations})
        s = cp.setup()
        s.operations[1].enabled = False
        cp.save(s)
        te = model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name='TE')
        te.shown = True
        cp.display([te])                                                          # parcours TypeEdit relus
        self.move_part()
        self.assertEqual(cp.current_paths(dates=False), [te])                    # « Un » revient décoché
        self.assertIn(te, cp.toolpaths)


if __name__ == '__main__':
    unittest.main()
