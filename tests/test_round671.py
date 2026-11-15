"""Round 671 : vue 3D, onglets « Pièce » (l'ensemble, chaque corps) et
« Prise » (une par position, par bridage) de la pièce choisie ; « + Prise »
gardée avec le dessin, retirée sans usinage ; placer, bridage, brut,
automatisme de la prise montrée — l'automatisme crée ses usinages dans
cette prise (corps seul, pièce retournée), zone choisie comprise."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.cam import strategies
from vectordrive.core import solids as SO
from vectordrive.core import workspace as WS
from tests.test_round596 import box_tris, two_boxes_stl

app = QApplication.instance() or QApplication([])


def one_box_stl():
    from vectordrive.io import stl_write
    f = pathlib.Path(tempfile.mkdtemp()) / 'un.stl'
    stl_write.write_stl(str(f), box_tris(0, 0, 0, 20, 10, 6))
    return str(f)


def three_boxes_stl():
    from vectordrive.io import stl_write
    t = np.concatenate([box_tris(0, 0, 0, 20, 10, 6), box_tris(40, 0, 0, 50, 10, 4), box_tris(80, 0, 0, 90, 10, 5)])
    f = pathlib.Path(tempfile.mkdtemp()) / 'trois.stl'
    stl_write.write_stl(str(f), t)
    return str(f)


def tabs(bar):
    return [bar.tabText(i) for i in range(bar.count())]


class FakeDoc:
    def __init__(self):
        self.extra = {}
        self.source_path = ''


class TestExtraSetups(unittest.TestCase):
    def test_declare(self):
        d = FakeDoc()
        self.assertTrue(WS.declare(d, '-Z', 1))
        self.assertFalse(WS.declare(d, '-Z', 1))                       # déjà là
        self.assertFalse(WS.declare(d, '', -1))                        # celle du dessin
        d.extra[WS.KEY_SETUPS] = {'+X|-1': WS.Workspace().to_dict(), 'mal': {}}
        self.assertEqual(WS.extra_setups(d), [('-Z', 1), ('+X', -1)])  # bridée : elle existe aussi
        WS.undeclare(d, '+X', -1)                                      # son bridage retiré avec elle
        self.assertNotIn('+X|-1', d.extra[WS.KEY_SETUPS])
        WS.undeclare(d, '-Z', 1)
        self.assertNotIn(WS.SETUPS_KEY, d.extra)
        d.extra[WS.SETUPS_KEY] = 'pas une liste'
        self.assertEqual(WS.extra_setups(d), [])

    def test_not_in_signature(self):
        from vectordrive.core.document import Document
        d = Document()
        before = strategies._doc_signature(d)
        WS.declare(d, '-Z', -1)                                        # rien de lu par le calcul
        self.assertEqual(strategies._doc_signature(d), before)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestPartTabs(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.open_path(two_boxes_stl())
        self.p = self.w._ensure_panel3d()
        self.assertTrue(self.p.refresh())

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def part(self, b):
        self.p.part_tabs.setCurrentIndex(self.p._tab_keys['part'].index(b))

    def test_tabs(self):
        p = self.p
        self.assertTrue(p.parts.isVisibleTo(p))
        self.assertFalse(p.setup_view.isVisibleTo(p))                  # la liste : remplacée par les onglets
        self.assertEqual(tabs(p.part_tabs), ['Ensemble', 'Corps 1', 'Corps 2'])
        self.assertEqual(tabs(p.setup_tabs), ['1. Comme le dessin', 'Toutes (recomposées)'])
        self.part(1)
        self.assertEqual(p.current_setup(), ('', 1))
        self.assertEqual(tabs(p.setup_tabs), ['1. Comme l\'ensemble'])
        self.assertAlmostEqual(p.view.model.bounds()[0], 40.0, 5)       # le corps 2 seul
        self.assertIn('Ce corps', p.place.toolTip())
        self.part(-1)
        self.assertEqual(p.current_setup(), ('', -1))
        self.assertAlmostEqual(p.view.model.bounds()[0], 0.0, 5)
        p.setup_tabs.setCurrentIndex(1)
        self.assertTrue(p.all_setups())

    def test_add_remove(self):
        p, w = self.p, self.w
        self.part(1)
        self.assertEqual(p.add_setup('-Z'), ('-Z', 1))
        self.assertEqual(p.current_setup(), ('-Z', 1))                 # montrée tout de suite
        self.assertEqual(tabs(p.setup_tabs), ['1. Comme l\'ensemble', '2. Dessous'])
        self.assertAlmostEqual(p.view.model.bounds()[2], -4.0, 5)       # retourné
        self.assertEqual(w.canvas.doc.extra[WS.SETUPS_KEY], ['-Z|1'])
        self.assertEqual(p.add_setup('+Z'), ('', 1))                   # face du dessin : la première
        self.assertEqual(p.current_setup(), ('', 1))
        self.part(-1)
        self.part(1)
        self.assertEqual(p.current_setup(), ('', 1))                   # la dernière montrée de ce corps
        p.setup_tabs.setCurrentIndex(1)
        self.part(-1)
        self.part(1)
        self.assertEqual(p.current_setup(), ('-Z', 1))
        self.assertFalse(p.removable('', 1))                           # la première : jamais
        self.assertTrue(p.remove_setup('-Z', 1))
        self.assertEqual(p.current_setup(), ('', 1))
        self.assertEqual(tabs(p.setup_tabs), ['1. Comme l\'ensemble'])
        w.undo()                                                       # revenue
        self.assertEqual(w.canvas.doc.extra[WS.SETUPS_KEY], ['-Z|1'])
        p.refresh()
        self.assertIn('2. Dessous', tabs(p.setup_tabs))

    def test_add_menu(self):
        p = self.p
        p._fill_add_menu()
        acts = {a.text(): a.isEnabled() for a in p.add_menu.actions()}
        self.assertFalse(acts['Dessus (déjà là)'])                     # la prise du dessin
        self.assertTrue(acts['Dessous'])
        next(a for a in p.add_menu.actions() if a.text() == 'Dessous').trigger()
        self.assertEqual(p.current_setup(), ('-Z', -1))
        self.assertEqual(tabs(p.setup_tabs), ['1. Comme le dessin', '2. Dessous', 'Toutes (recomposées)'])

    def test_clamping_of_shown_setup(self):
        p = self.p
        self.part(1)
        p.add_setup('-Z')
        dlg = p.clamping(exec_dialog=False)
        self.assertEqual(dlg.setup_key, ('-Z', 1))
        self.assertEqual(p.setup_note.text(), 'Bridage : aucun')
        self.assertIsNotNone(p.stock(exec_dialog=False))

    def test_auto3d_in_shown_setup(self):
        p, w = self.p, self.w
        self.part(1)
        p.add_setup('-Z')
        dlg = p.auto3d(exec_dialog=False, sequence='Ébauche seule')
        self.assertEqual(dlg.groups(), [(1, ['-Z'])])
        self.assertFalse(dlg.body_mode.isEnabled() or dlg.side_mode.isEnabled())
        self.assertIn('Corps 2, dessous', dlg.zone.text())
        ops = [x.op for x in dlg.planned]
        self.assertEqual(ops[0].kind, 'instruction')                   # poser le corps retourné
        self.assertTrue(all((o.setup_face, o.body3d) == ('-Z', 1) for o in ops[1:]))
        self.assertIn('Corps 2', ops[1].name)
        self.assertAlmostEqual(dlg.info.size_x, 10.0, 5)               # le corps seul, pas l'ensemble
        w.cam_panel.apply_auto3d(dlg.planned)
        p.refresh()
        self.assertEqual(p.current_setup(), ('-Z', 1))
        self.assertEqual(tabs(p.setup_tabs)[1], '2. Dessous (1)')      # ses usinages
        self.assertFalse(p.removable('-Z', 1))                         # un usinage : gardée

    def test_auto3d_zone_on_body(self):
        p = self.p
        self.part(1)
        v = p.view
        f = int(np.asarray(v.model.face_ids())[0])
        v.set_selection(faces=[f])
        dlg = p.auto3d(exec_dialog=False, sequence='Ébauche seule')
        ops = [x.op for x in dlg.planned if x.op.kind != 'instruction']
        self.assertTrue(ops and all(o.faces3d == [f] and o.body3d == 1 for o in ops))   # zone gardée

    def test_auto3d_whole_unchanged(self):
        dlg = self.p.auto3d(exec_dialog=False, sequence='Ébauche seule')
        self.assertIsNone(dlg.shown_setup)                             # l'ensemble : les choix habituels
        self.assertTrue(dlg.body_mode.isEnabled())
        self.assertGreater(dlg.body_mode.findData('chacun'), 0)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestThreeBodies(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.open_path(three_boxes_stl())
        self.p = self.w._ensure_panel3d()
        self.assertTrue(self.p.refresh())

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def part(self, b):
        self.p.part_tabs.setCurrentIndex(self.p._tab_keys['part'].index(b))

    def test_each_body_in_turn(self):
        from vectordrive.cam import mill3d
        p = self.p
        for b in (0, 1, 2, 0, 2):                                      # les poses ne chassent plus la pièce lue
            self.part(b)
            self.assertEqual(p.current_setup(), ('', b))
            self.assertEqual(tabs(p.part_tabs), ['Ensemble', 'Corps 1', 'Corps 2', 'Corps 3'])
        self.assertAlmostEqual(p.view.model.bounds()[0], 80.0, 5)
        dlg = p.auto3d(exec_dialog=False, sequence='Ébauche seule')
        self.assertEqual(dlg.groups(), [(2, [''])])
        mill3d._RAW.clear()                                            # noms retenus à la lecture
        p.refresh()
        self.assertEqual(len(tabs(p.part_tabs)), 4)
        self.assertEqual(p.current_setup(), ('', 2))

    def test_undo_add_on_body(self):
        p, w = self.p, self.w
        self.part(1)
        p.add_setup('-Y')
        self.assertEqual(p.current_setup(), ('-Y', 1))
        w.undo()
        p.refresh()
        self.assertEqual(p.current_setup(), ('', 1))                   # la première du même corps
        self.assertAlmostEqual(p.view.model.bounds()[0], 40.0, 5)       # la vue suit
        self.assertEqual(p._setup_memory()[1], '|1')

    def test_clamped_setup_not_counted_as_other(self):
        p, w = self.p, self.w
        self.part(2)
        p.add_setup('-Z')
        ws = next(iter(WS.builtin().values()))
        w.cam_panel.set_workspace(ws, ('-Z', 2))
        dlg = p.auto3d(exec_dialog=False, sequence='Ébauche seule')
        self.assertNotIn('autre(s) prise(s)', dlg.ws_text.text())

    def test_names_of_body_to_place(self):
        self.part(2)
        dlg = self.p.place_body(2, exec_dialog=False)
        self.assertIn('Corps 3', dlg.windowTitle())


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestSingleBody(unittest.TestCase):
    def test_setups_only(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(one_box_stl())
            p = w._ensure_panel3d()
            self.assertTrue(p.refresh())
            self.assertTrue(p.parts.isVisibleTo(p))
            self.assertFalse(p.part_tabs.isVisibleTo(p))               # un seul corps : pas d'onglets de pièce
            self.assertEqual(tabs(p.setup_tabs), ['1. Comme le dessin'])
            p.add_setup('-Z')
            self.assertEqual(tabs(p.setup_tabs), ['1. Comme le dessin', '2. Dessous', 'Toutes (recomposées)'])
            p.source.setCurrentIndex(p.source.findData('dessin'))      # pas la pièce : pas d'onglets
            self.assertFalse(p.parts.isVisibleTo(p))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
