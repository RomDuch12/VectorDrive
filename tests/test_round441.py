"""Round 441 : disposition TypeEdit — le bandeau Fichier complet du mode normal, en premier ;
formulaire de parcours agrandissable (⛶, F11), usinage par couleur replié en fin de formulaire."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vectordrive.cam import model
from vectordrive.ui.typeedit_layout import TELayout, TETab, TEPanel

app = QApplication.instance() or QApplication([])


class TestFileTab(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_file_tab_in_te(self):
        w = self.w
        r = w.ribbon
        n0 = len(r.page(r.indexOf(w.file_page)).groups())
        lay = TELayout(tabs=[TETab('Fichier', [TEPanel('Information', [('ID_FILE_PRINT_PREVIEW', True)]),
                                       TEPanel('Doublon', [('ID_FILE_PRINT', True)])]),
                             TETab('Accueil', [TEPanel('Presse', [('ID_EDIT_COPY', True), ('ID_EDIT_PASTE', True)])])])
        w.layout_active, w._te_layout = True, lay
        w._build_te_tabs(lay)
        w._build_custom_tab(restyle=False)
        i = r.indexOf(w.file_page)
        self.assertEqual(i, 0)
        self.assertTrue(r.isTabVisible(i))
        self.assertIn(w.A['quit'], [b.defaultAction() for b in w.file_page.findChildren(
            __import__('PySide6.QtWidgets', fromlist=['QToolButton']).QToolButton)])
        self.assertNotIn(r.tabText(i), [t for t, _g in w._vd_tab_menus()])  # pas en double dans « VectorDrive »
        self.assertEqual([r.tabText(k) for k in range(r.count())].count('Fichier'), 1)   # Fichier TypeEdit fusionné
        self.assertEqual(len(r.page(i).groups()), n0 + 1)                      # Doublon : déjà dans Fichier
        w._clear_te_tabs()
        self.assertEqual(len(r.page(r.indexOf(w.file_page)).groups()), n0)
        w.layout_active = False
        w._build_custom_tab(restyle=False)
        self.assertTrue(r.isTabVisible(r.indexOf(w.file_page)))


class TestOpForm(unittest.TestCase):
    def test_color_folded_and_full(self):
        from vectordrive.core.document import Document
        from vectordrive.ui.cam_panel import FieldsDialog
        doc = Document()
        op = model.Operation(kind='contour', sources=[0])
        dlg = FieldsDialog(None, 'Op', op, doc, [])
        self.assertIsNotNone(dlg.color_toggle)
        self.assertFalse(dlg.color_toggle.isChecked())
        self.assertFalse(dlg.color_box.isVisibleTo(dlg))             # replié
        self.assertTrue(dlg.widgets['sources'].isAncestorOf(dlg.widgets['sources']) or
                        dlg.color_box.isAncestorOf(dlg.widgets['sources']))
        lay = dlg.layout()
        idx = [lay.itemAt(i).widget() for i in range(lay.count())]
        self.assertLess(idx.index(dlg.color_box), len(idx) - 1)        # juste avant les boutons, à la fin
        dlg.color_toggle.setChecked(True)
        self.assertTrue(dlg.color_box.isVisibleTo(dlg))
        self.assertIn('couleur', dlg.color_toggle.text())
        self.assertTrue(dlg.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint)
        dlg.full_button.click()
        self.assertTrue(dlg.windowState() & Qt.WindowState.WindowFullScreen)
        dlg.full_button.click()
        self.assertFalse(dlg.windowState() & Qt.WindowState.WindowFullScreen)
        dlg.reject()
        tool = FieldsDialog(None, 'Outil', model.CamTool(name='F1'))
        self.assertIsNone(tool.color_toggle)                          # outil : pas d'usinage par couleur
        tool.reject()


if __name__ == '__main__':
    unittest.main()
