"""Round 1186 (demande du 27/11) : « maj garder le carnet client; ».

Le carnet de clients du BAT (`clients.json` et ses logos, ou le dossier choisi par le réglage `bat/clients`) survit à
tous les chemins de mise à jour : reprise d'une ancienne version (premier lancement, F10) et mise à jour par le dossier
VD — copié s'il n'y en a pas ici, sinon fusionné dans le carnet des données d'ici (clients d'ici gardés, ceux qui
manquent ajoutés avec leur logo, rien d'écrasé, copie de secours d'abord) ; jamais versé d'office dans un dossier
choisi ici ; dossier choisi par l'ancienne version : réglage repris si le carnet d'ici est vide, rien de copié ;
carnet illisible jamais perdu ; chemin de logo réseau jamais touché ; mise à jour en place (portable : `donnees`
jamais touché). Catégorie « Carnet de clients » de la configuration (.vdparam), import fusionné sans écraser. Bilan et
questions le disent.

Tout se passe dans des dossiers temporaires (LOCALAPPDATA isolé par `import tests`) ; aucune vraie boîte n'est ouverte
(`QMessageBox.exec` remplacé par un clic) ; aucune fenêtre principale n'est créée."""
import json
import os
import pathlib
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rcarnet.ini'))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QWidget  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive import app_update as AU  # noqa: E402
from vectordrive import portable as P  # noqa: E402
from vectordrive.io import clients as CL  # noqa: E402

BEFORE = 'avant : le carnet de clients n’était ni fusionné ni dit à la reprise, ni dans la configuration'
EMPTY_INI = '; VectorDrive portable : réglages enregistrés ici\n'


def need(obj, *names):
    for n in names:
        if not hasattr(obj, n):
            raise AssertionError(f'{BEFORE} ({n} absent)')


def make_version(box, name, keys=None) -> pathlib.Path:
    """Une version portable décompressée : box/name/VectorDrive/ avec l'exe et l'ini."""
    app_dir = pathlib.Path(box) / name / 'VectorDrive'
    app_dir.mkdir(parents=True)
    (app_dir / 'VectorDrive.exe').write_bytes(b'MZ')
    (app_dir / P.INI).write_text(EMPTY_INI, encoding='utf-8')
    if keys:
        s = QSettings(str(app_dir / P.INI), QSettings.Format.IniFormat)
        for k, v in keys.items():
            s.setValue(k, v)
        s.sync()
    return app_dir


def make_book(folder, clients: dict) -> pathlib.Path:
    """Un carnet : {nom : octets du logo (ou None)} — logos copiés par `clients.add`, comme le BAT le fait."""
    folder = pathlib.Path(folder)
    src = pathlib.Path(tempfile.mkdtemp(prefix='logos_'))
    try:
        for name, data in clients.items():
            logo = ''
            if data is not None:
                logo = str(src / f'{name}.svg')
                pathlib.Path(logo).write_bytes(data)
            CL.add(folder, name, logo, ville='Lyon')
    finally:
        shutil.rmtree(src, True)                         # les logos sont copiés dans le carnet
    return folder


def logo_bytes(folder, name) -> bytes:
    p = CL.logo_path(folder, CL.find(folder, name))
    return pathlib.Path(p).read_bytes() if p else b''


def tree_of(folder) -> dict:
    return {p.relative_to(folder).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in pathlib.Path(folder).rglob('*') if p.is_file()}


def text_of(res) -> str:
    from vectordrive.ui.main_window import MainWindow
    return MainWindow.adoption_text(None, res)


def book_of(res):
    need(res, 'book')
    return res.book


class Base(unittest.TestCase):
    """Une nouvelle version portable (`self.new`, VectorDrive.ini vide) posée à côté d'une ancienne."""

    def setUp(self):
        self.box = pathlib.Path(tempfile.mkdtemp(prefix='rcarnet_'))
        self.env = mock.patch.dict(os.environ, {})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(shutil.rmtree, self.box, True)
        self.new = make_version(self.box, 'VectorDrive-9.9.9-portable')
        os.environ['VECTORDRIVE_PORTABLE_DIR'] = str(self.new)   # jamais le registre du poste
        os.environ.pop('VECTORDRIVE_SETTINGS', None)
        P.LAST = None

    def old(self, keys=None, book=None):
        old = make_version(self.box, 'VectorDrive-1.41.0-portable', {'options/decimales': 3, **(keys or {})})
        if book:
            make_book(old / 'donnees' / 'clients', book)
        return old

    def mine(self):
        """Les réglages de cette version, déjà servie (reprise à la main)."""
        s = QSettings(str(self.new / P.INI), QSettings.Format.IniFormat)
        s.setValue('portable/reprise', 'non')
        s.setValue('vue/theme', 'mien')
        s.sync()
        return s


# --- 1. reprise d'une ancienne version ---------------------------------------------------------------------------
class Adopt(Base):

    def test_book_copied_when_absent_here_and_said(self):
        old = self.old(book={'Durand': b'<svg>durand</svg>', 'Petit': b'<svg>petit</svg>', 'Sans logo': None})
        before = tree_of(old)
        res = P.adopt(old)                               # premier lancement : rien ici
        b = book_of(res)
        here = self.new / 'donnees' / 'clients'
        self.assertEqual([c['nom'] for c in CL.load(here)], ['Durand', 'Petit', 'Sans logo'])
        self.assertEqual(logo_bytes(here, 'Durand'), b'<svg>durand</svg>')
        self.assertEqual(logo_bytes(here, 'Petit'), b'<svg>petit</svg>')
        self.assertEqual(CL.find(here, 'Petit')['ville'], 'Lyon')          # toutes ses données
        self.assertEqual((b.added, b.logos, b.kept), (3, 2, 0))
        self.assertEqual(res.failed, [])
        self.assertEqual(tree_of(old), before)                             # rien de changé là-bas
        self.assertIn('Carnet de clients : 3 client(s) ajouté(s), dont 2 avec leur logo ; 0 déjà là gardé(s)',
                      text_of(res))

    def test_book_merged_when_present_here_nothing_overwritten(self):
        here = make_book(self.new / 'donnees' / 'clients', {'Durand': b'<svg>le mien</svg>', 'Martin': None})
        stray = here / CL.LOGOS / 'Petit.svg'                               # un fichier d'ici au nom du logo à venir
        stray.write_bytes(b'<svg>autre</svg>')
        mine_before = (here / CL.FILE).read_bytes()
        old = self.old(book={'durand': b'<svg>ancien</svg>', 'Petit': b'<svg>petit</svg>'})
        before = tree_of(old)
        settings = self.mine()
        res = P.adopt(old, settings=settings, keep=True)                   # F10 : reprise à la main
        b = book_of(res)
        self.assertEqual([c['nom'] for c in CL.load(here)], ['Durand', 'Martin', 'Petit'])
        self.assertEqual(logo_bytes(here, 'Durand'), b'<svg>le mien</svg>')  # gardé tel quel
        self.assertEqual(logo_bytes(here, 'Petit'), b'<svg>petit</svg>')     # ajouté avec son logo
        self.assertEqual(stray.read_bytes(), b'<svg>autre</svg>')            # jamais écrasé
        self.assertEqual(CL.find(here, 'Petit')['logo'], 'logos/Petit_2.svg')
        backup = here / (CL.FILE + AU.BACKUP)
        self.assertEqual(backup.read_bytes(), mine_before)                   # copie de secours d'abord
        self.assertEqual((b.added, b.logos, b.kept), (1, 1, 1))
        self.assertIn(f'{here / CL.FILE} → {CL.FILE}{AU.BACKUP}', res.replaced)
        self.assertNotIn(str(old / 'donnees' / 'clients' / CL.FILE), res.skipped)
        self.assertEqual(tree_of(old), before)
        text = text_of(res)
        self.assertIn('1 client(s) ajouté(s), dont 1 avec leur logo ; 1 déjà là gardé(s)', text)
        self.assertIn(CL.FILE + AU.BACKUP, text)
        res2 = P.adopt(old, settings=settings, keep=True)                  # une seconde fois : rien de doublé
        self.assertEqual((res2.book.added, res2.book.kept), (0, 2))
        self.assertEqual(len(CL.load(here)), 3)

    def test_never_merged_into_a_folder_chosen_here(self):
        chosen = make_book(self.box / 'partage_ici', {'Martin': b'<svg>m</svg>'})
        shared_before = tree_of(chosen)
        settings = self.mine()
        settings.setValue(CL.SETTING, str(chosen))
        settings.sync()
        old = self.old(book={'Petit': b'<svg>petit</svg>', 'Durand': None})
        res = P.adopt(old, settings=settings, keep=True)
        b = book_of(res)
        self.assertEqual(tree_of(chosen), shared_before)                    # ni client, ni copie de secours
        self.assertFalse((self.new / 'donnees' / 'clients' / CL.FILE).exists())
        self.assertEqual(settings.value(CL.SETTING), str(chosen))
        self.assertEqual((b.shared, b.waiting, b.added), (str(chosen), 2, 0))
        self.assertIn(f'le dossier choisi ici ({chosen}) peut être partagé par d’autres postes : les 2 client(s) de '
                      'l’ancienne version n’y sont pas ajoutés d’office', text_of(res))

    def test_chosen_folder_of_the_old_version_taken_nothing_copied(self):
        network = make_book(self.box / 'reseau' / 'Clients', {'Durand': b'<svg>d</svg>'})
        old = self.old(keys={CL.SETTING: str(network)}, book={'Ancien carnet local': None})
        net_before = tree_of(network)
        res = P.adopt(old)                               # premier lancement
        b = book_of(res)
        self.assertEqual(QSettings(str(self.new / P.INI), QSettings.Format.IniFormat).value(CL.SETTING),
                         str(network))
        self.assertFalse((self.new / 'donnees' / 'clients' / CL.FILE).exists())   # rien de copié
        self.assertEqual(tree_of(network), net_before)                             # rien d'écrit là-bas
        self.assertEqual((b.chosen, res.book_taken, b.added), (str(network), True, 0))
        self.assertIn(f'le dossier choisi par l’ancienne version est repris ({network}) ; rien n’est copié',
                      text_of(res))

    def test_manual_empty_setting_here_empty_book_takes_the_chosen_folder(self):
        network = make_book(self.box / 'reseau' / 'Clients', {'Durand': None})
        settings = self.mine()
        settings.setValue(CL.SETTING, '')                # la fenêtre des options écrit chaque champ, vide compris
        settings.sync()
        old = self.old(keys={CL.SETTING: str(network)})
        res = P.adopt(old, settings=settings, keep=True)
        need(res, 'book_taken')
        self.assertEqual(settings.value(CL.SETTING), str(network))
        self.assertEqual(settings.value('vue/theme'), 'mien')                       # les autres : gardés
        self.assertTrue(res.book_taken)

    def test_manual_empty_setting_here_with_a_local_book_keeps_it(self):
        network = make_book(self.box / 'reseau' / 'Clients', {'Durand': None})
        make_book(self.new / 'donnees' / 'clients', {'Local': None})
        settings = self.mine()
        settings.setValue(CL.SETTING, '')
        settings.sync()
        old = self.old(keys={CL.SETTING: str(network)})
        res = P.adopt(old, settings=settings, keep=True)
        need(res, 'book_local')
        self.assertEqual(settings.value(CL.SETTING), '')                            # ce poste garde son carnet
        self.assertEqual((res.book_taken, res.book_local), (False, 1))
        self.assertEqual([c['nom'] for c in CL.load(self.new / 'donnees' / 'clients')], ['Local'])
        self.assertIn(f'celui des données d’ici (1 client(s)) reste employé ; le dossier choisi par l’ancienne version '
                      f'({network}) n’est pas repris', text_of(res))

    def test_manual_chosen_folder_here_kept(self):
        mine_dir = self.box / 'mon_partage'
        settings = self.mine()
        settings.setValue(CL.SETTING, str(mine_dir))
        settings.sync()
        theirs = self.box / 'leur_partage'
        old = self.old(keys={CL.SETTING: str(theirs)})
        res = P.adopt(old, settings=settings, keep=True)
        self.assertEqual(settings.value(CL.SETTING), str(mine_dir))
        need(res, 'book_taken')
        self.assertEqual((res.book.chosen, res.book_taken), (str(theirs), False))
        self.assertIn(f'le dossier choisi ici est gardé ; celui de l’ancienne version ({theirs}) n’est pas repris',
                      text_of(res))

    def test_other_files_of_the_clients_folder_still_carried(self):
        old = self.old(book={'Durand': None})
        (old / 'donnees' / 'clients' / 'Durand').mkdir()
        (old / 'donnees' / 'clients' / 'Durand' / 'fiche.json').write_text('{}', encoding='utf-8')
        res = P.adopt(old)
        self.assertTrue((self.new / 'donnees' / 'clients' / 'Durand' / 'fiche.json').is_file())
        self.assertEqual(book_of(res).added, 1)

    def test_unreadable_old_book_never_lost_and_nameless_clients_said(self):
        old = self.old()
        src = old / 'donnees' / 'clients'
        make_book(src, {'Petit': b'<svg>p</svg>'})
        (src / CL.FILE).write_text('{abîmé', encoding='utf-8')
        res = P.adopt(old)                               # rien ici : recopié tel quel, dit
        book_of(res)
        here = self.new / 'donnees' / 'clients'
        self.assertEqual((here / CL.FILE).read_text(encoding='utf-8'), '{abîmé')
        self.assertEqual((here / CL.LOGOS / 'Petit.svg').read_bytes(), b'<svg>p</svg>')
        self.assertTrue(any('illisible : recopié tel quel' in f for f in res.failed), res.failed)
        mine = make_book(self.box / 'b' / 'clients', {'Martin': None})      # un carnet ici : laissé, dit
        before = tree_of(mine)
        got = CL.merge(src, mine, backup=lambda f: 'copie')
        self.assertEqual(tree_of(mine), before)
        self.assertIn('non fusionné', got.failed[0])
        (src / CL.FILE).write_text(json.dumps({'version': 1, 'clients': [{'nom': 'Petit'}, {'ville': 'Lyon'}, 3]}),
                                   encoding='utf-8')
        got = CL.merge(src, mine)
        self.assertEqual(got.added, ['Petit'])
        self.assertTrue(any('2 client(s) sans nom' in f for f in got.failed), got.failed)

    def test_questions_mention_the_book(self):
        seen = {}

        def click(text):
            def fake_exec(box):
                seen['text'] = box.text() + '\n' + box.informativeText()
                next(b for b in box.buttons() if b.text() == text).click()
                return 0
            return fake_exec
        with mock.patch.object(QMessageBox, 'exec', click('Reprendre ses réglages')):
            self.assertIs(P._ask_adopt('VectorDrive-1.41.0', path='D:\\VD\\x'), True)
        self.assertIn('carnet de clients du BAT (fusionné avec celui d’ici)', seen['text'])
        dlg, _lst, _where = P._choose_dialog([AU.describe(self.old())])
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(any('carnet de clients' in lb.text() for lb in dlg.findChildren(QLabel)))
        from vectordrive.ui.main_window import MainWindow
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        with mock.patch.object(QMessageBox, 'exec', click('Reprendre')):
            self.assertTrue(MainWindow._confirm_adopt(parent, 'VectorDrive-1.41.0', 'D:\\VD\\x'))
        self.assertIn('le carnet de clients et les onglets', seen['text'])
        self.assertIn('rien d’office dans un dossier choisi ici', seen['text'])


# --- 2. mises à jour : en place (portable) et par le dossier VD ------------------------------------------------
class Update(Base):

    def test_update_in_place_and_by_the_versions_folder_keep_the_book(self):
        os.environ.pop(CL.ENV, None)
        self.assertEqual(CL.folder(None), self.new / 'donnees' / 'clients')    # portable : dans `donnees`
        archive = self.box / 'VectorDrive-9.9.10-portable.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('VectorDrive/VectorDrive.exe', 'MZ')
            z.writestr('VectorDrive/' + P.INI, EMPTY_INI)
        script = P.launch_portable_update(archive, pid=1, target=self.new, start=False)
        text = script.read_text(encoding='cp1252')
        shutil.rmtree(script.parent, True)
        self.assertIn(f'/XD {P.DATA}', text)                                   # en place : `donnees` jamais touché
        self.assertIn(f'/XF {P.INI}', text)                                    # ni le réglage du dossier choisi
        self.assertNotIn('/PURGE', text)
        self.assertNotIn('/MIR', text)
        # par le dossier VD : la nouvelle version a déjà un carnet (lancée une fois) — fusionné, rien d'écrasé
        here = make_book(self.new / 'donnees' / 'clients', {'Durand': b'<svg>le mien</svg>'})
        old = self.old(book={'Durand': b'<svg>ancien</svg>', 'Petit': b'<svg>p</svg>'})
        carried = AU.carry_settings(old, self.new)
        b = book_of(carried)
        self.assertEqual([c['nom'] for c in CL.load(here)], ['Durand', 'Petit'])
        self.assertEqual(logo_bytes(here, 'Durand'), b'<svg>le mien</svg>')
        self.assertEqual(logo_bytes(here, 'Petit'), b'<svg>p</svg>')
        self.assertEqual((b.added, b.kept), (1, 1))
        self.assertEqual(carried.failed, [])
        self.assertTrue((here / (CL.FILE + AU.BACKUP)).is_file())
        from vectordrive.ui.main_window import MainWindow
        lines = MainWindow.book_lines(b)                                      # la note de la mise à jour
        self.assertIn('Carnet de clients : 1 client(s) ajouté(s), dont 1 avec leur logo ; 1 déjà là gardé(s)', lines[0])
        self.assertIn(CL.FILE + AU.BACKUP, lines[1])

    def test_versions_folder_update_with_a_chosen_folder_copies_nothing(self):
        network = make_book(self.box / 'reseau', {'Durand': None})
        old = self.old(keys={CL.SETTING: str(network)}, book={'Ancien carnet local': None})
        carried = AU.carry_settings(old, self.new)
        self.assertEqual(book_of(carried).chosen, str(network))
        self.assertFalse((self.new / 'donnees' / 'clients' / CL.FILE).exists())
        self.assertEqual(QSettings(str(self.new / P.INI), QSettings.Format.IniFormat).value(CL.SETTING),
                         str(network))                                          # le réglage suit l'ini
        self.assertTrue(AU.book_taken(carried.book, self.new / P.INI))


# --- 3. la fusion elle-même ----------------------------------------------------------------------------------
class Merge(unittest.TestCase):

    def setUp(self):
        self.box = pathlib.Path(tempfile.mkdtemp(prefix='rcarnet_m_'))
        self.addCleanup(shutil.rmtree, self.box, True)

    def test_unreadable_book_here_never_rewritten(self):
        need(CL, 'merge')
        src = make_book(self.box / 'a', {'Petit': None})
        dst = self.box / 'b'
        dst.mkdir()
        (dst / CL.FILE).write_text('{abîmé', encoding='utf-8')
        got = CL.merge(src, dst, backup=lambda f: 'copie')
        self.assertEqual((got.added, got.replaced), ([], []))
        self.assertIn('illisible', got.failed[0])
        self.assertEqual((dst / CL.FILE).read_text(encoding='utf-8'), '{abîmé')

    def test_network_or_outside_logo_path_never_touched(self):
        need(CL, 'merge')
        src = make_book(self.box / 'a', {'A': None, 'B': None, 'C': None})
        data = json.loads((src / CL.FILE).read_text(encoding='utf-8'))
        for c, rel in zip(data['clients'], ('\\\\machine\\partage\\x.svg', '//machine/partage/x.svg', '../x.svg')):
            c['logo'] = rel
        (src / CL.FILE).write_text(json.dumps(data), encoding='utf-8')
        (self.box / 'x.svg').write_bytes(b'non')
        real_realpath, real_is_file, real_exists, real_stat = (os.path.realpath, pathlib.Path.is_file,
                                                               pathlib.Path.exists, os.stat)

        def guard(fn):
            def wrapped(p, *a, **k):
                if 'machine' in str(p):
                    raise AssertionError(f'accès réseau : {p}')
                return fn(p, *a, **k)
            return wrapped
        other = self.box / 'c'
        with mock.patch('os.path.realpath', guard(real_realpath)), mock.patch('os.stat', guard(real_stat)), \
                mock.patch.object(pathlib.Path, 'is_file', guard(real_is_file)), \
                mock.patch.object(pathlib.Path, 'exists', guard(real_exists)):
            got = CL.merge(src, other)
        self.assertEqual(got.added, ['A', 'B', 'C'])
        self.assertEqual(got.logos, 0)
        self.assertFalse((other / CL.LOGOS).exists())
        self.assertEqual(sum('refusé' in f for f in got.failed), 3, got.failed)

    def test_merge_cut_then_redone_leaves_no_orphan_nor_duplicate(self):
        need(CL, 'merge')
        src = make_book(self.box / 'a', {'Petit': b'<svg>p</svg>'})
        dst = make_book(self.box / 'b', {'Martin': None})
        with mock.patch.object(CL, '_save', side_effect=OSError('coupure')):
            got = CL.merge(src, dst)                     # coupée après la copie du logo
        self.assertEqual(got.added, [])
        self.assertTrue(got.failed)
        self.assertEqual([c['nom'] for c in CL.load(dst)], ['Martin'])
        got = CL.merge(src, dst)                         # refaite
        self.assertEqual(got.added, ['Petit'])
        self.assertEqual(CL.find(dst, 'Petit')['logo'], 'logos/Petit.svg')   # le logo déjà copié, repris
        self.assertEqual(sorted(p.name for p in (dst / CL.LOGOS).iterdir()), ['Petit.svg'])


# --- 4. la configuration exportée (.vdparam) ----------------------------------------------------------------
class Config(unittest.TestCase):

    def setUp(self):
        self.box = pathlib.Path(tempfile.mkdtemp(prefix='rcarnet_cfg_'))
        self.addCleanup(shutil.rmtree, self.box, True)
        self.env = mock.patch.dict(os.environ, {})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_book_round_trip_merged_never_overwritten(self):
        from vectordrive.io import params
        need(params, 'BOOK')
        self.assertIn(params.BOOK, dict(params.categories()))
        src = make_book(self.box / 'a', {'Durand': b'<svg>a</svg>', 'Petit': b'<svg>p</svg>'})
        st = QSettings(str(self.box / 'a.ini'), QSettings.Format.IniFormat)
        out = self.box / ('c' + params.EXT)
        os.environ[CL.ENV] = str(src)
        self.assertEqual(params.available(st)[params.BOOK], 2)
        counts = params.export(out, st, [params.BOOK])
        self.assertEqual(counts, {params.BOOK: 2})
        names = zipfile.ZipFile(out).namelist()
        for n in ('clients/clients.json', 'clients/logos/Durand.svg', 'clients/logos/Petit.svg'):
            self.assertIn(n, names)
        self.assertEqual(params.contents(out), {params.BOOK: 2})
        self.assertIn('2 clients du carnet', params.summary(counts))
        dst = make_book(self.box / 'b', {'durand': b'<svg>le mien</svg>'})
        before = (dst / CL.FILE).read_bytes()
        os.environ[CL.ENV] = str(dst)
        st2 = QSettings(str(self.box / 'b.ini'), QSettings.Format.IniFormat)
        got, backup = params.import_(out, st2, backup_dir=self.box / 'bk')
        self.assertEqual(got[params.BOOK], 1)
        self.assertEqual([c['nom'] for c in CL.load(dst)], ['durand', 'Petit'])
        self.assertEqual(logo_bytes(dst, 'durand'), b'<svg>le mien</svg>')         # jamais écrasé
        self.assertEqual(logo_bytes(dst, 'Petit'), b'<svg>p</svg>')
        self.assertEqual(backup, self.box / 'bk')
        self.assertEqual((backup / 'clients' / CL.FILE).read_bytes(), before)   # copie de secours d'abord
        got2, _bk = params.import_(out, st2, backup_dir=self.box / 'bk2')       # une seconde fois : rien de doublé
        self.assertEqual(got2[params.BOOK], 0)
        self.assertEqual(len(CL.load(dst)), 2)
        self.assertEqual(sorted(p.name for p in (dst / CL.LOGOS).iterdir()), ['Petit.svg', 'durand.svg'])


if __name__ == '__main__':
    unittest.main()
