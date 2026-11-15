"""Round 519 : bibliothèque — un symbole posé plusieurs fois n'est lu qu'une fois (copie neuve à chaque
pose) ; un fichier modifié est relu."""
import os
import pathlib
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry
from vectordrive.ui import symbols as SY


class TestSymbolCache(unittest.TestCase):
    def test_read_once_copy_each_time(self):
        d = pathlib.Path(tempfile.mkdtemp())
        f = d / 'rond.dxf'
        doc = Document()
        doc.add(Shape(path=geom.Path([geom.circle((50, 50), 5)])))
        doc.add(Shape(path=geom.Path([geom.rect(40, 40, 3, 3)])))
        registry.save_document(doc, f)
        real = registry.open_document
        with mock.patch.object(registry, 'open_document', side_effect=real) as rd:
            a = SY.file_as_group(f)
            b = SY.file_as_group(f)
            self.assertEqual(rd.call_count, 1)
        self.assertIsNot(a, b)
        self.assertNotEqual(a.id, b.id)                               # identifiants propres à chaque pose
        self.assertEqual(a.bbox(), b.bbox())
        bb = a.bbox()
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 0.0, places=6)    # centré sur l'origine
        time.sleep(0.05)
        doc.add(Shape(path=geom.Path([geom.rect(90, 90, 2, 2)])))
        registry.save_document(doc, f)                                  # modifié : relu
        os.utime(f, (time.time() + 5, time.time() + 5))
        with mock.patch.object(registry, 'open_document', side_effect=real) as rd:
            c = SY.file_as_group(f)
            self.assertEqual(rd.call_count, 1)
        self.assertNotEqual(c.bbox(), a.bbox())


if __name__ == '__main__':
    unittest.main()
