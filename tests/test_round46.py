"""Round 46 : lecture partielle des VND/GVT (classe inconnue en cours de
fichier)."""
import pathlib
import struct
import tempfile
import unittest

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry, vnd, vnd_write

DRAWS = pathlib.Path('C:/ProgramData/Gravotech/TypeEdit_V15-LaserType_V15/DRAWS')


class TestPartial(unittest.TestCase):
    def test_unknown_class_after_drawing(self):
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])))
        d.add(Shape(path=geom.Path([geom.circle((30, 5), 4)])))
        data = bytearray(vnd_write.write_document(d)[0])
        # nom de classe de la 1re courbe altéré : classe inconnue en cours de fichier
        i = data.find(b'CCourbe')
        self.assertGreater(i, 0)
        data[i:i + 7] = b'CXourbe'                       # 1re courbe : classe inconnue
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'p.vnd'
            f.write_bytes(bytes(data))
            with self.assertRaises(Exception):
                vnd.parse(bytes(data))                   # lecture stricte : échec
            doc = registry.open_document(f)              # lecture partielle : message
        self.assertTrue(any('lecture interrompue' in r for r in doc.report), doc.report)
        self.assertNotIn('vnd_source', doc.extra)        # pas de réécriture sur un fichier partiel

    def test_relief_gvt(self):
        f = DRAWS / 'Viking.gvt'
        if not f.exists():
            self.skipTest('Viking.gvt absent')
        d = registry.open_document(f)
        self.assertTrue(any('lecture interrompue' in r for r in d.report))


if __name__ == '__main__':
    unittest.main()
