"""Round 1082 (demande du 18/11 soir) : « barre d'état uniquement pied de fenetre, pas barre onglet » ; « Pas
déplacement flèche propre à chaque onglet » ; « Colonne parcours possibilité de renommer en dbleclick gauche ou menu
click droit »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1082.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
KEY = 'essai_1082'


class Provider:
    """Un plugin d'essai : ses opérations dans `doc.extra[KEY]` ([{'id', 'label'}]) ; il sait les renommer."""
    label = 'Essai'
    posts = ()

    def __init__(self, renames=True):
        self.calls = []
        if not renames:
            self.rename = None

    def rows(self, doc):
        return [{'ref': o['id'], 'label': o['label']} for o in doc.extra.get(KEY, [])]

    def edit(self, win, ref):
        self.calls.append(('edit', ref))

    def rename(self, doc, ref, name):
        self.calls.append(('rename', ref, name))
        for o in doc.extra.get(KEY, []):
            if o['id'] == ref:
                o['label'] = name
        return True


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1400, 900)
        self.w.show()
        self.addCleanup(self.close)

    def close(self):
        self.w.step_answer = None
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def put(self, x=0.0):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        sh = Shape(path=geom.Path([geom.rect(x, 0.0, 20.0, 14.0)]), tool=0)
        self.w.canvas.doc.add(sh)
        return sh


class StatusBar(Base):

    def test_the_selection_only_in_the_status_bar(self):
        sh = self.put()
        self.w.canvas.select([sh])
        app.processEvents()
        self.assertIn('20.000', self.w.lbl_sel.text())                       # au pied de la fenêtre
        self.assertEqual(self.w.ribbon.info.text(), '', 'avant : « 1 Courbe(s) (L 20.000 mm…) » aussi dans la rangée '
                                                        'des onglets du ruban')
        self.assertTrue(self.w.ribbon.info.isHidden())
        self.w.canvas.select([])
        self.assertEqual((self.w.lbl_sel.text(), self.w.ribbon.info.text()), ('', ''))


class ArrowStep(Base):

    def test_each_tab_has_its_step(self):
        w, c = self.w, self.w.canvas
        self.put()                                                          # l'onglet n'est plus vierge
        self.assertEqual(w.ask_arrow_step(True, 4.0), 4.0)
        first = w.doc_index
        w.new_document()
        app.processEvents()
        second = w.doc_index
        self.assertNotEqual(first, second)
        self.assertIsNone(c.arrow_step, 'avant : le pas saisi dans un onglet valait pour tous')
        self.assertEqual(w.ask_arrow_step(True, 2.5), 2.5)
        w.switch_tab(first)
        self.assertEqual(c.arrow_step, 4.0)
        w.switch_tab(second)
        self.assertEqual(c.arrow_step, 2.5)
        w.ask_arrow_step(True, 0.0)                                         # 0 : le pas des options, ici seulement
        self.assertIsNone(c.arrow_step)
        w.switch_tab(first)
        self.assertEqual(c.arrow_step, 4.0)

    def right(self):
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QKeyEvent
        c = self.w.canvas
        c.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier))

    def test_the_arrows_move_by_the_step_of_the_tab(self):
        w, c = self.w, self.w.canvas
        self.assertNotEqual(c.nudge_mm, 5.0)
        sh = self.put()
        w.ask_arrow_step(True, 5.0)
        w.new_document()
        app.processEvents()
        sh2 = self.put()
        c.select([sh2])
        x0 = c.selection_bbox()[0]
        self.right()                                                        # l'onglet neuf : le pas des options
        self.assertAlmostEqual(c.selection_bbox()[0] - x0, c.nudge_mm)
        w.switch_tab(0)
        c.select([sh])
        x0 = c.selection_bbox()[0]
        self.right()                                                        # le premier : le sien
        self.assertAlmostEqual(c.selection_bbox()[0] - x0, 5.0)


class Rename(Base):

    def setUp(self):
        super().setUp()
        from vectordrive.cam import model
        self.p = self.w.cam_panel
        sh = self.put()
        s = self.p.setup()
        tool = model.CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0, spindle=20000)
        s.tools = [tool]
        s.operations = [model.Operation(name='Gravure', kind='gravure', tool_id=tool.id, items=[sh.id], depth=0.2),
                        model.Operation(name='', kind='gravure', tool_id=tool.id, items=[sh.id], depth=0.4)]
        self.p.save(s)
        self.w.modified = False

    def name_cell(self, r):
        return self.p.ops.item(r, 0).text()

    def test_rename_by_name(self):
        p = self.p
        p._select_row(p.ops, 0)
        self.assertTrue(p.rename_op('Contour   extérieur'))
        self.assertEqual(p.setup().operations[0].name, 'Contour extérieur')
        self.assertTrue(self.name_cell(0).startswith('Contour extérieur'), self.name_cell(0))
        self.assertTrue(self.w.modified)
        self.assertFalse(p.rename_op('Contour extérieur'))                  # le même nom : rien de changé

    def test_an_empty_name_is_the_name_of_its_kind(self):
        from vectordrive.cam import model
        from vectordrive.i18n import tr
        p = self.p
        p._select_row(p.ops, 0)
        self.assertTrue(p.rename_op(''))
        self.assertEqual(p.setup().operations[0].name, '')
        self.assertTrue(self.name_cell(0).startswith(tr(model.op_kinds()['gravure'])), self.name_cell(0))

    def test_the_menu_has_rename(self):
        p = self.p
        p._select_row(p.ops, 1)
        m = p.op_menu(exec_menu=False)
        texts = [a.text() for a in m.actions()]
        self.assertIn('Renommer…', texts, 'avant : pas de « Renommer… » au clic droit')
        self.assertLess(texts.index('Modifier…'), texts.index('Renommer…'))
        m.deleteLater()

    def test_double_click_on_the_name_renames_elsewhere_edits(self):
        p = self.p
        seen = []
        p.rename_op = lambda name=None: seen.append('rename')
        p.edit_op = lambda *a, **k: seen.append('edit')
        p._select_row(p.ops, 1)
        p._op_double_clicked(p.ops.model().index(1, 0))
        p._op_double_clicked(p.ops.model().index(1, 2))                     # la colonne de l'outil : modifier
        p._op_double_clicked(p.ops.model().index(1, p.EYE_COL))             # l'œil : son propre clic
        self.assertEqual(seen, ['rename', 'edit'], 'avant : le double clic modifiait l\'opération, partout')

    def test_the_toolpaths_take_the_new_name(self):
        from vectordrive.cam.model import Toolpath
        p = self.p
        op = p.setup().operations[0]
        p.toolpaths = [Toolpath(op_id=op.id, tool_id=op.tool_id, name=op.name)]
        p._select_row(p.ops, 0)
        self.assertTrue(p.rename_op('Contour'))
        self.assertEqual(p.toolpaths[0].name, 'Contour', "avant : l'ancien nom restait écrit dans le programme")

    def test_undo_gives_the_old_name_back(self):
        p = self.p
        p._select_row(p.ops, 0)
        self.assertTrue(p.rename_op('Contour'))
        self.w.undo()
        app.processEvents()
        self.assertEqual(self.w.cam_panel.setup().operations[0].name, 'Gravure', 'avant : pas de Ctrl+Z')

    def test_the_double_click_signal_is_wired(self):
        p = self.p
        seen = []
        p.rename_op = lambda name=None: seen.append('rename')
        p.edit_op = lambda *a, **k: seen.append('edit')                     # (jamais la vraie fenêtre : elle attend)
        p._select_row(p.ops, 0)
        p.ops.doubleClicked.emit(p.ops.model().index(0, 0))
        self.assertEqual(seen, ['rename'])


class RenamePlugin(Base):

    def register(self, provider):
        from vectordrive import plugins
        plugins.Api(plugins.REGISTRY, None).add_operation_provider(KEY, provider)
        self.addCleanup(lambda: getattr(plugins.REGISTRY, 'op_providers', {}).pop(KEY, None))

    def row_of(self, ref):
        from vectordrive.cam import external
        return next(i for i, o in enumerate(self.w.cam_panel.setup().operations)
                    if external.is_external(o) and external.ref_of(o) == ref)

    def test_the_plugin_renames_its_operation(self):
        pr = Provider()
        self.register(pr)
        p = self.w.cam_panel
        self.w.canvas.doc.extra[KEY] = [{'id': 'a', 'label': 'Op A'}]
        p.refresh()
        r = self.row_of('a')
        p._select_row(p.ops, r)
        self.assertTrue(p.rename_op('Perçages du fond'))
        self.assertEqual(pr.calls, [('rename', 'a', 'Perçages du fond')])
        r = self.row_of('a')
        self.assertEqual(p.setup().operations[r].name, 'Perçages du fond')
        self.assertTrue(p.ops.item(r, 0).text().startswith('Perçages du fond'))

    def test_a_plugin_that_cannot_rename(self):
        pr = Provider(renames=False)
        self.register(pr)
        p = self.w.cam_panel
        self.w.canvas.doc.extra[KEY] = [{'id': 'a', 'label': 'Op A'}]
        p.refresh()
        r = self.row_of('a')
        p._select_row(p.ops, r)
        self.assertFalse(p.rename_op('Autre nom'))
        self.assertEqual(p.setup().operations[self.row_of('a')].name, 'Op A')
        self.assertIn('ne la renomme pas', self.w.statusBar().currentMessage())
        seen = []
        p.edit_op = lambda *a, **k: seen.append('edit')
        p._op_double_clicked(p.ops.model().index(r, 0))
        self.assertEqual(seen, ['edit'])                                    # son nom ne se renomme pas : elle s'ouvre

    def test_a_row_the_plugin_keeps(self):
        pr = Provider()
        pr.renamable = lambda doc, ref: ref != 'b'
        pr.name_of = lambda doc, ref: 'Op ' + ref.upper()
        self.register(pr)
        p = self.w.cam_panel
        self.w.canvas.doc.extra[KEY] = [{'id': 'a', 'label': 'Op A  (3 points)'}, {'id': 'b', 'label': 'Retouche'}]
        p.refresh()
        seen = []
        p.edit_op = lambda *a, **k: seen.append('edit')
        rb = self.row_of('b')
        p._select_row(p.ops, rb)
        p._op_double_clicked(p.ops.model().index(rb, 0))
        self.assertEqual(seen, ['edit'], "avant : « son plugin ne la renomme pas » au lieu de l'ouvrir")
        self.assertFalse(p.rename_op('X'))
        self.assertEqual(pr.calls, [])
        from unittest import mock
        ra = self.row_of('a')
        p._select_row(p.ops, ra)
        with mock.patch('PySide6.QtWidgets.QInputDialog.getText', return_value=('Op A', False)) as ask:
            p.rename_op()
        self.assertEqual(ask.call_args.kwargs.get('text'), 'Op A')          # le nom, sans « (3 points) »

    def test_undo_a_plugin_rename(self):
        pr = Provider()
        pr.undo_keys = (KEY,)
        self.register(pr)
        p = self.w.cam_panel
        self.w.canvas.doc.extra[KEY] = [{'id': 'a', 'label': 'Op A'}]
        p.refresh()
        p._select_row(p.ops, self.row_of('a'))
        n = len(self.w._undo)
        self.assertTrue(p.rename_op('Nouveau'))
        self.assertEqual(len(self.w._undo), n + 1)
        self.w.undo()
        app.processEvents()
        self.assertEqual(self.w.canvas.doc.extra[KEY][0]['label'], 'Op A')


if __name__ == '__main__':
    unittest.main()
