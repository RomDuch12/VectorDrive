"""Round 427 : opérations FAO — clic droit (mettre à jour avec la sélection, modifier, dupliquer,
supprimer, simuler)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestOpMenu(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.c = self.w.canvas
        self.cp = self.w.cam_panel
        self.a = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
        self.b = Shape(path=geom.Path([geom.rect(40, 0, 20, 10)]))
        self.c.doc.add(self.a)
        self.c.doc.add(self.b)
        self.c.select([self.a])
        self.op = self.cp.new_operation('gravure', exec_dialog=False)
        self.cp.ops.selectRow(0)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def tp_box(self):
        tp = next(t for t in self.cp.toolpaths if t.op_id == self.op.id)
        xs = [m.x for m in tp.moves if m.kind != 'rapid'] or [m.x for m in tp.moves]
        return min(xs), max(xs)

    def test_menu_and_update(self):
        m = self.cp.op_menu(exec_menu=False)
        texts = [a.text() for a in m.actions() if not a.isSeparator()]
        self.assertEqual(texts, ['Mettre à jour avec le dessin sélectionné', 'Modifier…', 'Dupliquer', 'Supprimer',
                                 'Lier au parcours précédent', 'Informations…', 'Compte rendu parcours outil…',
                                 'Afficher ou cacher le parcours', 'Inverser le sens du parcours',
                                 'Retirer le parcours calculé',
                                 'Simuler en 2D', 'Simuler en 3D', 'Matière restante après cette opération…',
                                 "Reprise d'usinage…"])   # rounds 699, 848, 861, 981, 998
        self.assertLess(self.tp_box()[1], 25)
        self.c.select([self.b])
        self.cp.update_op_from_selection()
        op = self.cp.setup().operations[0]
        self.assertEqual(op.items, [self.b.id])
        self.assertGreater(self.tp_box()[0], 35)                            # parcours refait sur l'autre dessin
        self.assertEqual(op.kind, self.op.kind)

    def test_duplicate_remove(self):
        c = self.cp.duplicate_op()
        ops = self.cp.setup().operations
        self.assertEqual(len(ops), 2)
        self.assertNotEqual(ops[1].id, ops[0].id)
        self.assertIn('(copie)', ops[1].name)
        self.assertEqual(ops[1].items, ops[0].items)
        self.assertIsNot(ops[1].items, ops[0].items)
        self.cp.ops.selectRow(0)
        self.cp.remove_op()
        self.assertEqual([o.id for o in self.cp.setup().operations], [c.id])
        self.assertFalse(any(t.op_id == self.op.id for t in self.cp.toolpaths))   # son parcours aussi

    def test_edit_takes_selection(self):
        self.c.select([self.b])
        dlg = self.cp.edit_op(exec_dialog=False)
        dlg.accept()
        self.assertEqual(self.cp.setup().operations[0].items, [self.b.id])
        self.assertGreater(self.tp_box()[0], 35)
        self.c.select([self.a])
        dlg = self.cp.edit_op(exec_dialog=False)
        dlg.reject()                                                           # annulé : rien ne change
        self.assertEqual(self.cp.setup().operations[0].items, [self.b.id])

    def test_simulate(self):
        self.cp.duplicate_op()
        self.cp.ops.selectRow(0)
        with mock.patch.object(self.w, 'show_toolpaths') as st:
            self.cp.simulate_op('sim3d')
            st.assert_called_once_with('sim3d')
        shown = [t.op_id for t in self.cp.toolpaths if t.shown]
        self.assertEqual(shown, [self.op.id])


if __name__ == '__main__':
    unittest.main()
