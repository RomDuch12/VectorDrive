"""Round 564 : impression en mosaïque — un dessin plus grand que la feuille, à l'échelle 1:1 sur plusieurs
feuilles repérées (A1, B1…), 6 mm de recouvrement."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.ui import printing

app = QApplication.instance() or QApplication([])


class TestMosaic(unittest.TestCase):
    def test_tiles(self):
        tiles = printing.mosaic_tiles((0, 0, 500, 20), 1.0, 10.0, 190.0, 277.0)
        self.assertEqual(len(tiles), 3)                                       # 500 mm sur 190 utiles
        self.assertEqual([t[2].split()[0] for t in tiles], ['A1', 'B1', 'C1'])
        z0, z1 = tiles[0][1], tiles[1][1]
        self.assertAlmostEqual(z0[2] - z1[0], printing.MOSAIC_OVERLAP)        # recouvrement
        self.assertGreaterEqual(tiles[-1][1][2], 500)                         # tout le dessin couvert

    def test_pdf_pages(self):
        from pypdf import PdfReader
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 500, 20)])))
        f = pathlib.Path(tempfile.mkdtemp()) / 'm.pdf'
        pr = QPrinter(QPrinter.PrinterMode.HighResolution)
        pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        pr.setOutputFileName(str(f))
        o = dict(printing.PRINT_DEFAULTS, orientation='portrait', mosaique=True)
        printing.setup_printer(pr, o)
        printing.print_drawing(d, pr, o)
        self.assertEqual(len(PdfReader(str(f)).pages), 3)
        f2 = pathlib.Path(tempfile.mkdtemp()) / 'r.pdf'
        pr = QPrinter(QPrinter.PrinterMode.HighResolution)
        pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        pr.setOutputFileName(str(f2))
        printing.print_drawing(d, pr, dict(o, mosaique=False))                # réduit : une feuille
        self.assertEqual(len(PdfReader(str(f2)).pages), 1)


if __name__ == '__main__':
    unittest.main()
