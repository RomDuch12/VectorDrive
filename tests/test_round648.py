"""Round 648 : plus de contrôles dans l'automatisme d'usinage 3D — faces
choisies (cases, part hors d'atteinte), crête de la boule, réglages complets
d'une étape (formulaire de l'opération, champs changés gardés), aperçu des
usinages prise par prise."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(tempfile.mkdtemp(), 'modeles_fao'))

from PySide6.QtWidgets import QApplication, QDoubleSpinBox

from tests.test_round596 import two_boxes_stl
from vectordrive.cam import auto3d as A
from vectordrive.cam import mill3d
from vectordrive.core import access3d as AC
from vectordrive.core import solids as SO

app = QApplication.instance() or QApplication([])


class TestLeftOut(unittest.TestCase):
    def test_boxes(self):
        m = mill3d.raw_model(two_boxes_stl())
        cache = {}
        left = AC.left_out(m, ['+Z'], 0.25, cache)
        self.assertAlmostEqual(left, 300.0 / 1120.0, delta=0.01)             # les deux dessous
        self.assertEqual(set(cache), {'+Z'})
        self.assertAlmostEqual(AC.left_out(m, ['+Z', '-Z'], 0.25, cache), 0.0, delta=1e-9)
        self.assertEqual(set(cache), {'+Z', '-Z'})
        self.assertAlmostEqual(AC.left_out(m, [], 0.25), 1.0, delta=1e-9)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestDialog(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.open_path(two_boxes_stl())
        self.w._ensure_panel3d()
        self.assertTrue(self.w.panel3d.refresh())

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def dialog(self, sequence):
        return self.w.panel3d.auto3d(exec_dialog=False, sequence=sequence)

    def test_chosen_sides(self):
        dlg = self.dialog('Ébauche seule')
        self.assertFalse(dlg.side_row.isVisibleTo(dlg))
        dlg.side_mode.setCurrentIndex(dlg.side_mode.findData('choisies'))
        self.assertTrue(dlg.side_row.isVisibleTo(dlg))
        self.assertEqual(dlg.chosen_sides(), ['+Z', '-Z'])                    # cochées comme les prises proposées
        self.assertEqual(dlg.groups(), [(-1, ['+Z', '-Z'])])
        dlg.side_checks['-Z'].setChecked(False)
        self.assertEqual(dlg.groups(), [(-1, ['+Z'])])
        self.assertIn('hors d\'atteinte : 26,', dlg.sides_text.text())        # les dessous
        self.assertIn('1 usinage(s)', dlg.summary.text())
        dlg.side_checks['+X'].setChecked(True)
        self.assertEqual(dlg.groups(), [(-1, ['+Z', '+X'])])
        self.assertEqual([p.op.setup_face for p in dlg.planned if p.tool is not None], ['+Z', '+X'])
        self.assertEqual(sum(1 for p in dlg.planned if p.tool is None), 2)   # « poser la pièce » avant chacune
        dlg.body_mode.setCurrentIndex(dlg.body_mode.findData('chacun'))
        self.assertEqual(dlg.groups(), [(0, ['+Z', '+X']), (1, ['+Z', '+X'])])
        self.assertIn('Corps 2', dlg.sides_text.text())
        for cb in dlg.side_checks.values():
            cb.setChecked(False)
        self.assertEqual(dlg.groups(), [(0, ['']), (1, [''])])               # aucune : comme le dessin
        dlg.side_mode.setCurrentIndex(dlg.side_mode.findData('toutes'))
        self.assertEqual(dlg.groups(), [(0, ['+Z', '-Z']), (1, ['+Z', '-Z'])])
        self.assertFalse(dlg.side_row.isVisibleTo(dlg))
        dlg.side_mode.setCurrentIndex(dlg.side_mode.findData('choisies'))
        self.assertEqual(dlg.chosen_sides(), [])                             # choix de l'utilisateur gardé

    def test_crest(self):
        dlg = self.dialog('Ébauche et finition')
        rough = dlg.table.cellWidget(0, 7)
        fin = dlg.table.cellWidget(1, 7)
        self.assertIsInstance(fin, QDoubleSpinBox)
        self.assertFalse(rough.isEnabled())                                  # fraise d'ébauche : sans crête
        self.assertTrue(fin.isEnabled())
        self.assertAlmostEqual(fin.value(), A.CRETE, 6)

        def finish():
            return next(p for p in dlg.planned if p.op.kind == 'surface3d')
        fin.setValue(0.05)
        self.assertEqual(dlg.seq.steps[1].params['crete'], 0.05)
        p = finish()
        self.assertAlmostEqual(p.op.stepover_mm, round(A.stepover_for_scallop(p.tool.diameter / 2, 0.05), 3), 6)
        self.assertIn(f'{p.op.stepover_mm:g}'.replace('.', ','), dlg.table.cellWidget(1, 6).toolTip())
        self.assertIn('Crête (mm) : 0,05', dlg.table.item(1, 1).toolTip())
        fin.setValue(0.0)                                                    # auto : la crête par défaut
        self.assertNotIn('crete', dlg.seq.steps[1].params)
        p = finish()
        self.assertAlmostEqual(p.op.stepover_mm, round(A.stepover_for_scallop(p.tool.diameter / 2, A.CRETE), 3), 6)

    def test_step_settings(self):
        dlg = self.dialog('Ébauche et finition')
        st = dlg.seq.steps[0]
        before = dict(st.params)
        fd = dlg.step_settings(0, exec_dialog=False)
        self.assertFalse(fd.widgets['kind'].isEnabled())                     # stratégie, outil : dans le tableau
        self.assertFalse(fd.widgets['tool_id'].isEnabled())
        for hidden in ('model_path', 'faces3d', 'setup_face', 'body3d', 'name'):
            self.assertNotIn(hidden, fd.widgets)
        self.assertTrue(fd.widgets['ramp'].isChecked())
        fd.widgets['ramp'].setChecked(False)
        fd.widgets['feed'].setValue(777.0)
        fd.accept()
        self.assertIs(st.params['ramp'], False)
        self.assertEqual(st.params['feed'], 777.0)
        changed = set(st.params) - set(before)
        self.assertEqual(changed, {'feed'})                                  # le reste : toujours automatique
        op = next(p.op for p in dlg.planned if p.op.kind == 'ebauche3d')
        self.assertEqual((op.ramp, op.feed), (False, 777.0))
        self.assertIn('non', dlg.table.item(0, 1).toolTip())                 # rampe : non
        fd = dlg.step_settings(0, exec_dialog=False)
        fd.reject()
        self.assertEqual(st.params['feed'], 777.0)                           # annulé : rien de changé
        name = dlg.save_as('Essai 648')
        self.assertEqual(A.all_sequences()[name][1].steps[0].params['feed'], 777.0)   # gardé avec la suite
        self.assertTrue(dlg.delete_current(confirm=False))
        dlg.table.cellWidget(1, 0).setChecked(False)
        self.assertIsNone(dlg.step_settings(1, exec_dialog=False))           # étape inactive

    def test_preview(self):
        dlg = self.dialog('Ébauche et finition')
        self.assertFalse(dlg.preview.isVisibleTo(dlg))
        self.assertEqual(dlg.preview_btn.text(), 'Aperçu des usinages (2)')
        self.assertEqual(dlg.preview.topLevelItemCount(), 2)                 # une prise : à plat
        dlg.preview_btn.setChecked(True)
        self.assertTrue(dlg.preview.isVisibleTo(dlg))
        first = dlg.preview.topLevelItem(0)
        self.assertEqual(first.text(0), 'Ébauche')
        p = dlg.planned[0]
        self.assertEqual(first.text(1), dlg_tool_text(p.tool))
        if p.origin == 'nouveau':
            self.assertIn('outil à créer', first.text(3))
        dlg.side_mode.setCurrentIndex(dlg.side_mode.findData('toutes'))
        self.assertEqual(dlg.preview.topLevelItemCount(), 2)                 # deux prises
        self.assertTrue(dlg.preview.topLevelItem(1).text(0).startswith('Poser la pièce : dessous'))
        self.assertEqual(dlg.preview.topLevelItem(1).childCount(), 2)
        self.assertEqual(dlg.preview_btn.text(), 'Aperçu des usinages (4)')


def dlg_tool_text(t):
    from vectordrive.ui.auto3d_dialog import _tool_text
    return _tool_text(t)


if __name__ == '__main__':
    unittest.main()
