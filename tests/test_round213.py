"""Round 213 : onglets du ruban — « Modifier » devient « Options » (un
bouton par onglet de la fenêtre des options, fenêtre agrandie), Options et
Aide tout à droite, FAO le dernier des onglets de gauche ; disposition
TypeEdit 13 : même chose, et le BAT à côté du devis (Coût)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QToolButton

from vectordrive.ui import typeedit_layout as TL

app = QApplication.instance() or QApplication([])

SCRIPT = """' script de ruban synthétique (même syntaxe que TypeEdit)
set categoryFile = configProduct.AddCategoryFromID(301)
set panelInfo = categoryFile.AddPanelFromID(561)
cmd = "ID_FILE_COST"
panelInfo.AddButton cmd,true,true
cmd = "ID_POST_IT"
panelInfo.AddButton cmd,true,true
set categoryModif = configProduct.AddCategoryFromID(304)
set panelConf = categoryModif.AddPanelFromID(562)
cmd = "ID_EDIT_OPTIONS"
panelConf.AddButton cmd,true,true
cmd = "ID_MANIPULER_SUPPORT"
panelConf.AddButton cmd,true,true
set categoryCAD = configProduct.AddCategoryFromID(307)
set panelMode = categoryCAD.AddPanelFromID(506)
cmd = "ID_COMPO_SHOWPALPOINT"
panelMode.AddButton cmd,true,true
set categoryFAO = configProduct.AddCategoryFromID(308)
set panelPath = categoryFAO.AddPanelFromID(563)
cmd = "ID_CREATEPATH"
panelPath.AddButton cmd,true,true
cmd = "ID_LISTPATH"
panelPath.AddButton cmd,true,true
"""
STRINGS = {301: 'Fichier', 304: 'Modifier', 307: 'TypeEdit', 308: 'FAO', 506: 'Mode', 561: 'Information',
           562: 'Configuration', 563: 'Parcours outil'}


def left_tabs(r) -> list:
    return [r.tabText(i) for i in range(r.count()) if r.tabBar().isTabVisible(i)]


class TestVectorDriveLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_order(self):
        r = self.w.ribbon
        left = left_tabs(r)
        self.assertEqual(left[-1], 'FAO 2D')                                       # FAO le dernier à gauche
        self.assertNotIn('FAO 3D', left)                                           # en 2D : son onglet seul
        self.assertEqual(left[:3], ['Fichier', 'Edition', 'Vue'])
        self.assertNotIn('Modifier', [r.tabText(i) for i in range(r.count())])
        self.assertEqual(r.right_titles(), ['Options', 'Aide'])                     # tout à droite
        self.assertNotIn('Options', left)
        self.assertTrue(r.right_bar.isVisible() or not r.isVisible())

    def test_options_tab_buttons(self):
        from vectordrive.ui.options import PAGES, SPEC
        r = self.w.ribbon
        i = next(i for i in range(r.count()) if r.tabText(i) == 'Options')
        acts = [b.defaultAction() for b in r.widget(i).findChildren(QToolButton) if b.defaultAction()]
        keys = [k for k, a in self.w.A.items() if a in acts]
        for _title, (slug, _icon) in PAGES.items():
            self.assertIn(f'options_{slug}', keys)
        self.assertIn('options', keys)                                              # la fenêtre (F10) reste
        dlg = self.w.options_dialog(exec_dialog=False, page='FAO')
        self.assertEqual(dlg.tabs.tabText(dlg.tabs.currentIndex()), 'FAO')
        avail = dlg.screen().availableGeometry()
        self.assertGreaterEqual(dlg.width(), min(980, avail.width() - 80))          # agrandie
        self.assertEqual(dlg.tabs.count(), len(SPEC))
        self.assertFalse(dlg.show_page('Inconnu'))
        dlg.deleteLater()

    def test_right_tabs_select(self):
        r = self.w.ribbon
        aide = next(i for i in range(r.count()) if r.tabText(i) == 'Aide')
        j = next(j for j in range(r.right_bar.count()) if r.right_bar.tabText(j) == 'Aide')
        r._right_clicked(j)
        self.assertEqual(r.currentIndex(), aide)
        self.assertEqual(r.right_bar.currentIndex(), j)
        fichier = next(i for i in range(r.count()) if r.tabText(i) == 'Fichier')
        r.setCurrentIndex(fichier)
        self.assertEqual(r.right_bar.currentIndex(), 0)                              # aucun onglet de droite choisi
        self.assertFalse(r.right_bar.isTabVisible(0))

    def test_new_tabs_before_fao(self):
        r = self.w.ribbon
        page = r.add_tab('Atelier')                                                  # onglet d'un plugin
        left = left_tabs(r)
        self.assertLess(left.index('Atelier'), left.index('FAO 2D'))
        i = next(i for i in range(r.count()) if r.tabText(i) == 'Atelier')
        r.removeTab(i)
        page.deleteLater()
        t = next(i for i in range(r.count()) if r.tabText(i) == self.w.text_tab_title)
        self.assertLess(t, next(i for i in range(r.count()) if r.tabText(i) == 'FAO 2D'))
        self.assertFalse(r.isTabVisible(t))                                         # contextuel : caché
        self.assertTrue(r.isTabVisible(next(i for i in range(r.count()) if r.tabText(i) == 'Aide')))

    def test_hidden_right_tab(self):
        from vectordrive.ui import ribbon_editor as RE
        r = self.w.ribbon
        RE.set_hidden(self.w.settings, ['Aide'])
        self.w._build_custom_tab()
        try:
            aide = next(i for i in range(r.count()) if r.tabText(i) == 'Aide')
            self.assertFalse(r.isTabVisible(aide))
            self.assertEqual(r.right_titles(), ['Options'])
        finally:
            RE.set_hidden(self.w.settings, [])
            self.w._build_custom_tab()
        self.assertEqual(r.right_titles(), ['Options', 'Aide'])


class TestTypeEditLayout(unittest.TestCase):
    def test_options_right_fao_last_bat_beside_cost(self):
        from vectordrive.ui.main_window import MainWindow
        TL._cache.clear()
        fake = TL.parse(SCRIPT, STRINGS)
        with mock.patch.object(TL, 'installed', return_value=fake):
            w = MainWindow()
            try:
                w.A['quote_essai'] = w.A['about']                                   # « Coût » relié par un plugin
                from vectordrive.ui import shortcuts
                with mock.patch.dict(shortcuts.TE_ACTIONS, {'ID_FILE_COST': 'quote_essai'}):
                    w.set_theme('typeedit13')
                r = w.ribbon
                self.assertTrue(w.layout_active)
                left = [r.tabText(i) for i in range(r.count()) if r.isTabVisible(i) and not r.is_right(i)]
                self.assertEqual(left, ['Fichier', 'TypeEdit', 'VectorDrive', 'FAO'])
                self.assertEqual(r.right_titles(), ['Options', 'Aide'])
                opt = next(i for i in range(r.count()) if r.isTabVisible(i) and r.tabText(i) == 'Options')
                self.assertTrue(r.widget(opt).property('te_layout'))                 # le « Modifier » de TypeEdit
                first = r.page(opt).groups()[0]
                self.assertEqual(first.title.text(), 'Options')                      # boutons des onglets d'abord
                fichier = next(i for i in range(r.count()) if r.tabText(i) == 'Fichier' and r.isTabVisible(i))
                info = next(g for g in r.page(fichier).groups() if g.title.text() == 'Information')
                acts = [b.defaultAction() for b in info.buttons()]
                self.assertEqual(acts[:2], [w.A['quote_essai'], w.A['proof']])        # BAT à côté du devis
                w.set_theme('clair')
                self.assertFalse(w.layout_active)
                self.assertEqual(r.right_titles(), ['Options', 'Aide'])
                left = [r.tabText(i) for i in range(r.count()) if r.isTabVisible(i) and not r.is_right(i)]
                self.assertEqual(left[-1], 'FAO 2D')
            finally:
                w.modified = False
                w.close()
                TL._cache.clear()


if __name__ == '__main__':
    unittest.main()
