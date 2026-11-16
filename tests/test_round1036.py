"""Round 1036 : demande du 15/11 ~10 h 20 « FAO parcours disponibles : fusionner les disponibles de base dans
"Parcours type" un dossier user (actuellement 2d-3d, et un TE (palette TE) si user a fait l'import; Tout ces dossiers
doivent etre renommables; bouton usinage par couleur tout en bas »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1036.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QMenu  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import templates as TPL  # noqa: E402
from vectordrive.ui import cam_palette as CP  # noqa: E402

FAMILIES = ['Usinage 2D', 'Usinage 2D-3D', 'Usinage 3D', 'Laser', 'Machine']


def template(name, folder='', origine='', preset='decoupe'):
    tpl = {'format': 'vectordrive-modele-fao', 'version': 1, 'name': name, 'description': 'essai', 'tools': [],
           'preset': preset, 'dossier': folder, 'operations': [{'kind': 'contour', 'depth': 1.0}], 'post': '',
           'machine': ''}
    if origine:
        tpl['origine'] = origine
    return tpl


MINE = template('Alu / Détour 2mm', 'Alu')
LOOSE = template('Détour simple')                                            # le vôtre, hors dossier
PLUG = template('Détour du plugin')                                          # celui d'un plugin : sous son parcours
TE = template('TypeEdit 13 — Meca3 / Atelier / Gravure V', 'TypeEdit 13 — Meca3 / Atelier', 'typeedit', 'gravure')
TTPL = dict(template('TypeEdit : Gravure fine', 'TypeEdit — modèles .ttpl', preset='gravure'),
            typeedit={'attrs': {}, 'params': {}})                            # fichier .ttpl repris de TypeEdit


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self._old = os.environ.get('VECTORDRIVE_CAM_TEMPLATES')
        os.environ['VECTORDRIVE_CAM_TEMPLATES'] = tempfile.mkdtemp()         # vos modèles : un dossier d'essai
        self.w = MainWindow()
        self.w.settings.remove(getattr(CP, 'NAMES', 'fao/palette/noms'))
        self.pal = self.w.cam_palette
        self.te_pal = True                                                   # la palette de TypeEdit est là
        self.found, self.favs, self.empty = {}, [], []

    def tearDown(self):
        self.w.settings.remove(getattr(CP, 'NAMES', 'fao/palette/noms'))
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        if self._old is None:
            os.environ.pop('VECTORDRIVE_CAM_TEMPLATES', None)
        else:
            os.environ['VECTORDRIVE_CAM_TEMPLATES'] = self._old

    def show(self, templates=(MINE, LOOSE, TE), favs=('cam_new_gravure',), empty=(), plugin=(PLUG,)):
        found = {t['name']: ('plugin', t) for t in plugin}
        found.update({t['name']: ('utilisateur', t) for t in templates})
        self.found, self.favs, self.empty = found, list(favs), list(empty)
        self.refresh()

    def patches(self, files=False):
        """Modèles (sauf `files` : ceux du dossier d'essai), dossiers vides, favoris, palette de TypeEdit."""
        import contextlib
        st = contextlib.ExitStack()
        if not files:
            st.enter_context(mock.patch.object(TPL, 'all_templates', return_value=self.found))
            st.enter_context(mock.patch.object(TPL, 'empty_folders', return_value=self.empty))
        st.enter_context(mock.patch.object(self.w.cam_panel, 'favorites', return_value=self.favs))
        st.enter_context(mock.patch.object(CP, 'te_palette', return_value=self.te_pal, create=True))
        return st

    def refresh(self, files=False):
        with self.patches(files):
            self.pal.refresh()

    def tops(self):
        t = self.pal.tree                                                    # « Mes process » (0.904.0) : à part
        return [t.topLevelItem(i) for i in range(t.topLevelItemCount())
                if t.topLevelItem(i).data(0, getattr(CP, 'ROLE_GROUP', 0)) != 'process']

    def top_texts(self):
        return [t.text(0) for t in self.tops()]

    @staticmethod
    def kids(item):
        return [item.child(i) for i in range(item.childCount())]


class ThreeFolders(Base):

    def test_type_mine_and_typeedit(self):
        self.show()
        tops = self.tops()
        self.assertEqual([t.text(0) for t in tops], ['Parcours type', 'Mes modèles', 'TypeEdit'])
        base, mine, te = tops
        self.assertEqual([k.text(0) for k in self.kids(base)][:5], FAMILIES)   # les familles de base, réunies
        cut = next(k for f in self.kids(base) for k in self.kids(f) if k.data(0, CP.ROLE_KIND) == 'decoupe')
        self.assertEqual([k.text(0) for k in self.kids(cut)], ['📄 Détour du plugin'])   # le plugin : sous son parcours
        self.assertTrue(mine.data(0, CP.ROLE_ROOT))                          # y déposer : hors dossier
        self.assertEqual([k.text(0) for k in self.kids(mine)], ['📁 Alu', '📄 Détour simple'])   # tous les vôtres
        self.assertEqual([k.text(0) for k in self.kids(te)], ['Favoris (palette TypeEdit)', '📁 TypeEdit 13 — Meca3'])
        fav = self.kids(te)[0]
        self.assertEqual([k.data(0, CP.ROLE_KIND) for k in self.kids(fav)], ['gravure'])
        self.assertIn('cam_new_decoupe', self.pal.items)

    def test_the_palette_without_an_import_and_ttpl_files(self):
        self.show(templates=(MINE,))                                         # palette de TypeEdit ou d'un plugin,
        self.assertEqual([t.text(0) for t in self.tops()], ['Parcours type', 'Mes modèles'])   # sans import :
        first = self.kids(self.tops()[0])[0]                                 # en tête des parcours type
        self.assertEqual(first.text(0), 'Favoris (palette TypeEdit)')
        self.assertEqual([k.data(0, CP.ROLE_KIND) for k in self.kids(first)], ['gravure'])
        self.show(templates=(MINE, TTPL), favs=())                           # .ttpl repris de TypeEdit : importés
        self.assertEqual([t.text(0) for t in self.tops()], ['Parcours type', 'Mes modèles', 'TypeEdit'])
        self.assertEqual([k.text(0) for k in self.kids(self.tops()[2])], ['📁 TypeEdit — modèles .ttpl'])

    def test_typeedit_only_after_the_import(self):
        self.show(templates=(MINE,), favs=())
        self.assertEqual([t.text(0) for t in self.tops()], ['Parcours type', 'Mes modèles'])
        moved = dict(TE, dossier='Alu', name='Alu / Gravure V')                 # rangé par l'utilisateur ailleurs
        self.show(templates=(moved,), favs=())
        self.assertEqual([t.text(0) for t in self.tops()], ['Parcours type', 'Mes modèles'])
        self.assertEqual([k.text(0) for k in self.kids(self.tops()[1])], ['📁 Alu'])

    def test_what_is_put_in_an_import_folder_stays_there(self):
        put = dict(MINE, dossier='TypeEdit 13 — Meca3/Atelier', name='TypeEdit 13 — Meca3/Atelier / Détour 2mm')
        self.show(templates=(TE, put, MINE), favs=(), empty=('TypeEdit 13 — Meca3/Nouveau', 'Bois'))
        self.assertEqual([t.text(0) for t in self.tops()], ['Parcours type', 'Mes modèles', 'TypeEdit'])
        _base, mine, te = self.tops()
        self.assertEqual([k.text(0) for k in self.kids(mine)], ['📁 Alu', '📁 Bois'])
        meca = self.kids(te)[0]
        self.assertEqual(meca.text(0), '📁 TypeEdit 13 — Meca3')
        self.assertEqual(sorted(k.text(0) for k in self.kids(meca)), ['📁 Atelier', '📁 Nouveau'])
        workshop = next(k for k in self.kids(meca) if k.text(0) == '📁 Atelier')
        self.assertEqual(len(self.kids(workshop)), 2)                        # l'importé et le vôtre, rangé là

    def test_opened_or_closed_folders_stay_so(self):
        self.show()
        base = self.tops()[0]
        self.assertEqual(base.text(0), 'Parcours type')
        self.kids(base)[0].setExpanded(False)
        self.tops()[2].setExpanded(False)
        self.refresh()
        base, _, te = self.tops()
        self.assertFalse(self.kids(base)[0].isExpanded())
        self.assertTrue(self.kids(base)[1].isExpanded())
        self.assertFalse(te.isExpanded())

    def test_no_empty_typeedit_folder_and_plugin_favourites_stay_at_the_top(self):
        self.w._machine_kind = 'laser'                                       # importés pour la fraiseuse seulement
        self.show(templates=(MINE, TE), favs=())
        self.assertEqual(self.top_texts(), ['Parcours type', 'Mes modèles'])
        self.w._machine_kind = ''
        self.te_pal = False                                                  # les favoris viennent d'un plugin :
        self.refresh()                                                       # en tête des parcours type, même
        self.assertEqual(self.top_texts(), ['Parcours type', 'Mes modèles', 'TypeEdit'])   # après l'import
        self.show(templates=(MINE, TE))
        base, _mine, te = self.tops()
        self.assertEqual(self.kids(base)[0].text(0), 'Favoris (palette TypeEdit)')
        self.assertEqual([k.text(0) for k in self.kids(te)], ['📁 TypeEdit 13 — Meca3'])

    def test_drops_on_the_palette_folders(self):
        self.show()
        self.assertEqual(self.top_texts(), ['Parcours type', 'Mes modèles', 'TypeEdit'])
        base, mine, te = self.tops()
        target = self.pal.tree.target_folder
        self.assertEqual(target(mine), '')                                   # « Mes modèles » : hors dossier
        for refused in (base, self.kids(base)[0], te, self.kids(te)[0]):     # les autres dossiers de la palette
            self.assertIsNone(target(refused), refused.text(0))
        self.assertEqual(target(self.kids(te)[1]), 'TypeEdit 13 — Meca3')    # un dossier d'import : oui


class ImportFolders(Base):
    """Un dossier d'import de TypeEdit renommé reste dans « TypeEdit » ; un nouvel import s'y refait."""

    def test_a_renamed_import_folder_stays_in_typeedit(self):
        from tests.test_round237 import tpp13
        path = os.path.join(tempfile.mkdtemp(), 'PathParam_Essai.TPP')
        with open(path, 'wb') as f:
            f.write(tpp13())
        with self.patches(files=True):
            self.assertEqual(self.pal.import_typeedit([path], quiet=True), 3)
            self.assertEqual(self.pal.rename_folder('TypeEdit — Essai', 'Essai'), 3)      # F2 : « Essai »
        self.refresh(files=True)
        self.assertEqual(self.top_texts(), ['Parcours type', 'Mes modèles', 'TypeEdit'])
        _base, mine, te = self.tops()
        self.assertEqual([k.text(0) for k in self.kids(te)], ['📁 Essai'])
        self.assertEqual(self.kids(mine), [])
        with self.patches(files=True):                                       # import refait : dans « Essai »,
            self.assertEqual(self.pal.import_typeedit([path], quiet=True), 3)            # sans doublon
        got = TPL.user_templates()
        self.assertEqual(len(got), 3)
        self.assertTrue(all(t['dossier'].startswith('Essai') for t in got.values()), sorted(got))

    def test_imports_from_before_and_moves(self):
        root_of = getattr(TPL, 'import_root', None)
        self.assertIsNotNone(root_of, 'avant : un dossier d\'import renommé n\'était plus reconnu')
        TPL.save_user(dict(TE))                                              # importé avant (sans sa racine)
        TPL.save_user(dict(MINE))
        self.assertEqual(root_of(TE), 'TypeEdit 13 — Meca3')
        self.assertEqual(TPL.rename_folder('TypeEdit 13 — Meca3', 'Meca3'), 1)
        t = TPL.user_templates()['Meca3/Atelier / Gravure V']
        self.assertEqual((t[TPL.ROOT_KEY], t[TPL.SOURCE_KEY], root_of(t)), ('Meca3', 'TypeEdit 13 — Meca3', 'Meca3'))
        self.assertEqual(TPL.root_of_source('TypeEdit 13 — Meca3'), 'Meca3')
        TPL.rename_folder('Meca3', 'Archives/Meca3')                         # rangé ailleurs : « Mes modèles »
        self.assertIsNone(root_of(TPL.user_templates()['Archives/Meca3/Atelier / Gravure V']))
        TPL.rename_folder('Archives/Meca3', 'Meca3')                         # remis : de nouveau dans « TypeEdit »
        self.assertEqual(root_of(TPL.user_templates()['Meca3/Atelier / Gravure V']), 'Meca3')
        TPL.rename_folder('Meca3/Atelier', 'Meca3/Laiton')                   # un sous-dossier : la racine reste
        self.assertEqual(root_of(TPL.user_templates()['Meca3/Laiton / Gravure V']), 'Meca3')
        TPL.rename_folder('Alu', 'Bois')                                     # pas importé : rien de plus
        self.assertNotIn(TPL.ROOT_KEY, TPL.user_templates()['Bois / Détour 2mm'])
        self.assertIsNone(root_of(TPL.user_templates()['Bois / Détour 2mm']))


class Renaming(Base):

    def rename(self, key, label=None):
        fn = getattr(self.pal, 'rename_group', None)
        self.assertIsNotNone(fn, 'avant : les dossiers de la palette ne se renommaient pas')
        with self.patches():
            return fn(key, label)

    def test_every_folder_is_renamable(self):
        self.show()
        self.assertEqual(self.rename('type', 'Mes parcours de base'), 'Mes parcours de base')
        self.rename('fam:Usinage 2D', 'Perçages')
        self.rename('user', 'Atelier')
        self.rename('te', 'TE13')
        self.rename('favoris', 'Palette')
        base, mine, te = self.tops()
        self.assertEqual([base.text(0), mine.text(0), te.text(0)], ['Mes parcours de base', 'Atelier', 'TE13'])
        self.assertEqual(self.kids(base)[0].text(0), 'Perçages')
        self.assertEqual(self.kids(te)[0].text(0), 'Palette')
        self.refresh()                                                       # retenu
        self.assertEqual(self.tops()[0].text(0), 'Mes parcours de base')
        self.assertEqual(self.rename('type', ''), 'Parcours type')           # vide : le nom d'origine
        self.assertEqual(self.tops()[0].text(0), 'Parcours type')
        self.assertIsNone(self.rename('absent', 'x'))

    def test_f2_and_right_click(self):
        self.show()
        base = self.tops()[0]
        self.pal.tree.setCurrentItem(base)
        self.assertEqual(self.pal.tree.currentItem(), base)                  # un dossier se choisit (pour F2)
        with mock.patch('PySide6.QtWidgets.QInputDialog.getText', return_value=('Base', True)), self.patches():
            self.pal.rename_selected()
        self.assertEqual(self.tops()[0].text(0), 'Base')
        shown = []
        from PySide6.QtCore import QPoint

        class Menu(QMenu):                                                    # le menu montré : ses commandes lues
            def popup(self, *_a):
                shown.append([x.text() for x in self.actions()])
        with mock.patch.object(CP, 'QMenu', Menu), \
                mock.patch.object(self.pal.tree, 'itemAt', return_value=self.tops()[0]):
            self.pal._menu(QPoint(5, 5))
        self.assertTrue(shown)
        self.assertIn('Renommer le dossier…', shown[-1])
        self.assertIn('Nom d’origine', shown[-1])                            # renommé : retour possible


class ColorAtTheBottom(Base):

    def test_machining_by_color_is_last(self):
        lay = self.pal.layout()
        self.assertEqual(lay.indexOf(self.pal.color_on), lay.count() - 2)
        self.assertEqual(lay.indexOf(self.pal.mode_row), lay.count() - 1)
        self.assertGreater(lay.indexOf(self.pal.color_on), lay.indexOf(self.pal.tree))


if __name__ == '__main__':
    unittest.main()
