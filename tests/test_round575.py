"""Round 575 : fiche d'un dessin (Ouvrir, Bibliothèque) — nombre de couleurs (outils) quand il en a plusieurs."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape, Tool
from vectordrive.io import registry
from vectordrive.ui.symbols import describe_file

app = QApplication.instance() or QApplication([])


class TestFiche(unittest.TestCase):
    def test_colors_line(self):
        d = Document()
        d.tools = [Tool(0, '#000000'), Tool(2, '#ff0000')]
        d.layers[0].items = [Shape(path=geom.Path([geom.rect(0, 0, 5, 5)]), tool=0),
                             Shape(path=geom.Path([geom.rect(9, 0, 5, 5)]), tool=2)]
        f = pathlib.Path(tempfile.mkdtemp()) / 'c.svg'
        registry.save_document(d, f)
        self.assertIn('2 couleurs (outils 1, 2)', describe_file(f))
        one = pathlib.Path(tempfile.mkdtemp()) / 'n.svg'
        d.layers[0].items = d.layers[0].items[:1]
        registry.save_document(d, one)
        self.assertNotIn('couleurs', describe_file(one))


if __name__ == '__main__':
    unittest.main()
