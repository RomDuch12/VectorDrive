"""Round 1035 : demande du 15/11 « le plugin BFM doit etre ajoutable par la suite depuis l'open source, sur win et
mac ». L'archive ajoutable d'un plugin se fabrique avec le cœur : `plugins.build_archive` et `outils/plugin_zip.py`
— le paquet à la racine, ses bibliothèques Python pures dans `_lib` avec leurs « .dist-info »."""
import contextlib
import importlib
import importlib.util
import io
import os
import pathlib
import sys
import tempfile
import textwrap
import unittest
import warnings
import zipfile
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1035.ini'))

from vectordrive import plugins as PL  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = 'essai_plugin_r1035'
LIB = 'essai_lib_r1035'
MOD = 'essai_mod_r1035'
COMP = 'essai_comp_r1035'
TWO = ('deux_a_r1035', 'deux_b_r1035')
BS = 'essai_bs_r1035'
TOOL = ROOT / 'outils' / 'plugin_zip.py'


def write(path: pathlib.Path, text: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


class Base(unittest.TestCase):

    def setUp(self):
        PL.reset()
        self.off = os.environ.pop(PL.ENV_OFF, None)               # un essai charge le plugin fabriqué
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.path = list(sys.path)
        # le plugin : son paquet, des données, et ce qui ne doit pas partir (caches, fichiers cachés)
        self.pkg = self.dir / 'src' / PKG
        write(self.pkg / '__init__.py', textwrap.dedent(f'''
            PLUGIN = {{'nom': 'Essai 1035', 'version': '1.0', 'api': 1, 'licence': 'MIT'}}
            SEEN = []

            def register(api):
                import {LIB}                             # apportée par le plugin, dans _lib
                SEEN.append({LIB}.VALUE)
        '''))
        write(self.pkg / 'donnees' / 'table.json', '{"v": 1}')
        write(self.pkg / 'sub' / 'm.py', 'X = 1\n')
        (self.pkg / 'sub' / 'm.pyc').write_bytes(b'cache')
        (self.pkg / '__pycache__').mkdir()
        (self.pkg / '__pycache__' / 'm.cpython-313.pyc').write_bytes(b'cache')
        (self.pkg / '.DS_Store').write_bytes(b'finder')
        write(self.pkg / '.git' / 'config', '[core]\n')
        # les bibliothèques du poste : une pure avec ses .dist-info, un module seul, une compilée (sous macOS)
        self.site = self.dir / 'site'
        write(self.site / LIB / '__init__.py', 'VALUE = 42\n')
        (self.site / LIB / '__pycache__').mkdir()
        (self.site / LIB / '__pycache__' / '__init__.cpython-313.pyc').write_bytes(b'cache')
        info = self.site / f'{LIB}-1.2.dist-info'
        write(info / 'METADATA', 'Metadata-Version: 2.1\nName: essai-lib-r1035\nVersion: 1.2\n')
        write(info / 'top_level.txt', f'{LIB}\n')
        write(info / 'RECORD', f'{LIB}/__init__.py,,\n{LIB}-1.2.dist-info/METADATA,,\n'
                               f'{LIB}-1.2.dist-info/top_level.txt,,\n{LIB}-1.2.dist-info/RECORD,,\n')
        write(self.site / f'{MOD}.py', 'Y = 2\n')                     # sa distribution a un autre nom
        other = self.site / 'autre_nom_r1035-0.1.dist-info'
        write(other / 'METADATA', 'Metadata-Version: 2.1\nName: autre-nom-r1035\nVersion: 0.1\n')
        write(other / 'top_level.txt', f'{MOD}\n')
        write(other / 'RECORD', f'{MOD}.py,,\nautre_nom_r1035-0.1.dist-info/METADATA,,\n'
                                f'autre_nom_r1035-0.1.dist-info/top_level.txt,,\n'
                                f'autre_nom_r1035-0.1.dist-info/RECORD,,\n')
        for m in TWO:                                                  # deux modules d'une même distribution
            write(self.site / f'{m}.py', 'Z = 3\n')
        two = self.site / 'deux_r1035-1.0.dist-info'
        write(two / 'METADATA', 'Metadata-Version: 2.1\nName: deux-r1035\nVersion: 1.0\n')
        write(two / 'top_level.txt', ''.join(f'{m}\n' for m in TWO))
        write(two / 'RECORD', ''.join(f'{m}.py,,\n' for m in TWO) + 'deux_r1035-1.0.dist-info/METADATA,,\n'
                              'deux_r1035-1.0.dist-info/top_level.txt,,\ndeux_r1035-1.0.dist-info/RECORD,,\n')
        write(self.site / f'{BS}.py', 'W = 4\n')                       # son RECORD aux barres inverses
        bs = self.site / f'{BS}-1.0.dist-info'
        write(bs / 'METADATA', f'Metadata-Version: 2.1\nName: {BS}\nVersion: 1.0\n')
        write(bs / 'RECORD', ''.join(f'{BS}-1.0.dist-info{chr(92)}{n},,\n' for n in ('METADATA', 'RECORD'))
              + f'{BS}.py,,\n')
        write(self.site / COMP / '__init__.py', 'from ._vite import f\n')
        (self.site / COMP / '_vite.cpython-313-darwin.so').write_bytes(b'\x7fELF')
        sys.path.insert(0, str(self.site))
        importlib.invalidate_caches()

    def tearDown(self):
        PL.reset()
        sys.path[:] = self.path
        importlib.invalidate_caches()
        for m in [m for m in sys.modules if m.startswith((PKG, LIB, MOD, COMP, BS, *TWO))]:
            del sys.modules[m]
        self.tmp.cleanup()
        if self.off is not None:
            os.environ[PL.ENV_OFF] = self.off

    def build(self, *args, **kw):
        fn = getattr(PL, 'build_archive', None)
        self.assertIsNotNone(fn, 'avant : rien pour fabriquer l’archive d’un plugin')
        return fn(*args, **kw)


class Build(Base):

    def test_the_archive_holds_the_package_and_its_libraries(self):
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter('always')
            out = self.build(self.pkg, self.dir / 'dist' / 'essai.zip', [LIB, MOD, *TWO, BS])
        self.assertEqual([str(w.message) for w in seen if 'Duplicate' in str(w.message)], [])
        self.assertEqual(out, self.dir / 'dist' / 'essai.zip')
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
        self.assertEqual(len(names), len(set(names)))                        # .dist-info commun : une fois
        for want in (f'{PKG}/__init__.py', f'{PKG}/donnees/table.json', f'{PKG}/sub/m.py', f'_lib/{LIB}/__init__.py',
                     f'_lib/{LIB}-1.2.dist-info/METADATA', f'_lib/{LIB}-1.2.dist-info/RECORD', f'_lib/{MOD}.py',
                     '_lib/autre_nom_r1035-0.1.dist-info/METADATA', '_lib/deux_a_r1035.py', '_lib/deux_b_r1035.py',
                     '_lib/deux_r1035-1.0.dist-info/METADATA', f'_lib/{BS}.py', f'_lib/{BS}-1.0.dist-info/METADATA'):
            self.assertIn(want, names)
        for n in names:
            self.assertTrue(n.startswith((f'{PKG}/', '_lib/')), n)
            self.assertNotIn('__pycache__', n)
            self.assertFalse(n.endswith('.pyc'), n)
            self.assertNotIn('/.', n)                                        # ni .DS_Store ni .git
        self.assertEqual(PL.archive_plugins(out), [PKG])
        self.assertEqual([p.name for p in out.parent.iterdir()], ['essai.zip'])   # pas de .tmp laissé

    def test_the_archive_is_added_and_the_plugin_loads(self):
        out = self.build(self.pkg, self.dir / 'essai.zip', [LIB])
        sys.path.remove(str(self.site))                                      # un autre poste : sans la bibliothèque
        importlib.invalidate_caches()
        self.assertIsNone(importlib.util.find_spec(LIB))
        dest = self.dir / 'plugins'
        self.assertEqual(PL.install(out, dest), [PKG])
        self.assertTrue((dest / '_lib' / f'{LIB}-1.2.dist-info' / 'METADATA').is_file())
        info = PL.load([dest], force=True)
        self.assertEqual([(i.module, i.error) for i in info], [(PKG, '')])
        self.assertEqual(sys.modules[PKG].SEEN, [42])
        self.assertEqual(pathlib.Path(sys.modules[LIB].__file__).parent, dest / '_lib' / LIB)

    def test_a_rebuilt_archive_replaces_the_old_one(self):
        out = self.dir / 'essai.zip'
        self.build(self.pkg, out, [LIB, LIB])                                # une bibliothèque nommée deux fois
        write(self.pkg / 'nouveau.py', 'Z = 3\n')
        self.build(self.pkg, out, [LIB])
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
        self.assertIn(f'{PKG}/nouveau.py', names)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(sorted(p.name for p in self.dir.iterdir() if p.is_file()), ['essai.zip'])

    def test_refusals(self):
        out = self.dir / 'refus.zip'
        notplugin = self.dir / 'src' / 'outil_r1035'
        write(notplugin / '__init__.py', 'X = 1\n')
        nopkg = self.dir / 'src' / 'dossier_r1035'
        write(nopkg / 'm.py', 'def register(api): pass\n')
        core = self.dir / 'src2' / 'vectordrive'
        write(core / '__init__.py', 'def register(api): pass\n')
        lib_like = self.dir / 'src3' / '_Lib'                             # le dossier _lib sous Windows et macOS
        write(lib_like / '__init__.py', 'def register(api): pass\n')
        cases = [((notplugin, out, ()), 'register'),
                 ((nopkg, out, ()), '__init__'),
                 ((core, out, ()), 'réservé'),
                 ((lib_like, out, ()), 'réservé'),
                 ((self.pkg, out, ['json']), 'standard'),
                 ((self.pkg, out, ['zz_introuvable_r1035']), 'introuvable'),
                 ((self.pkg, out, [COMP]), '.so'),                           # compilée : propre à un système
                 ((self.pkg, out, ['vectordrive']), 'réservé'),
                 ((self.pkg, out, ['pas-un-nom']), 'nom'),
                 ((self.pkg, out, [PKG]), 'lui-même'),
                 ((self.pkg, self.pkg / 'essai.zip', ()), 'paquet')]
        for args, word in cases:
            with self.assertRaises(ValueError, msg=word) as cm:
                self.build(*args)
            self.assertIn(word, str(cm.exception))
        self.assertFalse(out.exists())
        self.assertEqual([p.name for p in self.dir.iterdir() if p.is_file()], [])      # ni archive ni .tmp
        self.assertFalse((self.pkg / 'essai.zip').exists())

    def test_with_the_libraries_of_this_python(self):
        self.assertIsNotNone(getattr(PL, 'build_archive', None), 'avant : rien pour fabriquer l’archive d’un plugin')
        with self.assertRaises(ValueError) as cm:                            # numpy (du cœur) : compilée
            self.build(self.pkg, self.dir / 'n.zip', ['numpy'])
        self.assertIn('compilée', str(cm.exception))
        if importlib.util.find_spec('openpyxl') is None:
            return
        out = self.build(self.pkg, self.dir / 'x.zip', ['openpyxl'])
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
        self.assertIn('_lib/openpyxl/__init__.py', names)
        self.assertTrue(any(n.startswith('_lib/openpyxl-') and n.endswith('.dist-info/METADATA') for n in names))


class Everywhere(Base):
    """Une archive faite sur un système s'ajoute sur l'autre (relecture du round)."""

    def test_names_that_would_not_unpack_everywhere(self):
        check = getattr(PL, '_unportable', None)
        self.assertIsNotNone(check, 'avant : un nom impossible sous Windows partait dans l’archive')
        for ok in (f'{PKG}/donnees/table.json', f'_lib/{LIB}-1.2.dist-info/METADATA', f'{PKG}/auxiliaire.py'):
            self.assertEqual(check(ok), '', ok)
        for bad in (f'{PKG}/donnees/12:30.json', f'{PKG}/aux.py', f'{PKG}/COM1.txt', f'{PKG}/a?b.txt',
                    f'{PKG}/fin.', f'{PKG}/../dehors.py', f'{PKG}//vide.py', f'{PKG}/con .txt', f'{PKG}/COM¹.txt'):
            self.assertNotEqual(check(bad), '', bad)
        real = self.pkg / 'donnees' / 'table.json'
        for extra, word in (('donnees/12:30.json', 'Windows'), ('DONNEES/table.json', 'casse'),
                            ('SUB', 'casse')):                               # un fichier et le dossier « sub »
            fake = (lambda top, arc, extra=extra, tree=PL._tree: tree(top, arc) + [(real, f'{arc}/{extra}')])
            with mock.patch.object(PL, '_tree', side_effect=fake), self.assertRaises(ValueError) as cm:
                self.build(self.pkg, self.dir / 'n.zip', ())
            self.assertIn(word, str(cm.exception))
        self.assertFalse((self.dir / 'n.zip').exists())

    def test_a_file_dated_before_1980(self):
        os.utime(self.pkg / 'donnees' / 'table.json', (86400, 86400))      # 2/1/1970 (copié d'une archive…)
        out = self.build(self.pkg, self.dir / 'vieux.zip', ())
        self.assertEqual(PL.archive_plugins(out), [PKG])

    def test_the_package_keeps_the_name_of_its_folder(self):
        typed = self.pkg.parent / PKG.upper()                                # la casse tapée (Windows, macOS)
        if not typed.is_dir():
            self.skipTest('système qui tient compte de la casse')
        out = self.build(typed, self.dir / 'casse.zip', ())
        self.assertEqual(PL.archive_plugins(out), [PKG])                     # le nom du dossier sur le disque
        with self.assertRaises(ValueError):                                  # rangée dedans, même sous une autre casse
            self.build(self.pkg, typed / 'sous' / 'x.zip', ())
        link = self.dir / 'lien_r1035'
        try:
            os.symlink(self.pkg, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            return                                                           # liens interdits sur ce poste
        out = self.build(link, self.dir / 'lien.zip', ())
        self.assertEqual(PL.archive_plugins(out), ['lien_r1035'])            # le nom donné, pas celui de la cible


class CommandLine(Base):

    def tool(self):
        self.assertTrue(TOOL.is_file(), 'avant : pas de commande pour fabriquer l’archive')
        spec = importlib.util.spec_from_file_location('plugin_zip_r1035', TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def run_tool(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = self.tool().main([str(a) for a in args])
        return rc, out.getvalue(), err.getvalue()

    def test_the_command_writes_the_archive(self):
        rc, out, _ = self.run_tool(self.pkg, '--lib', LIB, '-o', self.dir / 'a.zip')
        self.assertEqual(rc, 0)
        self.assertEqual(PL.archive_plugins(self.dir / 'a.zip'), [PKG])
        self.assertIn(PKG, out)
        self.assertIn(LIB, out)
        here = os.getcwd()
        os.chdir(self.dir)
        try:
            rc, _, _ = self.run_tool(self.pkg)                               # d'office : dans le dossier courant
            self.assertEqual(rc, 0)
            self.assertTrue((self.dir / f'{PKG}.zip').is_file())
            (self.dir / f'{PKG}.zip').unlink()
            os.chdir(self.pkg)
            rc, _, err = self.run_tool('.')                                  # depuis le paquet : à côté de lui
            self.assertEqual(rc, 0, err)
            self.assertTrue((self.pkg.parent / f'{PKG}.zip').is_file())
            self.assertFalse((self.pkg / f'{PKG}.zip').exists())
        finally:
            os.chdir(here)                                                   # avant d'effacer le dossier (Windows)

    def test_the_command_says_why_it_refuses(self):
        rc, _, err = self.run_tool(self.pkg, '--lib', 'json', '-o', self.dir / 'b.zip')
        self.assertEqual(rc, 1)
        self.assertIn('standard', err)
        self.assertFalse((self.dir / 'b.zip').exists())

    def test_documented(self):
        text = (ROOT / 'docs' / 'ARCHITECTURE.md').read_text(encoding='utf-8')
        self.assertIn('outils/plugin_zip.py', text)
        self.assertIn('--lib', text)
        self.assertTrue({'.pyd', '.so'} <= set(getattr(PL, 'COMPILED', ())))


if __name__ == '__main__':
    unittest.main()
