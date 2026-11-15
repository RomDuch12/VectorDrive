"""Round 1032 : demande du 15/11 « dist mac aussi ? » (réponse : « Oui, en essai »). Les polices de macOS sont trouvées
(/System/Library/Fonts), le moteur natif se construit depuis le dépôt seul (vectorcraft-geom copié dans natif/vendor),
la version macOS est construite par GitHub Actions et jointe à chaque version publiée ; les données de couverture des
essais (chemins du poste) ne sont plus exportées."""
import ast
import fnmatch
import os
import pathlib
import re
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1032.ini'))

from vectordrive.core import fonts  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOME = pathlib.PurePosixPath('/Users/essai')


def platform_dirs():
    f = getattr(fonts, '_platform_dirs', None)
    if f is None:
        raise AssertionError('avant : les dossiers de polices ne dépendaient pas du système (rien pour macOS)')
    return f


def path_deps(cargo: pathlib.Path) -> dict[str, str]:
    """{crate : chemin} des dépendances `path = "…"` d'un Cargo.toml."""
    text = cargo.read_text(encoding='utf-8')
    return dict(re.findall(r'^([\w-]+)\s*=\s*\{[^}\n]*path\s*=\s*"([^"]+)"', text, re.M))


def posix(dirs) -> list[str]:
    return [d.as_posix() for d in dirs]


class FontFolders(unittest.TestCase):

    def test_macos_in_the_system_order(self):
        win, dirs = platform_dirs()('darwin', HOME, {})
        self.assertEqual(win, ())
        # celles de l'utilisateur d'abord (la première trouvée d'une famille est prise), Arial et les polices courantes
        # dans /System/Library/Fonts (Supplemental)
        self.assertEqual(posix(dirs), ['/Users/essai/Library/Fonts', '/Library/Fonts', '/System/Library/Fonts'])

    def test_linux(self):
        win, dirs = platform_dirs()('linux', HOME, {})
        self.assertEqual(win, ())
        self.assertEqual(posix(dirs), ['/Users/essai/.local/share/fonts', '/Users/essai/.fonts',
                                       '/usr/local/share/fonts', '/usr/share/fonts'])

    def test_windows_unchanged(self):
        win, dirs = platform_dirs()('win32', pathlib.Path('C:/Users/essai'),
                                    {'WINDIR': 'C:/Win', 'LOCALAPPDATA': 'C:/Local'})
        self.assertEqual(win, (pathlib.Path('C:/Win/Fonts'), pathlib.Path('C:/Local/Microsoft/Windows/Fonts')))
        self.assertEqual(dirs, [*win, pathlib.Path('C:/Users/essai/.fonts'), pathlib.Path('/usr/share/fonts'),
                                pathlib.Path('/Library/Fonts'), pathlib.Path('C:/Users/essai/Library/Fonts')])
        win, _ = platform_dirs()('win32', pathlib.Path('C:/Users/essai'), {})
        self.assertEqual(win, (pathlib.Path('C:/Windows/Fonts'),))

    def test_this_computer(self):
        win, dirs = platform_dirs()(sys.platform, pathlib.Path.home(), os.environ)
        self.assertEqual(fonts._WINDOWS_DIRS, win)
        self.assertIsInstance(fonts.FONT_DIRS, list)               # les réglages et les plugins y ajoutent des dossiers
        self.assertEqual([d for d in dirs if d not in fonts.FONT_DIRS], [])


class NativeEngineFromTheRepository(unittest.TestCase):

    def setUp(self):
        if not (ROOT / 'natif').is_dir():
            self.skipTest('sources natives absentes')

    def test_every_path_dependency_is_inside_the_repository(self):
        cargos = sorted((ROOT / 'natif').glob('*/Cargo.toml')) + sorted((ROOT / 'natif' / 'vendor').glob('*/Cargo.toml'))
        self.assertTrue(cargos)
        outside = []
        for cargo in cargos:
            for crate, rel in path_deps(cargo).items():
                target = (cargo.parent / rel).resolve()
                if ROOT.resolve() not in target.parents or not (target / 'Cargo.toml').is_file():
                    outside.append(f'{cargo.relative_to(ROOT).as_posix()} : {crate} = {rel}')
        self.assertEqual(outside, [])                              # avant : vectorcraft-geom hors du dépôt

    def test_the_geom_copy_keeps_its_licences(self):
        geom = ROOT / 'natif' / 'vendor' / 'vectorcraft-geom'
        for name in ('LICENSE-MIT', 'LICENSE-APACHE', 'NOTICE', 'Cargo.toml', 'src/lib.rs'):
            self.assertTrue((geom / name).is_file(), name)
        cargo = (geom / 'Cargo.toml').read_text(encoding='utf-8')
        self.assertIn('name = "vectorcraft-geom"', cargo)
        self.assertIn('license = "MIT OR Apache-2.0"', cargo)
        self.assertNotRegex(cargo, r'workspace\s*=\s*true')        # se construit hors du workspace d'origine
        self.assertEqual(path_deps(ROOT / 'natif' / 'vdpathops' / 'Cargo.toml')['vectorcraft-geom'],
                         '../vendor/vectorcraft-geom')
        self.assertIn('natif/vendor/vectorcraft-geom', (ROOT / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8'))

    def test_the_windows_extension_holds_no_local_path(self):
        pyd = ROOT / 'vectordrive' / 'vdpathops.pyd'
        if not pyd.is_file():
            self.skipTest('extension Windows absente')
        data = pyd.read_bytes()
        # avant : le dossier de compilation et le registre cargo du poste (nom de l'utilisateur)
        self.assertIsNone(re.search(rb'(?i)[a-z]:[\\/](users|documents)[\\/]', data))
        self.assertNotIn(b'Temp\\claude', data)

    def test_licences_of_the_linked_rust_crates(self):
        f = ROOT / 'licences' / 'vdpathops-crates.txt'
        self.assertTrue(f.is_file(), 'avant : seule la licence de vectorcraft dans licences/')
        text = f.read_text(encoding='utf-8')
        for crate in ('pyo3 ', 'kurbo ', 'smallvec ', 'serde ', 'thiserror ', 'arrayvec ', 'polycool ', 'rustc-hash ',
                      'memoffset ', 'once_cell '):
            self.assertIn('\n' + crate, text, crate)
        self.assertGreaterEqual(text.count('Permission is hereby granted, free of charge'), 15)
        self.assertIn('licences/vdpathops-crates.txt', (ROOT / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8'))


class MacBuild(unittest.TestCase):

    def test_workflow(self):
        wf = ROOT / '.github' / 'workflows' / 'macos.yml'
        self.assertTrue(wf.is_file())                              # avant : aucune construction pour macOS
        text = wf.read_text(encoding='utf-8')
        for need in ('macos-15', 'macos-15-intel', 'arm64', 'x86_64', 'natif/vdpathops/Cargo.toml',
                     'vectordrive/vdpathops.abi3.so', 'outils/macos/VectorDrive-macos.spec',
                     'dist/VectorDrive.app/Contents/MacOS/VectorDrive --autotest', 'gh release upload'):
            self.assertIn(need, text)
        self.assertIn('python VectorDrive.py --autotest', text)
        self.assertRegex(text, r'release:\s*\n\s*types:\s*\[published\]')
        self.assertNotIn('\t', text)
        # relecture : le moteur natif doit être chargé (sinon le remplaçant en Python, sans rien dire) et présent dans
        # l'application ; le nom de la version passe par l'environnement, jamais tel quel dans le shell
        self.assertIn('assert pathops._native', text)
        self.assertIn("find dist/VectorDrive.app -name 'vdpathops*.so'", text)
        self.assertIn('--remap-path-prefix', text)
        self.assertNotIn('upload "${{', text)
        self.assertIn('gh release upload "$TAG"', text)

    def test_spec(self):
        spec = ROOT / 'outils' / 'macos' / 'VectorDrive-macos.spec'
        self.assertTrue(spec.is_file())
        text = spec.read_text(encoding='utf-8')
        for need in ('BUNDLE(', "name='VectorDrive.app'", 'bundle_identifier=', "glob('vdpathops*.so')",
                     "collect_submodules('vectordrive'", 'THIRD_PARTY_NOTICES.md', "'licences'",
                     "'LSMinimumSystemVersion': '14.0'"):
            self.assertIn(need, text)
        compile(text, str(spec), 'exec')                           # recette Python valide
        for rel in re.findall(r"racine / '([^']+)'(?: / '([^']+)')?(?: / '([^']+)')?", text):
            path = ROOT.joinpath(*[p for p in rel if p])
            self.assertTrue(path.exists(), path)                   # chaque fichier repris existe
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('macOS (essai)', readme)
        self.assertIn('Ouvrir quand même', readme)                 # clic droit › Ouvrir ne suffit plus (macOS 15)
        self.assertIn('macOS 14', readme)

    def test_mac_native_build_not_versioned(self):
        ignore = (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines()
        self.assertIn('vectordrive/*.so', ignore)


class PublicExport(unittest.TestCase):

    def test_coverage_data_is_not_exported(self):
        src = (ROOT / 'outils' / 'exporter_public.py').read_text(encoding='utf-8')
        block = src[src.index('PRIVES = ['):]
        block = block[:block.index('\n]\n') + 3]
        prives = ast.literal_eval(block.split('=', 1)[1].strip())  # la liste seule (le module est un script)
        for name in ('.coverage', 'prof.out'):                    # avant : exportés (chemins du poste dedans)
            self.assertTrue(any(fnmatch.fnmatch(name, p) for p in prives), name)
        self.assertFalse(any(fnmatch.fnmatch('.github/workflows/macos.yml', p) for p in prives))


if __name__ == '__main__':
    unittest.main()
