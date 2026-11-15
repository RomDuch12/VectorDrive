"""Round 198 : « Convertir avec VectorDrive » au clic droit de l'explorateur
(registre jamais touché par les essais : écrivain, effaceur, lecteur simulés)."""
import os
import pathlib
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive import shellmenu as SM

PROG = (r'C:\Programmes\VectorDrive\VectorDrive.exe', [])
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="20mm" viewBox="0 0 40 20">'
       '<rect x="5" y="5" width="30" height="10"/></svg>')


class TestPlan(unittest.TestCase):
    def test_keys_and_commands(self):
        keys = dict(SM.plan(PROG))
        verb = r'Software\Classes\SystemFileAssociations\.dxf\shell\VectorDrive.Convertir'
        self.assertEqual(keys[verb]['ExtendedSubCommandsKey'], 'VectorDrive.Convertir.dxf')   # sans \shell final
        subs = [k for k in keys if k.startswith(r'Software\Classes\VectorDrive.Convertir.dxf\shell') and
                not k.endswith('command')]
        self.assertEqual([keys[k]['MUIVerb'] for k in subs], ['en SVG', 'en PDF', 'en EPS', SM.LOTS_TITLE])   # jamais DXF en DXF ; lots (257)
        cmd = keys[r'Software\Classes\VectorDrive.Convertir.vnd\shell\01dxf\command']['']
        self.assertEqual(cmd, r'"C:\Programmes\VectorDrive\VectorDrive.exe" --convert "%1" --to dxf --keep')
        self.assertTrue(all(k.startswith('Software\\Classes\\') for k in keys))                # HKCU\Software\Classes
        self.assertNotIn('vnd', [k for k, _l in SM.TARGETS])

    def test_install_check_uninstall_simulated(self):
        reg = {}

        def write(key, values):
            reg.setdefault(key, {}).update(values)

        def read(key, name):
            return reg.get(key, {}).get(name)

        def delete(root):
            gone = [k for k in reg if k == root or k.startswith(root + '\\')]
            for k in gone:
                del reg[k]
            return bool(gone)
        self.assertFalse(SM.check(read, PROG)[0])
        self.assertEqual(SM.install(write, PROG), len(SM.SOURCES))
        self.assertTrue(SM.check(read, PROG)[0])
        other = (r'D:\ancien\VectorDrive.exe', [])
        ok, why = SM.check(read, other)
        self.assertFalse(ok)
        self.assertIn('autre programme', why)
        self.assertGreater(SM.uninstall(delete), 0)
        self.assertEqual(reg, {})

    def test_dev_executable(self):
        exe, args = SM.executable()
        if not getattr(sys, 'frozen', False):
            self.assertTrue(args[0].endswith('VectorDrive.py'))


class TestConvertKeep(unittest.TestCase):
    def test_never_overwrites(self):
        import importlib.util
        root = pathlib.Path(SM.__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('vd_main', root / 'VectorDrive.py')
        main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main)
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp, 'plaque.svg')
            src.write_text(SVG, encoding='utf-8')
            old = pathlib.Path(tmp, 'plaque.dxf')
            old.write_text('ne pas écraser', encoding='utf-8')
            self.assertEqual(main.convert(str(src), 'dxf', None, keep=True), 0)
            self.assertEqual(old.read_text(encoding='utf-8'), 'ne pas écraser')
            self.assertTrue(pathlib.Path(tmp, 'plaque (2).dxf').exists())
            self.assertEqual(main.free_name(old).name, 'plaque (3).dxf')


if __name__ == '__main__':
    unittest.main()
