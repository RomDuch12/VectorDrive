"""Round 85 : mode portable."""
import json
import os
import pathlib
import tempfile
import unittest
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive import portable, update


class _Env:
    """Dossier d'application simulé, sans le fichier de réglages des tests."""

    def __init__(self, with_ini: bool):
        self.with_ini = with_ini

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        if self.with_ini:
            (self.dir / portable.INI).write_text('', encoding='utf-8')
        self.saved = {k: os.environ.get(k) for k in ('VECTORDRIVE_PORTABLE_DIR', 'VECTORDRIVE_SETTINGS')}
        os.environ['VECTORDRIVE_PORTABLE_DIR'] = str(self.dir)
        os.environ.pop('VECTORDRIVE_SETTINGS', None)
        return self.dir

    def __exit__(self, *a):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()


class TestPortable(unittest.TestCase):
    def test_detection_settings_data(self):
        with _Env(False) as d:
            self.assertFalse(portable.is_portable())
            self.assertNotEqual(portable.data_dir(), d / portable.DATA)
        with _Env(True) as d:
            self.assertTrue(portable.is_portable())
            self.assertEqual(portable.data_dir(), d / portable.DATA)
            s = portable.settings()
            s.setValue('options/essai', 42)
            s.sync()
            self.assertIn('essai=42', (d / portable.INI).read_text(encoding='utf-8'))

    def test_tests_settings_keep_priority(self):
        with _Env(True) as d:
            os.environ['VECTORDRIVE_SETTINGS'] = str(d / 'tests.ini')
            self.assertTrue(portable.settings().fileName().endswith('tests.ini'))

    def test_archive_and_update_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            app = tmp / 'VectorDrive'
            (app / '_internal').mkdir(parents=True)
            (app / 'VectorDrive.exe').write_bytes(b'MZ')
            (app / '_internal' / 'lib.dll').write_bytes(b'x')
            z = portable.make_archive(app, tmp / 'out' / 'VectorDrive-9.9.9-portable.zip')
            names = zipfile.ZipFile(z).namelist()
            self.assertIn('VectorDrive/VectorDrive.exe', names)
            self.assertIn('VectorDrive/_internal/lib.dll', names)
            self.assertIn('VectorDrive/' + portable.INI, names)
            target = tmp / 'cle'
            target.mkdir()
            script = portable.launch_portable_update(z, pid=1234, target=target, start=False)
            text = script.read_text(encoding='cp1252')
            self.assertIn('robocopy', text)
            self.assertIn(f'/XF {portable.INI}', text)
            self.assertIn(f'/XD {portable.DATA}', text)
            self.assertIn('PID eq 1234', text)
            self.assertIn(str(target / 'VectorDrive.exe'), text)

    def test_manifest_picks_portable_archive(self):
        with _Env(True), tempfile.TemporaryDirectory() as src:
            m = {'version': '99.0.0', 'installer': 'VectorDrive-99.0.0-setup.exe', 'sha256': 'AA',
                 'portable': 'VectorDrive-99.0.0-portable.zip', 'portable_sha256': 'BB'}
            (pathlib.Path(src) / update.MANIFEST).write_text(json.dumps(m), encoding='utf-8')
            up = update.check(src)
            self.assertTrue(up.portable)
            self.assertTrue(up.installer.endswith('portable.zip'))
            self.assertEqual(up.sha256, 'bb')
        with _Env(False), tempfile.TemporaryDirectory() as src:
            (pathlib.Path(src) / update.MANIFEST).write_text(json.dumps(m), encoding='utf-8')
            up = update.check(src)
            self.assertFalse(up.portable)
            self.assertTrue(up.installer.endswith('setup.exe'))


if __name__ == '__main__':
    unittest.main()
