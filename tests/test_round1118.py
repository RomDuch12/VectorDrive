"""Round 1118 : la fenêtre Ouvrir — le bouton « + » avec l'icône de la bibliothèque, la Bibli sous Récents et Favoris,
clic droit sur un dossier › Ajouter à la bibli (demande du 20/11)."""
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_NO_QUICK'] = '1'
_TMP = tempfile.mkdtemp(prefix='vd1118_')
# round 1159 : posés par setUpModule, plus à l'import (ils valaient alors pour tous les essais du processus)
_ENV = {'VECTORDRIVE_SETTINGS': os.path.join(_TMP, 'r1118.ini'),
        'VECTORDRIVE_SESSION': os.path.join(_TMP, 'session.json'),
        'VECTORDRIVE_CACHE': os.path.join(_TMP, 'cache')}
_SAVED = {}

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.ui import file_browser as FB  # noqa: E402
from vectordrive.ui.symbols import FAVORITES, RECENTS  # noqa: E402

UR = Qt.ItemDataRole.UserRole


def setUpModule():
    # lancé avec d'autres essais dans un seul processus : leur dossier temporaire commun a pu être vidé
    os.makedirs(_TMP, exist_ok=True)
    for k, v in _ENV.items():
        _SAVED[k] = os.environ.get(k)
        os.environ[k] = v


def tearDownModule():
    for k, v in _SAVED.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    shutil.rmtree(_TMP, ignore_errors=True)


class Bibli(unittest.TestCase):

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(dir=_TMP))
        self.a = self.tmp / 'Atelier'
        self.b = self.tmp / 'Clients'
        for d in (self.a / 'Plaques', self.b):
            d.mkdir(parents=True)
        (self.a / 'logo.svg').write_text('<svg/>', encoding='utf-8')
        self.s = QSettings(str(self.tmp / 's.ini'), QSettings.Format.IniFormat)
        self.s.setValue(FB.FileBrowserPanel.ROOTS_KEY, [str(self.a)])
        self.p = FB.FileBrowserPanel(self.s)

    def tearDown(self):
        self.p.deleteLater()

    def top(self):
        return [self.p.tree.topLevelItem(i).data(0, UR) for i in range(self.p.tree.topLevelItemCount())]

    def node(self):
        return self.p.tree.topLevelItem(self.top().index(FB.BIBLI))

    def children(self):
        n = self.node()
        return [n.child(i).data(0, UR) for i in range(n.childCount())]

    def names(self):
        return [self.p.list.item(i).text() for i in range(self.p.list.count())]

    def test_plus_button_has_library_icon(self):
        b = self.p.b_bibli
        self.assertIsInstance(b, QPushButton)
        self.assertEqual(b.text(), '+')
        self.assertFalse(b.icon().isNull(), 'le « + » avec l\'icône de la bibliothèque')
        self.assertIn('bibli', b.toolTip())

    def test_bibli_under_recents_and_favorites(self):
        top = self.top()
        self.assertEqual(top[:4], [RECENTS, FAVORITES, FB.BIBLI, FB.QUICK])
        self.assertEqual(self.children(), [str(self.a)])
        self.assertNotIn(str(self.a), top, 'plus parmi les lecteurs : sous la Bibli')
        self.assertTrue(self.node().isExpanded())
        self.assertFalse(self.node().icon(0).isNull())
        self.assertIn(self.a, self.p.roots, '(toujours une racine : dossier parent, emplacement…)')

    def test_click_on_bibli_lists_its_folders(self):
        self.p._folder_clicked(self.node())
        self.assertEqual(self.names(), ['Atelier'])
        self.assertTrue(self.p.where.text().startswith('Bibli'))
        self.p._folder_clicked(self.node().child(0))
        self.assertEqual(self.p._folder, self.a)
        self.p.go_back()
        self.assertEqual(self.names(), ['Atelier'], 'Précédent : la Bibli revient')
        self.p.set_view('vignettes' if self.p._view == 'details' else 'details')
        self.assertEqual(self.names(), ['Atelier'], 'affichage changé : la Bibli redessinée')

    def test_plus_adds_a_folder(self):
        with mock.patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory', return_value=str(self.b)):
            self.p.b_bibli.click()
        self.assertEqual(self.children(), [str(self.a), str(self.b)])
        self.assertEqual(self.s.value(FB.FileBrowserPanel.ROOTS_KEY), [str(self.a), str(self.b)])
        with mock.patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory', return_value=''):
            self.p.b_bibli.click()
        self.assertEqual(len(self.children()), 2, 'Annuler : rien')

    def test_plus_does_not_save_drives(self):
        with mock.patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory', return_value=str(self.b)):
            self.p.b_bibli.click()
        saved = self.s.value(FB.FileBrowserPanel.ROOTS_KEY)
        self.assertEqual(len(saved), 2, 'avant : Bureau, Documents et les lecteurs étaient retenus aussi')

    def test_old_saved_drives_not_in_bibli(self):
        sysr = FB.system_roots()
        self.s.setValue(FB.FileBrowserPanel.ROOTS_KEY, [str(self.a)] + [str(r) for r in sysr])
        p = FB.FileBrowserPanel(self.s)
        n = p.tree.topLevelItem(2)
        self.assertEqual([n.child(i).data(0, UR) for i in range(n.childCount())], [str(self.a)])
        tops = [p.tree.topLevelItem(i).data(0, UR) for i in range(p.tree.topLevelItemCount())]
        self.assertEqual(sum(1 for t in tops if t == str(sysr[0])), 1, 'une seule fois parmi les lecteurs')
        p.deleteLater()

    def test_single_entry_read_back_as_text(self):
        self.s.setValue(FB.FileBrowserPanel.ROOTS_KEY, str(self.b))   # INI : une liste d'un élément = texte
        p = FB.FileBrowserPanel(self.s)
        self.assertEqual([pp for pp in p.bibli_paths()], [self.b])
        p.deleteLater()

    def test_missing_folder_left_out(self):
        self.s.setValue(FB.FileBrowserPanel.ROOTS_KEY, [str(self.a), str(self.tmp / 'parti')])
        p = FB.FileBrowserPanel(self.s)
        self.assertEqual(p.bibli_paths(), [self.a])
        p.deleteLater()

    def menu_texts(self, widget, pos=None):
        m = self.p.menu(widget, pos, exec_menu=False)
        return [a.text() for a in m.actions()], m

    def select_in_list(self, path):
        for i in range(self.p.list.count()):
            it = self.p.list.item(i)
            if it.data(UR) == str(path):
                self.p.list.clearSelection()
                it.setSelected(True)
                self.p.list.setCurrentItem(it)
                return
        self.fail(f'{path} absent')

    def test_right_click_folder_adds_to_bibli(self):
        self.p.show_folder(self.tmp)
        self.select_in_list(self.b)
        texts, m = self.menu_texts(self.p.list)
        self.assertIn('Ajouter à la bibli', texts)
        i = texts.index('Ajouter à la bibli')
        self.assertTrue(texts[i - 1].endswith('Ajouter aux favoris'), 'juste après les favoris')
        m.actions()[i].trigger()
        self.assertEqual(self.children(), [str(self.a), str(self.b)])
        self.p.show_folder(self.tmp)
        self.select_in_list(self.b)
        texts, m = self.menu_texts(self.p.list)
        self.assertIn('Retirer de la bibli', texts)
        m.actions()[texts.index('Retirer de la bibli')].trigger()
        self.assertEqual(self.children(), [str(self.a)])

    def test_right_click_file_has_no_bibli(self):
        self.p.show_folder(self.a)
        self.select_in_list(self.a / 'logo.svg')
        texts, _m = self.menu_texts(self.p.list)
        self.assertNotIn('Ajouter à la bibli', texts)

    def test_right_click_in_tree(self):
        it = self.node().child(0)
        self.p.tree.setCurrentItem(it)
        texts, m = self.menu_texts(self.p.tree)
        self.assertIn('Retirer de la bibli', texts)
        m.actions()[texts.index('Retirer de la bibli')].trigger()
        self.assertEqual(self.children(), [])
        self.assertIn(FB.BIBLI, self.top(), 'la Bibli reste, vide')

    def test_right_click_on_bibli_node_shows_it(self):
        rect = self.p.tree.visualItemRect(self.node())
        self.assertIsNone(self.p.menu(self.p.tree, rect.center()))
        self.assertEqual(self.names(), ['Atelier'])

    def test_bibli_view_refreshed_after_change(self):
        self.p.show_bibli()
        self.p.add_to_bibli([self.b])
        self.assertEqual(self.names(), ['Atelier', 'Clients'])
        self.assertEqual(self.p.add_to_bibli([self.b]), 0, 'déjà dans la bibli')
        self.assertEqual(self.p.remove_from_bibli([self.a]), 1)
        self.assertEqual(self.names(), ['Clients'])

    def test_tree_follows_into_bibli_folder(self):
        self.p.show_folder(self.a / 'Plaques')
        cur = self.p.tree.currentItem()
        self.assertIsNotNone(cur)
        self.assertEqual(cur.text(0), 'Plaques')
        self.assertEqual(cur.parent().data(0, UR), str(self.a))
        self.assertEqual(cur.parent().parent().data(0, FB.Qt.ItemDataRole.UserRole), FB.BIBLI)

    def test_tree_keeps_folder_after_change(self):
        self.p.show_folder(self.a / 'Plaques')
        self.p.add_to_bibli([self.b])
        cur = self.p.tree.currentItem()
        self.assertIsNotNone(cur, 'l\'arbre refait : le dossier affiché reste choisi')
        self.assertEqual(cur.text(0), 'Plaques')
        self.assertEqual(self.p._folder, self.a / 'Plaques')

    def test_system_folder_has_no_bibli_action(self):
        sysr = FB.system_roots()[0]
        it = next(self.p.tree.topLevelItem(i) for i in range(self.p.tree.topLevelItemCount())
                  if self.p.tree.topLevelItem(i).data(0, UR) == str(sysr))
        self.p.tree.setCurrentItem(it)
        texts, _m = self.menu_texts(self.p.tree)
        self.assertNotIn('Ajouter à la bibli', texts, 'déjà montré d\'office : sans effet')

    def test_drop_folder_on_bibli(self):
        self.assertEqual(self.p.place_files([str(self.b), str(self.a / 'logo.svg')], FB.BIBLI), 1)
        self.assertEqual(self.children(), [str(self.a), str(self.b)])
        self.assertEqual(self.p.place_files([str(self.a / 'logo.svg')], FB.QUICK), 0, 'Accès rapide : rien')
        self.assertTrue((self.a / 'logo.svg').is_file())

    def test_virtual_nodes_never_selected_paths(self):
        self.p.tree.setCurrentItem(self.node())
        self.assertEqual(self.p.selected_paths(self.p.tree), [], 'Suppr, F2 : rien sur la Bibli')

    def test_remote_bibli_folder_not_a_root(self):
        with mock.patch('vectordrive.ui.symbols.is_remote', side_effect=lambda p: str(p) == str(self.b)):
            self.p.add_to_bibli([self.b])
        self.assertIn(str(self.b), self.children())
        self.assertNotIn(self.b, self.p.roots, 'un partage injoignable figerait chaque clic')

    def test_bibli_folders_protected(self):
        with mock.patch('vectordrive.ui.symbols.is_remote', side_effect=lambda p: str(p) == str(self.b)):
            self.p.add_to_bibli([self.b])                # un partage : pas une racine, mais protégé
        with mock.patch('vectordrive.ui.symbols.QMessageBox.question') as ask:
            self.assertEqual(self.p.delete([self.a, self.b]), 0)
            ask.assert_not_called()
        self.assertIsNone(self.p.rename(self.b, 'Autre'))
        self.assertTrue(self.a.is_dir() and self.b.is_dir())

    def test_bibli_folder_never_moved_by_drop(self):
        self.p.add_to_bibli([self.b])
        self.assertEqual(self.p.place_files([str(self.b)], str(self.a)), 0, 'lâché un cran trop bas : rien')
        self.assertTrue(self.b.is_dir())
        self.assertFalse((self.a / 'Clients').exists())

    def test_roots_follow_on_refresh(self):
        late = self.tmp / 'Cle'
        self.s.setValue(FB.FileBrowserPanel.ROOTS_KEY, [str(self.a), str(late)])
        p = FB.FileBrowserPanel(self.s)
        self.assertNotIn(late, p.roots)
        (late / 'Sous').mkdir(parents=True)               # la clé branchée, puis F5
        p.refresh()
        self.assertIn(late, p.roots)
        n = p.tree.topLevelItem(2)
        self.assertIn(str(late), [n.child(i).data(0, UR) for i in range(n.childCount())])
        p.deleteLater()

    def test_no_jump_to_other_branch(self):
        docs = self.a / 'Plaques'
        self.p.add_to_bibli([docs])                      # un dossier de la bibli dans un autre
        it = self.node().child(0)                        # Atelier › Plaques, choisi par un clic
        self.p._expand(it)
        it.setExpanded(True)
        sub = next(it.child(k) for k in range(it.childCount()) if it.child(k).text(0) == 'Plaques')
        self.p.tree.setCurrentItem(sub)
        self.p.select_in_tree(docs)
        self.assertIs(self.p.tree.currentItem(), sub, 'la sélection reste où l\'on a cliqué')

    def test_plus_refuses_system_folder(self):
        sysr = FB.system_roots()[0]
        self.assertEqual(self.p.add_to_bibli([sysr]), 0, 'déjà montré d\'office : il resterait invisible')
        self.assertEqual(self.s.value(FB.FileBrowserPanel.ROOTS_KEY), [str(self.a)])

    def test_nothing_created_in_bibli_view(self):
        self.p.show_bibli()
        self.assertIsNone(self.p.current_folder())
        with mock.patch('vectordrive.ui.symbols.QInputDialog.getText', return_value=('Neuf', True)):
            self.assertIsNone(self.p.new_folder())
        self.assertEqual(self.p.import_files(files=[str(self.a / 'logo.svg')]), 0)

    def test_refresh_relists_bibli_view(self):
        self.p.show_bibli()
        self.s.setValue(FB.FileBrowserPanel.ROOTS_KEY, [str(self.a), str(self.b)])   # changé ailleurs
        self.p.refresh()
        self.assertEqual(self.names(), ['Atelier', 'Clients'])
        self.assertEqual(self.p.tree.currentItem().data(0, UR), FB.BIBLI)

    def test_other_place_ends_bibli_view(self):
        self.p.show_bibli()
        self.p.show_folder(self.a)
        self.assertFalse(self.p._bibli_shown)
        self.p.add_to_bibli([self.b])
        self.assertEqual(self.p._folder, self.a)


if __name__ == '__main__':
    unittest.main()
