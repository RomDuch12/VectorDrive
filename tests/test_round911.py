"""Round 911 : listes d'outils triables par colonne (clic sur un titre : croissant, décroissant, puis l'ordre
d'origine ; T, Ø et avance en nombres) et filtrées. Panneau FAO : recherche et nature, tri retenu, l'outil choisi
retrouvé par son id. Bibliothèque et « Choisir un outil » : dossiers et groupes gardés en tête."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r911.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_TOOLS'] = os.path.join(tempfile.mkdtemp(), 'outils911.json')
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model  # noqa: E402

ASC, DESC = Qt.SortOrder.AscendingOrder, Qt.SortOrder.DescendingOrder


def tools():
    return [model.CamTool(number=10, name='Zeta 911', kind='fraise', diameter=12.0, feed=1200.0),
            model.CamTool(number=2, name='alpha 911', kind='foret', diameter=0.5, feed=90.0),
            model.CamTool(number=7, name='Mid 911', kind='fraise', diameter=3.0, feed=800.0)]


class Panel(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.settings.remove('fao/outils_tri')
        self.cp = self.w.cam_panel
        s = self.cp.setup()
        s.tools[:] = tools()
        s.operations[:] = []
        self.cp.save(s)
        self.cp.refresh()

    def tearDown(self):
        self.w.settings.remove('fao/outils_tri')
        self.w.modified = False
        self.w.close()

    def column(self, c):
        t = self.cp.tools
        return [t.item(r, c).text() for r in range(t.rowCount()) if not t.isRowHidden(r)]

    def test_sorting_by_column(self):
        t = self.cp.tools
        self.assertEqual(self.column(0), ['10', '2', '7'])                    # l'ordre du document
        t.sortByColumn(0, ASC)
        self.assertEqual(self.column(0), ['2', '7', '10'])                    # en nombres
        t.sortByColumn(3, DESC)
        self.assertEqual(self.column(3), ['12', '3', '0.5'])
        self.assertEqual(self.w.settings.value('fao/outils_tri'), '3,1')     # retenu
        self.cp.refresh()
        self.assertEqual(self.column(3), ['12', '3', '0.5'])                 # gardé d'un remplissage à l'autre
        t.horizontalHeader().setSortIndicator(-1, ASC)
        self.assertEqual(self.column(0), ['10', '2', '7'])                    # retour à l'ordre du document
        self.assertEqual(self.w.settings.value('fao/outils_tri'), '')

    def test_the_chosen_tool_is_found_by_its_id(self):
        t = self.cp.tools
        t.sortByColumn(3, ASC)                                                # Ø croissant : alpha d'abord
        self.cp._select_row(t, 0)
        self.assertEqual(self.cp.tool_row_index(), 1)
        self.cp.remove_tool()
        self.assertEqual([x.name for x in self.cp.setup().tools], ['Zeta 911', 'Mid 911'])

    def test_filters(self):
        self.cp.tools_filter.setText('alp')
        self.assertEqual(self.column(1), ['alpha 911'])
        self.cp.tools_filter.setText('T7')
        self.assertEqual(self.column(1), ['Mid 911'])
        self.cp.tools_filter.clear()
        self.cp.tools_kind.setCurrentIndex(self.cp.tools_kind.findData('fraise'))
        self.assertEqual(self.cp.filter_tools(), 2)
        self.assertEqual(self.column(1), ['Zeta 911', 'Mid 911'])

    def test_sort_is_kept_for_the_next_window(self):
        self.cp.tools.sortByColumn(4, ASC)
        self.w.settings.sync()
        from vectordrive.ui.main_window import MainWindow
        other = MainWindow()
        try:
            h = other.cam_panel.tools.horizontalHeader()
            self.assertEqual((h.sortIndicatorSection(), h.sortIndicatorOrder()), (4, ASC))
        finally:
            other.modified = False
            other.close()


class Trees(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import toollib
        lib = tools()
        toollib.set_folder(lib, 'Essai 911')
        toollib.save(lib, toollib.default_path(), [])

    def test_library_sorts_inside_folders(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            dlg = w.cam_panel.tool_library(exec_dialog=False)
            tree = dlg.tree
            folder = tree.topLevelItem(0)
            self.assertIn('Essai 911', folder.text(0))
            tree.sortByColumn(1, ASC)
            self.assertEqual([folder.child(i).text(1) for i in range(folder.childCount())], ['0.5', '3', '12'])
            self.assertFalse(dlg.acts['up'].isEnabled())                      # triée : pas de Monter / Descendre
            tree.sortByColumn(1, DESC)
            self.assertIn('Essai 911', tree.topLevelItem(0).text(0))
            self.assertEqual([tree.topLevelItem(0).child(i).text(1) for i in range(3)], ['12', '3', '0.5'])
            tree.header().setSortIndicator(-1, ASC)
            self.assertTrue(dlg.acts['up'].isEnabled())
            dlg.deleteLater()
        finally:
            w.modified = False
            w.close()

    def test_picker_keeps_groups_first(self):
        from vectordrive.cam import toollib
        from vectordrive.ui.tool_picker import ToolPickerDialog
        doc = [model.CamTool(number=1, name='Doc 911', kind='fraise', diameter=9.0)]
        lib = {t.id: t for t in toollib.load(toollib.default_path())}
        dlg = ToolPickerDialog(None, doc, lib)
        tree = dlg.tree
        first = tree.topLevelItem(0).text(0)
        self.assertEqual(first, 'Outils du document')
        for order in (ASC, DESC):
            tree.sortByColumn(0, order)
            self.assertEqual(tree.topLevelItem(0).text(0), first)             # les groupes à leur rang
        tree.sortByColumn(1, DESC)
        folder = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                      if 'Essai 911' in tree.topLevelItem(i).text(0))
        self.assertEqual([folder.child(i).text(1) for i in range(folder.childCount())], ['12', '3', '0.5'])
        tree.header().setSortIndicator(-1, ASC)                               # l'ordre d'origine, refait
        self.assertEqual(tree.topLevelItem(0).text(0), first)
        dlg.deleteLater()


if __name__ == '__main__':
    unittest.main()
