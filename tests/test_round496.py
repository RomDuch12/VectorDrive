"""Round 496 : vignettes de l'explorateur — contrôle de la pose quand le chemin du fournisseur contient
des espaces ou des accents (CodeBase encodé : « Claude code » → Claude%20code)."""
import pathlib
import tempfile
import unittest

from vectordrive import thumbshell as TS


class TestCodeBase(unittest.TestCase):
    def test_spaces_and_accents(self):
        d = pathlib.Path(tempfile.mkdtemp()) / 'Dépôt fichiers'
        d.mkdir()
        dll = d / 'Vignettes VD.dll'
        dll.write_bytes(b'x')
        self.assertIn('%20', dll.as_uri())
        self.assertEqual(TS.dll_of(dll.as_uri()), dll)
        reg = dict(TS.plan(dll, ('.dxf',), (r'C:\VD\VectorDrive.exe', [])))
        ok, why = TS.check(lambda k, n: reg.get(k, {}).get(n), (r'C:\VD\VectorDrive.exe', []))
        self.assertTrue(ok, why)
        dll.unlink()
        self.assertFalse(TS.check(lambda k, n: reg.get(k, {}).get(n), (r'C:\VD\VectorDrive.exe', []))[0])


if __name__ == '__main__':
    unittest.main()
