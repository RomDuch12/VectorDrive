"""Round 593 : automatismes d'usinage 3D — suites d'étapes (ébauche, demi-finition, finition…) livrées,
de plugin ou de l'utilisateur ; outils proposés d'après la pièce (le plus gros qui tient, la moitié du
précédent, rayon ≤ plus petit rayon creux), réglages déduits (passe, crête) ; fenêtre modifiable,
enregistrement, application en une annulation."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round591 import face_under, pocket_stl
from vectordrive.cam import auto3d as A
from vectordrive.cam import mill3d, model
from vectordrive.core import solids as SO
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])


def T(kind, d, cut=20.0, **kw):
    return model.CamTool(name=f'{kind} {d}', kind=kind, diameter=d, cut_length=cut, **kw)


class TestRules(unittest.TestCase):
    def setUp(self):
        self.info = A.PartInfo(100.0, 60.0, 12.0, 2.0, 60.0)
        self.tools = [T('fraise', 2), T('fraise', 6), T('fraise', 10, cut=8), T('fraise', 20),
                      T('boule', 1), T('boule', 3), T('boule', 4), T('boule', 6)]

    def test_big(self):
        t = A.pick_tool(A.Step('ebauche3d', tool_kind='fraise', rule='gros'), self.tools, self.info)
        self.assertEqual(t.diameter, 6)          # Ø20 > 60/4 ; Ø10 trop court (8 < 12 de profondeur)

    def test_middle(self):
        prev = self.tools[1]
        t = A.pick_tool(A.Step(tool_kind='boule', rule='moyen'), self.tools, self.info, prev)
        self.assertEqual(t.diameter, 3)          # moitié de Ø6

    def test_fine(self):
        t = A.pick_tool(A.Step(tool_kind='boule', rule='fin'), self.tools, self.info)
        self.assertEqual(t.diameter, 4)          # rayon ≤ 2 (plus petit rayon creux)
        info = A.PartInfo(30.0, 30.0, 5.0, 0.0, 30.0)
        t = A.pick_tool(A.Step(tool_kind='boule', rule='fin'), self.tools, info)
        self.assertEqual(t.diameter, 1)          # sans rayon connu : ≈ 1/30 de la pièce (Ø1 mini)

    def test_chosen_and_missing(self):
        st = A.Step(tool_kind='boule', rule='outil', tool_id=self.tools[7].id)
        self.assertIs(A.pick_tool(st, self.tools, self.info), self.tools[7])
        self.assertIsNone(A.pick_tool(A.Step(tool_kind='conique'), self.tools, self.info))
        nt = A.new_tool(A.Step(tool_kind='fraise', rule='gros'), self.info)
        self.assertEqual((nt.kind, nt.diameter, nt.number), ('fraise', 12.0, 0))
        self.assertEqual(A._round_d(2.5), 2.0)

    def test_scallop(self):
        so = A.stepover_for_scallop(1.5, 0.01)
        self.assertAlmostEqual(so, 2 * math.sqrt(2 * 1.5 * 0.01 - 1e-4), 12)
        h = 1.5 - math.sqrt(1.5 ** 2 - (so / 2) ** 2)
        self.assertAlmostEqual(h, 0.01, 9)       # la crête voulue

    def test_plan(self):
        seq = A.builtin()['Ébauche, demi-finition, finition']
        lib = [T('boule', 2.5)]
        out = A.plan(seq, self.tools[:2], lib, self.info, depth=12.0, defaults={'safe_z': 5.0})
        self.assertEqual([p.op.kind for p in out], ['ebauche3d', 'surface3d', 'surface3d'])
        rough, semi, fin = out
        self.assertEqual((rough.tool.diameter, rough.origin), (6, 'document'))
        self.assertEqual(rough.op.step_down, 0.2)                    # la passe de l'outil
        self.assertEqual(rough.op.stock, 0.5)
        self.assertEqual(rough.op.safe_z, 5.0)
        self.assertEqual((semi.tool.diameter, semi.origin), (2.5, 'bibliotheque'))
        self.assertGreaterEqual(fin.op.step_down, 1000.0)            # finition : la surface d'une passe
        self.assertEqual(fin.origin, 'bibliotheque')                 # boule Ø2,5 : seule boule disponible
        self.assertEqual(fin.op.raster_dir, 'xy')
        self.assertAlmostEqual(fin.op.stepover_mm, round(A.stepover_for_scallop(1.25, 0.01), 3), 9)
        seq.steps[1].enabled = False
        self.assertEqual(len(A.plan(seq, self.tools, [], self.info)), 2)

    def test_finish_alone_steps_down(self):
        out = A.plan(A.builtin()['Finition seule'], self.tools, [], self.info)
        self.assertEqual(out[0].op.step_down, 0.0)                  # seule : paliers à la passe de l'outil


class TestStorage(unittest.TestCase):
    def test_user_and_plugin(self):
        from vectordrive.cam import templates
        self.assertEqual(A.user_dir().parent, templates.user_dir().parent)
        seq = A.Sequence('Mon moule', 'essai', [A.Step('ebauche3d', 'É', 'fraise', 'gros', params={'stock': 0.2})])
        f = A.save_user(seq)
        self.assertTrue(f.is_file())
        try:
            found = A.all_sequences()['Mon moule']
            self.assertEqual(found[0], 'utilisateur')
            self.assertEqual(found[1].steps[0].params, {'stock': 0.2})
            self.assertNotIn('Mon moule', templates.user_templates())     # pas mêlé aux modèles d'usinage
        finally:
            self.assertTrue(A.delete_user('Mon moule'))
        from vectordrive.plugins import REGISTRY
        REGISTRY.templates.setdefault(A.KIND, {})['Gamme plugin'] = {'steps': [{'kind': 'surface3d'}]}
        try:
            self.assertEqual(A.all_sequences()['Gamme plugin'][0], 'plugin')
        finally:
            del REGISTRY.templates[A.KIND]['Gamme plugin']
        self.assertIn('Ébauche et finition', A.all_sequences())


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestPartAndWindow(unittest.TestCase):
    def test_analyze(self):
        f = pocket_stl()
        m = mill3d.load_model(Document(), f)
        i = A.analyze(m)
        self.assertEqual((round(i.size_x), round(i.size_y), round(i.depth)), (40, 20, 10))
        j = A.analyze(m, faces=[face_under(m, 20, 10)])
        self.assertEqual((round(j.size_x), round(j.size_y), round(j.depth)), (20, 10, 5))
        m.face_kinds = [{'genre': 'cylindre', 'rayon': 1.5, 'creux': True}, {'genre': 'cylindre', 'rayon': 0.8,
                                                                              'creux': False}]
        self.assertEqual(A.analyze(m).min_radius, 1.5)           # un bossage ne limite pas l'outil
        m.face_kinds = []

    def test_dialog_and_apply(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(pocket_stl())
            w._ensure_panel3d()
            p = w.panel3d
            self.assertTrue(p.refresh())
            dlg = p.auto3d(exec_dialog=False, sequence='Ébauche, demi-finition, finition')
            self.assertIn('toute la pièce', dlg.zone.text())
            self.assertEqual(dlg.table.rowCount(), 3)
            self.assertIn('3 usinage(s)', dlg.summary.text())
            dlg.add_step()
            self.assertEqual(dlg.table.rowCount(), 4)
            dlg.table.selectRow(3)
            dlg.move_step(-1)
            self.assertEqual(dlg.seq.steps[2].name, 'Finition')
            dlg.table.selectRow(2)
            dlg.remove_step()
            self.assertEqual(len(dlg.seq.steps), 3)
            dlg.table.cellWidget(0, 4).setValue(0.4)                 # surépaisseur de l'ébauche
            self.assertEqual(dlg.seq.steps[0].params['stock'], 0.4)
            dlg.table.cellWidget(1, 0).setChecked(False)             # sans demi-finition
            self.assertEqual(len(dlg.planned), 2)
            name = dlg.save_as('Ma gamme 3D')
            self.assertEqual(dlg.choice.currentData(), name)
            self.assertFalse(A.all_sequences()[name][1].steps[1].enabled)
            self.assertTrue(dlg.delete_current(confirm=False))
            self.assertNotIn(name, A.all_sequences())
            dlg.choice.setCurrentIndex(dlg.choice.findData('Ébauche et finition'))
            cp = w.cam_panel
            n_undo = len(w._undo)
            ops = cp.apply_auto3d(dlg.planned)
            self.assertEqual([o.kind for o in ops], ['ebauche3d', 'surface3d'])
            self.assertEqual(len(w._undo), n_undo + 1)                # une seule annulation
            s = cp.setup()
            self.assertTrue(all(s.tool(o.tool_id) is not None for o in ops))
            self.assertEqual(len({t.number for t in s.tools}), len(s.tools))   # numéros distincts
            for o in ops:
                tp = next(t for t in cp.toolpaths if t.op_id == o.id)
                self.assertTrue(tp.moves, o.name)
            w.undo()
            self.assertFalse(any(o.kind in ('ebauche3d', 'surface3d') for o in cp.setup().operations))
        finally:
            w.modified = False
            w.close()

    def test_selection_zone(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(pocket_stl())
            w._ensure_panel3d()
            p = w.panel3d
            p.refresh()
            p.view.set_selection(faces=[face_under(p.view.model, 20, 10)])
            dlg = p.auto3d(exec_dialog=False)
            self.assertIn('1 face(s)', dlg.zone.text())
            self.assertTrue(all(pl.op.faces3d for pl in dlg.planned))
            self.assertTrue(all(abs(pl.op.depth - min(5.0, pl.tool.cut_length)) < 1e-6 for pl in dlg.planned))   # 608
            self.assertTrue(all(pl.op.model_path == '' for pl in dlg.planned))   # la pièce du dessin
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
