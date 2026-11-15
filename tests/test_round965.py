"""Round 965 : un dessin imprimé à une échelle et plus grand que la feuille est réduit pour tenir — le message de fin
d'impression le dit (avant : « Envoyé à l'imprimante. », comme pour une épreuve à l'échelle)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r965.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtPrintSupport import QPrinter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402
from vectordrive.ui import printing  # noqa: E402


def pdf_printer(folder) -> QPrinter:
    pr = QPrinter(QPrinter.PrinterMode.HighResolution)
    pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    pr.setOutputFileName(str(pathlib.Path(folder) / 'x.pdf'))
    return pr


class Reduced(unittest.TestCase):

    def test_the_printing_module_knows_what_it_did(self):
        self.assertTrue(hasattr(printing, 'reduced'), 'l\'impression ne dit pas si elle a réduit')   # avant
        d = Document()
        big = Shape(path=geom.Path([geom.rect(0, 0, 400, 300)]))
        small = Shape(path=geom.Path([geom.circle((70.0, 10.0), 8.0)]))
        d.layers[0].items += [big, small]
        tmp = tempfile.mkdtemp()

        def run(items, **opts):
            o = dict(printing.PRINT_DEFAULTS, plaque=False, **opts)
            pr = pdf_printer(tmp)
            printing.setup_printer(pr, o)
            printing.print_drawing(d, pr, o, items=items)
            return printing.reduced()
        k = run([big], echelle='1')                                         # 400 × 300 sur un A4 : réduit
        self.assertIsNotNone(k)
        self.assertAlmostEqual(k, min(277 / 400, 190 / 300), delta=0.01)
        self.assertIsNone(run([small], echelle='1'))                        # il tient : à l'échelle
        self.assertIsNone(run([big], echelle='ajuster'))                    # ajusté : c'est ce qu'on a demandé
        self.assertIsNone(run([big], echelle='1', mosaique=True))           # plusieurs feuilles : l'échelle est gardée
        self.assertGreater(printing.LAST['sheets'], 1)

    def test_the_window_says_the_print_was_reduced(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            big = Shape(path=geom.Path([geom.rect(0, 0, 400, 300)]))
            small = Shape(path=geom.Path([geom.circle((70.0, 10.0), 8.0)]))
            for it in (big, small):
                w.canvas.doc.add(it)
            tmp = tempfile.mkdtemp()
            w.canvas.select([big])
            self.assertTrue(w.print_selection('1', exec_dialog=False, printer=pdf_printer(tmp)))
            said = w.statusBar().currentMessage()
            self.assertIn('réduit à 63 %', said)                            # avant : « Envoyé à l'imprimante. »
            self.assertIn('échelle', said)
            wide = Shape(path=geom.Path([geom.rect(0, 320, 250, 150)]))     # en largeur : tient sur un A4 couché
            w.canvas.doc.add(wide)
            w.canvas.select([wide])
            pr = pdf_printer(tmp)
            self.assertTrue(w.print_selection('1', exec_dialog=False, printer=pr))
            self.assertNotIn('réduit', w.statusBar().currentMessage())
            import re
            box = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)', pathlib.Path(pr.outputFileName()).read_bytes())
            self.assertGreater(float(box.group(1)), float(box.group(2)))    # avant : feuille en hauteur, sélection réduite
            w.canvas.select([small])
            self.assertTrue(w.print_selection('1', exec_dialog=False, printer=pdf_printer(tmp)))
            self.assertNotIn('réduit', w.statusBar().currentMessage())
            w.canvas.select([big])
            self.assertTrue(w.print_selection('ajuster', exec_dialog=False, printer=pdf_printer(tmp)))
            self.assertNotIn('réduit', w.statusBar().currentMessage())
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
