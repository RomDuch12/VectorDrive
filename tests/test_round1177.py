"""Round 1177 (demande du 24/11) : « Parametres, : dossier VD : Bouton maj App trouve la dernière (par défaut dans
P:\\Partage\\LOGICIEL\\) copie le zip dans mes documents […] dézippe quitte l'app en cours et charge la nouvelle en
reprenant ou non ses param et eventuellement met à jour le raccourci barre des taches menu démarrer » ; demande du
26/11 : une version portable d'une édition disait « à jour » à côté d'une archive plus récente de son édition déposée
seule dans le dossier réseau ; « Ne pas supprimer de versions antérieure automtiquement. Ajouter bouton mettre à jour
dans optios F10 », puis « màj attention à récupérer tous les onglets ».

Tout se passe dans des dossiers temporaires : archives fabriquées (un faux VectorDrive.exe de quelques octets),
`runner` factice pour les raccourcis, lanceur et sonde du canal d'instance factices : rien de lancé, ni P:, ni
Documents, ni menu Démarrer. Le seul canal réellement ouvert (`test_answers_real_local_channel`) porte un nom
d'essai tiré au hasard."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
import uuid
import zipfile
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rmaj.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')
os.environ.setdefault('VECTORDRIVE_APP_UPDATE', os.path.join(tempfile.mkdtemp(), 'maj_application'))

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : aucune mise à jour de l’application par dossier de versions'
EMPTY_INI = '; VectorDrive portable : réglages enregistrés ici\n'
#: l'ancienne preuve de reprise (élagage retiré le 26/11) : plus jamais écrite
OLD_PROOF = '.vd_repris.json'
#: une édition d'essai, son nom construit (archives `VectorDrive-<édition>-1.34.0-portable.zip`)
ED = 'B' + 'FM'


def au():
    try:
        from vectordrive import app_update
    except ImportError:
        raise AssertionError(BEFORE) from None
    return app_update


def tmp() -> pathlib.Path:
    return pathlib.Path(tempfile.mkdtemp())


def passed(app_dir) -> list:
    """Les passages d'onglets en attente dans une nouvelle version (`donnees/session_maj/…`)."""
    AU = au()
    if not hasattr(AU, 'pending_handovers'):
        raise AssertionError('avant : les onglets passés sont écrits dans la session propre de la nouvelle version')
    return AU.pending_handovers(AU.handover_root(app_dir))


def name_of(version, edition=''):
    return f'VectorDrive{"-" + edition if edition else ""}-{version}'


def make_zip(folder, version, edition='', extra=None, exe=True) -> pathlib.Path:
    """Une archive portable d'essai : VectorDrive/VectorDrive.exe (faux), VectorDrive.ini vide, un fichier."""
    path = pathlib.Path(folder) / (name_of(version, edition) + '-portable.zip')
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w') as z:
        if exe:
            z.writestr('VectorDrive/VectorDrive.exe', b'MZ faux ' + version.encode('ascii'))
        z.writestr('VectorDrive/VectorDrive.ini', EMPTY_INI)
        z.writestr('VectorDrive/_internal/base.txt', 'bibliotheques')
        for k, v in (extra or {}).items():
            z.writestr(k, v)
    return path


def make_version(root, version, edition='', mark=True, shipped=None) -> pathlib.Path:
    """Une version déjà dans le dossier VD, jamais utilisée : son dossier (marqué ou non), tel que décompressé de
    son archive, gardée dans zips/ ; `shipped` : fichiers de plus livrés par l'archive (relatifs à VectorDrive/)."""
    d = pathlib.Path(root) / name_of(version, edition)
    files = {'VectorDrive.exe': 'MZ', 'VectorDrive.ini': EMPTY_INI, '_internal/base.txt': 'x', **(shipped or {})}
    for rel, text in files.items():
        (d / 'VectorDrive' / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / 'VectorDrive' / rel).write_text(text, encoding='utf-8', newline='')
    if mark:
        (d / '.vd_version.json').write_text(json.dumps({'version': version, 'edition': edition}), encoding='utf-8')
    (pathlib.Path(root) / 'zips').mkdir(exist_ok=True)
    with zipfile.ZipFile(pathlib.Path(root) / 'zips' / (d.name + '-portable.zip'), 'w') as z:
        for rel, text in files.items():
            z.writestr('VectorDrive/' + rel, text)
    return d


def use(version_dir, **files) -> pathlib.Path:
    """La version a servi : des réglages dans son VectorDrive.ini, et les fichiers donnés (chemin relatif au dossier
    de l'application → texte)."""
    app_dir = pathlib.Path(version_dir) / 'VectorDrive'
    (app_dir / 'VectorDrive.ini').write_text('[options]\ndecimales=5\n', encoding='utf-8')
    for rel, text in files.items():
        (app_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        (app_dir / rel).write_text(text, encoding='utf-8')
    return app_dir


def stamp(path, when) -> None:
    os.utime(path, (when, when))


def make_link(path, target, wide=True) -> pathlib.Path:
    """Un faux .lnk : quelques octets qui nomment la cible, comme un vrai (UTF-16 ou ANSI)."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'L\x00\x00\x00' + str(target).encode('utf-16-le' if wide else 'ascii'))
    return path


def junction(link, target) -> bool:
    """Jonction (Windows) ou lien symbolique vers un dossier ; faux : impossible ici."""
    try:
        if sys.platform == 'win32':
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        else:
            os.symlink(target, link, target_is_directory=True)
    except (OSError, ImportError, AttributeError):
        return False
    return True


def unlink_junction(link) -> None:
    os.rmdir(link) if sys.platform == 'win32' else os.unlink(link)


class Shell:
    """Tient lieu de PowerShell : les cibles des .lnk dans un dictionnaire ; note les demandes."""

    def __init__(self, targets=None, fail='', errors=None):
        self.targets = {str(k): str(v) for k, v in (targets or {}).items()}
        self.calls, self.fail, self.errors = [], fail, dict(errors or {})

    def __call__(self, request):
        self.calls.append(request)
        if self.fail:
            raise OSError(self.fail)
        if request['action'] == 'lire':
            return {'cibles': [self.targets.get(p, '') for p in request['liens']]}
        out = []
        for w in request['liens']:
            err = self.errors.get(w['lien'], '')
            if not err:
                self.targets[w['lien']] = w['cible']
            out.append(err)
        return {'erreurs': out}

    def asked(self, action):
        return [x for c in self.calls if c['action'] == action for x in c['liens']]


class Alive:
    """Un processus lancé qui vit (ou s'est arrêté : `code`)."""

    def __init__(self, code=None):
        self.code = code

    def poll(self):
        return self.code


class Logic(unittest.TestCase):
    """`vectordrive.app_update` : la logique, sans fenêtre."""

    def setUp(self):
        self.AU = au()
        for name in ('run', 'Popen'):                    # rien n'est lancé : ni PowerShell ni exécutable
            p = mock.patch.object(subprocess, name, side_effect=AssertionError('processus lancé dans un essai'))
            p.start()
            self.addCleanup(p.stop)

    def test_find_latest_numeric_order_edition_subfolder(self):
        AU, src = self.AU, tmp()
        make_zip(src, '1.9.0')
        make_zip(src / 'vectordrive', '1.10.0')                              # un niveau de sous-dossier
        make_zip(src / 'a' / 'b', '9.0.0')                                   # deux niveaux : pas vu
        make_zip(src, '2.0.0', 'ABC')                                        # une autre édition
        (src / 'VectorDrive-8.0.0-setup.exe').write_bytes(b'MZ')             # pas une archive portable
        (src / 'VectorDrive-7.0-portable.zip').write_bytes(b'PK')            # pas 1.34.0
        path, version, edition = AU.find_latest(src)
        self.assertEqual((version, edition), ('1.10.0', ''))                 # 1.10.0 > 1.9.0 : en nombres
        self.assertEqual(path, src / 'vectordrive' / 'VectorDrive-1.10.0-portable.zip')
        got = AU.find_latest(src, 'abc')                                     # l'édition de l'application, sans la casse
        self.assertEqual((got.version, got.edition), ('2.0.0', 'ABC'))
        self.assertIsNone(AU.find_latest(src, 'autre'))                      # jamais une autre édition
        self.assertEqual(len(AU.scan(src)), 3)

    def test_find_latest_unreachable_folder_says_so(self):
        AU = self.AU
        missing = tmp() / 'partage absent'
        with self.assertRaises(AU.AppUpdateError) as cm:
            AU.find_latest(missing)
        self.assertIn('partage absent', str(cm.exception))

    def test_current_edition(self):
        AU, box = self.AU, tmp()
        self.assertEqual(AU.current_edition(box / 'VectorDrive-ABC-1.2.3-portable' / 'VectorDrive'), 'ABC')
        self.assertEqual(AU.current_edition(box / 'VectorDrive-1.2.3' / 'VectorDrive'), '')
        self.assertEqual(AU.current_edition(None, 'vectordrive-abc-latest.json'), 'abc')
        self.assertEqual(AU.current_edition(None, 'vectordrive-latest.json'), '')
        d = make_version(box, '1.0.0', 'XYZ')
        self.assertEqual(AU.current_edition(d / 'VectorDrive'), 'XYZ')       # la marque du dossier de version

    def test_install_copies_unzips_marks(self):
        AU, src, root = self.AU, tmp(), tmp() / 'VD'
        z = make_zip(src, '1.10.0')
        got = AU.install(z, root)
        self.assertEqual(got.folder, root / 'VectorDrive-1.10.0')
        self.assertEqual(got.exe, root / 'VectorDrive-1.10.0' / 'VectorDrive' / 'VectorDrive.exe')
        self.assertTrue(got.exe.is_file())
        self.assertFalse(got.reused)
        kept = root / 'zips' / z.name
        self.assertEqual(kept.stat().st_size, z.stat().st_size)              # l'archive copiée, entière
        mark = json.loads((got.folder / AU.MARK).read_text(encoding='utf-8'))
        self.assertEqual((mark['version'], mark['edition'], mark['source']), ('1.10.0', '', str(z)))
        self.assertNotIn('etat', mark)                                       # plus « en installation »
        self.assertEqual(sorted(p.name for p in root.iterdir()), ['VectorDrive-1.10.0', 'zips'])   # rien de provisoire
        self.assertEqual(AU.exe_of(got.folder), got.exe)
        ed = AU.install(make_zip(src, '2.0.0', 'ABC'), root)
        self.assertEqual((ed.folder.name, ed.edition), ('VectorDrive-ABC-2.0.0', 'ABC'))

    def test_install_reuses_complete_version(self):
        AU, src, root = self.AU, tmp(), tmp()
        z = make_zip(src, '1.10.0')
        first = AU.install(z, root)
        (first.exe.parent / 'VectorDrive.ini').write_text('[options]\nlangue=fr\n', encoding='utf-8')
        again = AU.install(z, root)
        self.assertTrue(again.reused)
        self.assertEqual(again.exe, first.exe)
        self.assertIn('langue=fr', (again.exe.parent / 'VectorDrive.ini').read_text(encoding='utf-8'))   # pas refaite
        broken = root / 'VectorDrive-3.0.0'                                  # là, sans exécutable : jamais écrasé
        broken.mkdir()
        (broken / 'mes notes.txt').write_text('à moi', encoding='utf-8')
        with self.assertRaises(AU.AppUpdateError):
            AU.install(make_zip(src, '3.0.0'), root)
        self.assertEqual((broken / 'mes notes.txt').read_text(encoding='utf-8'), 'à moi')

    def test_install_refuses_trapped_archive(self):
        AU, src, box = self.AU, tmp(), tmp()
        root = box / 'VD'
        traps = (({'../piege.txt': 'x'}, {}), ({'VectorDrive/../../piege.txt': 'x'}, {}), ({'/piege.txt': 'x'}, {}),
                 ({'C:/piege.txt': 'x'}, {}), ({}, {'exe': False}))           # « .. », absolu, lecteur, sans exécutable
        for i, (bad, kw) in enumerate(traps):
            with self.subTest(bad=bad, kw=kw):
                z = make_zip(src, f'1.0.{i}', extra=bad, **kw)
                with self.assertRaises(AU.AppUpdateError):
                    AU.install(z, root)
                self.assertFalse((root / f'VectorDrive-1.0.{i}').exists())   # rien d'installé
                self.assertEqual([p.name for p in root.iterdir() if p.name != 'zips'], [])   # rien de provisoire
        self.assertEqual([p.name for p in box.iterdir()], ['VD'])            # rien hors du dossier VD
        with self.assertRaises(AU.AppUpdateError):
            (src / 'VectorDrive-5.0.0-portable.zip').write_bytes(b'pas une archive')
            AU.install(src / 'VectorDrive-5.0.0-portable.zip', root)

    def test_carry_settings_copies_ini_and_data(self):
        AU, box = self.AU, tmp()
        old, new = box / 'ancienne' / 'VectorDrive', box / 'nouvelle' / 'VectorDrive'
        for d in (old / 'donnees' / 'outils', old / 'donnees' / 'recuperation', old / 'donnees' / 'session',
                  old / 'bibliotheque', new / 'donnees'):
            d.mkdir(parents=True)
        (old / 'VectorDrive.ini').write_text('[options]\ndecimales=5\n', encoding='utf-8')
        (old / 'donnees' / 'outils' / 'tools.json').write_text('[1]', encoding='utf-8')
        (old / 'donnees' / 'recuperation' / 'r.vdz').write_text('r', encoding='utf-8')
        (old / 'donnees' / 'session' / 'session.lock').write_text('verrou', encoding='utf-8')
        (old / 'donnees' / 'session' / 'onglets.json').write_text('{}', encoding='utf-8')
        (old / 'donnees' / 'garde.txt').write_text('ancien', encoding='utf-8')
        (old / 'bibliotheque' / 'forme.vdz').write_text('f', encoding='utf-8')
        (new / 'VectorDrive.ini').write_text(EMPTY_INI, encoding='utf-8')    # celui de l'archive : vide
        (new / 'donnees' / 'garde.txt').write_text('neuf', encoding='utf-8')
        stamp(old / 'donnees' / 'garde.txt', 1_600_000_000)                  # l'ancien est plus vieux
        got = AU.carry_settings(old, new)
        self.assertIn('decimales=5', (new / 'VectorDrive.ini').read_text(encoding='utf-8'))
        self.assertEqual((new / 'donnees' / 'outils' / 'tools.json').read_text(encoding='utf-8'), '[1]')
        self.assertFalse((new / 'donnees' / 'session').exists())             # 26/11 : les onglets passent à part
        self.assertTrue((new / 'bibliotheque' / 'forme.vdz').is_file())
        self.assertFalse((new / 'donnees' / 'recuperation').exists())        # la récupération reste à l'ancienne
        self.assertFalse((new / 'donnees' / 'session' / 'session.lock').exists())
        self.assertEqual((new / 'donnees' / 'garde.txt').read_text(encoding='utf-8'), 'neuf')   # plus récent : gardé…
        self.assertEqual((got.copied, got.failed), (3, []))                # (la session : plus copiée)
        self.assertEqual(got.skipped, [str(old / 'donnees' / 'garde.txt')])  # … mais pas repris : dit
        self.assertEqual(sorted(f[0] for f in got.files), ['VectorDrive.ini', 'bibliotheque/forme.vdz',
                                                           'donnees/outils/tools.json'])
        self.assertEqual((old / 'donnees' / 'garde.txt').read_text(encoding='utf-8'), 'ancien')   # rien de changé
        self.assertEqual([p for p in new.rglob('*') if p.name.endswith(AU.PART)], [])   # aucune copie provisoire
        again = AU.carry_settings(old, new)                                  # tout y est déjà, à l'identique
        self.assertEqual(again.copied, 0)
        self.assertEqual(sorted(f[0] for f in again.files), sorted(f[0] for f in got.files))

    def test_carry_settings_library_adds_never_overwrites(self):
        """La bibliothèque interne (à côté de l'exécutable) : les fichiers absents de la nouvelle version sont
        copiés, jamais un fichier qu'elle fournit n'est écrasé — même plus ancien que celui de l'utilisateur ; un
        fichier différent gardé ainsi n'est pas repris, et c'est dit."""
        AU, box = self.AU, tmp()
        old, new = box / 'ancienne' / 'VectorDrive', box / 'nouvelle' / 'VectorDrive'
        for d in (old / 'bibliotheque' / 'Logos BAT', old / 'bibliotheque' / 'Favoris',
                  old / 'bibliotheque' / 'Symboles', new / 'bibliotheque' / 'Symboles'):
            d.mkdir(parents=True)
        (old / 'VectorDrive.ini').write_text('[options]\ndecimales=5\n', encoding='utf-8')
        (new / 'VectorDrive.ini').write_text(EMPTY_INI, encoding='utf-8')
        (old / 'bibliotheque' / 'Logos BAT' / 'client.svg').write_text('logo', encoding='utf-8')
        (old / 'bibliotheque' / 'Favoris' / 'etoile.vdz').write_text('favori', encoding='utf-8')
        (old / 'bibliotheque' / 'Symboles' / 'fleche.vdz').write_text('retouchée', encoding='utf-8')
        (old / 'bibliotheque' / 'Symboles' / 'a moi.vdz').write_text('ajouté', encoding='utf-8')
        (new / 'bibliotheque' / 'Symboles' / 'fleche.vdz').write_text('fournie', encoding='utf-8')
        stamp(new / 'bibliotheque' / 'Symboles' / 'fleche.vdz', 1_600_000_000)   # plus ancienne
        got = AU.carry_settings(old, new)
        self.assertEqual(got.copied, 4)                                      # les réglages et trois fichiers absents
        self.assertEqual(got.skipped, [str(old / 'bibliotheque' / 'Symboles' / 'fleche.vdz')])
        lib = new / 'bibliotheque'
        self.assertEqual((lib / 'Logos BAT' / 'client.svg').read_text(encoding='utf-8'), 'logo')
        self.assertEqual((lib / 'Favoris' / 'etoile.vdz').read_text(encoding='utf-8'), 'favori')
        self.assertEqual((lib / 'Symboles' / 'a moi.vdz').read_text(encoding='utf-8'), 'ajouté')
        self.assertEqual((lib / 'Symboles' / 'fleche.vdz').read_text(encoding='utf-8'), 'fournie')   # jamais écrasée
        self.assertEqual((old / 'bibliotheque' / 'Symboles' / 'fleche.vdz').read_text(encoding='utf-8'), 'retouchée')
        self.assertEqual(AU.carry_settings(old, new).copied, 0)

    def test_carry_settings_nothing_without_portable(self):
        AU, box = self.AU, tmp()
        old, new = box / 'installee', box / 'nouvelle'
        (old / 'donnees').mkdir(parents=True)
        (old / 'donnees' / 'x.txt').write_text('x', encoding='utf-8')        # pas de VectorDrive.ini : pas portable
        new.mkdir()
        (new / 'VectorDrive.ini').write_text(EMPTY_INI, encoding='utf-8')
        self.assertEqual(AU.carry_settings(old, new).copied, 0)
        self.assertEqual(AU.carry_settings(None, new).copied, 0)
        self.assertEqual(sorted(p.name for p in new.iterdir()), ['VectorDrive.ini'])
        self.assertEqual((new / 'VectorDrive.ini').read_text(encoding='utf-8'), EMPTY_INI)
        self.assertTrue(AU.decline_settings(new))                            # « ne pas reprendre » : noté, une fois
        from PySide6.QtCore import QSettings
        self.assertEqual(QSettings(str(new / 'VectorDrive.ini'), QSettings.Format.IniFormat).value('portable/reprise'),
                         'non')
        self.assertFalse(AU.decline_settings(new))

    def shortcuts(self):
        box = tmp()
        dirs = {'demarrer': box / 'demarrer', 'bureau': box / 'bureau', 'barre': box / 'barre'}
        for d in dirs.values():
            d.mkdir()
        vd = box / 'VD'
        old = box / 'vieux' / 'VectorDrive.exe'
        new = vd / 'VectorDrive-1.3.0' / 'VectorDrive' / 'VectorDrive.exe'
        return box, dirs, vd, old, new

    def test_retarget_shortcuts_right_links_right_target(self):
        AU = self.AU
        box, dirs, vd, old, new = self.shortcuts()
        older = vd / 'VectorDrive-1.1.0' / 'VectorDrive' / 'VectorDrive.exe'
        a = make_link(dirs['demarrer'] / 'VectorDrive.lnk', old)
        b = make_link(dirs['barre'] / 'VectorDrive.lnk', old, wide=False)
        c = make_link(dirs['demarrer'] / 'Gravure' / 'Ancienne.lnk', older)  # une version du dossier VD
        d = make_link(dirs['bureau'] / 'Autre VectorDrive.lnk', 'D:\\ailleurs\\VectorDrive.exe')   # pas à nous
        e = make_link(dirs['bureau'] / 'Bloc-notes.lnk', 'C:\\Windows\\notepad.exe')
        f = make_link(dirs['bureau'] / 'Deja.lnk', new)                      # déjà sur la nouvelle
        shell = Shell({a: old, b: str(old).upper(), c: older, d: 'D:\\ailleurs\\VectorDrive.exe',
                       e: 'C:\\Windows\\notepad.exe', f: new})
        got = AU.retarget_shortcuts(old, new, shell, dirs=dirs, versions_dir=vd)
        self.assertNotIn(str(e), shell.asked('lire'))                        # ne nomme pas VectorDrive.exe : pas lu
        self.assertEqual(sorted(shell.asked('lire')), sorted(map(str, (a, b, c, d, f))))
        wrote = shell.asked('ecrire')
        self.assertEqual(sorted(w['lien'] for w in wrote), sorted(map(str, (a, b, c))))
        for w in wrote:
            self.assertEqual((w['cible'], w['dossier']), (str(new), str(new.parent)))
        self.assertEqual(sorted(got['changes']), sorted((a, b, c)))
        self.assertIsNone(got['cree'])                                       # le menu Démarrer en avait un
        self.assertEqual(got['erreurs'], [])
        self.assertEqual(shell.targets[str(d)], 'D:\\ailleurs\\VectorDrive.exe')

    def test_retarget_shortcuts_creates_start_menu_entry(self):
        AU = self.AU
        _box, dirs, vd, old, new = self.shortcuts()
        b = make_link(dirs['bureau'] / 'VectorDrive.lnk', old)
        shell = Shell({b: old})
        got = AU.retarget_shortcuts(old, new, shell, dirs=dirs, versions_dir=vd)
        made = dirs['demarrer'] / 'VectorDrive.lnk'
        self.assertEqual(got['cree'], made)
        self.assertEqual(got['changes'], [b])
        self.assertEqual(shell.targets[str(made)], str(new))
        self.assertEqual(AU.retarget_shortcuts(old, new, Shell(), dirs=dirs, versions_dir=vd, create=False)['cree'],
                         None)

    def test_retarget_shortcuts_error_is_not_fatal(self):
        AU = self.AU
        _box, dirs, vd, old, new = self.shortcuts()
        a = make_link(dirs['demarrer'] / 'VectorDrive.lnk', old)
        b = make_link(dirs['barre'] / 'VectorDrive.lnk', old)
        got = AU.retarget_shortcuts(old, new, Shell({a: old}, fail='PowerShell absent'), dirs=dirs, versions_dir=vd)
        self.assertEqual((got['changes'], got['cree']), ([], None))
        self.assertIn('PowerShell absent', got['erreurs'][0])
        shell = Shell({a: old, b: old}, errors={str(b): 'accès refusé'})     # un seul raccourci en échec
        got = AU.retarget_shortcuts(old, new, shell, dirs=dirs, versions_dir=vd)
        self.assertEqual(got['changes'], [a])
        self.assertEqual(len(got['erreurs']), 1)
        self.assertIn('accès refusé', got['erreurs'][0])

    def test_powershell_launcher_and_channel_never_run_in_tests(self):
        AU = self.AU
        script = AU.ps_script({'action': 'lire', 'liens': ['C:\\Menu Démarrer\\gravé à l’été.lnk']})
        self.assertIn('WScript.Shell', script)
        self.assertTrue(script.isascii())                                    # la demande en base64 : aucun accent
        self.assertNotIn('grav', script)
        self.assertTrue(AU.powershell_exe().lower().endswith('system32\\windowspowershell\\v1.0\\powershell.exe')
                        or os.sep != '\\')
        with self.assertRaises(AU.AppUpdateError):                           # dossier d'essais : jamais lancé
            AU.run_powershell({'action': 'lire', 'liens': []})
        with self.assertRaises(AU.AppUpdateError):                           # … ni le vrai canal interrogé
            AU.answers()
        exe = tmp() / 'VectorDrive.exe'
        exe.write_bytes(b'MZ')
        with self.assertRaises(AU.AppUpdateError):
            AU.launch(exe)
        seen = []
        self.assertTrue(AU.launch(exe, popen=lambda args, **kw: seen.append((args, kw['cwd']))))
        self.assertEqual(seen, [([str(exe)], str(exe.parent))])
        with self.assertRaises(AU.AppUpdateError):
            AU.launch(exe.parent / 'absent.exe', popen=lambda *a, **k: seen.append('non'))
        self.assertEqual(len(seen), 1)

    def test_folders_default_to_documents_and_share(self):
        AU = self.AU
        base = pathlib.Path(os.environ['VECTORDRIVE_APP_UPDATE'])
        self.assertEqual(AU.versions_dir(None), base / 'versions')           # essais : jamais Documents
        self.assertEqual(AU.source_dir(None), base / 'source')               # … ni P:
        self.assertEqual(set(AU.shortcut_dirs()), {'demarrer', 'bureau', 'barre'})
        for d in AU.shortcut_dirs().values():
            self.assertEqual(d.parent, base / 'raccourcis')                  # … ni le menu Démarrer
        from PySide6.QtCore import QSettings
        st = QSettings(str(tmp() / 'r.ini'), QSettings.Format.IniFormat)
        st.setValue('maj/dossier_vd', 'D:/VD')
        st.setValue('maj/dossier_source', 'D:/depot')
        self.assertEqual(AU.versions_dir(st), pathlib.Path('D:/VD'))
        self.assertEqual(AU.source_dir(st), pathlib.Path('D:/depot'))
        st.setValue('maj/dossier_source', 'P:\\Partage\\LOGICIEL')           # retenu tel quel par F10 : pas en essai
        self.assertEqual(AU.source_dir(st), base / 'source')
        with mock.patch.dict(os.environ):                                    # hors essais (rien n'est lu ni écrit)
            del os.environ['VECTORDRIVE_APP_UPDATE']
            self.assertEqual(AU.source_dir(None), pathlib.Path('P:\\Partage\\LOGICIEL'))
            self.assertEqual(AU.versions_dir(None).name, 'VectorDrive')
            from PySide6.QtCore import QStandardPaths
            docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
            self.assertEqual(AU.versions_dir(None).parent, pathlib.Path(docs))


class Window(unittest.TestCase):
    """`MainWindow.app_update`, la fenêtre de confirmation et F10 › Mises à jour."""

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        if not cls.w.docs:
            cls.w.new_document()

    @classmethod
    def tearDownClass(cls):
        w = cls.w
        for t in w.docs:
            t.modified = False
        w.modified = False
        w.close()
        w.deleteLater()
        app.processEvents()

    def setUp(self):
        self.AU = au()
        self.assertTrue(hasattr(self.w, 'app_update'), BEFORE)
        for name in ('run_powershell', 'launch', 'answers'):     # ni le vrai PowerShell, ni le vrai lanceur, ni le
            p = mock.patch.object(self.AU, name, side_effect=AssertionError('processus lancé dans un essai'))
            p.start()                                    # vrai canal (la fenêtre des options, elle, interroge le
            self.addCleanup(p.stop)                      # poste : `subprocess` reste)
        self.box = tmp()
        self.src, self.vd = self.box / 'partage', self.box / 'VD'
        self.src.mkdir()
        self.dirs = {'demarrer': self.box / 'demarrer', 'bureau': self.box / 'bureau', 'barre': self.box / 'barre'}
        for d in self.dirs.values():
            d.mkdir()
        self.launched, self.quits = [], []
        self.addCleanup(lambda: setattr(self.w, '_closing', False))

    def params(self, **kw):
        base = {'source': self.src, 'dossier': self.vd, 'ok': True, 'runner': Shell(),
                'dossiers_raccourcis': self.dirs, 'lanceur': lambda exe: self.launched.append(exe) or True,
                'sonde': lambda: bool(self.launched), 'delai': 0.3,
                'quitter': lambda: self.quits.append(1) or setattr(self.w, '_closing', True)}
        base.update(kw)
        return base

    def test_end_to_end_installs_launches_quits(self):
        w = self.w
        make_zip(self.src, '998.0.0')
        make_zip(self.src / 'vectordrive', '999.1.0')
        for v in ('0.0.1', '0.0.2'):
            make_version(self.vd, v)
        make_version(self.vd, '0.0.3', mark=False)
        old = self.box / 'en cours' / 'VectorDrive'                          # l'application en cours, portable
        (old / 'donnees' / 'outils').mkdir(parents=True)
        (old / 'VectorDrive.ini').write_text('[options]\ndecimales=5\n', encoding='utf-8')
        (old / 'donnees' / 'outils' / 'tools.json').write_text('[1]', encoding='utf-8')
        (old / 'bibliotheque' / 'Logos BAT').mkdir(parents=True)             # sa bibliothèque, à côté de l'exécutable
        (old / 'bibliotheque' / 'Logos BAT' / 'client.svg').write_text('logo', encoding='utf-8')
        pinned = make_link(self.dirs['barre'] / 'VectorDrive.lnk', old / 'VectorDrive.exe')
        shell = Shell({pinned: old / 'VectorDrive.exe'})
        with mock.patch.dict(os.environ, {'VECTORDRIVE_PORTABLE_DIR': str(old)}):
            res = w.app_update(self.params(runner=shell), exec_dialog=False)
        exe = self.vd / 'VectorDrive-999.1.0' / 'VectorDrive' / 'VectorDrive.exe'
        self.assertEqual((res['etat'], res['demarrage']), ('lance', 'ok'))
        self.assertTrue(exe.is_file())                                       # installée…
        self.assertTrue((self.vd / 'zips' / 'VectorDrive-999.1.0-portable.zip').is_file())
        self.assertEqual(self.launched, [exe])                               # … lancée (lanceur factice)…
        self.assertEqual(self.quits, [1])                                    # … et la fenêtre demande à quitter
        self.assertIn('decimales=5', (exe.parent / 'VectorDrive.ini').read_text(encoding='utf-8'))   # réglages repris
        self.assertEqual((exe.parent / 'donnees' / 'outils' / 'tools.json').read_text(encoding='utf-8'), '[1]')
        self.assertEqual((exe.parent / 'bibliotheque' / 'Logos BAT' / 'client.svg').read_text(encoding='utf-8'),
                         'logo')                                             # … et la bibliothèque
        self.assertEqual(sorted(p.name for p in self.vd.iterdir()),          # toutes les anciennes restent (26/11)
                         ['VectorDrive-0.0.1', 'VectorDrive-0.0.2', 'VectorDrive-0.0.3', 'VectorDrive-999.1.0', 'zips'])
        self.assertEqual(sorted(p.name for p in (self.vd / 'zips').iterdir()),
                         ['VectorDrive-0.0.1-portable.zip', 'VectorDrive-0.0.2-portable.zip',
                          'VectorDrive-0.0.3-portable.zip', 'VectorDrive-999.1.0-portable.zip'])
        self.assertNotIn('supprimes', res)
        self.assertEqual(shell.targets[str(pinned)], str(exe))               # le raccourci épinglé suit
        self.assertEqual(res['raccourcis']['cree'], self.dirs['demarrer'] / 'VectorDrive.lnk')
        self.assertTrue((old / 'VectorDrive.ini').is_file())                 # l'ancienne, hors du dossier VD : intacte
        self.assertFalse((old / OLD_PROOF).exists())                         # … et rien n'y est écrit
        base = pathlib.Path(os.environ['VECTORDRIVE_APP_UPDATE'])
        self.assertFalse(base.exists())                                      # rien dans les dossiers d'office

    def test_nothing_newer_says_so_and_does_nothing(self):
        w = self.w
        make_zip(self.src, '0.0.1')
        res = w.app_update(self.params(), exec_dialog=False)
        self.assertEqual(res['etat'], 'a_jour')
        self.assertIn('à jour', w.statusBar().currentMessage())
        self.assertEqual((self.launched, self.quits), ([], []))
        self.assertFalse(self.vd.exists())                                   # rien de copié, rien de créé
        with mock.patch.object(QMessageBox, 'information') as box:           # à l'écran : une boîte le dit
            self.assertEqual(w.app_update(self.params())['etat'], 'a_jour')
        self.assertIn('0.0.1', box.call_args[0][2])
        empty = self.box / 'vide'
        empty.mkdir()
        self.assertEqual(w.app_update(self.params(source=empty), exec_dialog=False)['etat'], 'rien')
        res = w.app_update(self.params(source=self.box / 'absent'), exec_dialog=False)
        self.assertEqual(res['etat'], 'erreur')                              # dossier injoignable : dit, sans blocage
        self.assertIn('absent', res['message'])
        self.assertFalse(self.vd.exists())

    def test_refusal_and_failed_launch_keep_the_window(self):
        w = self.w
        make_zip(self.src, '999.2.0')
        res = w.app_update(self.params(ok=False), exec_dialog=False)         # pas d'accord : rien
        self.assertEqual(res['etat'], 'annule')
        self.assertFalse(self.vd.exists())
        self.assertEqual(w.app_update({'source': self.src, 'dossier': self.vd, 'sonde': lambda: False},
                                      exec_dialog=False)['etat'], 'annule')
        self.assertFalse(self.vd.exists())                                   # sans « ok » : jamais d'installation
        shell = Shell()
        res = w.app_update(self.params(lanceur=lambda exe: False, raccourcis=False, runner=shell), exec_dialog=False)
        self.assertEqual(res['etat'], 'installe')                            # installée, pas lancée : on ne quitte pas
        self.assertTrue(res['exe'].is_file())
        self.assertEqual(self.quits, [])
        self.assertEqual(shell.calls, [])                                    # raccourcis décochés : rien de demandé

        def boom(_exe):
            raise OSError('lancement refusé')
        res = w.app_update(self.params(lanceur=boom), exec_dialog=False)     # déjà là : reprise ; erreur dite
        self.assertEqual(res['etat'], 'installe')
        self.assertIn('lancement refusé', w.statusBar().currentMessage())
        self.assertEqual(self.quits, [])

    def test_versions_folder_refused_when_unsafe(self):
        """Dossier VD = racine d'un lecteur, dossier de l'utilisateur ou dossier où chercher : refusé, rien n'est
        fait."""
        w, AU = self.w, self.AU
        make_zip(self.src, '999.2.5')
        for bad in (pathlib.Path(self.box.anchor), pathlib.Path.home(), self.src):
            with self.subTest(bad=bad):
                self.assertTrue(AU.unsafe_root(bad, self.src))
                res = w.app_update(self.params(dossier=bad), exec_dialog=False)
                self.assertEqual(res['etat'], 'erreur')
                self.assertIn('Dossier VD refusé', res['message'])
        with self.assertRaises(AU.AppUpdateError):
            AU.install(self.src / 'VectorDrive-999.2.5-portable.zip', pathlib.Path.home())
        self.assertEqual(AU.unsafe_root(self.vd, self.src), '')
        self.assertEqual(self.launched, [])
        self.assertEqual(sorted(p.name for p in self.src.iterdir()), ['VectorDrive-999.2.5-portable.zip'])

    def test_confirmation_window_says_everything(self):
        from vectordrive import __version__
        from vectordrive.ui.app_update_dialog import AppUpdateDialog
        AU = self.AU
        found = AU.Found(self.src / 'VectorDrive-999.0.0-portable.zip', '999.0.0', '')
        dest = self.vd / 'VectorDrive-999.0.0'
        dlg = AppUpdateDialog(self.w, found, dest, zips=self.vd / 'zips', portable=True)
        self.addCleanup(dlg.deleteLater)
        self.assertIn('999.0.0', dlg.headline.text())
        self.assertIn(__version__, dlg.headline.text())
        self.assertIn(str(found.path), dlg.origin.text())
        self.assertIn(str(dest), dlg.target.text())
        self.assertTrue(dlg.carry.isEnabled() and dlg.carry.isChecked())     # d'office : réglages repris
        self.assertEqual(dlg.carry.text(), 'Reprendre mes réglages, mes données et ma bibliothèque')
        self.assertTrue(dlg.shortcuts.isChecked())
        self.assertIn('Aucune ancienne version n’est supprimée', dlg.previous.text())    # 26/11 : toutes restent
        self.assertIn('chacune dans son dossier', dlg.previous.text())
        self.assertIn('Tous les onglets ouverts', dlg.tabs.text())           # 26/11 : tous les onglets suivent
        self.assertFalse(hasattr(dlg, 'doomed'))
        self.assertIn('fenêtre est prête', dlg.closing.text())
        self.assertEqual(dlg.values(), {'reprendre': True, 'raccourcis': True})
        dlg.carry.setChecked(False)
        dlg.shortcuts.setChecked(False)
        self.assertEqual(dlg.values(), {'reprendre': False, 'raccourcis': False})
        fixed = AppUpdateDialog(self.w, found, dest, portable=False, shortcuts=False)
        self.addCleanup(fixed.deleteLater)
        self.assertFalse(fixed.carry.isEnabled())                            # pas portable : grisée, et dit pourquoi
        self.assertFalse(fixed.carry.isChecked())
        self.assertIsNotNone(fixed.carry_note)
        self.assertIn('registre', fixed.carry_note.text())
        self.assertFalse(fixed.values()['reprendre'])
        self.assertFalse(fixed.shortcuts.isChecked())

    def test_not_portable_copies_no_settings(self):
        w = self.w
        make_zip(self.src, '999.3.0')
        res = w.app_update(self.params(reprendre=True), exec_dialog=False)   # depuis les sources : pas portable
        self.assertEqual(res['etat'], 'lance')
        from PySide6.QtCore import QSettings
        st = QSettings(str(res['exe'].parent / 'VectorDrive.ini'), QSettings.Format.IniFormat)
        self.assertEqual(sorted(st.allKeys()), ['portable/reprise'])         # rien de copié…
        self.assertEqual(st.value('portable/reprise'), 'non')                # … noté : ne pas le proposer
        self.assertEqual([p.name for p in (res['exe'].parent / 'donnees').iterdir()], ['session_maj'])   # onglets
        self.assertEqual(len(passed(res['exe'].parent)), 1)

    def test_options_and_command(self):
        from vectordrive.ui.options import BY_KEY, default_of, value
        w = self.w
        self.assertEqual(default_of(BY_KEY['maj/dossier_vd']), '')           # vide : Documents/VectorDrive
        self.assertEqual(default_of(BY_KEY['maj/dossier_source']), 'P:\\Partage\\LOGICIEL')
        self.assertEqual(BY_KEY['maj/dossier_vd'].kind, 'folder')
        self.assertEqual(BY_KEY['maj/dossier_source'].kind, 'folder')
        self.assertNotIn('maj/versions_gardees', BY_KEY)                     # 26/11 : plus d'élagage, plus de réglage
        self.assertIs(default_of(BY_KEY['maj/raccourcis']), True)
        self.assertTrue(value(w.settings, 'maj/raccourcis'))
        self.assertIn('app_update', w.A)                                     # dans la recherche de commandes
        self.assertEqual(w.A['app_update'].text(), 'Mettre à jour l’application…')
        dlg = w.options_dialog(exec_dialog=False, page='Mises à jour')
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.app_update_button.text(), 'Mettre à jour l’application…')
        self.assertEqual(dlg.widgets['maj/dossier_vd'].edit.placeholderText(), str(self.AU.default_versions_dir()))
        dlg.widgets['maj/source'].edit.setText(str(self.box / 'manifeste'))
        dlg.widgets['maj/dossier_vd'].edit.setText(str(self.vd))
        dlg.widgets['maj/dossier_source'].edit.setText(str(self.src))
        calls = []
        keys = ('maj/source', 'maj/dossier_source', 'maj/dossier_vd', 'maj/raccourcis')
        try:
            dlg.run_app_update(types.SimpleNamespace(update_application=lambda: calls.append(1)))
            self.assertEqual(calls, [1])                                     # le bouton lance la commande…
            self.assertEqual(self.AU.versions_dir(w.settings), self.vd)      # … avec les réglages de la fenêtre
            self.assertEqual(self.AU.source_dir(w.settings), self.src)
            self.assertEqual(w.settings.value('maj/source'), str(self.box / 'manifeste'))
        finally:
            for k in keys:
                w.settings.remove(k)


class Safety(unittest.TestCase):
    """Relectures de sûreté : installation et reprise sûres ; depuis le 26/11, aucune ancienne version n'est
    supprimée (l'élagage et sa preuve de reprise sont retirés)."""

    def setUp(self):
        self.AU = au()
        self.root = tmp() / 'VD'
        self.root.mkdir()
        for v in ('1.0.0', '1.1.0', '1.2.0', '1.3.0'):
            make_version(self.root, v)
        self.new = self.root / 'VectorDrive-1.3.0'
        self.new_app = self.new / 'VectorDrive'

    def test_minor_library_file_shipped_then_modified_is_the_users(self):
        AU, root = self.AU, self.root
        for v in ('1.0.0', '1.1.0'):                                         # archives qui livrent un symbole
            shutil.rmtree(root / f'VectorDrive-{v}')
            (root / 'zips' / f'VectorDrive-{v}-portable.zip').unlink()
            make_version(root, v, shipped={'bibliotheque/Symboles/fleche.vdz': 'livrée'})
        old = root / 'VectorDrive-1.1.0' / 'VectorDrive'                     # reprise : le livré ne compte pas
        (old / 'VectorDrive.ini').write_text('[options]\ndecimales=5\n', encoding='utf-8')
        (self.new_app / 'bibliotheque' / 'Symboles').mkdir(parents=True)
        (self.new_app / 'bibliotheque' / 'Symboles' / 'fleche.vdz').write_text('nouvelle', encoding='utf-8')
        got = AU.carry_settings(old, self.new_app)
        self.assertEqual((got.failed, got.skipped), ([], []))
        (self.new_app / 'bibliotheque' / 'Symboles' / 'fleche.vdz').write_text('autre', encoding='utf-8')
        user = root / 'VectorDrive-1.1.0' / 'VectorDrive' / 'bibliotheque' / 'Symboles' / 'fleche.vdz'
        user.write_text('à moi', encoding='utf-8')                           # retouché par l'utilisateur : le sien
        self.assertEqual(AU.carry_settings(old, self.new_app).skipped, [str(user)])

    def test_minor_archive_cannot_bring_mark(self):
        AU, src = self.AU, tmp()
        fake = json.dumps({'version': '9.9.9', 'edition': ''})
        z = make_zip(src, '5.0.0', extra={'.VD_VERSION.json': fake, 'VectorDrive/.VD_VERSION.json': fake})
        got = AU.install(z, self.root)
        self.assertEqual(sorted(p.name.lower() for p in got.exe.parent.iterdir()),
                         ['_internal', 'vectordrive.exe', 'vectordrive.ini'])
        self.assertEqual(AU.read_mark(got.folder)['source'], str(z))         # la marque : la nôtre

    def test_minor_staging_folder_needs_the_mark(self):
        AU, src = self.AU, tmp()
        z = make_zip(src, '6.0.0')
        stage = self.root / (AU.STAGING + 'VectorDrive-6.0.0')
        stage.mkdir()
        (stage / 'à moi.txt').write_text('x', encoding='utf-8')              # sans marque : jamais effacé
        with self.assertRaises(AU.AppUpdateError):
            AU.install(z, self.root)
        self.assertTrue((stage / 'à moi.txt').is_file())
        (stage / AU.MARK).write_text(json.dumps({'version': '6.0.0', 'edition': '', 'etat': 'installation'}),
                                     encoding='utf-8')                       # reste d'une installation à nous : refaite
        got = AU.install(z, self.root)
        self.assertFalse(stage.exists())
        self.assertTrue(got.exe.is_file())

    def test_minor_carry_writes_through_a_temporary_file(self):
        AU = self.AU
        old = use(self.root / 'VectorDrive-1.0.0', **{'donnees/outils/tools.json': '[1, 2, 3]'})
        dst = self.new_app / 'donnees' / 'outils' / 'tools.json'
        dst.parent.mkdir(parents=True)
        dst.write_text('[0]', encoding='utf-8')
        stamp(dst, 1_600_000_000)                                            # plus ancien : à remplacer
        real = shutil.copy2

        def half(src, to, *a, **kw):
            if pathlib.Path(src).name == 'tools.json' and not str(to).endswith(AU.BACKUP):
                pathlib.Path(to).write_text('[1, ', encoding='utf-8')        # coupée au milieu
                raise OSError(28, 'Espace insuffisant sur le disque')
            return real(src, to, *a, **kw)
        with mock.patch.object(shutil, 'copy2', side_effect=half):
            got = AU.carry_settings(old, self.new_app)
        self.assertEqual(dst.read_text(encoding='utf-8'), '[0]')             # jamais un fichier tronqué à sa place
        self.assertEqual([p.name for p in dst.parent.iterdir() if p.name.endswith(AU.PART)], [])
        self.assertEqual(len(got.failed), 1)
        self.assertIn('Espace insuffisant', got.failed[0])

    def test_b1_failed_copy_is_reported(self):
        AU, root = self.AU, self.root
        old = use(root / 'VectorDrive-1.0.0', **{'donnees/outils/tools.json': '[1]', 'donnees/modeles/m.json': '{}'})
        real = shutil.copy2

        def copy(src, dst, *a, **kw):
            if pathlib.Path(src).name == 'tools.json':
                raise OSError(28, 'Espace insuffisant sur le disque')
            return real(src, dst, *a, **kw)
        with mock.patch.object(shutil, 'copy2', side_effect=copy):
            got = AU.carry_settings(old, self.new_app)
        self.assertEqual(got.copied, 2)                                      # les réglages et l'autre fichier
        self.assertEqual(len(got.failed), 1)                                 # l'échec est nommé, pas avalé
        self.assertIn('tools.json', got.failed[0])
        self.assertIn('Espace insuffisant', got.failed[0])
        self.assertEqual((old / 'donnees' / 'outils' / 'tools.json').read_text(encoding='utf-8'), '[1]')

    def test_skipped_different_file_is_reported(self):
        AU = self.AU
        old = use(self.root / 'VectorDrive-1.0.0', **{'donnees/outils/tools.json': '[1]',
                                                       'donnees/modeles/m.json': '{}'})
        mine = self.new_app / 'donnees' / 'outils' / 'tools.json'           # la nouvelle a déjà le sien, plus récent
        mine.parent.mkdir(parents=True)
        mine.write_text('[9]', encoding='utf-8')
        same = self.new_app / 'donnees' / 'modeles' / 'm.json'              # … et un autre, identique
        same.parent.mkdir(parents=True)
        same.write_text('{}', encoding='utf-8')
        stamp(old / 'donnees' / 'outils' / 'tools.json', 1_600_000_000)
        stamp(old / 'donnees' / 'modeles' / 'm.json', 1_600_000_000)
        got = AU.carry_settings(old, self.new_app)
        self.assertEqual(mine.read_text(encoding='utf-8'), '[9]')            # gardé…
        self.assertEqual(got.skipped, [str(old / 'donnees' / 'outils' / 'tools.json')])   # … mais pas repris
        self.assertIn('donnees/modeles/m.json', [f[0] for f in got.files])   # identique : repris

    def test_third_copy_of_a_version_folder_is_never_taken(self):
        """Troisième relecture, mineur 3 : un dossier de version copié à l'Explorateur (« - Copie ») ou renommé
        garde la marque de l'original, pas son nom : jamais repris par `install`."""
        AU, root = self.AU, self.root
        copy = root / 'VectorDrive-1.0.0 - Copie'
        shutil.copytree(root / 'VectorDrive-1.0.0', copy)
        other = root / 'VectorDrive-1.2.9'
        shutil.copytree(root / 'VectorDrive-1.1.0', other)                   # renommé : sa marque dit 1.1.0
        self.assertFalse(AU.named_as_marked(copy, AU.read_mark(copy)))
        self.assertFalse(AU.named_as_marked(other, AU.read_mark(other)))
        self.assertTrue(AU.named_as_marked(root / 'VectorDrive-1.0.0', AU.read_mark(root / 'VectorDrive-1.0.0')))
        with self.assertRaises(AU.AppUpdateError):
            AU.install(make_zip(tmp(), '1.2.9'), root)                       # jamais prise pour la 1.2.9
        self.assertEqual(AU.already_there(other), (False, False))
        self.assertTrue((copy / 'VectorDrive' / 'VectorDrive.exe').is_file())
        self.assertTrue((other / 'VectorDrive' / 'VectorDrive.exe').is_file())

    def test_third_user_folders_refused_subfolder_accepted(self):
        """Troisième relecture, mineur 4 : Documents, Bureau, Téléchargements, racine de OneDrive (même redirigés)
        ne sont jamais le dossier VD lui-même ; un de leurs sous-dossiers, si."""
        from PySide6.QtCore import QStandardPaths as S
        AU, box = self.AU, tmp()
        docs, od = box / 'Documents redirigés', box / 'OneDrive - Entreprise'
        for d in (docs, od):
            d.mkdir()
        self.assertIn('Documents, Bureau', AU.unsafe_root(docs, special=[docs]))
        self.assertEqual(AU.unsafe_root(docs / 'VectorDrive', special=[docs]), '')
        with mock.patch.dict(os.environ, {'OneDriveCommercial': str(od)}):
            self.assertIn(od, AU.special_dirs())
            self.assertTrue(AU.unsafe_root(od))
            self.assertEqual(AU.unsafe_root(od / 'VectorDrive'), '')
            with self.assertRaises(AU.AppUpdateError):
                AU.install(make_zip(box, '9.0.0'), od)
        self.assertEqual(sorted(p.name for p in od.iterdir()), [])           # rien n'y est écrit
        for loc in (S.StandardLocation.DocumentsLocation, S.StandardLocation.DesktopLocation,
                    S.StandardLocation.DownloadLocation):
            where = S.writableLocation(loc)                                  # lu seulement
            if where:
                self.assertTrue(AU.unsafe_root(where), where)
        for name in ('Documents', 'Desktop', 'Downloads', 'OneDrive'):
            self.assertTrue(AU.unsafe_root(pathlib.Path.home() / name), name)

    def test_third_same_name_archive_reused_only_if_identical(self):
        """Troisième relecture, mineur 4 : une archive de même nom déjà dans `zips/` n'est reprise que si c'est la
        même (taille, archive lisible, mêmes entrées et CRC) ; sinon elle est mise de côté (relecture du 26/11 :
        jamais effacée), `….ancienne`, `….ancienne2`."""
        AU, root = self.AU, self.root
        src = make_zip(tmp(), '2.1.0', extra={'VectorDrive/x.txt': 'AAAA'})
        kept = root / 'zips' / src.name
        other = make_zip(tmp(), '2.1.0', extra={'VectorDrive/x.txt': 'BBBB'}).read_bytes()
        kept.write_bytes(other)
        self.assertEqual(kept.stat().st_size, src.stat().st_size)            # même taille, autre contenu
        inst = AU.install(src, root)
        self.assertEqual(kept.read_bytes(), src.read_bytes())
        self.assertEqual(kept.with_name(kept.name + '.ancienne').read_bytes(), other)    # gardée à côté
        self.assertEqual((inst.exe.parent / 'x.txt').read_text(encoding='utf-8'), 'AAAA')
        shutil.rmtree(inst.folder)
        kept.write_bytes(b'\0' * src.stat().st_size)                         # pas une archive : mise de côté aussi
        inst = AU.install(src, root)
        self.assertEqual(kept.read_bytes(), src.read_bytes())
        self.assertEqual(kept.with_name(kept.name + '.ancienne2').read_bytes(), b'\0' * src.stat().st_size)
        self.assertEqual(kept.with_name(kept.name + '.ancienne').read_bytes(), other)
        shutil.rmtree(inst.folder)
        stamp(kept, 1_000_000_000)                                           # la même : reprise telle quelle
        AU.install(src, root)
        self.assertEqual(kept.stat().st_mtime, 1_000_000_000)

    def test_c4_reuse_only_marked_and_backup_before_overwrite(self):
        AU, root, src = self.AU, self.root, tmp()
        plain = make_version(root, '2.0.0', mark=False)                      # complète mais pas à nous : jamais reprise
        with self.assertRaises(AU.AppUpdateError):
            AU.install(make_zip(src, '2.0.0'), root)
        self.assertTrue((plain / 'VectorDrive' / 'VectorDrive.exe').is_file())
        self.assertEqual(AU.already_there(plain), (False, False))
        self.assertEqual(AU.already_there(self.new), (True, False))
        new_app = use(self.new, **{'donnees/outils/tools.json': 'neuf'})     # déjà utilisée : ses réglages à elle
        self.assertEqual(AU.already_there(self.new), (True, True))
        old = use(root / 'VectorDrive-1.0.0', **{'donnees/outils/tools.json': 'ancien'})
        (old / 'VectorDrive.ini').write_text('[options]\ndecimales=2\n', encoding='utf-8')
        for f in (new_app / 'VectorDrive.ini', new_app / 'donnees' / 'outils' / 'tools.json'):
            stamp(f, 1_600_000_000)                                          # plus anciens : la reprise les remplace…
        got = AU.carry_settings(old, new_app)
        self.assertEqual((got.copied, got.failed, got.skipped), (2, [], []))
        self.assertIn('decimales=2', (new_app / 'VectorDrive.ini').read_text(encoding='utf-8'))
        self.assertIn('decimales=5', (new_app / ('VectorDrive.ini' + AU.BACKUP)).read_text(encoding='utf-8'))
        self.assertEqual((new_app / 'donnees' / 'outils' / ('tools.json' + AU.BACKUP)).read_text(encoding='utf-8'),
                         'neuf')                                             # … jamais sans copie de secours
        from vectordrive.ui.app_update_dialog import AppUpdateDialog
        found = AU.Found(src / 'VectorDrive-1.3.0-portable.zip', '1.3.0', '')
        dlg = AppUpdateDialog(None, found, self.new, portable=True, there=(True, True))
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(dlg.carry.isEnabled())
        self.assertFalse(dlg.carry.isChecked())                              # décochée d'office, et dit pourquoi
        self.assertIn('ses propres réglages', dlg.there_note.text())

    def test_damaged_archive_is_refused_and_its_copy_removed(self):
        import zlib
        AU, root, src = self.AU, self.root, tmp()
        z = make_zip(src, '4.0.0')
        for error in (zlib.error('flux abîmé'), EOFError('archive tronquée')):
            with mock.patch.object(zipfile.ZipFile, 'extract', side_effect=error):
                with self.assertRaises(AU.AppUpdateError):
                    AU.install(z, root)
            self.assertFalse((root / 'zips' / z.name).exists())              # la copie abîmée ne resservira pas
            self.assertFalse((root / 'VectorDrive-4.0.0').exists())
            self.assertEqual([p.name for p in root.iterdir() if p.name.startswith('.')], [])
        self.assertTrue(z.is_file())                                         # l'archive d'origine : intacte

    def test_shortcuts_same_edition_only_and_never_overwrite_a_stranger(self):
        AU = self.AU
        box = tmp()
        dirs = {'demarrer': box / 'demarrer', 'bureau': box / 'bureau', 'barre': box / 'barre'}
        for d in dirs.values():
            d.mkdir()
        vd = box / 'VD'
        new = vd / 'VectorDrive-1.3.0' / 'VectorDrive' / 'VectorDrive.exe'
        mine = vd / 'VectorDrive-1.1.0' / 'VectorDrive' / 'VectorDrive.exe'
        other = vd / 'VectorDrive-ABC-1.0.0' / 'VectorDrive' / 'VectorDrive.exe'
        a = make_link(dirs['bureau'] / 'VectorDrive.lnk', mine)
        b = make_link(dirs['bureau'] / 'VectorDrive ABC.lnk', other)         # une autre édition : reste à elle
        stranger = make_link(dirs['demarrer'] / 'VectorDrive.lnk', 'D:\\outils\\autre.exe')   # ce nom, autre programme
        shell = Shell({a: mine, b: other, stranger: 'D:\\outils\\autre.exe'})
        got = AU.retarget_shortcuts(None, new, shell, dirs=dirs, versions_dir=vd)
        self.assertEqual(got['changes'], [a])
        self.assertEqual(shell.targets[str(b)], str(other))
        self.assertIsNone(got['cree'])                                       # pas réécrit par une « création »
        self.assertEqual(shell.targets[str(stranger)], 'D:\\outils\\autre.exe')
        self.assertEqual([w['lien'] for w in shell.asked('ecrire')], [str(a)])
        self.assertNotIn('IconLocation', AU.ps_script({'action': 'ecrire', 'liens': []}))   # l'icône n'est pas touchée
        got = AU.retarget_shortcuts(None, other.parent / 'VectorDrive.exe', Shell({b: mine}), dirs=dirs,
                                    versions_dir=vd, edition='ABC', create=False)
        self.assertEqual(got['changes'], [])                                 # cible d'une autre édition que « ABC »


class Frozen(unittest.TestCase):
    """Exécutable empaqueté (PyInstaller) et contrôle de vie : écrits pour le cas réel, essayés par simulation."""

    def setUp(self):
        self.AU = au()

    def test_child_env_drops_what_pyinstaller_set(self):
        AU = self.AU
        old = os.path.join(str(tmp()), 'VectorDrive-1.0.0', 'VectorDrive')
        internal = os.path.join(old, '_internal')
        env = {'PATH': os.pathsep.join([internal, 'C:\\Windows\\System32', os.path.join(old, 'x'), '']),
               'QT_PLUGIN_PATH': os.path.join(internal, 'PySide6', 'plugins'),
               'QML2_IMPORT_PATH': os.path.join(internal, 'PySide6', 'qml'),
               '_PYI_APPLICATION_HOME_DIR': internal, '_PYI_PARENT_PROCESS_LEVEL': '1', '_MEIPASS2': internal,
               'NUMBER_OF_PROCESSORS': '8', 'VECTORDRIVE_INSTANCE': 'canal', 'APPDATA': 'C:\\Users\\x\\AppData'}
        got = AU.child_env(env, [internal, old])
        self.assertEqual(got['PATH'], 'C:\\Windows\\System32')               # ses entrées de PATH, retirées
        for k in ('QT_PLUGIN_PATH', 'QML2_IMPORT_PATH', '_PYI_APPLICATION_HOME_DIR', '_PYI_PARENT_PROCESS_LEVEL',
                  '_MEIPASS2'):
            self.assertNotIn(k, got)
        self.assertEqual((got['NUMBER_OF_PROCESSORS'], got['VECTORDRIVE_INSTANCE'], got['APPDATA']),
                         ('8', 'canal', 'C:\\Users\\x\\AppData'))            # le reste, tel quel (« 8 » : pas un
        #                                                                      chemin)
        self.assertEqual(got['PYINSTALLER_RESET_ENVIRONMENT'], '1')
        exe = os.path.join(old, 'VectorDrive.exe')
        with mock.patch.object(sys, 'frozen', True, create=True), \
                mock.patch.object(sys, '_MEIPASS', internal, create=True), \
                mock.patch.object(sys, 'executable', exe):
            self.assertEqual(AU.frozen_dirs(), [internal, old])
            self.assertNotIn('QT_PLUGIN_PATH', AU.child_env(env))
        self.assertEqual(AU.frozen_dirs(), [])                               # depuis les sources : rien à retirer
        self.assertIn('QT_PLUGIN_PATH', AU.child_env(env))

    def test_launch_frozen_detached_clean_env_dll_restored(self):
        AU = self.AU
        exe = tmp() / 'VectorDrive.exe'
        exe.write_bytes(b'MZ')
        internal = str(tmp() / '_internal')
        seen, calls = [], []

        def swap(value):
            calls.append(value)
            return 'C:\\ancienne\\_internal'

        def refuse(args, **kw):
            raise OSError('lancement refusé')
        proc = object()
        with mock.patch.object(AU, '_dll_directory', side_effect=swap), \
                mock.patch.object(sys, 'frozen', True, create=True), \
                mock.patch.object(sys, '_MEIPASS', internal, create=True), \
                mock.patch.dict(os.environ, {'QT_PLUGIN_PATH': internal + '\\PySide6\\plugins', '_PYI_X': '1'}):
            self.assertIs(AU.launch(exe, popen=lambda args, **kw: seen.append(kw) or proc), proc)
            if sys.platform == 'win32':
                self.assertEqual(calls, [None, 'C:\\ancienne\\_internal'])   # écarté, puis rétabli
                del calls[:]
                with self.assertRaises(OSError):
                    AU.launch(exe, popen=refuse)
                self.assertEqual(calls, [None, 'C:\\ancienne\\_internal'])   # … même si le lancement échoue
        kw = seen[0]
        self.assertEqual(kw['cwd'], str(exe.parent))
        self.assertNotIn('QT_PLUGIN_PATH', kw['env'])
        self.assertNotIn('_PYI_X', kw['env'])
        self.assertEqual(kw['env']['PYINSTALLER_RESET_ENVIRONMENT'], '1')
        self.assertEqual((kw['stdin'], kw['stdout'], kw['stderr']), (subprocess.DEVNULL,) * 3)
        if sys.platform == 'win32':
            self.assertEqual(kw['creationflags'], 0x00000008 | 0x00000200 | 0x01000000)

    def test_answers_real_local_channel(self):
        """Le canal d'instance unique est cherché comme Qt le crée (tube nommé sous Windows), sans connexion : un
        canal d'essai au nom tiré au hasard, jamais celui de l'utilisateur."""
        from PySide6.QtNetwork import QLocalServer
        AU = self.AU
        name = 'vd-essai-' + uuid.uuid4().hex
        self.assertFalse(AU.answers(name))
        server = QLocalServer()
        self.assertTrue(server.listen(name))
        try:
            self.assertTrue(AU.answers(name))
            self.assertFalse(server.hasPendingConnections())                 # rien n'a été envoyé à la fenêtre
        finally:
            server.close()
        self.assertFalse(AU.answers(name))
        from vectordrive.ui import instance                                  # le même canal pour toutes les versions
        with mock.patch.dict(os.environ, {'VECTORDRIVE_INSTANCE': ''}):
            self.assertNotRegex(instance.channel(), r'\d+\.\d+\.\d+')

    def test_wait_started(self):
        AU = self.AU
        t = time.monotonic()
        self.assertEqual(AU.wait_started(Alive(), lambda: False, timeout=0.3, step=0.05), 'muette')
        self.assertGreaterEqual(time.monotonic() - t, 0.3)                   # attend vraiment, pas 2,5 s de vie
        answers = iter([False, False, True])
        self.assertEqual(AU.wait_started(Alive(), lambda: next(answers), timeout=5, step=0.01), 'ok')
        self.assertEqual(AU.wait_started(Alive(1), lambda: True, timeout=5), 'arretee')   # morte : jamais « ok »
        self.assertEqual(AU.wait_started(True, lambda: True, timeout=0), 'ok')            # lanceur sans processus
        self.assertEqual(AU.wait_started(True, lambda: False, timeout=0), 'muette')
        self.assertEqual(AU.START_TIMEOUT, 30.0)
        from vectordrive.core import progress as P
        task = P.Task('essai')
        task.cancel()
        token = P.attach(task)
        try:
            with self.assertRaises(P.Cancelled):                             # annulable
                AU.wait_started(Alive(), lambda: False, timeout=5)
        finally:
            P.detach(token)


class Switch(unittest.TestCase):
    """`MainWindow.app_update` : la bascule ne se fait que si la nouvelle version répond, et rien ne se perd."""

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        if not cls.w.docs:
            cls.w.new_document()

    @classmethod
    def tearDownClass(cls):
        w = cls.w
        for t in w.docs:
            t.modified = False
        w.modified = False
        w.close()
        w.deleteLater()
        app.processEvents()

    def setUp(self):
        self.AU = au()
        for name in ('run_powershell', 'launch', 'answers'):
            p = mock.patch.object(self.AU, name, side_effect=AssertionError('processus lancé dans un essai'))
            p.start()
            self.addCleanup(p.stop)
        self.box = tmp()
        self.src, self.vd = self.box / 'partage', self.box / 'VD'
        self.src.mkdir()
        self.dirs = {k: self.box / k for k in ('demarrer', 'bureau', 'barre')}
        for d in self.dirs.values():
            d.mkdir()
        self.quits, self.shell, self.started = [], Shell(), []
        self.answer = True                                                   # la nouvelle version répond-elle ?
        self.server = types.SimpleNamespace(calls=[], on=True, ok=True)                # le canal d'instance (factice)
        self.server.close = lambda: self.server.calls.append('fermé') or setattr(self.server, 'on', False)
        self.server.listen = lambda _name: (self.server.calls.append('rouvert'),
                                            setattr(self.server, 'on', self.server.ok))[0] or self.server.ok
        self.server.isListening = lambda: self.server.on
        self.server.errorString = lambda: 'nom de canal refusé'
        self.w._instance_server = self.server
        self.addCleanup(lambda: delattr(self.w, '_instance_server'))
        self.addCleanup(lambda: setattr(self.w, '_closing', False))

    def params(self, proc=None, close=True, **kw):
        def launcher(exe):
            self.started.append(exe)
            return proc if proc is not None else Alive()

        def quit_():
            self.quits.append(1)
            if close:                                                        # fermeture acceptée (`closeEvent`)
                self.w._closing = True
        base = {'source': self.src, 'dossier': self.vd, 'ok': True, 'runner': self.shell, 'delai': 0.3,
                'dossiers_raccourcis': self.dirs, 'lanceur': launcher, 'quitter': quit_,
                'sonde': lambda: bool(self.started) and self.answer}
        base.update(kw)
        return base

    def running(self, version='0.0.2'):
        """L'application en cours : une version portable du dossier VD, avec réglages et données."""
        make_version(self.vd, '0.0.1')
        return use(make_version(self.vd, version), **{'donnees/outils/tools.json': '[1]'})

    def update(self, old, **kw):
        with mock.patch.dict(os.environ, {'VECTORDRIVE_PORTABLE_DIR': str(old)}):
            return self.w.app_update(self.params(**kw), exec_dialog=False)

    def assert_nothing_changed(self, res, old):
        self.assertEqual(res['etat'], 'installe')
        self.assertEqual(self.quits, [])                                     # on reste ouvert…
        self.assertEqual(self.shell.calls, [])                               # … ni raccourcis…
        self.assertTrue((self.vd / 'VectorDrive-0.0.1').is_dir())            # … toutes les versions restent
        self.assertFalse((old / OLD_PROOF).exists())

    def test_c3_new_version_that_dies_changes_nothing(self):
        w, old = self.w, self.running()
        make_zip(self.src, '999.4.0')
        pinned = make_link(self.dirs['barre'] / 'VectorDrive.lnk', old / 'VectorDrive.exe')
        self.shell.targets[str(pinned)] = str(old / 'VectorDrive.exe')
        self.answer = False
        res = self.update(old, proc=Alive(1))
        self.assert_nothing_changed(res, old)
        self.assertEqual(res['demarrage'], 'arretee')
        self.assertEqual(self.server.calls, ['fermé', 'rouvert'] * 2)        # (canal demandé) … et joignable
        self.assertIn('pas démarré', w.statusBar().currentMessage())

    def test_life_waits_for_the_instance_channel(self):
        """Vivante ne suffit plus : sans réponse sur le canal d'instance dans le délai, rien d'autre n'est fait."""
        w, old = self.w, self.running()
        make_zip(self.src, '999.4.5')
        self.answer = False
        t = time.monotonic()
        res = self.update(old, delai=0.4)
        self.assertGreaterEqual(time.monotonic() - t, 0.4)
        self.assert_nothing_changed(res, old)
        self.assertEqual(res['demarrage'], 'muette')
        self.assertIn('n’a pas répondu en 0 s', res['message'])
        self.assertIn('peut-être démarré', w.statusBar().currentMessage())
        self.assertEqual(self.server.calls, ['fermé', 'rouvert', 'fermé'])   # elle vit : canal laissé (5e relecture)

    def test_fifth_channel_left_while_the_new_version_lives(self):
        """Cinquième relecture : la nouvelle version lancée mais muette, ou l'attente annulée, ou encore vivante
        après une erreur : elle construit sa fenêtre et prendra le canal — la fenêtre restée ouverte ne le reprend
        pas (jamais deux écouteurs). Arrêtée, refusée, ou erreur avant tout lancement : repris."""
        from vectordrive.core.progress import Cancelled
        old = self.running()
        cases =[('muette', {'delai': 0.2}, False),
                 ('interrompu', {'sonde': None}, False),
                 ('erreur', {'proc': types.SimpleNamespace(poll=lambda: None)}, False),
                 ('arretee', {'proc': Alive(1)}, True),
                 ('refus', {'lanceur': lambda exe: None}, True),
                 ('erreur', {'lanceur': mock.Mock(side_effect=OSError('refusé'))}, True)]
        for i, (state, kw, again) in enumerate(cases):
            with self.subTest(state=state, i=i):
                make_zip(self.src, f'999.8.{i}')
                self.server.calls.clear()
                self.server.on, self.started[:] = True, []
                self.answer = False
                asked = []
                if 'sonde' in kw:                                            # Annuler pendant l'attente

                    def probe():
                        asked.append(1)
                        if len(asked) == 3:
                            raise Cancelled()
                        return False
                    kw = {'sonde': probe}
                if state == 'erreur' and 'proc' in kw:                       # vivante, mais l'attente échoue
                    with mock.patch.object(self.AU, 'wait_started', side_effect=RuntimeError('attente')):
                        res = self.update(old, **kw)
                else:
                    res = self.update(old, **kw)
                self.assertEqual(res['demarrage'], state, res.get('message'))
                want = ['fermé', 'rouvert', 'fermé'] + (['rouvert'] if again else [])
                self.assertEqual(self.server.calls, want)
                self.assertEqual(self.server.on, again)

    def test_life_another_window_on_the_channel_launches_nothing(self):
        """Une autre fenêtre tient le canal : dit AVANT toute installation, toute copie (troisième relecture) ; et si
        elle paraît pendant l'installation, rien n'est lancé."""
        old = self.running()
        make_zip(self.src, '999.4.6')
        asked, other = [], [True]
        with mock.patch.object(self.w, '_confirm_discard', side_effect=lambda: asked.append(1) or True):
            res = self.update(old, sonde=lambda: other[0])                   # une autre fenêtre tient le canal
        self.assertEqual(res['etat'], 'erreur')
        self.assertIn('autre fenêtre', res['message'])
        self.assertIn('Rien n’est installé', res['message'])
        self.assertEqual((self.started, asked, self.quits), ([], [], []))    # rien demandé, rien lancé
        self.assertFalse((self.vd / 'VectorDrive-999.4.6').exists())         # ni installée…
        self.assertFalse((self.vd / 'zips' / 'VectorDrive-999.4.6-portable.zip').exists())   # … ni copiée
        self.assertEqual(self.server.calls, ['fermé'])                       # pas rouvert : jamais deux fenêtres…
        self.assertFalse(self.server.on)
        self.assertFalse(hasattr(self.w, '_channel_timer'))                  # … ni repris plus tard (pas de minuterie)
        other[0] = False                                                     # l'autre fenêtre se ferme : le prochain
        app.processEvents()                                                  # lancement sera la fenêtre principale
        self.assertEqual(self.server.calls, ['fermé'])
        self.server.calls.clear()
        self.server.on = True                                                # (une autre fois, elle le servait)
        seen = []

        def probe():                                                         # libre d'abord, puis prise pendant
            seen.append(1)                                                   # l'installation
            return len(seen) > 1
        res = self.update(old, sonde=probe)
        self.assertEqual(self.started, [])                                   # la nouvelle lui passerait la main
        self.assert_nothing_changed(res, old)
        self.assertIn('autre fenêtre', res['message'])
        self.assertEqual(self.server.calls, ['fermé', 'rouvert', 'fermé'])   # le canal reste à l'autre

    def test_minor_cancel_while_waiting_says_it_may_have_started(self):
        from vectordrive.core.progress import Cancelled
        old = self.running()
        make_zip(self.src, '999.4.7')
        asked = []

        def probe():
            asked.append(1)
            if len(asked) == 2:                                              # Annuler pendant l'attente
                raise Cancelled()
            return False
        res = self.update(old, sonde=probe)
        self.assert_nothing_changed(res, old)
        self.assertEqual(res['demarrage'], 'interrompu')
        self.assertIn('Attente interrompue', res['message'])
        self.assertIn('a peut-être démarré', res['message'])
        self.assertNotIn('pas démarré', res['message'])

    def test_c3_tabs_then_launch_then_shortcuts_nothing_deleted(self):
        w, old = self.w, self.running()
        make_zip(self.src, '999.5.0')
        order = []
        real_retarget, real_hand = self.AU.retarget_shortcuts, w._app_update_hand_over

        def launcher(exe):
            order.append('lancement')
            self.started.append(exe)
            return Alive()

        def probe():
            order.append('canal')
            return bool(self.started)

        def retarget(*a, **kw):
            order.append('raccourcis')
            return real_retarget(*a, **kw)

        def hand(*a, **kw):
            order.append('onglets')
            return real_hand(*a, **kw)
        with mock.patch.object(self.AU, 'retarget_shortcuts', side_effect=retarget), \
                mock.patch.object(w, '_app_update_hand_over', side_effect=hand):
            res = self.update(old, lanceur=launcher, sonde=probe)
        self.assertEqual(res['etat'], 'lance')
        self.assertEqual(order, ['canal', 'onglets', 'canal', 'lancement', 'canal', 'raccourcis'])
        self.assertTrue(res['ferme'])
        self.assertEqual(res['non_repris'], [])
        self.assertEqual(sorted(p.name for p in self.vd.iterdir()),          # 26/11 : rien n'est supprimé
                         ['VectorDrive-0.0.1', 'VectorDrive-0.0.2', 'VectorDrive-999.5.0', 'zips'])
        self.assertTrue((old / 'donnees' / 'outils' / 'tools.json').is_file())   # l'ancienne : intacte, sans preuve
        self.assertFalse((old / OLD_PROOF).exists())
        self.assertEqual(self.quits, [1])
        self.assertEqual(self.server.calls, ['fermé', 'rouvert', 'fermé'])   # fermée : le canal est à la nouvelle
        self.assertFalse(getattr(w, '_update_settled', False))

    def test_refused_close_keeps_the_window(self):
        w, old = self.w, self.running()
        make_zip(self.src, '999.5.5')
        forgot = []
        w.modified = True
        self.addCleanup(lambda: setattr(w, 'modified', False))
        with mock.patch.object(w, '_forget_kept_now', side_effect=lambda: forgot.append(1)):
            res = self.update(old, close=False)                              # police en cours d'édition : refusée
        self.assertEqual(res['etat'], 'lance')
        self.assertFalse(res['ferme'])
        self.assertTrue(w.modified)                                          # son dessin reste « modifié »
        self.assertEqual(forgot, [1])
        self.assertEqual(self.server.calls, ['fermé', 'rouvert', 'fermé'])   # la nouvelle version tient le canal
        self.assertTrue(old.is_dir())
        self.assertFalse((old / OLD_PROOF).exists())

    def test_third_modified_state_unchanged_while_closing(self):
        """Troisième relecture, à corriger 1 : pendant la fermeture, l'onglet modifié le reste — la session de la
        version gardée en secours ne le dit pas « enregistré »."""
        w, old = self.w, self.running()
        make_zip(self.src, '999.5.6')
        w.modified = True
        self.addCleanup(lambda: setattr(w, 'modified', False))
        seen = []

        def quit_():
            seen.append((w.modified, w._confirm_discard()))                  # ce que voient la session et la question
            w._closing = True
        res = self.update(old, quitter=quit_)
        self.assertEqual(res['etat'], 'lance')
        self.assertEqual(seen, [(True, True)])                             # modifié, et rien de redemandé
        self.assertTrue(w.modified)

    def test_third_refused_while_the_assistant_works(self):
        """Troisième relecture, mineur 6 : l'assistant IA tient un onglet, ou un outil MCP est en cours : refusée,
        rien d'installé ; le texte en cours de frappe est fini avant que les onglets passent (26/11 : sans question)."""
        from vectordrive.agent.server import UiBridge
        w, old = self.w, self.running()
        make_zip(self.src, '999.6.5')
        w.agent_lock(w.docs[0])
        try:
            res = self.update(old)
        finally:
            w.agent_lock(None)
        self.assertEqual(res['etat'], 'occupe')
        self.assertIn('assistant IA travaille', res['message'])
        bridge = UiBridge(w)
        self.addCleanup(bridge.deleteLater)
        w._agent_server = types.SimpleNamespace(bridge=bridge)
        self.addCleanup(lambda: delattr(w, '_agent_server'))
        seen = []
        res = bridge.run(lambda: seen.append(bridge.active) or self.update(old))     # pendant un outil MCP
        self.assertEqual((res['etat'], seen, bridge.active), ('occupe', [1], 0))
        self.assertIn('pont MCP', res['message'])
        with self.assertRaises(ZeroDivisionError):
            bridge.run(lambda: 1 / 0)
        self.assertEqual(bridge.active, 0)                                   # compté juste, même en erreur
        self.assertEqual((self.started, self.quits), ([], []))
        self.assertFalse((self.vd / 'VectorDrive-999.6.5').exists())
        order = []
        with mock.patch.object(w, '_app_update_busy', side_effect=['', 'l’assistant IA travaille']):
            res = self.update(old)                                           # reparti pendant la confirmation
        self.assertEqual(res['etat'], 'occupe')
        self.assertFalse((self.vd / 'VectorDrive-999.6.5').exists())
        with mock.patch.object(w, 'finish_typing', side_effect=lambda: order.append('frappe')), \
                mock.patch.object(w, '_confirm_discard', side_effect=AssertionError('question posée')):
            self.assertEqual(self.update(old)['etat'], 'lance')              # 26/11 : plus de question…
        self.assertEqual(order, ['frappe'])                                  # … la frappe finie avant les onglets

    def test_fourth_channel_reopened_only_if_it_was_listening(self):
        """Quatrième relecture : le canal d'instance n'est rouvert que s'il écoutait avant et qu'il est libre ; un
        `listen()` refusé est noté et dit, sans plantage."""
        w = self.w
        old = self.running()
        make_zip(self.src, '999.7.0')
        self.server.on = False                                               # n'écoutait pas (refus d'avant…)
        self.answer = False
        res = self.update(old, proc=Alive(1))                                # libre, et la nouvelle s'arrête
        self.assertEqual(res['demarrage'], 'arretee')
        self.assertEqual(self.server.calls, [])                              # jamais rouvert, jamais refermé
        self.assertFalse(hasattr(w, '_channel_timer'))                       # (pas de minuterie)
        self.server.on, self.started[:] = True, []                           # écoutait, et libre : rouvert
        res = self.update(old, proc=Alive(1))
        self.assertEqual(self.server.calls, ['fermé', 'rouvert', 'fermé', 'rouvert'])
        self.assertTrue(self.server.on and w._app_update_listen)
        self.server.calls.clear()
        self.started[:] = []
        self.server.ok = False                                               # le système refuse le nom
        said = []
        with mock.patch.object(w.statusBar(), 'showMessage', side_effect=lambda text, *_a: said.append(text)):
            res = self.update(old, proc=Alive(1))
        self.assertEqual(res['demarrage'], 'arretee')
        self.assertEqual(self.server.calls, ['fermé', 'rouvert', 'rouvert'])     # retenté une fois, après l'échec
        self.assertFalse(w._app_update_listen)
        self.assertTrue(any('canal d’instance n’a pas pu être rouvert (nom de canal refusé)' in t for t in said))

    def test_fourth_user_folders_asked_once_in_the_interface_thread(self):
        """Quatrième relecture, mineur : les dossiers de l'utilisateur sont demandés une fois, dans le fil de
        l'interface, puis passés à l'examen, à l'installation et à l'élagage."""
        import threading
        AU, old = self.AU, self.running()
        make_zip(self.src, '999.7.5')
        real, where = AU.special_dirs, []

        def special():
            where.append(threading.current_thread() is threading.main_thread())
            return real()
        with mock.patch.object(AU, 'special_dirs', side_effect=special):
            res = self.update(old)
        self.assertEqual(res['etat'], 'lance')
        self.assertEqual(where, [True])

    def test_fifth_shortcut_folders_asked_in_the_interface_thread(self):
        """Cinquième relecture, mineur : les dossiers de raccourcis sont demandés dans le fil de l'interface, puis
        passés à `retarget_shortcuts`."""
        import threading
        AU, old = self.AU, self.running()
        make_zip(self.src, '999.8.9')
        where, given = [], []
        real = AU.retarget_shortcuts

        def folders():
            where.append(threading.current_thread() is threading.main_thread())
            return self.dirs

        def retarget(*a, **kw):
            given.append(kw.get('dirs'))
            return real(*a, **kw)
        with mock.patch.object(AU, 'shortcut_dirs', side_effect=folders), \
                mock.patch.object(AU, 'retarget_shortcuts', side_effect=retarget):
            res = self.update(old, dossiers_raccourcis=None, raccourcis=True)
        self.assertEqual(res['etat'], 'lance')
        self.assertEqual((where, given), ([True], [self.dirs]))

    def test_sixth_probe_error_leaves_the_channel(self):
        """Sixième relecture : la sonde du canal lève une exception — pas de réponse sûre, le canal n'est pas repris,
        ni à la vérification d'avant la confirmation, ni après la mise à jour."""
        w, old = self.w, self.running()
        make_zip(self.src, '999.9.1')

        def broken():
            raise OSError('tube injoignable')
        with mock.patch.object(w, '_app_update_reclaim', wraps=w._app_update_reclaim) as reclaim:
            res = self.update(old, sonde=broken)
        self.assertEqual(reclaim.call_count, 0)                              # pas même tenté (garde doublée)
        self.assertEqual(res['etat'], 'erreur')
        self.assertIn('tube injoignable', res['message'])
        self.assertEqual(self.server.calls, ['fermé'])                       # fermé pour demander, jamais repris
        self.assertFalse(self.server.on)
        self.assertEqual(self.started, [])
        self.assertFalse((self.vd / 'VectorDrive-999.9.1').exists())
        self.server.calls.clear()
        w._app_update_reclaim(self.server, broken)                           # le chemin d'après la mise à jour
        self.assertEqual(self.server.calls, [])
        self.assertFalse(self.server.on)

    def test_settled_close_asks_nothing_again(self):
        """La fermeture qui suit la mise à jour ne redemande rien (`_confirm_discard`) : tous les onglets viennent
        d'être passés à la nouvelle version — sans question ni onglet gardé (demande du 26/11)."""
        w, old = self.w, self.running()
        make_zip(self.src, '999.5.7')
        seen, kept = [], []
        keep, w.session_dir = w.session_dir, None                            # sans session silencieuse
        self.addCleanup(lambda: setattr(w, 'session_dir', keep))
        self.addCleanup(lambda: w.settings.remove(w.REOPEN_KEY))
        self.addCleanup(lambda: setattr(w, '_kept_now', []))
        w.modified = True                                                    # un dessin non enregistré
        self.addCleanup(lambda: setattr(w, 'modified', False))

        def quit_():
            seen.append(w._confirm_discard())                                # ce que fait `closeEvent`
            w._closing = True
        with mock.patch.object(w, '_ask_save', side_effect=AssertionError('question posée')), \
                mock.patch.object(w, '_needs_keeping', return_value=True), \
                mock.patch.object(w, '_keeps_closed', return_value=True), \
                mock.patch.object(w, '_keep_closed', side_effect=lambda t: kept.append(t) or object()):
            res = self.update(old, quitter=quit_)                            # aucun dessin gardé ni demandé
            self.assertEqual((res['etat'], seen), ('lance', [True]))
            self.assertEqual(kept, [])                                       # passés à la nouvelle, pas gardés ici
            self.assertGreaterEqual(res['onglets'], 1)
            self.assertFalse(w._update_settled)                              # hors de la fermeture : comme avant
            self.assertTrue(w._confirm_discard())
            self.assertEqual(len(kept), len(w.docs))

    def test_keep_state_failure_stops_before_anything_runs(self):
        w, old = self.w, self.running()
        make_zip(self.src, '999.5.8')
        with mock.patch.object(w, 'save_session', side_effect=OSError(28, 'Espace insuffisant sur le disque')):
            res = self.update(old)
        self.assertEqual(res['etat'], 'erreur')
        self.assertIn('rien n’est repris ni lancé', res['message'])
        self.assertIn('Espace insuffisant', res['message'])
        self.assertEqual(self.started, [])                                   # rien de lancé…
        new_ini = self.vd / 'VectorDrive-999.5.8' / 'VectorDrive' / 'VectorDrive.ini'
        self.assertFalse(self.AU.has_settings(new_ini))                      # … rien de repris…
        self.assertFalse(self.AU.handover_root(new_ini.parent).exists())     # … ni d'onglets passés
        self.assertEqual(self.server.calls, ['fermé', 'rouvert'])            # (canal demandé avant ; pas fermé)
        errors = []
        with mock.patch.object(w, 'save_session', side_effect=OSError('disque')):
            self.assertFalse(w._app_update_keep_state(errors))
        self.assertEqual(errors, ['disque'])
        self.assertTrue(w._app_update_keep_state([]))

    def test_skipped_file_is_told(self):
        w, old = self.w, self.running()
        make_zip(self.src, '999.5.9')
        mine = self.vd / 'VectorDrive-999.5.9' / 'VectorDrive' / 'donnees' / 'outils' / 'tools.json'
        real_install = self.AU.install

        def install(*a, **kw):                                               # version déjà là, avec son tools.json
            got = real_install(*a, **kw)
            mine.parent.mkdir(parents=True)
            mine.write_text('[9]', encoding='utf-8')
            stamp(old / 'donnees' / 'outils' / 'tools.json', 1_600_000_000)
            return got
        with mock.patch.object(self.AU, 'install', side_effect=install):
            res = self.update(old)
        self.assertEqual(res['etat'], 'lance')
        self.assertEqual(mine.read_text(encoding='utf-8'), '[9]')
        self.assertEqual(res['non_repris'], [str(old / 'donnees' / 'outils' / 'tools.json')])
        self.assertIn('non repris', w.statusBar().currentMessage())

    def test_b1_failed_carry_is_told_and_old_version_survives_next_update(self):
        w, old = self.w, self.running()
        make_zip(self.src, '999.7.0')
        real = shutil.copy2

        def copy(src, dst, *a, **kw):
            if pathlib.Path(src).name == 'tools.json':
                raise OSError(28, 'Espace insuffisant sur le disque')
            return real(src, dst, *a, **kw)
        with mock.patch.object(shutil, 'copy2', side_effect=copy):
            res = self.update(old)
        self.assertEqual(res['etat'], 'lance')
        self.assertEqual(len(res['non_repris']), 1)
        self.assertIn('tools.json', w.statusBar().currentMessage())          # dit à l'utilisateur
        make_zip(self.src, '999.8.0')                                        # la mise à jour suivante, depuis la neuve
        self.started.clear()
        again = self.update(res['exe'].parent, reprendre=False)
        self.assertEqual(again['etat'], 'lance')
        self.assertTrue(old.is_dir())                                        # l'ancienne reste, toujours
        self.assertTrue(res['exe'].is_file())                                # … et celle d'avant aussi
        self.assertEqual((old / 'donnees' / 'outils' / 'tools.json').read_text(encoding='utf-8'), '[1]')

    def test_c1_no_carry_still_hands_over_the_unsaved_drawing(self):
        """Demande du 26/11 : réglages repris ou non, application portable ou non, le dessin non enregistré suit la
        nouvelle version — aucune question, rien d'enregistré à la place de l'utilisateur."""
        from vectordrive.ui import session
        w, old = self.w, self.running()
        make_zip(self.src, '999.9.0')
        w.modified = True                                                    # un dessin non enregistré
        self.addCleanup(lambda: setattr(w, 'modified', False))
        no = AssertionError('question posée')
        for i, (kw, there) in enumerate((({'reprendre': False}, old), ({}, None))):
            with self.subTest(i=i), mock.patch.object(w, '_ask_save', side_effect=no), \
                    mock.patch.object(w, '_confirm_discard', side_effect=no):
                if there is None:                                            # depuis les sources (pas portable)
                    make_zip(self.src, '999.9.1')
                    self.started.clear()
                    res = w.app_update(self.params(), exec_dialog=False)
                else:
                    res = self.update(old, **kw)
                self.assertEqual(res['etat'], 'lance')
                self.assertIn('reprise=non', (res['exe'].parent / 'VectorDrive.ini').read_text(encoding='utf-8'))
                index = session.load_index(passed(res['exe'].parent)[0])
                self.assertTrue(any(e['modified'] and e['file'] for e in index['docs']))   # le dessin, tel quel
                self.assertTrue(w.modified)                                  # rien d'enregistré ici

    def test_c2_kept_tabs_are_remembered_before_settings_are_copied(self):
        w, old = self.w, self.running()
        make_zip(self.src, '999.10.0')
        new_ini = self.vd / 'VectorDrive-999.10.0' / 'VectorDrive' / 'VectorDrive.ini'
        seen = []
        w._remember_reopen = lambda: seen.append(self.AU.has_settings(new_ini))
        self.addCleanup(lambda: w.__dict__.pop('_remember_reopen', None))
        keep, w.session_dir = w.session_dir, None                            # une fenêtre sans session silencieuse
        self.addCleanup(lambda: setattr(w, 'session_dir', keep))
        res = self.update(old)
        self.assertEqual(res['etat'], 'lance')
        self.assertEqual(seen[:1], [False])                                  # noté AVANT la copie de VectorDrive.ini
        w.session_dir, seen[:] = keep, []                                    # avec une session : elle garde tout
        make_zip(self.src, '999.11.0')
        self.started.clear()
        self.update(old)
        self.assertEqual(seen, [])
        self.assertTrue(self.AU.has_settings(new_ini))


# --- demande du 26/11 --------------------------------------------------------------------------------------------
def upd():
    from vectordrive import update
    if not hasattr(update, 'look'):
        raise AssertionError('avant : la vérification ne lit que le manifeste')
    return update


def manifest(folder, version, name='vectordrive-latest.json'):
    """Un manifeste d'essai et son installateur factice dans `folder`."""
    from vectordrive import update
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    setup = folder / f'VectorDrive-{version}-setup.exe'
    setup.write_bytes(b'MZ installateur factice')
    (folder / name).write_text(json.dumps({'version': version, 'installer': setup.name,
                                           'sha256': update.sha256_file(setup)}), encoding='utf-8')
    return setup


class NoDeletion(unittest.TestCase):
    """« Ne pas supprimer de versions antérieures automatiquement » : plus aucun code d'élagage."""

    def test_no_pruning_code_left(self):
        AU = au()
        for name in ('prune', 'examine', 'keep_reason', 'mark_carried', 'unmark_carried', '_remove_version',
                     'marked', 'Pruned', 'PROOF', 'DOOMED', 'reason_text', 'kept_text'):
            self.assertFalse(hasattr(AU, name), name)
        text = pathlib.Path(AU.__file__).read_text(encoding='utf-8')
        self.assertEqual(text.count('shutil.rmtree('), 2)       # le dossier provisoire marqué, le passage d'onglets
        self.assertIn('def _remove_tree(', text)
        self.assertIn('def drop_handover(', text)
        from vectordrive.ui.options import BY_KEY
        self.assertNotIn('maj/versions_gardees', BY_KEY)

    def test_two_updates_in_a_row_keep_every_version(self):
        AU = au()
        src, vd = tmp(), tmp() / 'VD'
        for v in ('1.0.0', '1.1.0'):
            make_version(vd, v)
        for v in ('2.0.0', '3.0.0'):
            AU.install(make_zip(src, v), vd)
        self.assertEqual(sorted(p.name for p in vd.iterdir()),
                         ['VectorDrive-1.0.0', 'VectorDrive-1.1.0', 'VectorDrive-2.0.0', 'VectorDrive-3.0.0', 'zips'])
        self.assertEqual(len(list((vd / 'zips').iterdir())), 4)


class Lookup(unittest.TestCase):
    """`update.look` / `update.check` : une archive portable déposée seule est reconnue par son nom, de la même
    édition seulement ; le manifeste garde la priorité s'il est au moins aussi récent ; jamais « à jour » sans avoir
    pu chercher."""

    def setUp(self):
        self.U = upd()
        for name in ('run', 'Popen'):
            p = mock.patch.object(subprocess, name, side_effect=AssertionError('processus lancé dans un essai'))
            p.start()
            self.addCleanup(p.stop)

    def test_archive_dropped_alone_found_by_its_name_same_edition_only(self):
        U, d = self.U, tmp()
        make_zip(d, '999.1.0')                                               # le cœur
        make_zip(d, '999.0.0', ED)
        make_zip(d / 'sous-dossier', '999.2.0', ED)                          # un sous-dossier direct : vu
        got = U.look('', '1.29.0', folders=[d], edition=ED)
        up = got.update
        self.assertEqual((up.version, up.sha256, up.portable, up.folder), ('999.2.0', '', True, str(d)))
        self.assertTrue(up.installer.endswith(f'VectorDrive-{ED}-999.2.0-portable.zip'))
        self.assertIsNone(got.manifest)                                      # pas de source : pas de manifeste lu
        self.assertEqual(U.look('', '1.29.0', folders=[d], edition='').update.version, '999.1.0')    # le cœur
        none = U.look('', '1.29.0', folders=[d], edition='XYZ')              # jamais une autre édition
        self.assertIsNone(none.update)
        self.assertIsNone(none.archive)
        self.assertEqual(U.check('', '1.29.0', [d], ED).version, '999.2.0')
        self.assertIsNone(U.check('', '999.2.0', [d], ED))                   # déjà la dernière : à jour

    def test_the_reported_case_archive_in_the_update_folder_without_manifest(self):
        """1.29.0 de l'édition, la 1.32.0 de son édition déposée seule dans le dossier des mises à jour : trouvée."""
        U, src = self.U, tmp()
        make_zip(src, '1.32.0', ED)
        make_zip(src, '1.40.0')                                              # le cœur, plus récent : jamais pris
        up = U.check(str(src), current='1.29.0', edition=ED)
        self.assertEqual((up.version, up.folder), ('1.32.0', str(src)))
        got = U.look(str(src), '1.29.0', folders=[src], edition=ED)          # même dossier deux fois : regardé une fois
        self.assertEqual(got.folders, [str(src)])
        self.assertEqual(got.manifest, '')                                   # (pas de manifeste)

    def test_manifest_keeps_priority_when_at_least_as_recent(self):
        U, src, d = self.U, tmp(), tmp()
        manifest(src, '999.5.0')
        make_zip(d, '999.5.0')
        up = U.check(str(src), '1.0.0', [d], '')
        self.assertEqual((up.version, up.folder), ('999.5.0', ''))           # le manifeste, avec son empreinte
        self.assertEqual(len(up.sha256), 64)
        make_zip(d, '999.6.0')                                               # plus récente que le manifeste
        up = U.check(str(src), '1.0.0', [d], '')
        self.assertEqual((up.version, up.folder, up.sha256), ('999.6.0', str(d), ''))
        old = tmp()
        manifest(old, '0.0.1')                                               # manifeste ancien, archive neuve
        got = U.look(str(old), '1.0.0', folders=[d], edition='')
        self.assertEqual((got.manifest, got.update.version), ('0.0.1', '999.6.0'))

    def test_never_up_to_date_without_having_looked(self):
        U, d = self.U, tmp()
        missing = tmp() / 'partage absent'
        with self.assertRaises(U.UpdateError) as cm:
            U.check('', '1.0.0', [missing], '')
        self.assertIn('partage absent', str(cm.exception))
        got = U.look('', '1.0.0', folders=[missing, d], edition='')
        self.assertIsNone(got.update)
        self.assertEqual(len(got.errors), 1)
        make_zip(d, '999.7.0')                                               # trouvée ailleurs : l'erreur ne gêne pas
        self.assertEqual(U.check('', '1.0.0', [missing, d], '').version, '999.7.0')
        broken = tmp()
        (broken / 'vectordrive-latest.json').write_text('{"version": "9.0.0"}', encoding='utf-8')
        self.assertEqual(U.check(str(broken), '1.0.0', [d], '').version, '999.7.0')
        with self.assertRaises(U.UpdateError):                               # manifeste incomplet, rien d'autre
            U.check(str(broken), '1.0.0', [], '')

    def test_edition_from_the_plugin_manifest(self):
        from vectordrive.plugins import REGISTRY
        U, d = self.U, tmp()
        make_zip(d, '999.8.0')
        make_zip(d, '999.1.0', ED)
        self.assertEqual(U.look('', '1.0.0', folders=[d]).update.version, '999.8.0')     # le cœur
        with mock.patch.object(REGISTRY, 'update_manifest', f'vectordrive-{ED.lower()}-latest.json'):
            self.assertEqual(U.look('', '1.0.0', folders=[d]).update.version, '999.1.0')     # l'édition

    def test_archive_without_fingerprint_never_goes_to_the_installer(self):
        U, d = self.U, tmp()
        z = make_zip(d, '999.9.0')
        up = U.Update('999.9.0', str(z), '', portable=True, folder=str(d))
        dest = tmp()
        with self.assertRaises(U.UpdateError):
            U.fetch(up, dest)
        self.assertEqual(list(dest.iterdir()), [])


class Check(unittest.TestCase):
    """La fenêtre : la vérification (au démarrage, « Mises à jour », le bouton de F10) dit ce qu'elle trouve, et une
    archive déposée seule passe par la mise à jour par dossier."""

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        w = cls.w
        for t in w.docs:
            t.modified = False
        w.modified = False
        w.close()
        w.deleteLater()
        app.processEvents()

    def setUp(self):
        self.U, self.AU = upd(), au()
        for name in ('run_powershell', 'launch', 'answers'):
            p = mock.patch.object(self.AU, name, side_effect=AssertionError('processus lancé dans un essai'))
            p.start()
            self.addCleanup(p.stop)
        from vectordrive import portable
        for mod, name in ((self.U, 'fetch'), (self.U, 'launch_installer'), (portable, 'launch_portable_update')):
            p = mock.patch.object(mod, name, side_effect=AssertionError('installateur lancé'))
            p.start()
            self.addCleanup(p.stop)
        self.box = tmp()
        self.calls = []
        self.w.app_update = lambda params=None, exec_dialog=True: self.calls.append(params) or {'etat': 'vu'}
        self.addCleanup(lambda: self.w.__dict__.pop('app_update', None))
        for k in ('maj/source', 'maj/dossier_source'):
            self.addCleanup(lambda k=k: self.w.settings.remove(k))

    def test_found_archive_goes_to_the_folder_update(self):
        w, d = self.w, self.box / 'depot'
        make_zip(d, '999.1.0')
        got = self.U.look('', folders=[d])
        w._upd_silent = False
        self.assertEqual(w._update_found(got), {'etat': 'vu'})
        self.assertEqual(self.calls, [{'source': str(d)}])                   # la mise à jour par dossier, sa fenêtre

    def test_up_to_date_says_where_it_looked_and_what_it_saw(self):
        w, src, d = self.w, self.box / 'source', self.box / 'depot'
        manifest(src, '0.0.1')
        make_zip(d, '0.0.2')
        got = self.U.look(str(src), folders=[d])
        self.assertIsNone(got.update)
        w._upd_silent = False
        with mock.patch.object(QMessageBox, 'information') as box:
            w._update_found(got)
        text = box.call_args[0][2]
        for part in ('à jour', '0.0.1', '0.0.2', str(src), str(d)):
            self.assertIn(part, text)
        missing = self.box / 'partage absent'
        got = self.U.look(str(src), folders=[missing])
        with mock.patch.object(QMessageBox, 'warning') as box:
            w._update_found(got)
        self.assertIn('tout n’a pas pu être vérifié', box.call_args[0][2])
        self.assertIn('partage absent', box.call_args[0][2])
        w._upd_silent = True                                                 # au démarrage : la barre d'état le dit
        with mock.patch.object(QMessageBox, 'information', side_effect=AssertionError('boîte')):
            w._update_found(got)
        self.assertIn('partage absent', w.statusBar().currentMessage())
        self.assertEqual(self.calls, [])

    def wait_calls(self, n=1, limit=10.0):
        t = time.monotonic()
        while len(self.calls) < n and time.monotonic() - t < limit:
            app.processEvents()
            time.sleep(0.02)

    def test_check_updates_finds_an_archive_dropped_alone(self):
        """Le cas rapporté, de bout en bout : la recherche au démarrage voit l'archive déposée seule dans le dossier
        réglé, sans manifeste — avec ou sans source des mises à jour."""
        w, src, d = self.w, self.box / 'source', self.box / 'depot'
        src.mkdir()
        make_zip(d, '999.3.0')
        w.settings.setValue('maj/dossier_source', str(d))
        for source in (str(src), ''):
            with self.subTest(source=source):
                self.calls.clear()
                w.settings.setValue('maj/source', source)
                w.check_updates(silent=True)
                self.wait_calls()
                self.assertEqual(self.calls, [{'source': str(d)}])
        self.calls.clear()
        w.settings.setValue('maj/source', str(d))                            # déposée dans la source elle-même
        w.settings.setValue('maj/dossier_source', str(src))
        w.check_updates(silent=True)
        self.wait_calls()
        self.assertEqual(self.calls, [{'source': str(d)}])

    def test_update_application_says_or_installs(self):
        w, d = self.w, self.box / 'depot'
        d.mkdir()
        w.settings.setValue('maj/source', '')
        w.settings.setValue('maj/dossier_source', str(d))
        with mock.patch.object(QMessageBox, 'information') as box:
            self.assertIsNone(w.update_application())                        # rien : il le dit
        self.assertIn('Aucune archive portable de cette édition', box.call_args[0][2])
        make_zip(d, '999.4.0')
        self.assertEqual(w.update_application(), {'etat': 'vu'})
        self.assertEqual(self.calls, [{'source': str(d)}])

    def test_button_first_in_the_tab_visible_and_wired(self):
        from PySide6.QtWidgets import QFormLayout
        w = self.w
        dlg = w.options_dialog(exec_dialog=False, page='Mises à jour')
        self.addCleanup(dlg.deleteLater)
        b = dlg.app_update_button
        form = b.parentWidget().layout()
        self.assertIsInstance(form, QFormLayout)
        self.assertEqual(form.getWidgetPosition(b)[0], 0)                    # en tête de l'onglet
        dlg.show()
        app.processEvents()
        self.assertTrue(b.isVisible())
        seen = []
        w.update_application = lambda: seen.append(1)
        self.addCleanup(lambda: w.__dict__.pop('update_application', None))
        self.addCleanup(lambda: [w.settings.remove(k) for k in dlg.APP_UPDATE_KEYS])
        b.click()
        self.assertEqual(seen, [1])
        w.A['app_update'].trigger()                                          # la commande : la même vérification
        self.assertEqual(seen, [1, 1])
        dlg.close()

    def test_vectordrive_py_reopens_the_tabs_after_an_update(self):
        import vectordrive
        text = (pathlib.Path(vectordrive.__file__).resolve().parents[1] / 'VectorDrive.py').read_text(encoding='utf-8')
        at = text.index('w.reopen_after_update()')
        self.assertLess(text.index('w.restore_session()'), at)
        self.assertLess(at, text.index('w.reopen_kept()'))


class Tabs(unittest.TestCase):
    """« màj attention à récupérer tous les onglets » : enregistrés, modifiés, jamais enregistrés, épinglés,
    renommés, dans le même ordre, avec l'onglet actif — session silencieuse ou non, réglages repris ou non."""

    params = Switch.params
    update = Switch.update
    running = Switch.running

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()                                                # une fenêtre neuve par essai
        self.addCleanup(self.shut, self.w)
        Switch.setUp(self)

    @staticmethod
    def shut(win):
        lock = getattr(win, '_session_lock', None)
        for t in win.docs:
            t.modified = False
        win.modified = False
        win.close()
        if lock is not None:
            lock.unlock()
        win.deleteLater()
        app.processEvents()

    def shape(self, k=0):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        return Shape(path=geom.Path([geom.rect(20 * k, 0, 10, 10)]))

    def tabs(self):
        """Six onglets mélangés ; rend ce que la nouvelle version doit retrouver et le nom de l'onglet actif."""
        from vectordrive.core.document import Document
        from vectordrive.io import native
        w = self.w
        files = []
        for i, n in enumerate((1, 2)):
            doc = Document()
            for k in range(n):
                doc.add(self.shape(k))
            files.append(self.box / f'plaque {"AB"[i]}.vdz')
            native.write(doc, files[-1])
        self.assertTrue(w.open_path(str(files[0])))                          # enregistré, intact
        self.assertTrue(w.open_path(str(files[1])))                          # enregistré, puis modifié
        w.canvas.doc.add(self.shape(5))
        w.modified = True
        active = w.docs[w.doc_index].name()
        for title, pinned in (('', False), ('Plaque client', True), ('Vide nommé', False)):
            w.new_document()                                                 # jamais enregistrés
            if title != 'Vide nommé':
                w.canvas.doc.add(self.shape(3))
                w.modified = True
            if title:
                w._dress_tab(title, pinned)                                  # renommé, épinglé
        w.new_document()                                                     # vide, jamais touché : rien à garder
        w.switch_tab(next(i for i, t in enumerate(w.docs) if t.name() == active))
        want = [(t.name(), os.path.normcase(os.path.abspath(t.path)) if t.path else None, bool(t.modified),
                 bool(t.pinned), t.title) for t in w.docs if not t.pristine()]
        self.assertEqual(len(want), 5)
        self.assertTrue(want[0][3])                                          # l'épinglé en tête
        return want, active

    @staticmethod
    def seen(win):
        return [(t.name(), os.path.normcase(os.path.abspath(t.path)) if t.path else None, bool(t.modified),
                 bool(t.pinned), t.title) for t in win.docs]

    def new_window(self):
        """La nouvelle version, à son lancement : une fenêtre neuve, sans session silencieuse."""
        from vectordrive.ui.main_window import MainWindow
        new = MainWindow()
        self.addCleanup(self.shut, new)
        new.session_dir = None
        return new

    def handed(self, version):
        """Les onglets mélangés passés à une nouvelle version : (ce qu'elle doit retrouver, l'onglet actif, son
        dossier d'application, le passage)."""
        old = self.running()
        want, active = self.tabs()
        make_zip(self.src, version)
        res = self.update(old)
        self.assertEqual(res['etat'], 'lance', res.get('message'))
        got = passed(res['exe'].parent)
        self.assertEqual(len(got), 1)
        return want, active, res['exe'].parent, got[0]

    def test_all_tabs_come_back_in_the_new_version(self):
        w, old = self.w, self.running()
        want, active = self.tabs()
        keep = w.session_dir
        self.addCleanup(lambda: setattr(w, 'session_dir', keep))
        lock_dir = tmp()
        cases = (('sans session, réglages repris', {}, False), ('sans session, réglages non repris',
                                                                {'reprendre': False}, False),
                 ('session silencieuse', {}, True))
        for i, (label, kw, with_session) in enumerate(cases):
            with self.subTest(label):
                make_zip(self.src, f'999.20.{i}')
                self.started.clear()
                w._closing = False
                w.session_dir = None
                if with_session:
                    self.assertTrue(w.start_session(lock_dir))
                with mock.patch.object(w, '_ask_save', side_effect=AssertionError('question posée')):
                    res = self.update(old, **kw)
                self.assertEqual(res['etat'], 'lance', res.get('message'))
                self.assertEqual(res['onglets'], len(want))
                self.assertEqual(self.seen(w)[:len(want)], want)            # cette fenêtre : rien de changé
                app_dir = res['exe'].parent
                self.assertEqual(len(passed(app_dir)), 1)
                self.assertFalse((app_dir / 'donnees' / 'session').exists())     # jamais sa session à elle
                new = self.new_window()
                self.assertEqual(new.reopen_after_update(self.AU.handover_root(app_dir)), len(want))
                self.assertEqual(self.seen(new), want)                       # tous, dans l'ordre, tels quels
                self.assertEqual(new.docs[new.doc_index].name(), active)     # l'onglet actif
                self.assertEqual(passed(app_dir), [])                        # rouverts : une fois…
                self.assertEqual(new.reopen_after_update(self.AU.handover_root(app_dir)), 0)     # … pas plus

    def test_reopened_only_after_success_and_never_in_a_loop(self):
        """Relecture du 26/11 (3) : le passage n'est retiré qu'une fois rouvert en entier ; la tentative est comptée
        avant — un plantage pendant la réouverture n'en laisse qu'une de plus, jamais une boucle ; une erreur le garde,
        avec son dossier dit."""
        from vectordrive.ui import session
        want, _a, app_dir, folder = self.handed('999.21.0')
        root = self.AU.handover_root(app_dir)
        new = self.new_window()
        with mock.patch.object(session, 'restore', side_effect=RuntimeError('dessin abîmé')):
            self.assertEqual(new.reopen_after_update(root), 0)
        self.assertEqual(passed(app_dir), [folder])                          # gardé…
        self.assertEqual(self.AU.tries_of(folder), self.AU.MAX_TRIES)        # … sans revenir de lui-même
        self.assertIn(str(folder), new.statusBar().currentMessage())
        with mock.patch.object(session, 'restore', side_effect=AssertionError('rouvert encore')):
            self.assertEqual(new.reopen_after_update(root), 0)
        self.AU.note_try(folder, 1)                                          # le lancement d'avant est mort en plein
        newer = self.new_window()                                            # milieu : une tentative de plus
        self.assertEqual(newer.reopen_after_update(root), len(want))
        self.assertEqual(self.seen(newer), want)
        self.assertEqual(passed(app_dir), [])
        self.assertFalse(root.exists())                                      # (vide : parti aussi)

    def test_missing_drawing_keeps_the_handover(self):
        from vectordrive.ui import session
        want, _a, app_dir, folder = self.handed('999.22.0')
        index = session.load_index(folder)
        lost = folder / next(e['file'] for e in index['docs'] if e['file'] and not e['path'])
        lost.rename(lost.with_suffix('.cache'))                              # un dessin jamais enregistré, perdu
        new = self.new_window()
        self.assertEqual(new.reopen_after_update(self.AU.handover_root(app_dir)), len(want) - 1)
        self.assertEqual(passed(app_dir), [folder])                          # gardé, et dit
        self.assertIn(str(folder), new.statusBar().currentMessage())
        self.assertEqual(new.reopen_after_update(self.AU.handover_root(app_dir)), 0)     # pas de doublons ensuite

    def test_files_already_open_are_skipped_or_reopened_apart(self):
        """La session silencieuse de la nouvelle version a déjà rouvert des fichiers : un fichier intact du passage,
        déjà ouvert, est sauté ; un dessin modifié dont le fichier est déjà ouvert revient à part, sans fichier
        (« Enregistrer sous »), jamais perdu."""
        want, _a, app_dir, folder = self.handed('999.23.0')
        files = [p for (_n, p, _m, _pin, _t) in want if p]
        self.assertEqual(len(files), 2)
        new = self.new_window()
        for f in files:
            self.assertTrue(new.open_path(f))                                # (sa propre session)
        n = new.reopen_after_update(self.AU.handover_root(app_dir))
        self.assertEqual(n, len(want) - 1)                                   # le fichier intact : pas deux fois
        names = [t.name().lower() for t in new.docs]                         # (chemins ouverts en minuscules)
        self.assertEqual(names.count('plaque a.vdz'), 1)
        apart = [t for t in new.docs if t.name().lower() == 'plaque b.vdz' and not t.path]
        self.assertEqual(len(apart), 1)                                      # le modifié, à part
        self.assertTrue(apart[0].modified)
        self.assertEqual(passed(app_dir), [])


class Review(unittest.TestCase):
    """Relecture de sûreté du 26/11 de la version avec onglets passés : session propre d'une version déjà là jamais
    touchée (1), manifeste d'une archive portable par la mise à jour par dossier (2), archive sans VectorDrive.ini
    (4), passage retiré quand la nouvelle version n'a pas démarré (5)."""

    params = Switch.params
    update = Switch.update
    running = Switch.running
    setUp = Tabs.setUp
    shut = staticmethod(Tabs.shut)
    shape = Tabs.shape
    tabs = Tabs.tabs
    seen = staticmethod(Tabs.seen)

    def own_session(self, app_dir) -> dict:
        """La session propre d'une version déjà là : un dessin non enregistré, l'index, une copie de secours."""
        d = pathlib.Path(app_dir) / 'donnees' / 'session'
        d.mkdir(parents=True)
        (d / 'session.json').write_text('{"version": 1, "docs": [{"file": "dessin_0.vdz", "modified": true}]}',
                                        encoding='utf-8')
        (d / 'dessin_0.vdz').write_bytes(b'dessin de la 999 jamais enregistre')
        (d / 'session.json.avant_reprise').write_text('secours', encoding='utf-8')
        return {p.name: p.read_bytes() for p in d.iterdir()}

    def test_present_version_keeps_its_own_session(self):
        """(1) GRAVE : 1.29 → 1.34, la 1.34 garde des dessins non enregistrés dans sa session ; la 1.29, relancée,
        repropose la 1.34 déjà là : sa session n'est jamais réécrite ni nettoyée, ses copies de secours restent ; les
        onglets de la 1.29 arrivent à part."""
        from vectordrive.ui import session
        w, old = self.w, self.running()
        (old / 'donnees' / 'session').mkdir(parents=True)
        (old / 'donnees' / 'session' / 'session.json').write_text('{"version": 1, "docs": []}', encoding='utf-8')
        w.new_document()
        w.canvas.doc.add(self.shape(1))
        w.modified = True                                                    # un dessin de l'ancienne, non enregistré
        for i, carry in enumerate((True, False)):
            with self.subTest(reprendre=carry):
                v = f'999.30.{i}'
                present = use(make_version(self.vd, v), **{'donnees/outils/tools.json': '[7]'})
                stamp(present / 'VectorDrive.ini', 1_000_000_000)            # ses réglages : plus anciens
                self.own_session(present)
                for p in (present / 'donnees' / 'session').iterdir():
                    stamp(p, 1_000_000_000)                                  # plus anciens que ceux de l'ancienne
                mine = {p.name: p.read_bytes() for p in (present / 'donnees' / 'session').iterdir()}
                make_zip(self.src, v)
                self.started.clear()
                self.w._closing = False
                res = self.update(old, reprendre=carry)
                self.assertEqual(res['etat'], 'lance', res.get('message'))
                self.assertEqual(res['exe'].parent, present)                 # reprise telle quelle
                own = present / 'donnees' / 'session'
                self.assertEqual({p.name: p.read_bytes() for p in own.iterdir()}, mine)     # intacte
                got = passed(present)
                self.assertEqual(len(got), 1)
                index = session.load_index(got[0])
                self.assertTrue(any(e['modified'] and e['file'] for e in index['docs']))     # les siens, à part

    def test_session_is_never_carried(self):
        AU = au()
        old = use(make_version(tmp(), '1.0.0'), **{'donnees/session/session.json': '{}',
                                                   'donnees/session/dessin_0.vdz': 'x',
                                                   'donnees/session_maj/a/session.json': '{}',
                                                   'donnees/outils/tools.json': '[1]'})
        new = make_version(tmp(), '2.0.0') / 'VectorDrive'
        AU.carry_settings(old, new)
        self.assertTrue((new / 'donnees' / 'outils' / 'tools.json').is_file())
        self.assertFalse((new / 'donnees' / 'session').exists())
        self.assertFalse((new / 'donnees' / 'session_maj').exists())

    def test_failed_start_drops_the_handover_silent_one_keeps_it(self):
        """(5) Arrêtée, en erreur : le passage écrit dans la nouvelle version est retiré (une relance à la main plus
        tard ne rouvrirait qu'une copie périmée) ; muette : gardé (elle démarre peut-être)."""
        w, old = self.w, self.running()

        def refuse(_exe):
            raise OSError('lancement refusé')
        cases = (('arretee', {'proc': Alive(1)}, False), ('erreur', {'lanceur': refuse}, False),
                 ('muette', {'delai': 0.2}, True))
        for i, (state, kw, kept) in enumerate(cases):
            with self.subTest(state):
                make_zip(self.src, f'999.31.{i}')
                self.started.clear()
                self.answer = False
                res = self.update(old, **kw)
                self.assertEqual(res['demarrage'], state)
                self.assertEqual(len(passed(res['exe'].parent)), 1 if kept else 0)
                self.assertTrue(w.docs)                                      # la fenêtre reste, ses onglets aussi
                self.assertTrue(res['exe'].is_file())                        # la version, elle, reste

    def test_present_version_without_ini_stops_before_launch(self):
        """(4) Une version sans VectorDrive.ini ne serait pas portable : les onglets ne lui sont pas passés, rien
        n'est lancé, et c'est dit."""
        old = self.running()
        bare = make_version(self.vd, '999.32.0')
        (bare / 'VectorDrive' / 'VectorDrive.ini').unlink()
        make_zip(self.src, '999.32.0')
        res = self.update(old, reprendre=False)
        self.assertEqual(res['etat'], 'erreur')
        self.assertIn('ne serait pas portable', res['message'])
        self.assertEqual(self.started, [])
        self.assertFalse((bare / 'VectorDrive' / 'donnees').exists())

    def test_archive_without_ini_is_refused(self):
        AU, root = au(), tmp() / 'VD'
        z = tmp() / 'VectorDrive-3.0.0-portable.zip'
        with zipfile.ZipFile(z, 'w') as f:
            f.writestr('VectorDrive/VectorDrive.exe', b'MZ')
        with self.assertRaises(AU.AppUpdateError) as cm:
            AU.install(z, root)
        self.assertIn('VectorDrive.ini', str(cm.exception))
        self.assertFalse((root / 'VectorDrive-3.0.0').exists())

    def test_manifest_archive_goes_through_the_folder_update(self):
        """(2) Application portable, manifeste qui désigne une archive portable : son empreinte vérifiée, puis la
        mise à jour par dossier — jamais recopiée sur l'application en cours ; empreinte fausse : rien."""
        from vectordrive import portable, update
        w = self.w
        z = make_zip(tmp(), '999.33.0')
        up = update.Update('999.33.0', str(z), update.sha256_file(z), portable=True)
        w._upd_silent = False                                                # à la demande (au démarrage : Review2)
        self.addCleanup(setattr, w, '_upd_silent', True)
        seen = []

        def caught(params=None, exec_dialog=True):
            arc = pathlib.Path(params['archive'])
            seen.append((params['version'], arc.read_bytes() == z.read_bytes(), arc))
            return {'etat': 'vu'}
        w.app_update = caught
        self.addCleanup(lambda: w.__dict__.pop('app_update', None))
        with mock.patch.object(portable, 'is_portable', return_value=True), \
                mock.patch.object(portable, 'launch_portable_update', side_effect=AssertionError('sur place')), \
                mock.patch.object(update, 'launch_installer', side_effect=AssertionError('installateur')):
            self.assertEqual(w._update_found(update.Lookup(update=up)), {'etat': 'vu'})
            self.assertEqual([s[:2] for s in seen], [('999.33.0', True)])
            self.assertFalse(seen[0][2].exists())                            # copie provisoire retirée
            bad = update.Update('999.33.0', str(z), '0' * 64, portable=True)
            with mock.patch.object(QMessageBox, 'critical') as box:
                self.assertIsNone(w._update_found(update.Lookup(update=bad)))
            self.assertIn('SHA-256', box.call_args[0][2])
            self.assertEqual(len(seen), 1)

    def test_manifest_archive_installs_in_its_own_folder(self):
        old = self.running()
        z = make_zip(tmp(), '999.34.0')
        arc = z.with_name('archive du manifeste.zip')                        # nom donné par le manifeste
        z.rename(arc)
        res = self.update(old, archive=str(arc), version='999.34.0')
        self.assertEqual(res['etat'], 'lance', res.get('message'))
        self.assertEqual(res['exe'].parent, self.vd / 'VectorDrive-999.34.0' / 'VectorDrive')
        self.assertTrue((old / 'VectorDrive.exe').is_file())                 # l'ancienne, intacte
        self.assertTrue((self.vd / 'zips' / 'VectorDrive-999.34.0-portable.zip').is_file())
        self.assertEqual(len(passed(res['exe'].parent)), 1)


class Review2(unittest.TestCase):
    """Deuxième relecture du 26/11 : index illisible ou d'une autre version jamais effacé (1) ; mise à jour sans
    dessin, fichier introuvable : jamais bloqué (2) ; effacement raté après la réouverture : pas de doublons (3) ;
    passage d'une tentative restée sans réponse retiré à la suivante (4) ; question d'abord au démarrage."""

    params = Switch.params
    update = Switch.update
    running = Switch.running
    setUp = Tabs.setUp
    shut = staticmethod(Tabs.shut)
    shape = Tabs.shape
    tabs = Tabs.tabs
    seen = staticmethod(Tabs.seen)
    new_window = Tabs.new_window
    handed = Tabs.handed

    def test_unreadable_or_foreign_index_is_kept_untouched(self):
        """(1) GRAVE : un index illisible, verrouillé ou d'une version à venir bloque le passage — jamais réécrit,
        jamais effacé, et dit ; un index d'une version plus ancienne est accepté."""
        from vectordrive.ui import session
        want, _a, app_dir, folder = self.handed('999.40.0')
        root = self.AU.handover_root(app_dir)
        index = folder / 'session.json'
        good = index.read_bytes()
        for label, data in (('illisible', b'{"version": 1, "docs": [ coupe'), ('vide', b''),
                            ('version à venir', good.replace(b'"version": 1', b'"version": 99')),
                            ('pas un index', b'[1, 2]')):
            with self.subTest(label):
                index.write_bytes(data)
                new = self.new_window()
                self.assertEqual(new.reopen_after_update(root), 0)
                self.assertEqual(index.read_bytes(), data)                   # jamais réécrit…
                self.assertEqual(passed(app_dir), [folder])                  # … ni effacé
                self.assertTrue(any(folder.glob('dessin_*.vdz')))
                self.assertEqual(self.AU.tries_of(folder), 0)
                self.assertIn(str(folder), new.statusBar().currentMessage())
        index.write_bytes(good)                                              # écrit par une version d'avant : repris
        new = self.new_window()
        with mock.patch.object(session, 'VERSION', 2):
            self.assertEqual(new.reopen_after_update(root), len(want))
        self.assertEqual(passed(app_dir), [])

    def test_update_without_drawing_never_blocks(self):
        """(2) Le cas le plus courant : un seul onglet, vide, jamais touché — rien d'écrit pour lui, le passage se
        retire au lancement, aucun message à chaque lancement."""
        w, old = self.w, self.running()
        self.assertEqual(len(w.docs), 1)
        self.assertTrue(w.docs[0].pristine())
        make_zip(self.src, '999.41.0')
        res = self.update(old)
        self.assertEqual((res['etat'], res['onglets']), ('lance', 0))
        app_dir = res['exe'].parent
        new = self.new_window()
        self.assertEqual(new.reopen_after_update(self.AU.handover_root(app_dir)), 0)
        self.assertEqual(passed(app_dir), [])
        self.assertFalse(self.AU.handover_root(app_dir).exists())

    def test_missing_file_is_told_once_without_blocking(self):
        """(2) Un fichier intact passé par son seul chemin, introuvable au lancement (partage absent) : dit par la
        réouverture, sans bloquer le passage ; les dessins, eux, reviennent."""
        want, _a, app_dir, folder = self.handed('999.42.0')
        intact = next(p for (_n, p, modified, _pin, _t) in want if p and not modified)
        os.replace(intact, intact + '.ailleurs')
        new = self.new_window()
        self.assertEqual(new.reopen_after_update(self.AU.handover_root(app_dir)), len(want) - 1)
        self.assertEqual(passed(app_dir), [])                                # pas bloqué
        self.assertIn('introuvable', new.statusBar().currentMessage())

    def test_failed_removal_never_reopens_twice(self):
        """(3) La réouverture a réussi mais l'effacement échoue (antivirus, indexeur) : l'index est déjà renommé, le
        passage ne revient pas ; il est nettoyé au lancement suivant."""
        want, _a, app_dir, folder = self.handed('999.43.0')
        root = self.AU.handover_root(app_dir)
        new = self.new_window()
        with mock.patch.object(self.AU, 'drop_handover', return_value=False):
            self.assertEqual(new.reopen_after_update(root), len(want))
        self.assertTrue(folder.is_dir())                                     # pas effacé…
        self.assertTrue((folder / 'session.json.rouvert').is_file())         # … mais retiré d'un coup
        self.assertEqual(passed(app_dir), [])
        again = self.new_window()
        self.assertEqual(again.reopen_after_update(root), 0)                 # jamais deux fois
        self.assertEqual(len(again.docs), 1)
        self.assertFalse(folder.exists())                                    # nettoyé

    def test_locked_index_still_never_reopens_twice(self):
        """(3e relecture) L'index rouvert ne se renomme pas (antivirus) et l'effacement échoue : le témoin neuf
        `rouvert` suffit — jamais rouvert de nouveau, nettoyé au lancement suivant."""
        real = os.replace

        def locked(src, dst, *a, **k):
            if str(dst).endswith('session.json.rouvert'):
                raise PermissionError(13, 'verrouillé', str(src))
            return real(src, dst, *a, **k)

        want, _a, app_dir, folder = self.handed('999.45.0')
        root = self.AU.handover_root(app_dir)
        with mock.patch.object(self.AU, 'drop_handover', return_value=False), \
                mock.patch.object(self.AU.os, 'replace', locked):
            self.assertEqual(self.new_window().reopen_after_update(root), len(want))
        self.assertTrue((folder / 'session.json').is_file())                 # index resté…
        self.assertTrue((folder / 'rouvert').is_file())                      # … mais témoin écrit
        self.assertEqual(passed(app_dir), [])
        again = self.new_window()
        self.assertEqual(again.reopen_after_update(root), 0)                 # jamais deux fois
        self.assertEqual(len(again.docs), 1)
        self.assertFalse(folder.exists())                                    # nettoyé

    def test_unmarkable_handover_is_held_not_reopened(self):
        """(3e relecture) Ni témoin ni renommage possibles : les tentatives au maximum, jamais rouvert de nouveau,
        rien de perdu."""
        want, _a, app_dir, folder = self.handed('999.45.1')
        root = self.AU.handover_root(app_dir)
        with mock.patch.object(self.AU, 'retire_handover', return_value=False):
            self.assertEqual(self.new_window().reopen_after_update(root), len(want))
        self.assertEqual(self.AU.tries_of(folder), self.AU.MAX_TRIES)
        again = self.new_window()
        self.assertEqual(again.reopen_after_update(root), 0)                 # jamais deux fois
        self.assertEqual(len(again.docs), 1)
        self.assertTrue(folder.is_dir())                                     # gardé, rien de perdu

    def test_second_attempt_replaces_the_unanswered_handover(self):
        """(4) Une tentative restée sans réponse (muette) laisse son passage ; la suivante le retire s'il n'a jamais
        été rouvert (ses onglets sont toujours ici) — pas deux passages des mêmes onglets. Rouvert entre-temps (une
        tentative comptée) : laissé."""
        w, old = self.w, self.running()
        self.tabs()
        make_zip(self.src, '999.44.0')
        self.answer = False
        first = self.update(old, delai=0.2)
        self.assertEqual(first['demarrage'], 'muette')
        one = passed(first['exe'].parent)
        self.assertEqual(len(one), 1)
        make_zip(self.src, '999.44.1')                                       # nouvelle tentative, une autre version
        self.started.clear()
        self.answer = True
        second = self.update(old)
        self.assertEqual(second['etat'], 'lance')
        self.assertEqual(passed(first['exe'].parent), [])                    # l'ancien passage : retiré
        self.assertEqual(len(passed(second['exe'].parent)), 1)
        w._closing = False                                                   # rouvert entre-temps : laissé
        make_zip(self.src, '999.44.2')
        self.started.clear()
        self.answer = False
        third = self.update(old, delai=0.2)
        kept = passed(third['exe'].parent)[0]
        self.AU.note_try(kept, 1)
        make_zip(self.src, '999.44.3')
        self.started.clear()
        self.answer = True
        self.update(old)
        self.assertEqual(passed(third['exe'].parent), [kept])

    def test_silent_start_asks_before_copying(self):
        """Remarque : au démarrage (recherche silencieuse), le manifeste d'une archive portable fait d'abord poser la
        question ; rien n'est copié ni téléchargé avant."""
        from vectordrive import portable, update
        w = self.w
        z = make_zip(tmp(), '999.45.0')
        up = update.Update('999.45.0', str(z), update.sha256_file(z), portable=True)
        calls = []
        w.app_update = lambda params=None, exec_dialog=True: calls.append(params) or {'etat': 'vu'}
        self.addCleanup(lambda: w.__dict__.pop('app_update', None))
        w._upd_silent = True
        self.addCleanup(setattr, w, '_upd_silent', True)
        with mock.patch.object(portable, 'is_portable', return_value=True):
            with mock.patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No), \
                    mock.patch.object(update, 'fetch', side_effect=AssertionError('copiée avant la question')):
                self.assertIsNone(w._update_found(update.Lookup(update=up)))
            self.assertEqual(calls, [])
            with mock.patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
                self.assertEqual(w._update_found(update.Lookup(update=up)), {'etat': 'vu'})
        self.assertEqual([c['version'] for c in calls], ['999.45.0'])


class Remarks(unittest.TestCase):
    """Remarques de la relecture du 26/11 : recherche du démarrage seulement dans la fenêtre qui tient le canal ;
    archive « (1).zip » ignorée, et dit."""

    setUpClass = classmethod(Check.setUpClass.__func__)
    tearDownClass = classmethod(Check.tearDownClass.__func__)

    def test_startup_check_only_in_the_window_holding_the_channel(self):
        w = self.w
        calls = []
        with mock.patch.object(w, 'check_updates', side_effect=lambda **kw: calls.append(kw)):
            w._startup_update_check()                                        # --nouvelle-fenetre, script : rien
            self.assertEqual(calls, [])
            w._instance_server = object()
            try:
                w._startup_update_check()
            finally:
                del w._instance_server
        self.assertEqual(calls, [{'silent': True}])

    def test_odd_archive_name_is_told(self):
        U, AU, d = upd(), au(), tmp()
        odd = make_zip(d, '999.40.0')
        odd.rename(odd.with_name('VectorDrive-999.40.0-portable (1).zip'))
        names = []
        self.assertEqual(AU.scan(d, names), [])
        self.assertEqual(names, ['VectorDrive-999.40.0-portable (1).zip'])
        got = U.look('', '1.0.0', folders=[d], edition='')
        self.assertIsNone(got.update)
        text = self.w._update_seen(got)
        self.assertIn('VectorDrive-999.40.0-portable (1).zip', text)
        self.assertIn('Ignorées', text)

    def test_handover_never_removes_anything_else(self):
        AU = au()
        other = tmp() / 'session'
        other.mkdir()
        (other / 'session.json').write_text('{}', encoding='utf-8')
        self.assertFalse(AU.drop_handover(other))                            # pas un passage : jamais effacé
        self.assertTrue((other / 'session.json').is_file())
        app_dir = tmp()
        a, b = AU.new_handover(app_dir), AU.new_handover(app_dir)
        self.assertNotEqual(a, b)                                            # un dossier par passage, jamais réécrit
        self.assertTrue(AU.drop_handover(a))
        self.assertTrue(b.is_dir())


if __name__ == '__main__':
    unittest.main()
