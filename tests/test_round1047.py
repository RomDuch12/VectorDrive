"""Round 1047 : demande du 15/11, 23 h 30 — « enregistrer la liste des parcours dans FAO parcours dossier mes process et
user doit pouvoir enregistrer et gérer ses process. Pour l'appliquer à une autre gravure, il faudra les adapter aux
nouvelles formes : colonne opérations à coté de l'oeil mettre un bouton icone actualiser qui appliquera ce parcours aux
formes sélectionnées »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1047.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication([])

PROCESS = 'Mes process'


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self._old = os.environ.get('VECTORDRIVE_CAM_TEMPLATES')
        os.environ['VECTORDRIVE_CAM_TEMPLATES'] = tempfile.mkdtemp()     # vos modèles : un dossier d'essai
        self.w = MainWindow()
        self.p = self.w.cam_panel
        self.pal = self.w.cam_palette
        doc = self.w.canvas.doc
        self.shapes = []
        for r in ((0, 0, 20, 14), (30, 0, 12, 8), (50, 0, 10, 10)):
            sh = Shape(path=geom.Path([geom.rect(*r)]), tool=0)
            doc.add(sh)
            self.shapes.append(sh)
        s = self.p.setup()
        self.tool = model.CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0)
        s.tools = [self.tool]
        s.operations = [model.Operation(name='Gravure', kind='gravure', tool_id=self.tool.id,
                                        items=[self.shapes[0].id], depth=0.2),
                        model.Operation(name='Détourage', kind='gravure', tool_id=self.tool.id,
                                        items=[self.shapes[1].id], depth=0.5)]
        self.p.save(s)

    def tearDown(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        if self._old is None:
            os.environ.pop('VECTORDRIVE_CAM_TEMPLATES', None)
        else:
            os.environ['VECTORDRIVE_CAM_TEMPLATES'] = self._old

    def group(self):
        t = self.pal.tree
        for i in range(t.topLevelItemCount()):
            if t.topLevelItem(i).text(0) == PROCESS:
                return t.topLevelItem(i)
        return None

    def kids(self, it):
        return [it.child(i) for i in range(it.childCount())]

    def select(self, *shapes):
        self.w.canvas.select(list(shapes))


class MyProcesses(Base):

    def test_a_folder_my_processes_after_my_models(self):
        g = self.group()
        self.assertIsNotNone(g, 'avant : pas de dossier « Mes process » dans la palette')
        t = self.pal.tree
        names = [t.topLevelItem(i).text(0) for i in range(t.topLevelItemCount())]
        self.assertEqual(names.index(PROCESS), names.index('Mes modèles') + 1)
        self.assertEqual(len(self.kids(g)), 1)                              # vide : comment le remplir
        self.assertIn('clic droit', self.kids(g)[0].text(0))

    def test_save_the_operations_of_the_drawing_as_a_process(self):
        from vectordrive.cam import templates as TPL
        save = getattr(self.pal, 'save_process', None)
        self.assertIsNotNone(save, 'avant : pas d’enregistrement de process')
        self.assertEqual(save('Plaque laiton'), 'Plaque laiton')
        tpl = TPL.user_templates()['Plaque laiton']
        self.assertTrue(tpl.get('process'))
        self.assertEqual([o['name'] for o in tpl['operations']], ['Gravure', 'Détourage'])
        self.assertTrue(all(o['items'] == [] for o in tpl['operations']))  # les formes d'un dessin : pas gardées
        rows = self.kids(self.group())
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].text(0).startswith('📋 Plaque laiton'))
        self.assertIn('2', rows[0].text(0))                                 # « — 2 opération(s) »
        self.assertIn('Détourage', rows[0].toolTip(0))

    def test_a_model_of_several_operations_already_saved_is_shown(self):
        self.p.save_template('Réglage complet', 'deux opérations')        # « Enregistrer le réglage comme modèle… »
        g = self.group()
        self.assertIsNotNone(g, 'avant : pas de dossier « Mes process »')
        self.assertEqual([k.text(0).split('  —')[0] for k in self.kids(g)], ['📋 Réglage complet'])

    def test_click_applies_it_to_the_selected_shapes(self):
        save = getattr(self.pal, 'save_process', None)
        self.assertIsNotNone(save, 'avant : pas d’enregistrement de process')
        save('Plaque')
        s = self.p.setup()
        s.operations = []
        self.p.save(s)
        self.select(self.shapes[2])
        row = self.kids(self.group())[0]
        seen = {}

        def apply(name, **kw):
            seen.update(kw, name=name)
            return []
        with mock.patch.object(self.p, 'apply_template', side_effect=apply):
            self.pal._clicked(row)
        self.assertEqual(seen.get('name'), 'Plaque')
        self.assertEqual(seen.get('prefer'), 'objets')                       # d'office : les formes sélectionnées
        self.pal.apply_process('Plaque', exec_dialog=False, items=[self.shapes[2].id])
        ops = self.p.setup().operations
        self.assertEqual([o.name for o in ops], ['Gravure', 'Détourage'])
        self.assertTrue(all(o.items == [self.shapes[2].id] for o in ops))

    def test_manage_rename_update_delete(self):
        from vectordrive.cam import templates as TPL
        save = getattr(self.pal, 'save_process', None)
        self.assertIsNotNone(save, 'avant : pas d’enregistrement de process')
        save('Plaque')
        self.assertEqual(self.pal.rename_template('Plaque', 'Plaque 2'), 'Plaque 2')
        self.assertTrue(self.kids(self.group())[0].text(0).startswith('📋 Plaque 2'))
        self.pal.move_template('Plaque 2', 'Laiton')
        name = next(iter(TPL.user_templates()))
        folder = self.kids(self.group())[0]
        self.assertEqual(folder.text(0), '📁 Laiton')                        # rangé dans un dossier de Mes process
        s = self.p.setup()
        s.operations = s.operations[:1]
        self.p.save(s)
        self.assertTrue(self.pal.update_process(name, confirm=False))       # refait avec les opérations du dessin
        tpl = TPL.user_templates()[name]
        self.assertEqual(len(tpl['operations']), 1)
        self.assertEqual(tpl.get('dossier'), 'Laiton')
        self.pal.delete_template(name, confirm=False)
        self.assertEqual(TPL.user_templates(), {})

    def test_menus(self):
        save = getattr(self.pal, 'save_process', None)
        self.assertIsNotNone(save, 'avant : pas d’enregistrement de process')
        save('Plaque')
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QMenu
        from vectordrive.ui import cam_palette as CP
        row = self.kids(self.group())[0]
        shown = []

        class Menu(QMenu):                                                    # le menu montré : ses commandes lues
            def popup(self, *_a):
                shown.append([x.text() for x in self.actions()])
        with mock.patch.object(CP, 'QMenu', Menu), mock.patch.object(self.pal.tree, 'itemAt', return_value=row):
            self.pal._menu(QPoint(5, 5))
        self.assertTrue(shown)
        texts = shown[-1]
        for want in ('Appliquer au dessin…', 'Remplacer par les opérations du dessin', 'Renommer le modèle…',
                     'Ranger dans un dossier…', 'Enregistrer les opérations du dessin comme process…'):
            self.assertIn(want, texts)

    def test_add_to_process_button_next_to_program(self):
        from vectordrive.cam import templates as TPL
        b = getattr(self.p, 'process_button', None)
        self.assertIsNotNone(b, 'avant : pas de bouton « Ajouter aux process »')
        row = self.p.program_button.parentWidget().layout()
        lay = next(row.itemAt(i).layout() for i in range(row.count()) if row.itemAt(i).layout() is not None
                   and row.itemAt(i).layout().indexOf(self.p.program_button) >= 0)
        self.assertEqual(lay.indexOf(b), lay.indexOf(self.p.program_button) + 1)    # juste à droite du programme
        self.assertEqual(b.text(), 'Ajouter aux process')
        with mock.patch('PySide6.QtWidgets.QInputDialog.getText', return_value=('Plaque', True)):
            b.click()
        self.assertTrue(TPL.user_templates()['Plaque'].get('process'))
        self.assertTrue(self.kids(self.group())[0].text(0).startswith('📋 Plaque'))

    def test_applied_without_the_window_to_the_selected_shapes(self):
        save = getattr(self.pal, 'save_process', None)
        self.assertIsNotNone(save, 'avant : pas d’enregistrement de process')
        save('Plaque')
        s = self.p.setup()
        s.operations = []
        self.p.save(s)
        self.select(self.shapes[2])
        self.pal.apply_process('Plaque', exec_dialog=False)
        self.assertTrue(all(o.items == [self.shapes[2].id] for o in self.p.setup().operations))

    def two_atelier_folders(self):
        """Un process et un modèle d'une opération, chacun dans un dossier « Atelier » (de son groupe)."""
        from vectordrive.cam import templates as TPL
        save = getattr(self.pal, 'save_process', None)
        self.assertIsNotNone(save, 'avant : pas d’enregistrement de process')
        save('Plaque')
        self.pal.move_template('Plaque', 'Atelier')
        s = self.p.setup()
        s.operations = s.operations[:1]
        self.p.save(s)
        self.p.save_template('Modèle A', '')
        TPL.set_folder('Modèle A', 'Atelier')
        self.pal.refresh()

    def where(self):
        from vectordrive.cam import templates as TPL
        return {TPL.label_of(t): t.get('dossier') for t in TPL.user_templates().values()}

    def user_folder(self):
        t = self.pal.tree
        mine = next(t.topLevelItem(i) for i in range(t.topLevelItemCount())
                    if t.topLevelItem(i).text(0) == 'Mes modèles')
        return next(k for k in self.kids(mine) if k.text(0) == '📁 Atelier')

    def choose(self, item):
        self.pal.tree.clearSelection()
        item.setSelected(True)

    def test_deleting_a_process_folder_keeps_the_models_folder(self):
        self.two_atelier_folders()
        pfolder = self.kids(self.group())[0]
        self.assertEqual(pfolder.text(0), '📁 Atelier')
        self.choose(pfolder)
        self.pal.delete_selected(confirm=False)
        self.assertEqual(self.where(), {'Modèle A': 'Atelier'})

    def test_deleting_a_models_folder_keeps_the_processes(self):
        self.two_atelier_folders()
        self.choose(self.user_folder())
        self.pal.delete_selected(confirm=False)
        self.assertEqual(self.where(), {'Plaque': 'Atelier'}, 'les process d’un dossier du même nom supprimés')

    def test_renaming_folders_apart(self):
        self.two_atelier_folders()
        rename = getattr(self.pal, 'rename_process_folder', None)
        self.assertIsNotNone(rename, 'avant : les dossiers des process ne se renomment pas à part')
        rename('Atelier', 'Laiton')
        self.assertEqual(self.where(), {'Plaque': 'Laiton', 'Modèle A': 'Atelier'})
        self.pal.rename_folder('Atelier', 'Bois')
        self.assertEqual(self.where(), {'Plaque': 'Laiton', 'Modèle A': 'Bois'})
        self.choose(self.kids(self.group())[0])                             # F2 sur un dossier de process
        with mock.patch.object(self.pal, '_ask_folder', return_value='Cuivre'):
            self.pal.rename_selected()
        self.assertEqual(self.where(), {'Plaque': 'Cuivre', 'Modèle A': 'Bois'})

    def test_a_drop_stays_in_its_group(self):
        self.two_atelier_folders()
        same = getattr(self.pal.tree, 'same_zone', None)
        self.assertIsNotNone(same, 'avant : un process se dépose dans « Mes modèles »')
        mine = self.user_folder()
        self.choose(self.kids(self.group())[0])                             # un dossier de process...
        self.assertFalse(same(mine))                                        # ... pas dans « Mes modèles »
        self.assertTrue(same(self.group()))
        self.choose(mine)                                                   # un dossier de modèles...
        self.assertFalse(same(self.group()))                                # ... pas dans « Mes process »
        self.assertTrue(same(mine.parent()))

    def test_a_click_on_a_process_folder_opens_it(self):
        self.two_atelier_folders()
        pfolder = self.kids(self.group())[0]
        was = pfolder.isExpanded()
        with mock.patch.object(self.p, 'apply_template') as apply:
            self.pal._clicked(pfolder)
        apply.assert_not_called()                                           # un dossier n'est pas un process
        self.assertNotEqual(pfolder.isExpanded(), was)

    def test_same_name_never_overwritten(self):
        from vectordrive.cam import templates as TPL
        save = getattr(self.pal, 'save_process', None)
        self.assertIsNotNone(save, 'avant : pas d’enregistrement de process')
        save('Plaque')
        self.pal.move_template('Plaque', 'A')
        s = self.p.setup()
        s.operations = s.operations[:1]
        self.p.save(s)
        self.p.save_template('Plaque', '')                                  # un modèle du même nom, dans B
        TPL.set_folder('Plaque', 'B')
        self.pal.refresh()
        self.pal.rename_process_folder('A', 'B')                            # B / Plaque existe : rien d'écrasé
        self.assertEqual(sorted(TPL.user_templates()), ['A / Plaque', 'B / Plaque'])
        self.assertTrue(TPL.user_templates()['A / Plaque'].get('process'))

    def test_applying_a_process_is_undone(self):
        save = getattr(self.pal, 'save_process', None)
        self.assertIsNotNone(save, 'avant : pas d’enregistrement de process')
        save('Plaque')
        s = self.p.setup()
        s.operations = s.operations[:1]
        self.p.save(s)
        self.select(self.shapes[2])
        self.pal.apply_process('Plaque', exec_dialog=False, replace=True)
        self.assertEqual(len(self.p.setup().operations), 2)
        self.w.undo()
        ops = self.p.setup().operations
        self.assertEqual([o.name for o in ops], ['Gravure'])
        self.assertEqual(ops[0].items, [self.shapes[0].id])

    def test_replace_asks_first(self):
        save = getattr(self.pal, 'save_process', None)
        self.assertIsNotNone(save, 'avant : pas d’enregistrement de process')
        save('Plaque')
        with mock.patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            self.assertFalse(self.pal.update_process('Plaque'))


class Retarget(Base):

    def cell(self, r):
        return self.p.ops.item(r, getattr(self.p, 'REFRESH_COL', 5))

    def test_a_refresh_button_next_to_the_eye(self):
        p = self.p
        col = getattr(p, 'REFRESH_COL', None)
        self.assertIsNotNone(col, 'avant : pas de bouton ⟳ dans la liste des opérations')
        hh = p.ops.horizontalHeader()
        self.assertEqual(hh.visualIndex(p.EYE_COL), 0)
        self.assertEqual(hh.visualIndex(col), 1)                            # juste après l'œil
        self.assertEqual([self.cell(r).text() for r in range(2)], ['⟳', '⟳'])
        self.assertIn('sélectionnées', self.cell(0).toolTip())

    def test_click_takes_the_selected_shapes(self):
        p = self.p
        col = getattr(p, 'REFRESH_COL', None)
        self.assertIsNotNone(col, 'avant : pas de bouton ⟳ dans la liste des opérations')
        self.select(self.shapes[2])
        p.ops.cellClicked.emit(1, col)
        ops = p.setup().operations
        self.assertEqual(ops[1].items, [self.shapes[2].id])
        self.assertEqual(ops[0].items, [self.shapes[0].id])                 # les autres opérations : inchangées
        self.assertIn('1', p.ops.item(1, 0).text())                         # « (1 obj.) »

    def test_nothing_selected_says_so(self):
        p = self.p
        retarget = getattr(p, 'retarget_op', None)
        self.assertIsNotNone(retarget, 'avant : pas de ⟳')
        self.select()
        self.assertFalse(retarget(0))
        self.assertIn('sélectionnez', p.info.text())
        self.assertEqual(p.setup().operations[0].items, [self.shapes[0].id])

    def test_computed_path_is_redone(self):
        p = self.p
        retarget = getattr(p, 'retarget_op', None)
        self.assertIsNotNone(retarget, 'avant : pas de ⟳')
        p.compute()
        before = [tp for tp in p.toolpaths if tp.op_id == p.setup().operations[0].id]
        self.assertTrue(before)
        x0 = min(m.x for m in before[0].moves)
        self.select(self.shapes[2])
        self.assertTrue(retarget(0))
        after = [tp for tp in p.toolpaths if tp.op_id == p.setup().operations[0].id]
        self.assertTrue(after)
        self.assertGreater(min(m.x for m in after[0].moves), x0 + 40)      # sur la 3e forme (x 50 à 60)
        self.assertEqual(len(p.toolpaths), 2)                               # l'autre parcours gardé

    def test_undo(self):
        p = self.p
        retarget = getattr(p, 'retarget_op', None)
        self.assertIsNotNone(retarget, 'avant : pas de ⟳')
        self.select(self.shapes[2])
        retarget(0)
        self.w.undo()
        self.assertEqual(p.setup().operations[0].items, [self.shapes[0].id])

    def test_loose_paths_have_no_button(self):
        p = self.p
        col = getattr(p, 'REFRESH_COL', None)
        self.assertIsNotNone(col, 'avant : pas de ⟳')
        p.compute()
        s = p.setup()
        s.operations = s.operations[:1]                                     # la 2e opération retirée : son parcours reste
        p.save(s)
        self.assertGreater(p.ops.rowCount(), 1)
        self.assertEqual(self.cell(p.ops.rowCount() - 1).text(), '')
        self.assertFalse(p.retarget_op(p.ops.rowCount() - 1, items=[self.shapes[2].id]))


if __name__ == '__main__':
    unittest.main()
