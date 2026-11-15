"""Round 1012 : réponse 13 du 14/11 — les parcours sans opération (programme relu, parcours TypeEdit) sont des lignes
du tableau des opérations, avec leur œil ; la liste « Parcours » à part ne se montre plus pour eux."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1012.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402


def close(w):
    w.modified = False
    for t in getattr(w, 'docs', []):
        t.modified = False
    w.close()
    app.processEvents()


def loose(name, source, depth=0.5):
    tp = model.Toolpath(op_id='', tool_id='', name=name, source=source)
    tp.moves = [model.Move('rapid', 0.0, 0.0, 5.0), model.Move('plunge', 0.0, 0.0, -depth),
                model.Move('feed', 10.0, 0.0, -depth), model.Move('feed', 10.0, 10.0, -depth),
                model.Move('rapid', 10.0, 10.0, 5.0)]
    return tp


class LooseRows(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(close, self.w)
        self.p = p = self.w.cam_panel
        doc = self.w.canvas.doc
        ids = []
        for k in range(2):
            sh = Shape(path=geom.Path([geom.rect(k * 15.0, 0, 10, 8)]), tool=0)
            doc.add(sh)
            ids.append(sh.id)
        s = p.setup()
        t = model.CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0)
        s.tools = [t]
        s.operations = [model.Operation(name=f'Op {k}', kind='gravure', tool_id=t.id, items=[i], depth=0.2)
                        for k, i in enumerate(ids)]
        p.save(s)
        p.compute()
        self.assertEqual(len(p.toolpaths), 2)
        p.display(p.toolpaths + [loose('Lettrage', 'typeedit', 0.3), loose('Relu', 'nc')])

    def cell(self, r, c=0):
        return self.p.ops.item(r, c).text()

    def test_rows_after_the_operations(self):
        p = self.p
        self.assertEqual(p.ops.rowCount(), 4)                                    # avant : 2, et une liste à part
        self.assertTrue(p.paths_group.isHidden())                               # avant : montrée
        self.assertEqual([self.cell(2), self.cell(3)], ['Lettrage', 'Relu'])
        self.assertIn('TypeEdit', self.cell(2, 1))
        self.assertEqual(self.cell(2, 3), '0.3')
        self.assertTrue(p.ops.item(2, 0).font().italic())
        self.assertFalse(p.ops.item(2, 0).flags() & Qt.ItemFlag.ItemIsUserCheckable)
        self.assertIs(p.ops.item(3, p.EYE_COL).data(Qt.ItemDataRole.UserRole), True)   # son œil, ouvert
        p.toggle_op_paths(3)                                                     # l'œil : caché
        self.assertFalse(p.toolpaths[3].shown)
        self.assertIs(p.ops.item(3, p.EYE_COL).data(Qt.ItemDataRole.UserRole), False)
        self.assertNotIn(p.toolpaths[3], p.checked_paths())
        p.refresh()                                                              # le réglage relu : elles restent
        self.assertEqual(p.ops.rowCount(), 4)
        self.assertEqual(self.cell(3), 'Relu')

    def test_operation_commands_leave_them_alone(self):
        p = self.p
        p._select_row(p.ops, 2)
        self.assertEqual(p._row(p.ops), -1)                                      # pas une opération
        self.assertEqual(p._loose_row(), 2)
        self.assertEqual(p._current_op()[2], None)
        self.assertEqual(len(p.chosen_ops()), 2)                               # aucune opération choisie : toutes
        with mock.patch.object(p, 'program_form', return_value='form') as form:  # double clic : en faire une opération
            self.assertEqual(p.edit_op(exec_dialog=False), 'form')
        self.assertIs(form.call_args[0][0], p.toolpaths[2])
        menu = p.op_menu(exec_menu=False)
        self.assertIsNotNone(menu)
        texts = [a.text() for a in menu.actions()]
        self.assertIn('En faire une opération…', texts)                         # le menu de ces lignes
        self.assertIn('Retirer le parcours', texts)
        with mock.patch.object(p, '_confirm_remove_loose', return_value=False) as ask:
            p.remove_op()                                                        # Suppr, refusé : rien ne part
        self.assertIs(ask.call_args[0][0], p.toolpaths[2])
        self.assertEqual(len(p.toolpaths), 4)
        with mock.patch.object(p, '_confirm_remove_loose', return_value=True):
            p.remove_op()                                                        # Suppr : retiré, l'opération non
        self.assertEqual(len(p.setup().operations), 2)
        self.assertEqual([tp.name for tp in p.toolpaths[2:]], ['Relu'])
        self.assertEqual(p.ops.rowCount(), 3)
        p._select_row(p.ops, 0)
        self.assertEqual(p._row(p.ops), 0)
        self.assertEqual(p._loose_row(), -1)

    def test_the_list_shows_for_a_path_between_two_operations(self):
        p = self.p
        t = p.toolpaths
        p.display([t[0], t[2], t[1], t[3]])                                      # écrit entre deux opérations
        self.assertFalse(p.paths_group.isHidden())
        p.display([t[0], t[1], t[2], t[3]])
        self.assertTrue(p.paths_group.isHidden())

    def test_up_and_down_move_the_path(self):
        p = self.p
        p._select_row(p.ops, 2)                                                  # Lettrage, 3e parcours écrit
        p.move_op(-1)                                                            # ↑ : avant la 2e opération
        self.assertEqual([tp.name for tp in p.toolpaths][1], 'Lettrage')
        self.assertFalse(p.paths_group.isHidden())                              # l'ordre d'écriture se montre
        self.assertEqual(p._loose_row(), 1)                                      # toujours choisi
        self.assertEqual(len(p.setup().operations), 2)
        p.move_op(1)                                                             # ↓ : revenu
        self.assertEqual([tp.name for tp in p.toolpaths][2], 'Lettrage')
        self.assertTrue(p.paths_group.isHidden())
        self.assertEqual(sorted({i.row() for i in p.ops.selectedIndexes()}), [2])   # sa ligne, choisie

    def test_up_passes_all_the_paths_of_an_operation(self):
        import copy
        p = self.p
        t = p.toolpaths
        p.display([t[0], t[1], copy.copy(t[1]), t[2], t[3]])                    # la 2e opération : deux passes
        p._select_row(p.ops, 2)
        p.move_op(-1)                                                            # ↑ : avant les deux, pas entre
        ids = [tp.op_id for tp in p.toolpaths]
        self.assertEqual(p.toolpaths[1].name, 'Lettrage')
        self.assertEqual(ids[2], ids[3])
        p.move_op(1)
        self.assertEqual(p.toolpaths[3].name, 'Lettrage')
        p.move_op(1)                                                             # un autre parcours sans opération
        self.assertEqual([tp.name for tp in p.toolpaths[3:]], ['Relu', 'Lettrage'])
        p.move_op(1)                                                             # déjà le dernier : rien
        self.assertEqual(p.toolpaths[4].name, 'Lettrage')


if __name__ == '__main__':
    unittest.main()
