"""Round 1117 : la fenêtre Ouvrir cherche un dossier, un fichier dont le nom contient… parmi les favoris et le dossier
affiché, avec tous leurs sous-dossiers ; index la première fois, puis index d'abord, vérifié, dossiers changés relus,
index réécrit s'il a changé (demande du 20/11) ; les trois recherches sur la même ligne."""
import json
import os
import pathlib
import shutil
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
_TMP = tempfile.mkdtemp(prefix='vd1117_')
# round 1159 : posés par setUpModule, plus à l'import (ils valaient alors pour tous les essais du processus)
_ENV = {'VECTORDRIVE_SETTINGS': os.path.join(_TMP, 'r1117.ini'),
        'VECTORDRIVE_SESSION': os.path.join(_TMP, 'session.json'),
        'VECTORDRIVE_CACHE': os.path.join(_TMP, 'cache')}
_SAVED = {}

from PySide6.QtCore import QEvent, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

app = QApplication.instance() or QApplication([])

import vectordrive  # noqa: E402
from vectordrive.core import fav_index as FI  # noqa: E402
from vectordrive.ui import file_browser as FB  # noqa: E402
from vectordrive.ui.file_browser import matcher  # noqa: E402


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


def touch(p: pathlib.Path) -> pathlib.Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('x', encoding='utf-8')
    return p


def bump(folder: pathlib.Path, step: float = 5.0) -> None:
    """La date du dossier avancée (le système de fichiers la change à la seconde près parfois)."""
    t = os.stat(folder).st_mtime + step
    os.utime(folder, (t, t))


def tree(base: pathlib.Path) -> pathlib.Path:
    touch(base / 'Clients' / 'Dupont' / 'plaque_dupont.svg')
    touch(base / 'Clients' / 'Dupont' / 'notes.txt')
    touch(base / 'Clients' / 'Martin' / 'Été 2026' / 'badge_martin.dxf')
    touch(base / 'Archives' / 'vieux' / 'plaque_ancienne.svg')
    (base / 'Archives' / 'Dupont-old').mkdir(parents=True)
    return base


class Index(unittest.TestCase):
    """`core.fav_index` seul (sans Qt)."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(dir=_TMP))
        self.fav = tree(self.tmp / 'fav')
        self.file = self.tmp / 'idx.json'

    def idx(self):
        return FI.FavIndex(self.file)

    def test_first_time_indexes_everything(self):
        idx = self.idx()
        self.assertFalse(idx.indexed(self.fav))
        got = idx.search([self.fav], 'fichier', matcher('plaque'))
        self.assertEqual(sorted(p.name for p in got), ['plaque_ancienne.svg', 'plaque_dupont.svg'])
        self.assertTrue(idx.indexed(self.fav))
        self.assertTrue(self.file.is_file(), "enregistré à la fin de la recherche")
        self.assertFalse(idx.save(), 'rien de changé : pas réécrit')
        data = json.loads(self.file.read_text(encoding='utf-8'))
        self.assertEqual(data['version'], FI.VERSION)
        again = self.idx()                               # relu du disque : l'index répond sans le parcourir
        self.assertEqual(len(again.lookup([self.fav], 'fichier', matcher('plaque'))), 2)

    def test_folder_kind_and_accents(self):
        idx = self.idx()
        got = idx.search([self.fav], 'dossier', matcher('dupont'))
        self.assertEqual(sorted(p.name for p in got), ['Dupont', 'Dupont-old'])
        self.assertTrue(all(p.is_dir() for p in got))
        self.assertEqual([p.name for p in idx.lookup([self.fav], 'dossier', matcher('ete'))], ['Été 2026'])
        self.assertEqual(idx.lookup([self.fav], 'dossier', matcher('plaque')), [], 'un fichier n\'est pas un dossier')

    def test_extension_filter(self):
        idx = self.idx()
        idx.search([self.fav], 'fichier', matcher('*'))
        names = {p.name for p in idx.lookup([self.fav], 'fichier', matcher('*'), ('.svg',))}
        self.assertEqual(names, {'plaque_dupont.svg', 'plaque_ancienne.svg'})

    def test_next_time_index_first_then_verified_then_new(self):
        idx = self.idx()
        idx.search([self.fav], 'fichier', matcher('plaque'))
        idx.save()
        (self.fav / 'Archives' / 'vieux' / 'plaque_ancienne.svg').unlink()
        bump(self.fav / 'Archives' / 'vieux')
        touch(self.fav / 'Clients' / 'Martin' / 'plaque_martin.svg')
        bump(self.fav / 'Clients' / 'Martin')
        idx = self.idx()
        first = idx.lookup([self.fav], 'fichier', matcher('plaque'))
        self.assertEqual(len(first), 2, 'd\'abord ce que l\'index connaît (le fichier retiré y est encore)')
        box = {}
        reads = []
        real = idx._read
        idx._read = lambda f: (reads.append(pathlib.Path(f)), real(f))[1]
        got = idx.search([self.fav], 'fichier', matcher('plaque'), first=first, box=box)
        self.assertEqual([p.name for p in box['verifies']], ['plaque_dupont.svg'], 'vérifiés : le retiré écarté')
        self.assertEqual(sorted(p.name for p in got), ['plaque_dupont.svg', 'plaque_martin.svg'])
        self.assertEqual(sorted(r.name for r in reads), ['Martin', 'vieux'], 'seuls les dossiers changés relus')
        self.assertFalse(idx.dirty, "enregistré par la recherche")
        self.assertIn("plaque_martin.svg", self.file.read_text(encoding="utf-8"))
        idx2 = self.idx()
        reads.clear()
        idx2._read = lambda f: (reads.append(f), real(f))[1]
        idx2.search([self.fav], 'fichier', matcher('plaque'))
        self.assertEqual(reads, [])
        self.assertFalse(idx2.dirty, 'rien de changé : l\'index n\'est pas réécrit')

    def test_removed_subfolder_dropped(self):
        idx = self.idx()
        idx.search([self.fav], 'dossier', matcher('*'))
        shutil.rmtree(self.fav / 'Clients' / 'Martin')
        bump(self.fav / 'Clients')
        got = idx.search([self.fav], 'dossier', matcher('*'))
        self.assertNotIn('Martin', {p.name for p in got})
        self.assertNotIn('Été 2026', {p.name for p in got})
        rec = idx.roots[FI.key_of(self.fav)]['dirs']
        self.assertFalse(any('Martin' in k for k in rec))

    def test_removed_root_and_forget(self):
        idx = self.idx()
        other = tree(self.tmp / 'autre')
        idx.search([self.fav, other], 'dossier', matcher('dupont'))
        self.assertTrue(idx.indexed(other))
        idx.dirty = False
        self.assertTrue(idx.forget([self.fav]))
        self.assertFalse(idx.indexed(other))
        self.assertTrue(idx.dirty)

    def test_nested_roots_once(self):
        roots = FI.top_roots([self.fav / 'Clients', self.fav, self.fav, self.tmp / 'favx'])
        self.assertEqual(roots, [self.fav, self.tmp / 'favx'], 'un favori compris dans un autre : parcouru une fois')

    def test_hidden_and_dot_names_skipped(self):
        touch(self.fav / '.git' / 'plaque_cachee.svg')
        touch(self.fav / '$RECYCLE.BIN' / 'plaque_corbeille.svg')
        touch(self.fav / 'Clients' / 'secret_plaque.svg')
        idx = FI.FavIndex(self.file, hidden=lambda e: e.name.startswith('secret'))
        got = {p.name for p in idx.search([self.fav], 'fichier', matcher('plaque'))}
        self.assertEqual(got, {'plaque_dupont.svg', 'plaque_ancienne.svg'})

    def test_limit(self):
        idx = self.idx()
        self.assertEqual(len(idx.search([self.fav], 'fichier', matcher('*'), limit=2)), 2)

    def test_cancel_keeps_what_is_read(self):
        from vectordrive.core import progress
        idx = self.idx()
        calls = {'n': 0}
        real = progress.check

        def check():
            calls['n'] += 1
            if calls['n'] > 3:
                raise progress.Cancelled()
            return real()
        with mock.patch.object(FI.progress, 'check', check):
            with self.assertRaises(progress.Cancelled):
                idx.search([self.fav], 'fichier', matcher('*'))
        self.assertTrue(self.file.is_file(), 'ce qui est lu est enregistré (par le fil de calcul)')
        self.assertTrue(self.idx().roots, 'relu : la partie déjà parcourue')
        self.assertFalse(idx.lock.locked())
        got = idx.search([self.fav], 'fichier', matcher('plaque'))
        self.assertEqual(len(got), 2, 'la fois suivante finit le parcours')

    def test_cancel_while_rescanning_saves(self):
        from vectordrive.core import progress
        idx = self.idx()
        idx.search([self.fav], 'fichier', matcher('*'))
        touch(self.fav / 'Clients' / 'Dupont' / 'plaque_deux.svg')
        bump(self.fav / 'Clients' / 'Dupont')
        before = self.file.read_text(encoding='utf-8')
        state = {'read': False}
        real, real_read = progress.check, idx._read

        def read(folder):
            if pathlib.Path(folder).name == 'Dupont':
                state['read'] = True                     # Annuler juste après la relecture de ce dossier
            return real_read(folder)
        idx._read = read

        def check():
            if state['read']:
                raise progress.Cancelled()
            return real()
        with mock.patch.object(FI.progress, 'check', check):
            with self.assertRaises(progress.Cancelled):
                idx.search([self.fav], 'fichier', matcher('*'))
        self.assertNotEqual(self.file.read_text(encoding='utf-8'), before, 'avant : rien d\'enregistré')
        self.assertIn('plaque_deux.svg', {p.name for p in self.idx().lookup([self.fav], 'fichier', matcher('deux'))})

    def test_unreachable_root_keeps_its_index(self):
        idx = self.idx()
        idx.search([self.fav], 'fichier', matcher('plaque'))
        gone = self.tmp / 'fav_parti'
        self.fav.rename(gone)                            # partage injoignable, clé débranchée…
        self.assertFalse(idx.update(self.fav))
        self.assertTrue(idx.indexed(self.fav))
        self.assertEqual(len(idx.lookup([self.fav], 'fichier', matcher('plaque'))), 2, 'gardé pour son retour')
        gone.rename(self.fav)

    def test_unreachable_root_results_left_out(self):
        idx = self.idx()
        other = tree(self.tmp / 'nas')
        idx.search([self.fav, other], 'fichier', matcher('plaque'))
        gone = self.tmp / 'nas_arrete'
        other.rename(gone)                               # le NAS arrêté : ses fichiers ne sont pas montrés
        got = idx.search([self.fav, other], 'fichier', matcher('plaque'))
        self.assertEqual(len(got), 2)
        self.assertTrue(all(self.fav in p.parents for p in got))
        self.assertTrue(idx.indexed(other))
        gone.rename(other)

    def test_file_root_not_indexed(self):
        f = touch(self.tmp / 'seul.svg')
        idx = self.idx()
        self.assertFalse(idx.update(f))
        self.assertFalse(idx.indexed(f))

    def test_unreliable_dates_reread_everything(self):
        idx = self.idx()
        idx.search([self.fav], 'fichier', matcher('*'))
        self.assertTrue(FI._dates_reliable(str(self.fav)), 'NTFS : les dates des dossiers suffisent')
        idx2 = self.idx()
        reads = []
        real = idx2._read
        idx2._read = lambda f: (reads.append(f), real(f))[1]
        with mock.patch.object(FI, '_dates_reliable', return_value=False):        # FAT, exFAT
            idx2.search([self.fav], 'fichier', matcher('*'))
        self.assertEqual(len(reads), len(idx2.roots[FI.key_of(self.fav)]['dirs']))

    def test_only_links_skipped_not_cloud_files(self):
        class St:
            def __init__(self, tag):
                self.st_file_attributes = 0x400
                self.st_reparse_tag = tag

        class Entry:                                     # (sans is_junction : Python d'avant 3.12)
            def __init__(self, tag):
                self.name, self.path, self._tag = 'x', 'x', tag

            def is_symlink(self):
                return False

            def stat(self, follow_symlinks=True):
                return St(self._tag)
        self.assertTrue(FI._reparse(Entry(0xA0000003)), 'jonction')
        self.assertTrue(FI._reparse(Entry(0xA000000C)), 'lien symbolique')
        self.assertFalse(FI._reparse(Entry(0x9000601A)), 'OneDrive (fichiers à la demande) : un dossier ordinaire')
        self.assertFalse(FI._reparse(Entry(0x80000013)), 'déduplication')

    def test_shared_index(self):
        a = FI.shared(self.tmp / 'commun.json')
        self.assertIs(FI.shared(self.tmp / 'commun.json'), a, 'un seul index (et un seul verrou) par fichier')
        self.assertIsNot(FI.shared(self.tmp / 'autre.json'), a)

    def test_extra_verified(self):
        idx = self.idx()
        f = touch(self.tmp / 'fav_fichier.svg')
        box = {}
        idx.search([self.fav], 'fichier', matcher('plaque'), box=box, extra=[f, self.tmp / 'absent.svg'])
        self.assertIn(f, box['verifies'])
        self.assertNotIn(self.tmp / 'absent.svg', box['verifies'])

    def test_unencodable_name_does_not_break_save(self):
        idx = self.idx()
        idx.roots['k'] = {'root': 'k', 'dirs': {'': [1.0, ['a\udc80.svg'], []]}}
        idx.dirty = True
        self.assertTrue(idx.save(), 'demi-caractère UTF-16 : écrit tel quel')
        self.assertEqual(self.idx().roots['k']['dirs'][''][1], ['a\udc80.svg'])
        self.assertEqual([p.name for p in self.tmp.glob('*.tmp')], [])

    @unittest.skipUnless(os.name == 'nt', 'jonction : Windows')
    def test_junction_not_followed(self):
        import _winapi
        try:
            _winapi.CreateJunction(str(self.fav / 'Clients'), str(self.fav / 'Archives' / 'boucle'))
        except OSError as ex:
            self.skipTest(str(ex))
        got = {str(p) for p in self.idx().search([self.fav], 'fichier', matcher('plaque_dupont'))}
        self.assertEqual(len(got), 1, 'une jonction ne duplique pas l\'arbre (ni ne boucle)')
        os.rmdir(self.fav / 'Archives' / 'boucle')

    def test_malformed_entries_dropped(self):
        self.file.write_text(json.dumps({'version': FI.VERSION, 'roots': {
            FI.key_of(self.fav): {'root': str(self.fav), 'dirs': {'': [1, 'pas une liste', []]}},
            'x': {'root': 'x', 'dirs': {'': [1, [], []]}}}}), encoding='utf-8')
        idx = self.idx()
        self.assertEqual(list(idx.roots), ['x'])
        self.assertEqual(len(idx.search([self.fav], 'fichier', matcher('plaque'))), 2)

    def test_corrupt_file_ignored(self):
        self.file.write_text('{pas du json', encoding='utf-8')
        idx = self.idx()
        self.assertEqual(idx.roots, {})
        self.assertEqual(len(idx.search([self.fav], 'fichier', matcher('plaque'))), 2)


class Panel(unittest.TestCase):
    """Les deux champs de la fenêtre Ouvrir."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(dir=_TMP))
        os.environ['VECTORDRIVE_CACHE'] = str(self.tmp / 'cache')
        self.fav = tree(self.tmp / 'fav')
        self.s = QSettings(str(self.tmp / 's.ini'), QSettings.Format.IniFormat)
        self.s.setValue('navigateur/favoris', [str(self.fav)])
        self.p = FB.FileBrowserPanel(self.s)
        self.p.EXTS = ('.svg', '.dxf')

    def tearDown(self):
        self.p.deleteLater()

    def names(self):
        return sorted(pathlib.Path(self.p.list.item(i).data(Qt.ItemDataRole.UserRole)).name
                      for i in range(self.p.list.count()) if self.p.list.item(i).data(FB.ROLE_KIND) != 'up')

    def test_three_searches_on_one_line(self):
        lay = FB._layout_of(self.p.search, self.p.layout())
        self.assertIsNotNone(lay)
        i = lay.indexOf(self.p.search)
        self.assertEqual(lay.indexOf(self.p.fav_dir), i + 1)
        self.assertEqual(lay.indexOf(self.p.fav_file), i + 2)
        self.assertIn('Dossier', self.p.fav_dir.placeholderText())
        self.assertIn('Fichier', self.p.fav_file.placeholderText())
        self.assertTrue(self.p.fav_dir.isClearButtonEnabled())

    def test_file_search_lists_files(self):
        got = self.p.search_favorites('fichier', 'plaque')
        self.assertEqual(sorted(p.name for p in got), ['plaque_ancienne.svg', 'plaque_dupont.svg'])
        self.assertEqual(self.names(), ['plaque_ancienne.svg', 'plaque_dupont.svg'])
        self.assertIn('dans les favoris', self.p.where.text())
        self.assertIn('2', self.p.where.text())
        idx_file = pathlib.Path(os.environ['VECTORDRIVE_CACHE']) / 'VectorDrive' / FB.FAV_INDEX_FILE
        self.assertTrue(idx_file.is_file(), 'l\'index enregistré à côté des autres caches')

    def test_format_filter_applies(self):
        got = self.p.search_favorites('fichier', 'notes')
        self.assertEqual(got, [], 'un .txt n\'est pas du format choisi')

    def test_folder_search_lists_folders(self):
        got = self.p.search_favorites('dossier', 'dupont')
        self.assertEqual(sorted(p.name for p in got), ['Dupont', 'Dupont-old'])
        kinds = {self.p.list.item(i).data(FB.ROLE_KIND) for i in range(self.p.list.count())}
        self.assertEqual(kinds, {'dir'})
        self.p.show_folder(got[0])                       # un double clic : le dossier s'ouvre
        self.assertEqual(self.p._folder, got[0])
        self.assertFalse(self.p._search_results)

    def test_second_search_shows_index_first(self):
        self.p.search_favorites('fichier', 'plaque')
        (self.fav / 'Archives' / 'vieux' / 'plaque_ancienne.svg').unlink()
        bump(self.fav / 'Archives' / 'vieux')
        touch(self.fav / 'Clients' / 'plaque_neuve.svg')
        bump(self.fav / 'Clients')
        p2 = FB.FileBrowserPanel(self.s)                 # une autre fois : l'index relu du disque
        p2.EXTS = ('.svg',)
        shown = []
        real = p2.show_fav_results

        def spy(kind, text, paths, folder=None, checking=False, stopped=False):
            shown.append((sorted(p.name for p in paths), checking))
            return real(kind, text, paths, folder, checking, stopped)
        p2.show_fav_results = spy
        got = p2.search_favorites('fichier', 'plaque')
        self.assertEqual(shown[0], (['plaque_ancienne.svg', 'plaque_dupont.svg'], True),
                         'd\'abord l\'index, tout de suite, « vérification… »')
        self.assertEqual(sorted(p.name for p in got), ['plaque_dupont.svg', 'plaque_neuve.svg'])
        self.assertFalse(shown[-1][1])
        p2.deleteLater()

    def test_displayed_folder_searched_too(self):
        other = tree(self.tmp / 'ailleurs')
        touch(other / 'plaque_ailleurs.svg')
        self.p.show_folder(other)
        got = self.p.search_favorites('fichier', 'plaque_a')
        self.assertEqual(sorted(p.name for p in got),               # (le dossier affiché a aussi sa plaque_ancienne)
                         ['plaque_ailleurs.svg', 'plaque_ancienne.svg', 'plaque_ancienne.svg'])
        self.assertEqual(len({str(p) for p in got}), 3)
        self.assertIn(str(other), self.p.where.text())
        # la recherche suivante (résultats montrés) garde ce dossier
        got = self.p.search_favorites('dossier', 'martin')
        self.assertEqual(len(got), 2, 'Martin des favoris et Martin du dossier affiché')
        self.assertIn(other, self.p.fav_scope()[1:])
        idx = self.p.fav_index()
        self.assertTrue(idx.indexed(other), 'gardé indexé (derniers dossiers où l\'on a cherché)')
        self.assertEqual(self.s.value(FB.OTHERS_KEY), [str(other)])

    def test_displayed_folder_inside_favorite_once(self):
        self.p.show_folder(self.fav / 'Clients')
        got = self.p.search_favorites('dossier', 'dupont')
        self.assertEqual(sorted(p.name for p in got), ['Dupont', 'Dupont-old'], 'pas en double')

    def test_folder_selected_in_favorites_view(self):
        other = tree(self.tmp / 'choisi')
        self.s.setValue('navigateur/favoris', [str(self.fav), str(other)])
        self.p.show_favorites()
        self.assertIsNone(self.p.fav_scope()[1])
        for i in range(self.p.list.count()):
            it = self.p.list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == str(other):
                self.p.list.setCurrentItem(it)
                it.setSelected(True)
        self.assertEqual(self.p.fav_scope()[1], other)

    def test_favorite_removed_is_forgotten(self):
        self.p.search_favorites('dossier', 'dupont')
        idx = self.p.fav_index()
        self.assertTrue(idx.indexed(self.fav))
        self.s.setValue('navigateur/favoris', [])
        self.p.show_recents()
        self.assertEqual(self.p.search_favorites('dossier', 'dupont'), [])
        self.assertFalse(idx.indexed(self.fav))

    def test_unplugged_favorite_keeps_its_index(self):
        self.p.search_favorites('dossier', 'dupont')
        idx = self.p.fav_index()
        gone = self.tmp / 'debranche'
        self.fav.rename(gone)                            # clé USB débranchée : plus dans favorite_paths
        self.assertEqual(self.p.search_favorites('dossier', 'dupont'), [])
        self.assertTrue(idx.indexed(self.fav), 'son index attend son retour')
        gone.rename(self.fav)
        reads = []
        real = idx._read
        idx._read = lambda f: (reads.append(f), real(f))[1]
        try:
            self.assertEqual(len(self.p.search_favorites('dossier', 'dupont')), 2)
        finally:
            del idx._read
        self.assertLess(len(reads), 3, 'pas réindexé en entier')

    def test_favorite_kept_out_of_others(self):
        self.p.show_folder(self.fav)
        self.p.search_favorites('dossier', 'dupont')
        self.assertIn(self.s.value(FB.OTHERS_KEY), (None, [], ''))

    def test_lock_busy_search_looks_up_itself(self):
        self.p.search_favorites('fichier', 'plaque')
        idx = self.p.fav_index()
        real = idx.lock

        class Busy:                                      # une recherche annulée tient encore l'index
            def acquire(self, timeout=-1):
                return False

            def __enter__(self):
                return real.__enter__()

            def __exit__(self, *a):
                return real.__exit__(*a)
        idx.lock = Busy()
        try:
            from vectordrive.ui import progress as UP
            seen = {}

            def cancelled(parent, title, fn, *args):
                seen['first'] = args[-3]
                box = args[-2]
                box['verifies'] = fn.__self__.lookup(args[0], 'fichier', args[2], args[3])
                raise UP.Cancelled()
            with mock.patch.object(UP, 'run', cancelled):
                got = self.p.search_favorites('fichier', 'plaque')
        finally:
            idx.lock = real
        self.assertIsNone(seen['first'], 'None : la recherche consulte l\'index elle-même')
        self.assertEqual(len(got), 2)

    def test_refresh_redoes_results(self):
        self.p.search_favorites('fichier', 'plaque')
        (self.fav / 'Archives' / 'vieux' / 'plaque_ancienne.svg').unlink()   # supprimé depuis la liste, F5…
        bump(self.fav / 'Archives' / 'vieux')
        self.p.refresh()
        self.assertEqual(self.names(), ['plaque_dupont.svg'])
        self.assertTrue(self.p._fav_shown)
        self.p.set_view('vignettes' if self.p._view == 'details' else 'details')
        self.assertEqual(self.names(), ['plaque_dupont.svg'], 'l\'élément supprimé ne revient pas')

    def test_favorite_file_matches_directly(self):
        f = touch(self.tmp / 'seul' / 'plaque_favorite.svg')
        self.s.setValue('navigateur/favoris', [str(self.fav), str(f)])
        got = self.p.search_favorites('fichier', 'favorite')
        self.assertEqual([p.name for p in got], ['plaque_favorite.svg'])

    def test_empty_text_does_nothing(self):
        self.p.show_folder(self.fav)
        self.assertEqual(self.p.search_favorites('fichier', '  '), [])
        self.assertEqual(self.p._folder, self.fav)

    def test_navigation_ends_results(self):
        self.p.search_favorites('fichier', 'plaque')
        self.assertTrue(self.p._fav_shown)
        self.p.show_folder(self.fav)
        self.assertFalse(self.p._fav_shown)
        self.assertFalse(self.p._search_results)
        self.assertIsNone(self.p.fav_scope()[1] if self.p._folder is None else None)

    def test_view_change_redraws_results(self):
        self.p.search_favorites('fichier', 'plaque')
        self.p.set_view('vignettes' if self.p._view == 'details' else 'details')
        self.assertEqual(self.names(), ['plaque_ancienne.svg', 'plaque_dupont.svg'])
        self.assertTrue(self.p._fav_shown)

    def test_others_read_back_as_text(self):
        other = tree(self.tmp / 'ailleurs')
        self.s.setValue(FB.OTHERS_KEY, str(self.tmp / 'vieux'))             # INI : une liste d'un élément = texte
        self.p.show_folder(other)
        self.p.search_favorites('dossier', 'dupont')
        self.assertEqual(self.s.value(FB.OTHERS_KEY), [str(other), str(self.tmp / 'vieux')])

    def test_folder_inside_favorite_not_in_others(self):
        self.p.show_folder(self.fav / 'Clients')
        self.p.search_favorites('dossier', 'dupont')
        self.assertIn(self.s.value(FB.OTHERS_KEY), (None, [], ''))

    def test_drive_root_not_searched(self):
        root = pathlib.Path(pathlib.Path(_TMP).anchor)
        self.p._folder = root
        self.assertIsNone(self.p.fav_scope()[1], 'tout un lecteur : jamais indexé d\'office')

    def test_no_disk_access_to_favorites_in_ui(self):
        seen = []
        real = pathlib.Path.is_dir

        def spy(path):
            seen.append(path)
            return real(path)
        self.p.show_folder(self.fav)
        with mock.patch.object(FB.pathlib.Path, 'is_dir', spy), \
                mock.patch('vectordrive.ui.progress.run', side_effect=lambda *a: []):
            self.p.search_favorites('dossier', 'dupont')
        self.assertEqual([s for s in seen if s != self.fav], [], 'un partage injoignable ne fige pas la fenêtre')

    def test_main_filter_cleared(self):
        self.p.show_folder(self.fav / 'Clients')
        self.p.search.setText('zzz')
        got = self.p.search_favorites('fichier', 'plaque')
        self.assertEqual(self.p.search.text(), '')
        self.assertEqual(len(self.names()), len(got), 'aucun résultat caché par le filtre de la liste')

    def test_main_search_ends_fav_results(self):
        self.p.search_favorites('fichier', 'plaque')
        self.p.show_folder(self.fav)
        self.p.search_favorites('fichier', 'plaque')
        self.p._folder = self.fav
        self.p.search.setText('plaque')
        self.p._search()
        self.assertFalse(self.p._fav_shown)

    def test_navigated_emitted(self):
        got = []
        self.p.navigated.connect(lambda: got.append(1))
        self.p.search_favorites('fichier', 'plaque')
        self.assertTrue(got)
        self.assertFalse(self.p.can_up())

    def test_format_change_redoes_file_search(self):
        self.p.search_favorites('fichier', 'a')
        self.assertIn('badge_martin.dxf', self.names())
        self.p.set_exts(('.svg',))
        self.assertNotIn('badge_martin.dxf', self.names())
        self.assertIn('plaque_dupont.svg', self.names())
        self.assertTrue(self.p._fav_shown)

    def test_enter_and_escape(self):
        self.p.fav_file.setText('plaque')
        QTest.keyClick(self.p.fav_file, Qt.Key.Key_Return)
        self.assertEqual(self.names(), ['plaque_ancienne.svg', 'plaque_dupont.svg'])
        self.p.fav_dir.setText('dupont')
        QTest.keyClick(self.p.fav_dir, Qt.Key.Key_Enter)
        self.assertEqual(self.names(), ['Dupont', 'Dupont-old'])
        QTest.keyClick(self.p.fav_dir, Qt.Key.Key_Escape)
        self.assertEqual(self.p.fav_dir.text(), '')

    def test_cancel_keeps_verified(self):
        self.p.search_favorites('fichier', 'plaque')
        from vectordrive.ui import progress as UP

        def cancelled(parent, title, fn, *args):
            box = args[-2]
            box['verifies'] = fn.__self__.still_there(list(args[-1]) + list(args[-3]), 'fichier')
            raise UP.Cancelled()
        with mock.patch.object(UP, 'run', cancelled):
            got = self.p.search_favorites('fichier', 'plaque')
        self.assertEqual(len(got), 2)
        self.assertIn('arrêtée', self.p.where.text())


class Dialog(unittest.TestCase):

    def test_enter_in_field_does_not_open(self):
        tmp = pathlib.Path(tempfile.mkdtemp(dir=_TMP))
        os.environ['VECTORDRIVE_CACHE'] = str(tmp / 'cache')
        fav = tree(tmp / 'fav')
        win = QWidget()
        win.settings = QSettings(str(tmp / 's.ini'), QSettings.Format.IniFormat)
        win.settings.setValue('navigateur/favoris', [str(fav)])
        dlg = FB.FileBrowser(win)
        dlg.show()
        dlg.panel.fav_file.setFocus()
        dlg.panel.fav_file.setText('plaque')
        QTest.keyClick(dlg.panel.fav_file, Qt.Key.Key_Return)
        self.assertTrue(dlg.isVisible(), 'Entrée cherche, la fenêtre reste ouverte')
        self.assertEqual(dlg.paths, [])
        self.assertGreaterEqual(dlg.panel.list.count(), 2)
        dlg.reject()
        win.deleteLater()


if __name__ == '__main__':
    unittest.main()
