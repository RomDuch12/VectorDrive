"""Round 21 : presse-papiers SVG (vers et depuis d'autres logiciels), impression."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.core.geom import Path
from vectordrive.io import svg


class TestSvgString(unittest.TestCase):
    def test_round_trip_in_memory(self):
        d = Document()
        d.add(Shape(path=Path([geom.circle((10, 10), 5)])))
        back = svg.read_data(svg.to_string(d).encode('utf-8'))
        self.assertAlmostEqual(back.layers[0].items[0].path.length(), 10 * math.pi, places=4)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_copy_marks_and_paste_internal(self):
        from PySide6.QtWidgets import QApplication
        w = self.w
        sh = w.canvas.doc.add(Shape(path=Path([geom.rect(0, 0, 10, 5)])))
        w.canvas.select([sh])
        w.copy()
        md = QApplication.clipboard().mimeData()
        self.assertTrue(md.hasFormat('image/svg+xml'))
        self.assertIn(b'<svg', bytes(md.data('image/svg+xml')))
        self.assertIsNone(w._external_svg())                 # notre propre copie : collage interne
        w.paste()
        self.assertEqual(sum(1 for _ in w.canvas.doc.iter_items()), 2)

    def test_paste_external_svg(self):
        from PySide6.QtCore import QMimeData
        from PySide6.QtWidgets import QApplication
        w = self.w
        md = QMimeData()
        md.setText('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 20 10">'
                   '<rect x="0" y="0" width="20" height="10"/></svg>')
        QApplication.clipboard().setMimeData(md)
        self.assertIsNotNone(w._external_svg())
        w.paste()
        items = list(w.canvas.doc.iter_items())
        self.assertEqual(len(items), 1)
        bb = items[0].bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 20, places=6)

    def test_print_to_pdf(self):
        from PySide6.QtPrintSupport import QPrinter
        from vectordrive.io import proof
        from vectordrive.ui import printing
        d = Document()
        d.add(Shape(path=Path([geom.rect(0, 0, 100, 20)])))
        with tempfile.TemporaryDirectory() as t:
            for name, fn in (('dessin.pdf', lambda pr: printing.print_drawing(d, pr)),
                             ('bat.pdf', lambda pr: printing.print_proof(d, proof.ProofInfo(client='Essai'), pr))):
                pr = QPrinter(QPrinter.PrinterMode.HighResolution)
                pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                f = pathlib.Path(t) / name
                pr.setOutputFileName(str(f))
                fn(pr)
                self.assertGreater(f.stat().st_size, 1000)
                self.assertEqual(f.read_bytes()[:5], b'%PDF-')
            pr = QPrinter(QPrinter.PrinterMode.HighResolution)
            pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            pr.setOutputFileName(str(pathlib.Path(t) / 'x.pdf'))
            pw, ph = printing.print_drawing(d, pr)
            self.assertGreater(pw, ph)                          # dessin large : feuille en paysage


if __name__ == '__main__':
    unittest.main()
