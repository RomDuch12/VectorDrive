"""Round 6 : interface FR/EN, mise à jour automatique, installateur."""
import json
import os
import pathlib
import re
import string
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive import __version__, i18n, update

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'outils'))


def fields(s: str) -> list:
    return sorted((f or '', spec or '') for _, f, spec, _ in string.Formatter().parse(s) if f is not None)


class TestI18n(unittest.TestCase):
    def tearDown(self):
        i18n.set_language('fr')

    def test_every_string_translated(self):
        import i18n_wrap
        strings = i18n_wrap.extract(sorted((ROOT / 'vectordrive').rglob('*.py')))
        table = json.loads((ROOT / 'vectordrive' / 'ressources' / 'i18n' / 'en.json').read_text(encoding='utf-8'))
        self.assertGreater(len(strings), 250)
        self.assertEqual([s for s in strings if s not in table], [])
        # mêmes champs {0}, {1:.3f}… dans la traduction
        for fr, en in table.items():
            with self.subTest(fr):
                self.assertEqual(fields(fr), fields(en))

    def test_switch(self):
        self.assertEqual(i18n.set_language('en'), 'en')
        self.assertEqual(i18n.tr('Fichier'), 'File')
        self.assertEqual(i18n.tr('{0} copie(s) créée(s)').format(3), '3 copy(ies) created')
        self.assertEqual(i18n.decimal_sep(), '.')
        i18n.set_language('fr')
        self.assertEqual(i18n.tr('Fichier'), 'Fichier')
        self.assertEqual(i18n.decimal_sep(), ',')
        self.assertIn(i18n.set_language(None), ('fr', 'en'))

    def test_window_in_english(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        i18n.set_language('en')
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            self.assertEqual(w.A['open'].text(), 'Open')
            self.assertEqual(w.ribbon.tabText(0), 'File')
            # la hauteur du ruban laisse voir les titres de groupes
            for i in range(w.ribbon.count()):
                sc = w.ribbon.widget(i)
                self.assertGreaterEqual(sc.height(), sc.widget().sizeHint().height())
        finally:
            w.modified = False
            w.close()


class TestUpdate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.setup = self.dir / 'VectorDrive-9.0.0-setup.exe'
        self.setup.write_bytes(b'MZ installateur factice')

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self, **kw):
        m = {'version': '9.0.0', 'installer': self.setup.name, 'sha256': update.sha256_file(self.setup)}
        m.update(kw)
        (self.dir / update.MANIFEST).write_text(json.dumps(m), encoding='utf-8')

    def test_versions(self):
        self.assertLess(update.parse_version('0.1.0'), update.parse_version('0.1.1'))
        self.assertLess(update.parse_version('0.9'), update.parse_version('0.10.0'))
        self.assertEqual(update.parse_version('v1.2.3'), (1, 2, 3))

    def test_check_and_fetch(self):
        self.assertIsNone(update.check(str(self.dir)))                 # pas de manifeste
        self.manifest()
        up = update.check(str(self.dir))
        self.assertEqual(up.version, '9.0.0')
        dest = pathlib.Path(self.tmp.name) / 'dl'
        dest.mkdir()
        got = update.fetch(up, dest)
        self.assertEqual(got.read_bytes(), self.setup.read_bytes())
        self.assertIsNone(update.check(str(self.dir), current='9.0.0'))  # déjà à jour

    def test_bad_hash_refused(self):
        self.manifest(sha256='0' * 64)
        up = update.check(str(self.dir))
        dest = pathlib.Path(self.tmp.name) / 'dl'
        dest.mkdir()
        with self.assertRaises(update.UpdateError):
            update.fetch(up, dest)
        self.assertEqual(list(dest.iterdir()), [])

    def test_incomplete_manifest(self):
        (self.dir / update.MANIFEST).write_text('{"version": "9.0.0"}', encoding='utf-8')
        with self.assertRaises(update.UpdateError):
            update.check(str(self.dir))

    def test_plain_http_refused(self):
        with self.assertRaises(update.UpdateError):
            update.check('http://exemple.invalid/maj/')

    def test_not_frozen(self):
        self.assertFalse(update.can_install())


class TestInstallerScript(unittest.TestCase):
    def test_iss(self):
        iss = (ROOT / 'installeur' / 'VectorDrive.iss').read_text(encoding='utf-8')
        self.assertIn('PrivilegesRequired=lowest', iss)
        self.assertIn(r'Software\Classes\.vdz', iss)
        self.assertNotIn('.vnd', re.sub(r';.*', '', iss))       # les .vnd restent à TypeEdit
        self.assertIn('ShouldRelaunch', iss)

    def test_version_resource_from_package(self):
        spec = (ROOT / 'VectorDrive.spec').read_text(encoding='utf-8')
        self.assertIn('__version__', spec)
        self.assertRegex(__version__, r'^\d+\.\d+\.\d+$')


if __name__ == '__main__':
    unittest.main()
