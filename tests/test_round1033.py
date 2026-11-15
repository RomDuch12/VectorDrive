"""Round 1033 : demande du 15/11 « le plugin BFM doit etre ajoutable par la suite depuis l'open source, sur win et
mac ». Options › Plugins › « Ajouter un plugin… » : l'archive .zip d'un plugin est décompressée dans le dossier des
plugins de l'utilisateur, ses bibliothèques Python (`_lib/`) avec ; le plugin est chargé au démarrage suivant."""
import os
import pathlib
import sys
import tempfile
import textwrap
import unittest
import zipfile
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1033.ini'))

from PySide6.QtWidgets import QApplication, QLabel, QPushButton  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive import plugins as PL  # noqa: E402
from vectordrive import portable  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIB_MOD = 'essai_lib_r1033'
PKG = 'essai_plugin_r1033'


def plugin_init(version: str) -> str:
    return textwrap.dedent(f'''
        PLUGIN = {{'nom': 'Essai 1033', 'version': '{version}', 'api': 1, 'licence': 'MIT'}}
        SEEN = []

        def register(api):
            import {LIB_MOD}                       # une bibliothèque apportée par le plugin, dans _lib
            SEEN.append({LIB_MOD}.VALUE)
    ''')


def make_zip(path: pathlib.Path, version='1.0', extra: dict | None = None, lib=True) -> pathlib.Path:
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr(f'{PKG}/__init__.py', plugin_init(version))
        z.writestr(f'{PKG}/donnees/table.json', '{"v": "%s"}' % version)
        if lib:
            z.writestr(f'_lib/{LIB_MOD}/__init__.py', 'VALUE = 42\n')
        z.writestr('LISEZMOI.txt', 'pas un plugin')
        for name, text in (extra or {}).items():
            z.writestr(name, text)
    return path


class Base(unittest.TestCase):

    def setUp(self):
        PL.reset()
        self.off = os.environ.pop(PL.ENV_OFF, None)               # ces essais chargent des plugins
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.path = list(sys.path)

    def tearDown(self):
        PL.reset()
        sys.path[:] = self.path
        for m in [m for m in sys.modules if m.startswith((PKG, LIB_MOD))]:
            del sys.modules[m]
        self.tmp.cleanup()
        if self.off is not None:
            os.environ[PL.ENV_OFF] = self.off

    def need(self):
        self.assertTrue(all(hasattr(PL, n) for n in ('install', 'ArchiveError', 'user_dir')),
                        'avant : aucun moyen d’ajouter un plugin depuis l’application')


class Install(Base):

    def test_the_archive_is_unpacked_and_its_libraries_found(self):
        install = getattr(PL, 'install', None)
        self.assertIsNotNone(install, 'avant : aucun moyen d’ajouter un plugin depuis l’application')
        dest = self.dir / 'plugins'
        names = install(make_zip(self.dir / 'essai.zip'), dest)
        self.assertEqual(names, [PKG])
        self.assertTrue((dest / PKG / '__init__.py').is_file())
        self.assertTrue((dest / PKG / 'donnees' / 'table.json').is_file())   # des fichiers vrais (données lues)
        self.assertTrue((dest / '_lib' / LIB_MOD / '__init__.py').is_file())
        self.assertFalse((dest / 'LISEZMOI.txt').exists())                    # rien d'autre de l'archive
        info = PL.load([dest], force=True)
        self.assertEqual([(i.module, i.error) for i in info], [(PKG, '')])   # _lib dans sys.path avant le chargement
        self.assertEqual(sys.modules[PKG].SEEN, [42])
        self.assertEqual(sys.path[-1], str(dest / '_lib'))                   # à la fin : le cœur reste prioritaire

    def test_a_new_version_replaces_the_old_one(self):
        self.need()
        dest = self.dir / 'plugins'
        PL.install(make_zip(self.dir / 'v1.zip', '1.0', {f'{PKG}/ancien.py': 'X = 1\n'}), dest)
        dest.joinpath('copie-1.0.zip').write_bytes((self.dir / 'v1.zip').read_bytes())   # rangée à la main avant
        PL.install(make_zip(self.dir / 'v2.zip', '2.0'), dest)
        self.assertIn("'version': '2.0'", (dest / PKG / '__init__.py').read_text(encoding='utf-8'))
        self.assertFalse((dest / PKG / 'ancien.py').exists())                # le paquet remplacé en entier
        self.assertTrue((dest / '_lib' / LIB_MOD).is_dir())
        self.assertFalse((dest / 'copie-1.0.zip').exists())                  # l'autre version n'est plus chargée
        self.assertTrue((dest / 'copie-1.0.zip.ancien').is_file())           # mais elle est gardée
        self.assertEqual([p.name for p in dest.iterdir() if p.name.startswith('.ajout_')], [])

    def test_refused_archives(self):
        self.need()
        dest = self.dir / 'plugins'
        bad = self.dir / 'pas_un_zip.zip'
        bad.write_text('texte', encoding='utf-8')
        cases = {'illisible': bad}
        empty = self.dir / 'vide.zip'
        with zipfile.ZipFile(empty, 'w') as z:
            z.writestr('outil/__init__.py', 'X = 1\n')                       # un paquet, mais pas un plugin
            z.writestr('_lib/x/__init__.py', 'def register(api): pass\n')    # _lib n'est jamais un plugin
        cases['vide'] = empty
        core = self.dir / 'coeur.zip'
        with zipfile.ZipFile(core, 'w') as z:
            z.writestr('vectordrive/__init__.py', 'def register(api): pass\n')
        cases['reserve'] = core
        cases['chemin'] = make_zip(self.dir / 'sortie.zip', extra={f'{PKG}/../../dehors.txt': 'x'})
        cases['paquet'] = make_zip(self.dir / 'aide.zip', extra={'aide_r1033/__init__.py': 'X = 1\n'})  # pas dans _lib
        for kind, archive in cases.items():
            with self.assertRaises(PL.ArchiveError, msg=kind) as cm:
                PL.install(archive, dest)
            self.assertEqual(cm.exception.kind, kind)
        self.assertIn('aide_r1033', cm.exception.detail)
        self.assertFalse((self.dir / 'dehors.txt').exists())
        self.assertFalse((dest / PKG).exists())

    def v1(self, dest):
        PL.install(make_zip(self.dir / 'v1.zip', '1.0', {f'{PKG}/ancien.py': 'X = 1\n',
                                                         f'_lib/{LIB_MOD}/vieux.py': 'X = 1\n'}), dest)

    def assert_v1(self, dest):
        self.assertTrue((dest / PKG / 'ancien.py').is_file())
        self.assertIn("'version': '1.0'", (dest / PKG / '__init__.py').read_text(encoding='utf-8'))
        self.assertTrue((dest / '_lib' / LIB_MOD / 'vieux.py').is_file())   # ses bibliothèques aussi
        self.assertEqual([p.name for p in dest.iterdir() if p.name.startswith(('.ajout_', '.anciens_'))], [])

    def busy(self, also=lambda src: False):
        real = pathlib.Path.replace

        def replace(src, target):                       # le nouveau paquet ne peut pas prendre sa place
            if (src.name == PKG and src.parent.name.startswith('.ajout_')) or also(src):
                raise PermissionError('fichier en service')
            return real(src, target)
        return mock.patch.object(pathlib.Path, 'replace', replace)

    def test_a_failed_replacement_keeps_the_old_version(self):
        self.need()
        dest = self.dir / 'plugins'
        self.v1(dest)
        with self.busy(), self.assertRaises(OSError):
            PL.install(make_zip(self.dir / 'v2.zip', '2.0'), dest)
        self.assert_v1(dest)                                                 # avant : l'ancien supprimé d'abord

    def test_nothing_is_erased_when_even_the_restore_fails(self):
        self.need()
        dest = self.dir / 'plugins'
        self.v1(dest)
        with self.busy(lambda src: src.parent.name.startswith('.anciens_')), self.assertRaises(OSError) as cm:
            PL.install(make_zip(self.dir / 'v2.zip', '2.0'), dest)
        kept = [p for p in dest.iterdir() if p.name.startswith('.anciens_')]
        self.assertEqual(len(kept), 1)
        self.assertIn(str(kept[0]), str(cm.exception))                       # dit où est l'ancienne version
        self.assertEqual(len(list(kept[0].glob('*/ancien.py'))), 1)
        self.assertEqual(len(list(kept[0].glob('*/vieux.py'))), 1)

    def test_a_damaged_archive_changes_nothing(self):
        self.need()
        dest = self.dir / 'plugins'
        self.v1(dest)
        bad = make_zip(self.dir / 'v2.zip', '2.0')
        raw = bad.read_bytes()
        self.assertEqual(raw.count(b'{"v": "2.0"}'), 1)
        bad.write_bytes(raw.replace(b'{"v": "2.0"}', b'{"v": "9.0"}'))  # un membre abîmé (CRC faux)
        name = make_zip(self.dir / 'nom.zip', '2.0', {f'{PKG}/donnees/€.json': '{}'})
        raw = name.read_bytes()
        self.assertEqual(raw.count('€'.encode()), 2)
        name.write_bytes(raw.replace('€'.encode(), b'\xff\xfe\xfd'))         # un nom mal encodé (UTF-8 annoncé)
        for archive in (bad, name):
            with self.assertRaises(PL.ArchiveError) as cm:                   # avant : BadZipFile, UnicodeDecodeError
                PL.install(archive, dest)
            self.assertEqual(cm.exception.kind, 'illisible')
            self.assert_v1(dest)
        folder = self.dir / 'rangees'
        folder.mkdir()
        name.replace(folder / 'nom.zip')                                     # rangée telle quelle : pas d'arrêt
        self.assertEqual(PL._candidates(folder), [])
        self.assertEqual(PL.load([folder], force=True), [])

    def test_archives_in_the_folder(self):
        self.need()
        dest = self.dir / 'plugins'
        dest.mkdir()
        make_zip(dest / 'essai.zip')                                        # choisie dans le dossier des plugins
        dest.joinpath('essai.zip.ancien').write_bytes(b'copie d avant')
        make_zip(dest / 'VIEUX.ZIP')                                        # « .ZIP » : chargée aussi sous macOS
        make_zip(dest / 'deux.zip', extra={'autre_r1033/__init__.py': 'def register(api): pass\n'})
        self.assertEqual(PL.install(dest / 'essai.zip', dest), [PKG])
        self.assertTrue((dest / PKG / '__init__.py').is_file())
        self.assertFalse((dest / 'essai.zip').exists())                      # sinon chargée en double
        self.assertEqual((dest / 'essai.zip.ancien').read_bytes(), b'copie d avant')
        self.assertTrue((dest / 'essai.zip.ancien2').is_file())              # la copie d'avant n'est pas écrasée
        self.assertTrue((dest / 'VIEUX.ZIP.ancien').is_file())
        self.assertTrue((dest / 'deux.zip').is_file())                       # elle apporte un autre plugin : gardée
        self.assertEqual(PL.archives_with(dest, [PKG]), [dest / 'deux.zip'])

    def test_libraries_are_updated_item_by_item(self):
        self.need()
        dest = self.dir / 'plugins'
        PL.install(make_zip(self.dir / 'v1.zip', '1.0', {
            f'_lib/{LIB_MOD}/vieux.py': 'X = 1\n', '_lib/et_lib-1.0.dist-info/METADATA': 'Version: 1.0\n',
            '_lib/autre_r1033/__init__.py': 'Y = 2\n'}), dest)
        PL.install(make_zip(self.dir / 'v2.zip', '2.0', {'_lib/et_lib-2.0.dist-info/METADATA': 'Version: 2.0\n'}),
                   dest)
        lib = dest / '_lib'
        self.assertFalse((lib / LIB_MOD / 'vieux.py').exists())              # la bibliothèque remplacée en entier
        self.assertTrue((lib / LIB_MOD / '__init__.py').is_file())
        self.assertFalse((lib / 'et_lib-1.0.dist-info').exists())            # pas deux versions annoncées
        self.assertTrue((lib / 'et_lib-2.0.dist-info' / 'METADATA').is_file())
        self.assertTrue((lib / 'autre_r1033' / '__init__.py').is_file())     # les autres gardées


class LibrariesOfAPlugin(Base):

    def test_lib_inside_an_archive_left_zipped(self):
        d = self.dir / 'plugins'
        d.mkdir()
        make_zip(d / 'essai.zip')                                           # rangée telle quelle, sans décompresser
        info = PL.load([d], force=True)
        self.assertEqual([(i.module, i.error) for i in info], [(PKG, '')])   # avant : ModuleNotFoundError
        self.assertEqual(sys.modules[PKG].SEEN, [42])

    def test_a_lib_folder_is_never_a_plugin(self):
        d = self.dir / 'plugins'
        (d / '_lib' / 'x').mkdir(parents=True)
        (d / '_lib' / '__init__.py').write_text('def register(api): pass\n', encoding='utf-8')
        self.assertEqual(PL._candidates(d), [])
        with zipfile.ZipFile(d / 'rangee.zip', 'w') as z:                   # ni dans une archive rangée telle quelle
            z.writestr('_lib/__init__.py', 'def register(api): pass\n')
        self.assertEqual(PL._candidates(d), [])


class OptionsPage(Base):

    def dialog(self):
        from vectordrive.ui.options import OptionsDialog
        dlg = OptionsDialog(portable.settings(), page='Plugins')
        self.addCleanup(dlg.deleteLater)
        return dlg

    def test_add_a_plugin_from_the_options(self):
        self.need()
        dest = self.dir / 'donnees' / 'plugins'
        with mock.patch.object(PL, 'user_dir', lambda: dest):
            dlg = self.dialog()
            add = dlg.findChild(QPushButton, 'addPluginButton')
            self.assertIsNotNone(add)                                        # avant : seulement des dossiers en plus
            self.assertEqual(add.text(), 'Ajouter un plugin…')
            status = dlg.findChild(QLabel, 'pluginStatus')
            self.assertEqual(dlg.add_plugin(str(make_zip(self.dir / 'essai.zip'))), [PKG])
            self.assertTrue((dest / PKG / '__init__.py').is_file())
            self.assertIn(PKG, status.text())
            self.assertIn('prochain démarrage', status.text())
            bad = self.dir / 'mauvais.zip'
            with zipfile.ZipFile(bad, 'w') as z:
                z.writestr('rien.txt', 'x')
            self.assertEqual(dlg.add_plugin(str(bad)), [])
            self.assertIn('Plugin non ajouté', status.text())
            self.assertIn('aucun plugin', status.text())
            from PySide6.QtWidgets import QFileDialog
            with mock.patch.object(QFileDialog, 'getOpenFileName', return_value=('', '')):
                self.assertEqual(dlg.add_plugin(), [])                       # fenêtre de choix fermée : rien

    def test_only_the_portable_plugins_folder_keeps_priority(self):
        self.need()
        dest = self.dir / 'donnees' / 'plugins'
        app = self.dir / 'portable'
        with mock.patch.object(PL, 'user_dir', lambda: dest), \
                mock.patch.object(portable, 'app_dir', lambda: app):
            dlg = self.dialog()
            status = dlg.findChild(QLabel, 'pluginStatus')
            PL.REGISTRY.plugins[:] = [PL.PluginInfo(module=PKG, path=str(self.dir / 'reglages'))]   # passe après
            self.assertEqual(dlg.add_plugin(str(make_zip(self.dir / 'essai.zip'))), [PKG])
            self.assertNotIn('prioritaire', status.text())                   # avant : averti à tort
            for where in (app / 'plugins', app / 'plugins' / 'essai.zip'):  # passe avant : averti
                PL.REGISTRY.plugins[:] = [PL.PluginInfo(module=PKG, path=str(where))]
                self.assertEqual(dlg.add_plugin(str(make_zip(self.dir / 'essai.zip'))), [PKG])
                self.assertIn('prioritaire', status.text(), where)
                self.assertNotIn('Redémarrez', status.text())
            PL.REGISTRY.plugins[:] = [PL.PluginInfo(module=PKG, path=str(dest))]   # celui qu'on remplace
            make_zip(dest / 'deux.zip', extra={'autre_r1033/__init__.py': 'def register(api): pass\n'})
            self.assertEqual(dlg.add_plugin(str(make_zip(self.dir / 'essai.zip'))), [PKG])
            self.assertNotIn('prioritaire', status.text())
            self.assertIn('Redémarrez VectorDrive', status.text())           # ses fichiers changés sous lui
            self.assertIn('deux.zip', status.text())                         # l'archive gardée est nommée

    def test_an_unwritable_plugin_folder(self):
        self.need()
        blocker = self.dir / 'fichier'
        blocker.write_text('x', encoding='utf-8')
        from PySide6.QtGui import QDesktopServices
        with mock.patch.object(PL, 'user_dir', lambda: blocker / 'plugins'), \
                mock.patch.object(QDesktopServices, 'openUrl') as opened:
            dlg = self.dialog()
            dlg.findChild(QPushButton, 'pluginFolderButton').click()        # avant : exception dans le bouton
            self.assertIn('impossible à créer', dlg.findChild(QLabel, 'pluginStatus').text())
        opened.assert_not_called()

    def test_open_the_plugin_folder(self):
        self.need()
        dest = self.dir / 'donnees' / 'plugins'
        from PySide6.QtGui import QDesktopServices
        with mock.patch.object(PL, 'user_dir', lambda: dest), \
                mock.patch.object(QDesktopServices, 'openUrl') as opened:
            dlg = self.dialog()
            dlg.findChild(QPushButton, 'pluginFolderButton').click()
        self.assertTrue(dest.is_dir())
        self.assertEqual(pathlib.Path(opened.call_args[0][0].toLocalFile()), dest)


class MacAndBuilds(unittest.TestCase):

    def test_user_data_on_macos(self):
        home = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(__import__('shutil').rmtree, home, True)
        new = home / 'Library' / 'Application Support' / 'VectorDrive'
        with mock.patch.object(portable, 'is_portable', return_value=False), \
                mock.patch.object(portable.sys, 'platform', 'darwin'), \
                mock.patch.object(pathlib.Path, 'home', return_value=home):
            self.assertEqual(portable.data_dir(), new)
            (home / 'VectorDrive').mkdir()                                   # données d'une première version macOS
            self.assertEqual(portable.data_dir(), home / 'VectorDrive')       # gardées où elles sont
            new.mkdir(parents=True)
            self.assertEqual(portable.data_dir(), new)
        with mock.patch.object(portable, 'is_portable', return_value=False), \
                mock.patch.object(portable.sys, 'platform', 'win32'), \
                mock.patch.dict(os.environ, {'LOCALAPPDATA': str(pathlib.Path('C:/Local'))}):
            self.assertEqual(portable.data_dir(), pathlib.Path('C:/Local') / 'VectorDrive')
        user_dir = getattr(PL, 'user_dir', None)
        self.assertIsNotNone(user_dir)
        self.assertEqual(user_dir(), portable.data_dir() / 'plugins')
        import ast                                                           # le rapport des essais au même endroit
        src = (ROOT / 'VectorDrive.py').read_text(encoding='utf-8')
        fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == '_report_file')
        seg = ast.get_source_segment(src, fn)
        self.assertIn("'darwin'", seg)
        self.assertIn("'Application Support'", seg)

    def test_builds_carry_the_standard_library_of_plugin_libraries(self):
        for spec in (ROOT / 'VectorDrive.spec', ROOT / 'outils' / 'macos' / 'VectorDrive-macos.spec'):
            text = spec.read_text(encoding='utf-8')
            for mod in ("'xml.etree.ElementTree'", "'zipfile'", "'xml.sax.saxutils'", "'numbers'"):
                self.assertIn(mod, text, spec.name)
        doc = (ROOT / 'docs' / 'ARCHITECTURE.md').read_text(encoding='utf-8')
        self.assertIn('Ajouter un plugin', doc)
        self.assertIn('_lib', doc)


if __name__ == '__main__':
    unittest.main()
