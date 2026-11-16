"""Round 1049 : demande du 15/11, 22 h 30 — « Onglets colonnes pas assez de place soit icones soit icone plus label
concis » : les onglets des panneaux d'une colonne portent une icône et un libellé court ; le titre entier reste dans
la barre du panneau, les menus et la bulle de l'onglet ; « Titres entiers dans les onglets » revient à avant."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1049.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDockWidget, QTabBar  # noqa: E402

app = QApplication.instance() or QApplication([])

FULL = {'dims': 'Dimensions (F2)', 'layers': 'Calques', 'symbols': 'Bibliothèque', 'fao': 'FAO : parcours',
        'fao_liste': 'FAO : opérations et parcours', 'programme': 'Programme machine',
        'polices': 'Reconnaître une police'}
SHORT = {'dims': 'F2', 'layers': 'Calques', 'symbols': 'Biblio', 'fao': 'Parcours', 'fao_liste': 'Opérations',
         'programme': 'Programme', 'polices': 'Police'}


def spin(n=6):
    for _ in range(n):
        app.processEvents()


class Tabs(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1500, 900)
        self.w.show()
        spin()
        self.cols = self.w.columns

    def tearDown(self):
        self.w.settings.remove('panneaux_colonnes/onglets')
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def C(self):
        from vectordrive.ui import columns
        self.assertIsNotNone(getattr(columns, 'short_title', None), 'avant : les onglets portent le titre entier')
        return columns

    def dock(self, name):
        return self.w.findChild(QDockWidget, name)

    def bars(self):
        return [b for b in self.w.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly)
                if b.count()]

    def test_short_labels_on_the_tabs_full_titles_in_the_bars(self):
        C = self.C()
        for name, short in SHORT.items():
            d = self.dock(name)
            self.assertEqual(d.windowTitle(), short, name)                  # ce que Qt écrit sur l'onglet
            self.assertEqual(C.full_title(d), FULL[name])
            self.assertEqual(d.titleBarWidget().title.text(), FULL[name])  # la barre du panneau : le titre entier
        texts = [b.tabText(i) for b in self.bars() for i in range(b.count())]
        self.assertTrue(texts)
        self.assertTrue(set(texts) <= set(SHORT.values()), texts)

    def test_an_icon_and_the_full_title_as_tip(self):
        self.C()
        seen = 0
        for b in self.bars():
            for i in range(b.count()):
                d = self.cols.dock_at(b, i)
                self.assertIsNotNone(d)
                self.assertFalse(b.tabIcon(i).isNull(), d.objectName())
                self.assertEqual(b.tabToolTip(i), FULL[d.objectName()])
                seen += 1
        self.assertGreaterEqual(seen, 2)

    def test_icon_back_when_a_panel_comes_back(self):
        self.C()
        d = self.dock('symbols')
        d.setVisible(not d.isVisible())
        spin()
        d.setVisible(not d.isVisible())
        spin()
        for b in self.bars():
            for i in range(b.count()):
                self.assertFalse(b.tabIcon(i).isNull(), b.tabText(i))       # Qt a refait l'onglet : icône reposée
        before = [b.tabIcon(i).cacheKey() for b in self.bars() for i in range(b.count())]
        from vectordrive.ui import icons
        icons._cache.clear()                                                 # comme un thème changé : une autre encre
        self.cols.dress_tabs(refresh=True)
        after = [b.tabIcon(i).cacheKey() for b in self.bars() for i in range(b.count())]
        self.assertTrue(before and all(x != y for x, y in zip(before, after)), 'icônes pas refaites')

    def test_full_titles_on_demand_and_kept(self):
        self.C()
        m = self.cols.menu(self.dock('layers'))
        self.addCleanup(m.deleteLater)
        a = next((x for x in m.actions() if x.text() == 'Titres entiers dans les onglets'), None)
        self.assertIsNotNone(a)
        self.assertTrue(a.isCheckable() and not a.isChecked())
        a.trigger()
        spin()
        self.assertEqual(self.cols.tab_mode(), 'entier')
        self.assertEqual(self.w.settings.value('panneaux_colonnes/onglets'), 'entier')
        for name, full in FULL.items():
            self.assertEqual(self.dock(name).windowTitle(), full)
        for b in self.bars():
            for i in range(b.count()):
                self.assertTrue(b.tabIcon(i).isNull())
        self.cols.set_tab_mode('court')
        spin()
        self.assertEqual(self.dock('dims').windowTitle(), 'F2')

    def test_menus_show_full_titles(self):
        self.C()
        m = self.cols.menu(self.dock('layers'))
        self.addCleanup(m.deleteLater)
        subs = [x.menu() for x in m.actions() if x.menu() is not None]
        texts = [x.text() for s in subs for x in s.actions()]
        self.assertIn('Dimensions (F2)', texts)
        self.assertNotIn('F2', texts)

    def test_a_plugin_panel(self):
        C = self.C()
        late = QDockWidget('Catalogue général des pièces', self.w)
        late.setObjectName('plugin_essai1049')
        self.w.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, late)
        spin()
        self.assertEqual(late.windowTitle(), 'Catalogue')                   # le début du titre, 14 caractères au plus
        self.assertEqual(late.titleBarWidget().title.text(), 'Catalogue général des pièces')
        given = QDockWidget('Devis et bons à tirer', self.w)
        given.setObjectName('plugin_devis1049')
        given.setProperty('vd_court', 'Devis')                               # donné par le plugin (`add_panel(short=)`)
        self.w.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, given)
        spin()
        self.assertEqual(given.windowTitle(), 'Devis')
        self.assertEqual(C.full_title(given), 'Devis et bons à tirer')
        for title, short in (('Graveuse — Opérations et programme', 'Opérations'),   # « Machine — Panneau » : le
                             ('Graveuse — Pilote de la machine', 'Pilote')):         # panneau, sans mot de liaison
            d = QDockWidget(title, self.w)
            d.setObjectName('plugin_' + short.lower() + '1049')
            self.w.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, d)
            spin()
            self.assertEqual(d.windowTitle(), short, title)
        self.assertEqual(given.toggleViewAction().text(), 'Devis et bons à tirer')   # le menu de Qt : titre entier
        late.setWindowTitle('Mon catalogue')                                 # renommé par son plugin : tel quel
        spin()
        self.assertEqual(late.windowTitle(), 'Mon catalogue')
        self.assertEqual(late.titleBarWidget().title.text(), 'Mon catalogue')

    def test_plugin_api_takes_a_short_label(self):
        self.C()
        import inspect
        from vectordrive import plugins
        self.assertIn('short', inspect.signature(plugins.Api.add_panel).parameters)
        self.assertEqual(plugins.PanelSpec('k', 'Titre', lambda w: None).short, '')

    def test_icons_drawn(self):
        self.C()
        from vectordrive.ui import icons
        for key in ('tab_dims', 'tab_layers', 'tab_library', 'tab_paths', 'tab_ops', 'tab_program', 'tab_fonts',
                    'tab_panel'):
            self.assertIn(key, icons.ICONS)
            self.assertFalse(icons.icon(key).isNull())


if __name__ == '__main__':
    unittest.main()
