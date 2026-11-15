"""Round 694 : usinage 3D automatique — liste « Usinages » à côté de la vue
3D (ceux de la prise montrée) : modifier l'usinage (sans la sélection du
dessin), son outil (parcours de ses usinages refaits), recalculer,
dupliquer, monter, supprimer le parcours seul, supprimer l'usinage
(annulable), activer ; ruban FAO 3D, groupe « Usinages » (Full HD) ;
fenêtre de l'automatisme : « Outil de l'étape… » (copie modifiée)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vectordrive.core import solids as SO
from tests.test_round596 import two_boxes_stl

app = QApplication.instance() or QApplication([])


def names(lst):
    return [lst.tree.topLevelItem(i).text(0) for i in range(lst.tree.topLevelItemCount())]


def states(lst):
    return [lst.tree.topLevelItem(i).text(2) for i in range(lst.tree.topLevelItemCount())]


class TestRibbon(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_group(self):
        from tests.test_round672 import full_hd, tab_index
        w = self.w
        page = w.ribbon.page(tab_index(w.ribbon, 'FAO 3D'))
        titles = [g.title.text() for g in page.groups()]
        self.assertEqual(titles.index('Usinages'), titles.index('Usinage 3D') + 1)
        g = next(g for g in page.groups() if g.title.text() == 'Usinages')
        self.assertEqual([b.defaultAction() for b in g.buttons()],
                         [w.A[k] for k in ('cam3d_ops_list', 'cam3d_op_edit', 'cam3d_op_tool', 'cam3d_op_remove')])
        colors = next(g for g in page.groups() if g.title.text() == 'Corps et couleurs')
        self.assertIn(w.A['cam3d_colors'], [b.defaultAction() for b in colors.buttons()])
        self.assertEqual(w.A['cam3d_colors'].menu().actions(),
                         [w.A[k] for k in ('cam3d_part_color', 'cam3d_edge_color', 'cam3d_reset_colors')])
        self.assertEqual(page.fit(full_hd()), [])
        self.assertFalse(any(g.iconic for g in page.groups()))          # libellés gardés en Full HD
        self.assertTrue(w.A['cam3d_ops_list'].isCheckable() and w.A['cam3d_ops_list'].isChecked())


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestList(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.open_path(two_boxes_stl())
        self.p = self.w._ensure_panel3d()
        self.assertTrue(self.p.refresh())
        self.lst = self.p.ops_list
        self.assertFalse(self.lst.isVisibleTo(self.p))                  # pas d'usinage : pas de liste
        with mock.patch('vectordrive.ui.auto3d_dialog.Auto3DDialog.exec', return_value=1):
            self.ops = self.p.auto3d(sequence='Ébauche et finition')
        self.cp = self.w.cam_panel

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def op(self, i=0):
        oid = self.lst.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
        return next(o for o in self.cp.setup().operations if o.id == oid)

    def test_after_auto(self):
        lst, cp = self.lst, self.cp
        made = [o for o in self.ops if o.kind != 'instruction']
        self.assertEqual(len(made), 2)
        self.assertTrue(lst.isVisibleTo(self.p))
        self.assertEqual(names(lst), [o.name for o in made])
        self.assertEqual(lst.current_id(), made[0].id)                   # le premier choisi
        self.assertEqual(cp._current_op()[2].id, made[0].id)             # aussi dans le panneau FAO
        self.assertEqual(states(lst), ['calculé', 'calculé'])
        self.assertIn('2 usinage(s) créé(s)', self.w.statusBar().currentMessage())
        self.assertEqual(lst.title.text(), 'Usinages (2)')

    def test_remove_path_and_recompute(self):
        lst, cp = self.lst, self.cp
        op = self.op()
        n = len(cp.setup().operations)
        self.assertGreater(lst.remove_path(), 0)
        self.assertFalse(any(t.op_id == op.id for t in cp.toolpaths))
        self.assertEqual(len(cp.setup().operations), n)                  # l'usinage reste
        self.assertEqual(states(lst)[0], 'à calculer')
        self.assertEqual(lst.remove_path(), 0)                           # plus rien : dit
        self.assertIn('Pas de parcours calculé', self.w.statusBar().currentMessage())
        lst.recompute()
        self.assertTrue(any(t.op_id == op.id for t in cp.toolpaths))
        self.assertEqual(states(lst)[0], 'calculé')

    def test_remove_op_undo(self):
        w, lst, cp = self.w, self.lst, self.cp
        op = self.op()
        second = self.op(1)
        w.A['cam3d_op_remove'].trigger()
        self.assertNotIn(op.id, [o.id for o in cp.setup().operations])
        self.assertFalse(any(t.op_id == op.id for t in cp.toolpaths))
        self.assertEqual(names(lst), [second.name])
        self.assertEqual(lst.current_id(), second.id)                    # la suivante choisie
        w.undo()
        self.assertIn(op.id, [o.id for o in cp.setup().operations])     # Annuler la rend
        self.assertEqual(len(names(lst)), 2)

    def test_edit_op(self):
        from vectordrive.ui.cam_panel import FieldsDialog
        lst, cp = self.lst, self.cp
        op = self.op()
        items = list(op.items)
        calls = []
        real = cp.compute_op
        with mock.patch.object(cp, '_selected', return_value=[mock.Mock(id='trait')]), \
                mock.patch.object(cp, 'compute_op', side_effect=lambda o: calls.append(o.id) or real(o)):
            dlg = lst.edit(exec_dialog=False)
            self.assertIsInstance(dlg, FieldsDialog)
            dlg.widgets['stock'].setValue(0.5)
            dlg.accept()
        self.assertEqual(lst.current_id(), op.id)                        # toujours dans la liste, choisi
        before, op = op, self.op()
        self.assertAlmostEqual(op.stock, 0.5)
        self.assertEqual(op.items, items)                                # sélection du dessin pas prise
        self.assertEqual(calls, [op.id])                                 # son parcours refait
        self.assertEqual(op.body3d, -1)                                  # toute la pièce, pas le corps 1
        self.assertEqual(op.wrap_guide, [])                              # liste gardée (pas le texte « [] »)
        self.assertEqual((op.setup_face, op.faces3d, op.contours3d),
                         (before.setup_face, before.faces3d, before.contours3d))

    def test_form_whole_part_body(self):
        from vectordrive.ui.cam_panel import FieldsDialog
        s = self.cp.setup()
        op = self.op()
        dlg = FieldsDialog(None, 'x', op, self.w.canvas.doc, s.tools)
        self.assertEqual(dlg.widgets['body3d'].value(), -1)
        self.assertEqual(dlg.widgets['body3d'].text(), 'toute la pièce')
        dlg.widgets['body3d'].setValue(1)
        dlg.apply()
        self.assertEqual(op.body3d, 1)
        dlg.deleteLater()

    def test_edit_tool(self):
        lst, cp = self.lst, self.cp
        op = self.op()
        s = cp.setup()
        tid = op.tool_id
        users = [o.id for o in s.operations if o.tool_id == tid]
        calls = []
        real = cp.compute_op
        undo = len(self.w._undo)
        with mock.patch.object(cp, 'compute_op', side_effect=lambda o: calls.append(o.id) or real(o)):
            dlg = lst.edit_tool(exec_dialog=False)
            self.assertIn('Outil de', dlg.windowTitle())
            dlg.widgets['diameter'].setValue(5.0)
            dlg.accept()
        self.assertAlmostEqual(cp.setup().tool(tid).diameter, 5.0)
        self.assertEqual(sorted(calls), sorted(users))                  # parcours des usinages de l'outil
        self.assertEqual(len(self.w._undo), undo + 1)

    def test_duplicate_move(self):
        lst, cp = self.lst, self.cp
        a, b = self.op(), self.op(1)
        c = lst.duplicate()
        self.assertEqual(lst.current_id(), c.id)
        self.assertEqual(names(lst)[1], c.name)
        self.assertEqual(states(lst)[1], 'à calculer')
        lst.select(a.id)
        self.assertTrue(lst.move(1))
        ids = [lst.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) for i in range(3)]
        self.assertEqual(ids, [c.id, a.id, b.id])
        self.assertEqual(lst.current_id(), a.id)
        self.assertEqual([o.id for o in cp.setup().operations if o.kind != 'instruction'], ids)
        lst.select(c.id)
        self.assertFalse(lst.move(-1))                                   # déjà le premier

    def test_enable_and_toggle(self):
        w, lst, cp = self.w, self.lst, self.cp
        op = self.op()
        lst.tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Unchecked)
        self.assertFalse(next(o for o in cp.setup().operations if o.id == op.id).enabled)
        self.assertTrue(lst._refill.isActive())                          # liste refaite après le signal de la case
        app.processEvents()
        self.assertEqual(lst.tree.topLevelItem(0).checkState(0), Qt.CheckState.Unchecked)
        self.assertEqual(lst.current_id(), op.id)
        w.A['cam3d_ops_list'].setChecked(False)
        self.assertFalse(lst.isVisibleTo(self.p))
        self.assertFalse(lst.wanted())
        w.A['cam3d_ops_list'].setChecked(True)
        self.assertTrue(lst.isVisibleTo(self.p))

    def test_keys(self):
        from PySide6.QtTest import QTest
        w, lst, cp = self.w, self.lst, self.cp
        w.show()
        w.activateWindow()
        lst.tree.setFocus()
        op = self.op()
        erased = []
        w.A['delete'].triggered.connect(lambda *_: erased.append(1))
        QTest.keyClick(lst.tree, Qt.Key.Key_Delete)
        self.assertNotIn(op.id, [o.id for o in cp.setup().operations])
        self.assertEqual(erased, [])                                     # « Effacer » du dessin : pas lancé
        with mock.patch.object(lst, 'edit') as edit:
            QTest.keyClick(lst.tree, Qt.Key.Key_M, Qt.KeyboardModifier.ControlModifier)
        edit.assert_called_once_with()

    def test_nothing_chosen(self):
        lst = self.lst
        lst.tree.clearSelection()
        self.assertIsNone(lst.edit(exec_dialog=False))
        self.assertEqual(lst.remove_path(), 0)
        self.assertIn('Choisissez un usinage', self.w.statusBar().currentMessage())

    def test_shown_setup_only(self):
        p, lst = self.p, self.lst
        p.part_tabs.setCurrentIndex(p._tab_keys['part'].index(1))       # le corps 2 : pas ses usinages
        self.assertEqual(p.current_setup(), ('', 1))
        self.assertEqual(names(lst), [])
        self.assertTrue(lst.empty.isVisibleTo(p))
        self.assertTrue(lst.isVisibleTo(p))                              # le dessin en a : liste gardée
        p.part_tabs.setCurrentIndex(p._tab_keys['part'].index(-1))
        self.assertEqual(len(names(lst)), 2)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestStepTool(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.open_path(two_boxes_stl())
        self.p = self.w._ensure_panel3d()
        self.assertTrue(self.p.refresh())

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_step_tool(self):
        dlg = self.p.auto3d(exec_dialog=False, sequence='Ébauche seule')
        first = next(x for x in dlg.planned if x.step is dlg.seq.steps[0])
        orig = first.tool
        before = (orig.id, orig.diameter, orig.name)
        t = dlg.step_tool(0, exec_dialog=False)
        t.widgets['diameter'].setValue(3.0)
        t.accept()
        st = dlg.seq.steps[0]
        self.assertEqual(st.rule, 'outil')
        self.assertIn(st.tool_id, dlg.edited_tools)
        got = next(x for x in dlg.planned if x.step is st)
        self.assertAlmostEqual(got.tool.diameter, 3.0)
        self.assertTrue(got.tool.name.endswith('(modifié)'))
        self.assertEqual((orig.id, orig.diameter, orig.name), before)   # l'outil d'origine ne change pas
        t2 = dlg.step_tool(0, exec_dialog=False)                         # la copie, modifiée de nouveau
        t2.widgets['diameter'].setValue(4.0)
        t2.accept()
        self.assertEqual(len(dlg.edited_tools), 1)
        got = next(x for x in dlg.planned if x.step is st)
        self.assertAlmostEqual(got.tool.diameter, 4.0)
        ops = self.w.cam_panel.apply_auto3d(dlg.planned)
        s = self.w.cam_panel.setup()
        t = s.tool(next(o for o in ops if o.kind != 'instruction').tool_id)
        self.assertAlmostEqual(t.diameter, 4.0)                          # ajoutée au dessin
        dlg.deleteLater()


if __name__ == '__main__':
    unittest.main()
