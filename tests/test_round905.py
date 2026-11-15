"""Round 905 : le calque « Trajectoires » se déplie, une ligne par parcours (case, nom, outil, mouvements). Double-clic : le
formulaire complet de l'opération du parcours ; validé, le parcours est recalculé. Un programme lu (SimPL, ISO…) arrive dans
ce calque, un parcours par outil, déplié ; le formulaire d'un de ses parcours en fait une opération (tracé repris dans un
calque du dessin, outil reconnu, profondeur du programme), dont le parcours remplace celui du programme, à sa place."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r905.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model as M  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

# deux outils : un carré de 10 à 0,3 mm de profondeur (T1), un trait en deux passes jusqu'à 0,4 mm (T2)
PROG = """%
T1 M6 (FRAISE D2)
G0 X0 Y0 Z5
G1 Z-0.3 F300
G1 X10 Y0
G1 X10 Y10
G1 X0 Y10
G1 X0 Y0
G0 Z5
T2 M6 (CONE 30 D3)
G0 X20 Y0
G1 Z-0.2
G1 X40 Y0
G1 Z-0.4
G1 X20 Y0
G0 Z5
M30
"""


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.lp, self.cp = self.w.layers_panel, self.w.cam_panel

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def computed(self):
        """Un rectangle du dessin, une opération de tracé et son parcours calculé."""
        doc = self.w.canvas.doc
        sh = Shape(path=geom.Path([geom.polyline([(0, 0), (20, 0), (20, 10), (0, 10)], closed=True)]))
        doc.active_layer.items.append(sh)
        s = self.cp.setup()
        t = M.CamTool(name='Cône', kind='conique', diameter=3.0, tip=0.1, angle=30.0)
        s.tools.append(t)
        op = M.Operation(kind='gravure', name='Cadre', tool_id=t.id, items=[sh.id], depth=0.2)
        s.operations = [op]
        self.cp.save(s)
        return self.cp.compute_op(op), op

    def program(self):
        self.cp.ask_program_tool = lambda tp, tool: 'keep'             # 906 : outil inconnu, gardé sans l'enregistrer
        path = os.path.join(tempfile.mkdtemp(), 'essai.nc')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(PROG)
        return self.w.open_nc_program(path)

    def children(self):
        row = self.lp.traj_row()
        return row, [row.child(k) for k in range(row.childCount())]


class Rows(Base):

    def test_one_row_per_toolpath_folded_by_a_click(self):
        tp, _op = self.computed()
        row, kids = self.children()
        self.assertEqual(row.text(1), 'Trajectoires')
        self.assertEqual([k.text(1) for k in kids], [tp.name])
        self.assertEqual(kids[0].text(2), 'Cône')
        self.assertEqual(kids[0].text(3), str(len(tp.moves)))
        self.assertFalse(row.isExpanded())                               # replié au départ
        self.lp._clicked(row, self.lp.COL_NAME)
        self.assertTrue(row.isExpanded())
        self.lp.refresh()                                                # déplié : il le reste
        self.assertTrue(self.lp.traj_row().isExpanded())
        self.assertEqual(len(self.w.canvas.doc.layers), 1)               # pas un calque du dessin

    def test_a_row_shows_or_hides_its_toolpath(self):
        self.computed()
        _row, kids = self.children()
        kids[0].setCheckState(0, Qt.CheckState.Unchecked)
        self.assertFalse(self.cp.toolpaths[0].shown)
        self.assertEqual(self.w.canvas.toolpaths, [])
        self.assertEqual(self.cp.paths.item(0).checkState(), Qt.CheckState.Unchecked)
        self.cp.paths.item(0).setCheckState(Qt.CheckState.Checked)        # et la liste des parcours la suit
        _row, kids = self.children()
        self.assertEqual(kids[0].checkState(0), Qt.CheckState.Checked)


class Form(Base):

    def test_double_click_opens_the_form(self):
        tp, op = self.computed()
        _row, kids = self.children()
        with mock.patch.object(self.cp, 'toolpath_form') as form:
            self.lp._double(kids[0], 1)
        form.assert_called_once_with(tp)
        dlg = self.cp.toolpath_form(tp, exec_dialog=False)               # le formulaire complet de l'opération
        self.assertEqual(dlg.obj.id, op.id)
        dlg.accept()
        self.assertEqual(len(self.cp.toolpaths), 1)
        self.assertEqual(self.cp.toolpaths[0].op_id, op.id)
        self.assertNotEqual(self.cp.toolpaths[0].uid, tp.uid)            # recalculé


class Program(Base):

    def test_a_program_comes_in_one_row_per_tool(self):
        prog = self.program()
        self.assertEqual(len(self.cp.toolpaths), 2)
        self.assertNotIn(prog, self.cp.toolpaths)
        row, kids = self.children()
        self.assertTrue(row.isExpanded())
        self.assertEqual(len(kids), 2)
        self.assertIn('T1', kids[0].text(1))
        self.assertIn('T2', kids[1].text(1))

    def test_its_form_makes_an_operation_that_replaces_it(self):
        self.program()
        first, second = self.cp.toolpaths
        dlg = self.cp.toolpath_form(second, exec_dialog=False)
        self.assertIsInstance(dlg, QDialog)
        self.assertEqual(len(self.w.canvas.doc.layers), 1)               # rien d'ajouté tant que ce n'est pas validé
        dlg.accept()
        doc = self.w.canvas.doc
        self.assertEqual(len(doc.layers), 2)
        layer = doc.layers[-1]
        self.assertIn('Programme', layer.name)
        self.assertEqual(len(layer.items), 1)                             # le trait, repris une fois
        op = self.cp.setup().operations[-1]
        self.assertEqual(op.kind, 'gravure')
        self.assertAlmostEqual(op.depth, 0.4)
        self.assertAlmostEqual(op.step_down, 0.2)                         # deux passes, comme le programme
        self.assertEqual(op.items, [layer.items[0].id])
        self.assertEqual(len(self.cp.toolpaths), 2)
        self.assertIs(self.cp.toolpaths[0], first)                        # l'autre reste
        self.assertEqual(self.cp.toolpaths[1].op_id, op.id)               # à la place du parcours du programme
        self.assertTrue(self.cp.toolpaths[1].moves)

    def test_cancelled_nothing_changes(self):
        self.program()
        tps = list(self.cp.toolpaths)
        dlg = self.cp.toolpath_form(tps[0], exec_dialog=False)
        dlg.reject()
        self.assertEqual(self.cp.toolpaths, tps)
        self.assertEqual(len(self.w.canvas.doc.layers), 1)
        self.assertEqual(self.cp.setup().operations, [])


if __name__ == '__main__':
    unittest.main()
