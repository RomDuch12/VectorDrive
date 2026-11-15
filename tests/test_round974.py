"""Round 974 : la page d'un PDF écrit par VectorDrive porte toujours /Resources (la norme l'exige ; sans elle
Inkscape 1.3 s'arrêtait en erreur à l'ouverture)."""
import io
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r974.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from pypdf import PdfReader  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Plate, Shape  # noqa: E402
from vectordrive.io import proof, registry  # noqa: E402


class Resources(unittest.TestCase):

    def test_a_page_without_image_declares_its_resources(self):
        raw = proof.pdf_bytes(['0 0 m 10 10 l S'], 100.0, 50.0, [], 'essai')
        page = PdfReader(io.BytesIO(raw), strict=True).pages[0]
        self.assertIsNotNone(page.get('/Resources'))                         # avant : absente
        self.assertEqual(list(page['/Resources'].keys()), ['/ProcSet'])

    def test_a_saved_drawing_and_its_ai_twin(self):
        d = Document()
        d.plate = Plate(width=80.0, height=40.0)
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(10, 10, 30, 20)])))
        folder = pathlib.Path(tempfile.mkdtemp())
        for name in ('dessin.pdf', 'dessin.ai'):
            registry.save_document(d, str(folder / name))
            page = PdfReader(str(folder / name), strict=True).pages[0]
            self.assertIn('/Resources', page, name)                          # avant : absente
            back = registry.open_document(str(folder / name))
            self.assertEqual(sum(len(it.path.contours) for L in back.layers for it in L.items), 2, name)   # cadre + forme


if __name__ == '__main__':
    unittest.main()
