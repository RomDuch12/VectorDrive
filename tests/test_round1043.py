"""Round 1043 : demande du 15/11 « Outils : … Affichage directement de la derniere liste d'outils utilisée …, ne plus
afficher mes outils mais des etoiles devant chacun pour les remonter en tête de liste Favoris (pliable dépliable), les
outils sont réarrangeables à la souris; pas de liste bibliothèques outils (remplacé par arborescence dossiers) »
(2e partie : le gestionnaire d'outils en un seul arbre)."""
import json
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1043.ini'))
os.environ.setdefault('VECTORDRIVE_TOOLS', os.path.join(tempfile.mkdtemp(), 'tools.json'))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from vectordrive.cam import model, toollib  # noqa: E402

app = QApplication.instance() or QApplication([])
ROLE = Qt.ItemDataRole.UserRole
LIB = 'Lib 1043'


class Settings(dict):
    def value(self, k, d=None):
        return self.get(k, d)

    def setValue(self, k, v):                                         # noqa: N802
        self[k] = v


class Parent(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings


def tool(name, kind='fraise', d=3.0, angle=0.0, folder='', ref=''):
    t = model.CamTool(name=name, kind=kind, diameter=d, angle=angle, ref=ref)
    t.folder = folder
    return t


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive import plugins
        self.s = Settings()
        self.parent = Parent(self.s)
        self.addCleanup(self.parent.deleteLater)
        self.path = pathlib.Path(tempfile.mkdtemp()) / 'tools.json'
        self.m1, self.m2 = tool('Mine 1', d=2.0, folder='Atelier'), tool('Mine 2', 'boule', 1.0, folder='Gravure')
        toollib.save([self.m1, self.m2], self.path)
        self.lib = [tool('Plug 6', d=6.0, ref='P-6'), tool('Plug 3', d=3.0, ref='P-3'),
                    tool('Plug V90', 'conique', 3.0, 90.0, ref='P-V90')]
        plugins.reset()
        api = plugins.Api(plugins.REGISTRY, plugins.PluginInfo('essai1043', name='Essai'))
        api.add_tool_library(LIB, lambda: [model.CamTool.from_dict(t.to_dict()) for t in self.lib])
        self.addCleanup(plugins.reset)

    def dialog(self, show=False, panel=None):
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        dlg = ToolLibraryDialog(self.parent, panel, self.path)
        self.addCleanup(dlg.deleteLater)
        if show:
            dlg.show()
            app.processEvents()
        return dlg

    @staticmethod
    def label(it):
        return it.text(0).split('  (')[0]

    def tops(self, dlg):
        return [dlg.tree.topLevelItem(i) for i in range(dlg.tree.topLevelItemCount())]

    def node(self, dlg, name):
        hit = next((t for t in self.tops(dlg) if self.label(t) == '📚 ' + name), None)
        if hit is None:
            raise AssertionError(f'pas de « {name} » dans l’arbre : {[self.label(t) for t in self.tops(dlg)]}')
        return hit

    def row(self, dlg, name, in_favs=False):
        for it in dlg._items():
            p, fav = it.parent(), False
            while p is not None:
                fav = fav or self.label(p).startswith('★')
                p = p.parent()
            if it.data(0, ROLE) and it.text(0).split(' — ')[0].strip() == name and fav == in_favs:
                return it
        raise AssertionError(f'{name} absent de l’arbre')

    def favs(self, *tools):
        self.s['outils/favoris'] = json.dumps([toollib.favorite_key(t) for t in tools])


class OneTree(Base):

    def test_no_library_list_every_library_in_the_tree(self):
        dlg = self.dialog()
        self.assertTrue(dlg.source.isHidden())                               # plus de liste « Bibliothèque »
        self.assertEqual([self.label(t) for t in self.tops(dlg)], ['📚 ' + LIB, '📚 Mes outils'])
        mine = self.node(dlg, 'Mes outils')
        self.assertEqual([self.label(mine.child(i)) for i in range(mine.childCount())], ['📁 Atelier', '📁 Gravure'])
        plug = self.node(dlg, LIB)
        self.assertEqual([self.label(plug.child(i)) for i in range(plug.childCount())], ['📁 Cylindriques',
                                                                                         '📁 Coniques'])
        self.assertIn('5 outil(s)', dlg.info.text())

    def test_the_commands_follow_the_chosen_tool(self):
        dlg = self.dialog()
        dlg.tree.setCurrentItem(self.row(dlg, 'Plug 3'))
        self.assertEqual(dlg.source_key(), LIB)
        self.assertEqual(dlg.selected().name, 'Plug 3')
        self.assertFalse(dlg.acts['new'].isEnabled())                        # bibliothèque d'un plugin : lecture
        self.assertTrue(dlg.acts['keep'].isEnabled())
        dlg.tree.setCurrentItem(self.row(dlg, 'Mine 1'))
        self.assertEqual(dlg.source_key(), '__mienne__')
        self.assertTrue(dlg.acts['new'].isEnabled())
        self.assertTrue(dlg.rename('Mine 1 bis'))
        self.assertEqual([t.name for t in toollib.load(self.path)], ['Mine 1 bis', 'Mine 2'])

    def test_opens_on_the_last_list_and_folder(self):
        dlg = self.dialog()
        dlg.tree.setCurrentItem(self.row(dlg, 'Plug 6'))
        self.assertEqual((self.s.get('outils/derniere_liste'), self.s.get('outils/dernier_dossier')),
                         (LIB, 'Cylindriques/Cyl 6'))
        dlg2 = self.dialog()
        self.assertEqual(dlg2.source_key(), LIB)
        self.assertTrue(self.node(dlg2, LIB).isExpanded())
        self.assertFalse(self.node(dlg2, 'Mes outils').isExpanded())
        self.assertTrue(self.row(dlg2, 'Plug 6').parent().isExpanded())      # son dernier dossier : ouvert
        self.assertFalse(self.row(dlg2, 'Plug 3').parent().isExpanded())

    def test_mine_folders_under_their_library(self):
        dlg = self.dialog()
        mine = self.node(dlg, 'Mes outils')
        it = self.row(dlg, 'Mine 1')
        self.assertIs(it.parent().parent(), mine)
        dlg.tree.setCurrentItem(it)
        target = next(mine.child(i) for i in range(mine.childCount()) if self.label(mine.child(i)) == '📁 Gravure')
        self.assertTrue(dlg.dropped(target))                                 # glissé sur un dossier : rangé
        self.assertEqual({t.name: t.folder for t in toollib.load(self.path)}, {'Mine 1': 'Gravure',
                                                                              'Mine 2': 'Gravure'})

    def test_a_copy_appears_at_once(self):
        dlg = self.dialog()
        dlg.tree.setCurrentItem(self.row(dlg, 'Plug V90'))
        self.assertEqual(dlg.copy_to_mine(), 1)
        it = self.row(dlg, 'Plug V90')                                       # dans sa bibliothèque…
        self.assertEqual(it.data(0, ROLE + 3), LIB)
        copies = [x for x in dlg._items() if x.data(0, ROLE) and x.text(0).startswith('Plug V90')
                  and x.data(0, ROLE + 3) == '__mienne__']
        self.assertEqual(len(copies), 1)                                     # … et déjà sous Mes outils


class Favourites(Base):

    def test_on_top_from_every_library(self):
        self.favs(self.lib[2], self.m2)
        dlg = self.dialog()
        top = self.tops(dlg)[0]
        self.assertTrue(self.label(top).startswith('★ Favoris'), self.label(top))
        self.assertEqual([top.child(i).text(0).split(' — ')[0].strip() for i in range(top.childCount())],
                         ['Plug V90', 'Mine 2'])
        dlg.tree.setCurrentItem(self.row(dlg, 'Plug V90', in_favs=True))
        self.assertEqual(dlg.source_key(), LIB)                              # la ligne d'un favori : sa bibliothèque
        self.assertNotIn('outils/derniere_liste', self.s)                    # (pas retenue comme dernière liste)

    def test_star_click_and_drops(self):
        dlg = self.dialog(show=True)
        it = self.row(dlg, 'Mine 1')
        dlg.tree.scrollToItem(it)
        r = dlg.tree.visualItemRect(it)
        QTest.mouseClick(dlg.tree.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(r.left() + 8, r.center().y()))
        for _ in range(3):
            app.processEvents()
        key = toollib.favorite_key
        self.assertEqual(json.loads(self.s.get('outils/favoris', '[]')), [key(self.m1)])
        top = self.tops(dlg)[0]
        self.assertTrue(self.label(top).startswith('★ Favoris'), self.label(top))
        plug = self.row(dlg, 'Plug 3')                                       # glissé sur le groupe : au bout
        dlg.tree.setCurrentItem(plug)
        self.assertTrue(dlg.dropped(self.tops(dlg)[0]))
        self.assertEqual(json.loads(self.s['outils/favoris']), [key(self.m1), key(self.lib[1])])
        moving = self.row(dlg, 'Plug 3', in_favs=True)                       # glissé sur un favori : avant lui
        dlg.tree.setCurrentItem(moving)
        self.assertTrue(dlg.dropped(self.row(dlg, 'Mine 1', in_favs=True)))
        self.assertEqual(json.loads(self.s['outils/favoris']), [key(self.lib[1]), key(self.m1)])
        top = self.tops(dlg)[0]
        self.assertEqual([top.child(i).text(0).split(' — ')[0].strip() for i in range(top.childCount())],
                         ['Plug 3', 'Mine 1'])
        top.setExpanded(False)                                               # plié : retenu
        self.assertFalse(self.tops(self.dialog())[0].isExpanded())


class DocPanel:
    """Panneau FAO d'essai : chaque `setup()` rend un réglage neuf, relu de ce qui a été enregistré (comme le vrai)."""

    def __init__(self, tools, operations=()):
        self.saved = model.CamSetup(tools=list(tools), operations=list(operations)).to_dict()

    def setup(self):
        return model.CamSetup.from_dict(self.saved)

    def save(self, s):
        self.saved = s.to_dict()


class AfterReview(Base):
    """Relecture : outils du document, imports, dépôts sous une ligne, glisser refusé, favoris renommés."""

    def test_a_document_favourite(self):
        d = tool('Doc 1043', d=4.0)
        self.favs(d)
        try:
            dlg = self.dialog(panel=DocPanel([d]))
        except KeyError as ex:                                              # (avant : l'outil cherché dans un
            self.fail(f'favori d’un outil du document : {ex!r}')             # autre réglage que celui de l'arbre)
        top = self.tops(dlg)
        self.assertTrue(top and self.label(top[0]).startswith('★ Favoris'), [self.label(t) for t in top])
        self.assertEqual([top[0].child(i).text(0).split(' — ')[0].strip() for i in range(top[0].childCount())],
                         ['Doc 1043'])

    def test_a_document_tool_edited_is_kept(self):
        panel = DocPanel([tool('Doc 1043', d=4.0)])
        dlg = self.dialog(panel=panel)
        dlg.tree.setCurrentItem(self.row(dlg, 'Doc 1043'))
        self.assertEqual(dlg.source_key(), '__document__')
        self.assertTrue(dlg.rename('Doc 1043 bis'))
        self.assertEqual([t.name for t in panel.setup().tools], ['Doc 1043 bis'])   # enregistré dans le document
        dlg.tree.setCurrentItem(self.row(dlg, 'Doc 1043 bis'))
        dlg.w['name'].setText('Doc 1043 ter')
        dlg.apply()
        self.assertEqual([t.name for t in panel.setup().tools], ['Doc 1043 ter'])

    def test_an_import_from_a_plugin_library_goes_to_my_tools(self):
        src = pathlib.Path(tempfile.mkdtemp()) / 'import1043.json'
        toollib.save([tool('Imp 1043', d=5.0)], src)
        dlg = self.dialog()
        dlg.tree.setCurrentItem(self.row(dlg, 'Plug 3'))
        self.assertEqual(dlg.source_key(), LIB)
        self.assertEqual(dlg.import_file(src), 1)
        self.assertIn('Imp 1043', [t.name for t in toollib.load(self.path)])    # pas perdu dans le plugin
        self.assertEqual(dlg.source_key(), '__mienne__')
        self.row(dlg, 'Imp 1043')

    def test_a_drop_below_a_tool_puts_it_after(self):
        import inspect
        abc = [tool(n, folder='F') for n in ('A 1043', 'B 1043', 'C 1043')]
        toollib.save(abc, self.path)
        dlg = self.dialog()
        self.assertIn('after', inspect.signature(dlg.dropped).parameters)   # marque du dépôt sous la ligne
        dlg.tree.setCurrentItem(self.row(dlg, 'A 1043'))
        self.assertTrue(dlg.dropped(self.row(dlg, 'B 1043'), True))
        self.assertEqual([t.name for t in toollib.load(self.path)], ['B 1043', 'A 1043', 'C 1043'])
        dlg.tree.setCurrentItem(self.row(dlg, 'C 1043'))
        self.assertTrue(dlg.dropped(self.row(dlg, 'B 1043'), False))       # sur la ligne : avant elle
        self.assertEqual([t.name for t in toollib.load(self.path)], ['C 1043', 'B 1043', 'A 1043'])
        key = toollib.favorite_key
        self.favs(abc[0], abc[1])
        dlg2 = self.dialog()
        dlg2.tree.setCurrentItem(self.row(dlg2, 'A 1043', in_favs=True))
        self.assertTrue(dlg2.dropped(self.row(dlg2, 'B 1043', in_favs=True), True))     # favoris : après
        self.assertEqual(json.loads(self.s['outils/favoris']), [key(abc[1]), key(abc[0])])

    def test_another_library_is_not_dropped_in_my_tools(self):
        self.favs(self.m1)
        dlg = self.dialog()
        refuses = getattr(dlg.tree, 'refuses', None)
        self.assertIsNotNone(refuses, 'le dépôt est refusé dès le survol')
        dlg.tree.setCurrentItem(self.row(dlg, 'Plug 3'))
        self.assertTrue(refuses(self.row(dlg, 'Mine 2')))                  # Mes outils : refusé
        self.assertFalse(refuses(self.tops(dlg)[0]))                        # les favoris : accepté
        self.assertFalse(dlg.dropped(self.row(dlg, 'Mine 2')))
        dlg.tree.setCurrentItem(self.row(dlg, 'Mine 1'))
        self.assertFalse(refuses(self.row(dlg, 'Mine 2')))                  # ranger Mes outils : accepté

    def test_a_renamed_favourite_stays_one(self):
        self.favs(self.m1, self.m2)
        dlg = self.dialog()
        dlg.tree.setCurrentItem(self.row(dlg, 'Mine 1'))
        self.assertTrue(dlg.rename('Mine 1 bis'))
        renamed = next(t for t in toollib.load(self.path) if t.name == 'Mine 1 bis')
        key = toollib.favorite_key
        self.assertEqual(json.loads(self.s['outils/favoris']), [key(renamed), key(self.m2)])   # à sa place
        dlg.tree.setCurrentItem(self.row(dlg, 'Mine 2'))
        dlg.w['name'].setText('Mine 2 bis')
        dlg.apply()
        renamed2 = next(t for t in toollib.load(self.path) if t.name == 'Mine 2 bis')
        self.assertEqual(json.loads(self.s['outils/favoris']), [key(renamed), key(renamed2)])


class SecondReview(Base):
    """Seconde relecture : outil du document utilisé, imports, copies d'un favori, fiche en cours, sélection,
    dépôts refusés."""

    def test_a_used_document_tool_is_not_deleted(self):
        d, e = tool('Doc 1043', d=4.0), tool('Doc libre 1043', d=5.0)
        panel = DocPanel([d, e], [model.Operation(name='Op 1043', tool_id=d.id)])
        dlg = self.dialog(panel=panel)
        dlg.tree.setCurrentItem(self.row(dlg, 'Doc 1043'))
        self.assertEqual(dlg.delete(confirm=False), 0)                     # une opération s'en sert : gardé
        self.assertEqual([t.name for t in panel.setup().tools], ['Doc 1043', 'Doc libre 1043'])
        self.assertIn('Doc 1043', dlg.info.text())
        dlg.tree.setCurrentItem(self.row(dlg, 'Doc libre 1043'))
        self.assertEqual(dlg.delete(confirm=False), 1)
        self.assertEqual([t.name for t in panel.setup().tools], ['Doc 1043'])

    def test_imports_always_go_to_my_tools(self):
        self.s['outils/derniere_liste'] = '__document__'                  # dernière liste : le document
        panel = DocPanel([tool('Doc 1043', d=4.0)])
        dlg = self.dialog(panel=panel)
        label = getattr(dlg, 'lib_label', None)
        self.assertIsNotNone(label, 'la bibliothèque des commandes n’était pas montrée')
        self.assertIn('Outils du document', label.text())
        src = pathlib.Path(tempfile.mkdtemp()) / 'import1043.json'
        toollib.save([tool('Imp 1043', d=5.0)], src)
        self.assertEqual(dlg.import_file(src), 1)
        self.assertIn('Imp 1043', [t.name for t in toollib.load(self.path)])
        self.assertEqual([t.name for t in panel.setup().tools], ['Doc 1043'])     # pas dans le document
        self.assertIn('Mes outils', label.text())

    def test_a_changed_copy_leaves_the_original_starred(self):
        copy = model.CamTool.from_dict(self.m1.to_dict())
        copy.id = model.new_id()
        panel = DocPanel([copy])
        self.favs(self.m1)
        dlg = self.dialog(panel=panel)
        doc = next((it for it in dlg._items() if it.data(0, ROLE + 3) == '__document__' and it.data(0, ROLE)), None)
        self.assertIsNotNone(doc, 'pas d’outils du document dans l’arbre')
        dlg.tree.setCurrentItem(doc)
        self.assertTrue(dlg.rename('Mine 1 copie'))
        key = toollib.favorite_key
        renamed = panel.setup().tools[0]
        self.assertEqual(json.loads(self.s['outils/favoris']), [key(self.m1), key(renamed)])   # les deux

    def test_a_star_click_keeps_the_form_being_typed(self):
        dlg = self.dialog()
        toggle = getattr(dlg, 'toggle_favorite', None)
        self.assertIsNotNone(toggle)
        dlg.tree.setCurrentItem(self.row(dlg, 'Mine 1'))
        dlg.w['name'].setText('Mine 1 en cours')
        toggle(self.m1)
        self.assertEqual(dlg.w['name'].text(), 'Mine 1 en cours')         # pas rechargée
        self.assertEqual(dlg.current.name, 'Mine 1')
        dlg.tree.setCurrentItem(self.row(dlg, 'Mine 2'))
        dlg.w['notes'].setPlainText('notes en cours')
        self.assertTrue(dlg.dropped(self.tops(dlg)[0]))                    # glissé dans les favoris
        self.assertEqual(dlg.w['notes'].toPlainText(), 'notes en cours')
        self.assertIsNotNone(dlg.current)                                  # « Enregistrer la fiche » marche encore
        dlg.apply()
        self.assertEqual({t.name: t.notes for t in toollib.load(self.path)}['Mine 2'], 'notes en cours')

    def test_a_selection_stays_in_one_library(self):
        from PySide6.QtCore import QItemSelectionModel
        dlg = self.dialog()
        dlg.tree.setCurrentItem(self.row(dlg, 'Mine 1'))
        self.row(dlg, 'Mine 2').setSelected(True)
        dlg.tree.setCurrentItem(self.row(dlg, 'Plug 3'), 0, QItemSelectionModel.SelectionFlag.Select)   # Ctrl + clic
        names = sorted(it.text(0).split(' — ')[0].strip() for it in dlg.tree.selectedItems())
        self.assertEqual(names, ['Plug 3'])
        self.assertEqual([t.name for t in dlg.selected_tools()], ['Plug 3'])

    def test_drops_that_would_do_nothing_are_refused(self):
        self.favs(self.m1)
        dlg = self.dialog()
        refuses = getattr(dlg.tree, 'refuses', None)
        self.assertIsNotNone(refuses)
        dlg.tree.setCurrentItem(self.row(dlg, 'Mine 1', in_favs=True))    # un favori glissé hors des favoris
        self.assertTrue(refuses(self.row(dlg, 'Mine 2')))
        self.assertFalse(dlg.dropped(self.row(dlg, 'Mine 2')))
        self.assertEqual({t.name: t.folder for t in toollib.load(self.path)}['Mine 1'], 'Atelier')   # pas bougé
        mine = self.node(dlg, 'Mes outils')
        dlg.tree.setCurrentItem(mine.child(0))                              # un dossier glissé dans les favoris
        self.assertTrue(refuses(self.tops(dlg)[0]))


if __name__ == '__main__':
    unittest.main()
