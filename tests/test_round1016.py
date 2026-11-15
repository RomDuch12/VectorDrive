"""Round 1016 : demande du 14/11, 19 h 45 — « Choisir un outil » et la bibliothèque d'outils en colonnes
arrangeables (arborescence gardée), le n° T seulement si sa colonne est montrée, plein écran d'office ; pas d'outil mis
d'office dans le formulaire d'une opération."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1016.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model  # noqa: E402


class Settings(dict):
    def value(self, k, d=None):
        return self.get(k, d)

    def setValue(self, k, v):                                                # noqa: N802
        self[k] = v


def library():
    a = model.CamTool(name='Cyl 1016', diameter=2.0, number=7, ref='R1016', vendor='V', cut_length=6.0, feed=750.0)
    b = model.CamTool(name='Cone 1016', kind='conique', diameter=3.0, angle=30.0, number=8)
    return {t.id: t for t in (a, b)}


def tool_rows(dlg):
    return [it for it in dlg._items() if it.data(0, Qt.ItemDataRole.UserRole)]


class Picker(unittest.TestCase):

    def test_columns_and_number(self):
        from vectordrive.ui import tool_columns as TC
        from vectordrive.ui.tool_picker import ToolPickerDialog
        st = Settings()
        dlg = ToolPickerDialog(None, [], library(), settings=st)
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.tree.columnCount(), len(TC.COLUMNS))             # avant : 3 colonnes
        h = dlg.tree.header()
        t_col = TC.KEYS.index('number')
        self.assertTrue(h.isSectionHidden(t_col))                             # le n° T : colonne cachée d'office
        cyl = next(it for it in tool_rows(dlg) if 'Cyl 1016' in it.text(0))
        self.assertFalse(cyl.text(0).startswith('T7'))                        # avant : « T7 Cyl 1016 — … »
        self.assertEqual(cyl.text(TC.KEYS.index('ref')), 'R1016')
        self.assertEqual(cyl.text(TC.KEYS.index('cut_length')), '6')
        self.assertEqual(cyl.text(TC.KEYS.index('feed')), '750')
        self.assertTrue(h.sectionsMovable())
        m = TC.column_menu(dlg.tree, st, 'outils/choix_colonnes')
        act = next(a for a in m.actions() if a.text() == 'T')
        act.setChecked(True)                                                  # clic droit : la colonne T montrée
        self.assertFalse(h.isSectionHidden(t_col))
        self.assertEqual(cyl.text(t_col), 'T7')
        self.assertIn('outils/choix_colonnes/entete', st)
        again = ToolPickerDialog(None, [], library(), settings=st)            # retenu
        self.addCleanup(again.deleteLater)
        self.assertFalse(again.tree.header().isSectionHidden(t_col))
        st['outils/choix_colonnes/cles'] = 'name diameter'                    # autres colonnes : disposition oubliée
        other = ToolPickerDialog(None, [], library(), settings=st)
        self.addCleanup(other.deleteLater)
        self.assertTrue(other.tree.header().isSectionHidden(t_col))

    def test_full_screen_by_default(self):
        from vectordrive.ui.tool_picker import ToolPickerDialog
        st = Settings()
        dlg = ToolPickerDialog(None, [], library(), settings=st)
        self.assertTrue(dlg.windowState() & Qt.WindowState.WindowFullScreen)  # avant : agrandie
        self.assertFalse(dlg.toggle_full_screen())                            # F11 : agrandie…
        dlg.done(0)
        dlg.deleteLater()
        dlg = ToolPickerDialog(None, [], library(), settings=st)              # … et retenu
        self.addCleanup(dlg.deleteLater)
        self.assertFalse(dlg.windowState() & Qt.WindowState.WindowFullScreen)
        self.assertTrue(dlg.windowState() & Qt.WindowState.WindowMaximized)


class Library(unittest.TestCase):

    def test_library_columns(self):
        from vectordrive.ui import tool_columns as TC
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            dlg = w.cam_panel.tool_library(exec_dialog=False)
            self.assertEqual(dlg.tree.columnCount(), len(TC.COLUMNS))
            self.assertTrue(dlg.tree.header().isSectionHidden(TC.KEYS.index('number')))
            self.assertEqual(TC.shown_keys(dlg.tree)[:2], ['name', 'diameter'])
            self.assertTrue(dlg.windowState() & Qt.WindowState.WindowFullScreen)
            dlg.close()
        finally:
            w.modified = False
            for t in getattr(w, 'docs', []):
                t.modified = False
            w.close()
            app.processEvents()


class NoToolByDefault(unittest.TestCase):

    def test_form_without_tool(self):
        from vectordrive.ui.cam_panel import FieldsDialog
        doc_tool = model.CamTool(name='Doc 1016', diameter=1.0)
        op = model.Operation(name='P', kind='poche', tool_id='')
        dlg = FieldsDialog(None, 'Opération', op, tools=[doc_tool], library=list(library().values()))
        self.addCleanup(dlg.deleteLater)
        w = dlg.widgets['tool_id']
        self.assertEqual(w.currentData(), '')                                 # avant : le premier outil
        self.assertIn('Choisir un outil', w.currentText())
        self.assertFalse(dlg.accept_checked())                                # OK sans outil : refusé, signalé
        self.assertNotEqual(dlg.result(), 1)
        self.assertIn('c92a2a', w.styleSheet())
        w.setCurrentIndex(w.findData(doc_tool.id))
        self.assertTrue(dlg.accept_checked())
        op2 = model.Operation(name='P', kind='poche', tool_id=doc_tool.id)
        dlg2 = FieldsDialog(None, 'Opération', op2, tools=[doc_tool], library=list(library().values()))
        self.addCleanup(dlg2.deleteLater)
        self.assertEqual(dlg2.widgets['tool_id'].currentData(), doc_tool.id)  # un outil choisi : gardé
        self.assertEqual(dlg2.widgets['tool_id'].findData(''), -1)

    def test_no_tool_created_for_the_form(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = w.cam_panel
            p.library_tools = lambda: []
            s = p.setup()
            n = len(s.tools)
            self.assertIsNone(p._tool_for(s, 'boule', create=False))         # avant : « Fraise boule Ø1 » créée
            self.assertEqual(len(s.tools), n)
            self.assertEqual(p._tool_for(s, 'boule').kind, 'boule')          # sans formulaire (scripts) : comme avant
            self.assertEqual(len(s.tools), n + 1)
        finally:
            w.modified = False
            for t in getattr(w, 'docs', []):
                t.modified = False
            w.close()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
