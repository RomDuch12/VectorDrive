"""Round 699 : « Lier au parcours précédent » lie les opérations dans la
liste — le calcul d'une seule opération liée (formulaire validé) part des
parcours d'avant, les opérations liées suivantes sont refaites ; liaison
montrée (↳) dans les listes ; une opération monte ou descend avec ses
opérations liées ; lier ou délier par le clic droit."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class Base(unittest.TestCase):
    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.cam.model import CamTool
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.p = self.w.cam_panel
        doc = self.w.canvas.doc
        ids = []
        for r in ((-10, -7, 20, 14), (-6, -3, 4, 6), (2, -3, 4, 6)):
            sh = Shape(path=geom.Path([geom.rect(*r)]), tool=0)
            doc.add(sh)
            ids.append(sh.id)
        s = self.p.setup()
        self.cyl = CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0)
        self.cone = CamTool(name='V', kind='conique', diameter=6.0, tip=0.2, angle=60.0, number=2, cut_length=15)
        s.tools = [self.cyl, self.cone]
        self.pocket = model.Operation(name='Ébauche', kind='poche', tool_id=self.cyl.id, items=list(ids), depth=1.0,
                                      step_down=1.0)
        self.carve = model.Operation(name='Gravure', kind='vcarve', tool_id=self.cone.id, items=list(ids), depth=1.0,
                                     link_previous=True)
        s.operations = [self.pocket, self.carve]
        self.p.save(s)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def names(self):
        return [o.name for o in self.p.setup().operations]

    def select(self, name):
        # pas selectRow : une touche Ctrl ou Maj laissée enfoncée par un autre
        # essai ajouterait la ligne à la sélection au lieu de la remplacer
        from PySide6.QtCore import QItemSelectionModel
        t, r = self.p.ops, self.names().index(name)
        flags = QItemSelectionModel.SelectionFlag
        t.selectionModel().setCurrentIndex(t.model().index(r, 0), flags.ClearAndSelect | flags.Rows)


class TestLinkedCompute(Base):
    def test_single_compute_uses_previous(self):
        from vectordrive.cam import strategies
        self.p.compute_op(self.pocket)
        tp = self.p.compute_op(self.carve)
        self.assertTrue(any('lier au parcours précédent' in w for w in tp.warnings))   # lié, comme en tout calculer
        s = self.p.setup()
        whole = strategies.compute_all(self.w.canvas.doc, s)[1]
        self.assertEqual(len(tp.moves), len(whole.moves))
        alone = strategies.compute(self.w.canvas.doc, s, s.operations[1])
        self.assertGreater(len(alone.moves), len(tp.moves))             # sans liaison : toute la gravure

    def test_previous_computed_when_missing(self):
        tp = self.p.compute_op(self.carve)                              # l'ébauche n'est pas encore calculée
        self.assertTrue(any('lier au parcours précédent' in w for w in tp.warnings))

    def test_linked_redone_after_previous(self):
        self.p.compute_op(self.pocket)
        first = self.p.compute_op(self.carve)
        s = self.p.setup()
        s.operations[0].depth = 0.2                                     # ébauche moins profonde : plus à graver
        self.p.save(s)
        self.p.compute_op(s.operations[0])
        again = next(t for t in self.p.toolpaths if t.op_id == self.carve.id)
        self.assertIsNot(again, first)
        self.assertNotEqual(len(again.moves), len(first.moves))
        self.assertEqual([t.op_id for t in self.p.toolpaths], [self.pocket.id, self.carve.id])


class TestLinkedList(Base):
    def add(self, name, linked=False):
        from vectordrive.cam import model
        s = self.p.setup()
        s.operations.append(model.Operation(name=name, kind='contour', tool_id=self.cyl.id, link_previous=linked))
        self.p.save(s)

    def test_marks_in_lists(self):
        self.p.refresh()
        self.assertFalse(self.p.ops.item(0, 0).text().startswith('↳'))
        self.assertTrue(self.p.ops.item(1, 0).text().startswith('↳ Gravure'))
        self.assertIn('« Ébauche »', self.p.ops.item(1, 0).toolTip())
        self.p.compute_op(self.pocket)
        self.p.compute_op(self.carve)
        self.assertEqual([self.p.paths.item(i).text() for i in range(self.p.paths.count())], ['Ébauche', '↳ Gravure'])

    def test_move_with_linked(self):
        self.add('C')
        self.add('D')
        self.select('C')
        self.p.move_op(-1)                                              # par-dessus tout le bloc lié
        self.assertEqual(self.names(), ['C', 'Ébauche', 'Gravure', 'D'])
        self.select('Ébauche')
        self.p.move_op(1)                                               # l'ébauche emmène sa gravure liée
        self.assertEqual(self.names(), ['C', 'D', 'Ébauche', 'Gravure'])
        self.assertEqual(self.p._row(self.p.ops), 2)
        self.p.move_op(-1)
        self.assertEqual(self.names(), ['C', 'Ébauche', 'Gravure', 'D'])
        self.select('Gravure')
        self.p.move_op(1)                                               # une opération liée bouge seule
        self.assertEqual(self.names(), ['C', 'Ébauche', 'D', 'Gravure'])

    def test_duplicate_after_linked(self):
        self.add('C')
        self.select('Ébauche')
        c = self.p.duplicate_op()
        self.assertEqual(self.names(), ['Ébauche', 'Gravure', c.name, 'C'])
        self.select('Gravure')
        c2 = self.p.duplicate_op()
        self.assertEqual(self.names()[2], c2.name)
        self.assertTrue(self.p.setup().operations[2].link_previous)

    def test_menu_toggle(self):
        self.select('Gravure')
        m = self.p.op_menu(exec_menu=False)
        a = next(a for a in m.actions() if a.text() == 'Lier au parcours précédent')
        self.assertTrue(a.isCheckable() and a.isChecked() and a.isEnabled())
        self.p.toggle_link()
        self.assertFalse(self.p.setup().operations[1].link_previous)
        self.p.refresh()
        self.assertFalse(self.p.ops.item(1, 0).text().startswith('↳'))
        self.select('Ébauche')
        m = self.p.op_menu(exec_menu=False)
        a = next(a for a in m.actions() if a.text() == 'Lier au parcours précédent')
        self.assertFalse(a.isEnabled())                                 # la première : rien avant elle


if __name__ == '__main__':
    unittest.main()
