"""Round 981 : panneau FAO — les opérations et leurs parcours dans un seul tableau (un œil par ligne), la liste des
parcours seulement quand un parcours n'a pas d'opération, la liste des outils repliée tout en bas, sous son bouton."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r981.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.p = self.w.cam_panel
        doc = self.w.canvas.doc
        ids = []
        for r in ((0, 0, 20, 14), (30, 0, 12, 8)):
            sh = Shape(path=geom.Path([geom.rect(*r)]), tool=0)
            doc.add(sh)
            ids.append(sh.id)
        s = self.p.setup()
        self.tool = model.CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0)
        s.tools = [self.tool, model.CamTool(name='Cyl 3', diameter=3.0, number=2, cut_length=9)]
        s.operations = [model.Operation(name=n, kind='gravure', tool_id=self.tool.id, items=[i], depth=0.2)
                        for n, i in zip(('Un', 'Deux'), ids)]
        self.p.save(s)

    def tearDown(self):
        if hasattr(self.p, 'set_tools_open'):
            self.p.set_tools_open(False)
        self.w.modified = False
        self.w.close()

    def eye(self, r):
        """L'œil de la ligne `r` : True (parcours montré), False (caché), None (pas de parcours)."""
        cell = self.p.ops.item(r, getattr(self.p, 'EYE_COL', 4))
        return None if cell is None else cell.data(Qt.ItemDataRole.UserRole)

    def select(self, r):
        from PySide6.QtCore import QItemSelectionModel
        t = self.p.ops
        f = QItemSelectionModel.SelectionFlag
        t.selectionModel().setCurrentIndex(t.model().index(r, 0), f.ClearAndSelect | f.Rows)


class OneTable(Base):

    def test_an_eye_on_each_operation(self):
        p = self.p
        self.assertEqual(p.ops.columnCount(), 5)                             # avant : pas d'œil sur les opérations
        self.assertEqual(p.ops.horizontalHeader().visualIndex(p.EYE_COL), 0)  # en tête de ligne
        self.assertEqual([self.eye(0), self.eye(1)], [None, None])           # pas encore de parcours
        self.assertIsNone(p.toggle_op_paths(0))
        p.compute()
        self.assertEqual([tp.name for tp in p.toolpaths], ['Un', 'Deux'])
        self.assertEqual([self.eye(0), self.eye(1)], [True, True])
        p.ops.cellClicked.emit(1, p.EYE_COL)                                 # un clic sur l'œil : parcours caché
        self.assertEqual([tp.shown for tp in p.toolpaths], [True, False])
        self.assertEqual([self.eye(0), self.eye(1)], [True, False])
        self.assertEqual([tp.name for tp in p.checked_paths()], ['Un'])      # ni dessiné, ni écrit
        p.ops.cellClicked.emit(1, 0)                                         # un clic ailleurs sur la ligne : rien
        self.assertEqual(self.eye(1), False)
        p.ops.cellClicked.emit(1, p.EYE_COL)
        self.assertEqual([tp.shown for tp in p.toolpaths], [True, True])
        p.set_path_shown(0, False)                                           # caché d'ailleurs (calque Trajectoires)
        self.assertEqual([self.eye(0), self.eye(1)], [False, True])
        self.assertEqual(p.ops.item(0, 0).checkState(), Qt.CheckState.Checked)   # la case : toujours l'opération active
        self.assertTrue(p.ops.item(0, 0).text().startswith('Un'))

    def test_paths_list_only_for_paths_without_operation(self):
        from vectordrive.cam import model
        p = self.p
        p.compute()
        self.assertFalse(p.paths.isVisibleTo(p))                             # avant : la même liste, deux fois
        self.assertEqual(p.paths.count(), 2)                                 # un rang par parcours, comme avant
        read = model.Toolpath('', '', [model.Move('feed', 0, 0, 0)], name='Lu')
        p.display(p.toolpaths + [read])                                      # un programme lu : pas d'opération
        self.assertFalse(p.paths.isVisibleTo(p))                            # 1012 : une ligne du tableau
        self.assertEqual(p.ops.rowCount(), 3)
        self.assertEqual(p.paths.count(), 3)
        self.assertEqual([self.eye(0), self.eye(1)], [True, True])
        p.paths.setCurrentRow(2)
        p.remove_path()
        self.assertFalse(p.paths.isVisibleTo(p))

    def test_path_of_the_operation_by_right_click(self):
        p = self.p
        self.select(1)
        acts = {a.text(): a for a in p.op_menu(exec_menu=False).actions()}
        self.assertIn('Afficher ou cacher le parcours', acts)                # avant : seulement dans la liste du bas
        self.assertFalse(acts['Afficher ou cacher le parcours'].isEnabled())  # pas encore de parcours
        p.compute()
        self.select(1)
        acts = {a.text(): a for a in p.op_menu(exec_menu=False).actions()}
        acts['Afficher ou cacher le parcours'].trigger()
        self.assertEqual([tp.shown for tp in p.toolpaths], [True, False])
        acts['Inverser le sens du parcours'].trigger()
        self.assertTrue(getattr(p.toolpaths[1], 'reversed', False))
        self.assertFalse(getattr(p.toolpaths[0], 'reversed', False))
        acts['Retirer le parcours calculé'].trigger()
        self.assertEqual([tp.name for tp in p.toolpaths], ['Un'])
        self.assertEqual([self.eye(0), self.eye(1)], [True, None])


class ToolsAtTheBottom(Base):

    def test_tools_folded_under_their_button(self):
        from vectordrive.ui.main_window import MainWindow
        p = self.p
        self.assertTrue(p.split.widget(0).isAncestorOf(p.ops))               # avant : les outils en tête du panneau
        self.assertTrue(p.split.widget(p.split.count() - 1).isAncestorOf(p.tools))
        self.assertFalse(p.tools.isVisibleTo(p))                             # repliée d'office
        self.assertTrue(p.tools_toggle.isVisibleTo(p))
        self.assertIn('(2)', p.tools_toggle.text())                          # le nombre d'outils du dessin
        self.assertEqual(p.tools.rowCount(), 2)                              # la liste reste remplie
        p.tools_toggle.click()
        self.assertTrue(p.tools.isVisibleTo(p))
        self.assertTrue(p.tools_open())
        other = MainWindow()                                                 # retenu : dépliée au prochain lancement
        try:
            self.assertTrue(other.cam_panel.tools.isVisibleTo(other.cam_panel))
        finally:
            other.modified = False
            other.close()
        p.tools_toggle.click()
        self.assertFalse(p.tools.isVisibleTo(p))


if __name__ == '__main__':
    unittest.main()
