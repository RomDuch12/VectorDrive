"""Round 437 : fichier endommagé — message clair (UnreadableFile), jamais une erreur interne brute ;
import d'outils (CSV à lignes trop longues, archive abîmée)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry


class TestDamaged(unittest.TestCase):
    def test_messages(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])))
        for ext in ('.vdz', '.pdf'):
            p = tmp / ('a' + ext)
            registry.save_document(d, str(p))
            data = p.read_bytes()
            p.write_bytes(data[:len(data) // 2])                   # coupé en deux
            with self.assertRaises(ValueError) as cm:
                registry.open_document(str(p))
            if isinstance(cm.exception, registry.UnreadableFile):
                self.assertIn('a' + ext, str(cm.exception))
                self.assertIsNotNone(cm.exception.cause)
        p = tmp / 'b.vdz'
        p.write_bytes(b'PK\x03\x04' + bytes(40))                     # zip faux
        with self.assertRaises(registry.UnreadableFile) as cm:
            registry.open_document(str(p))
        self.assertIn('b.vdz', str(cm.exception))


class TestToolImports(unittest.TestCase):
    def test_csv_and_zip(self):
        from vectordrive.cam import toollib
        tmp = pathlib.Path(tempfile.mkdtemp())
        p = tmp / 'a.csv'
        p.write_text('name;kind;diameter\nF2;fraise;2;en trop;encore\nF3;fraise;3\n', encoding='utf-8')
        tools, _n = toollib.import_file(p)                        # ligne trop longue : surplus ignoré
        self.assertEqual([(t.name, t.diameter) for t in tools], [('F2', 2.0), ('F3', 3.0)])
        z = tmp / 'b.zip'
        z.write_bytes(b'PK\x05\x06' + bytes(10))
        with self.assertRaises(toollib.ToolLibError):
            toollib.import_file(z)


if __name__ == '__main__':
    unittest.main()
