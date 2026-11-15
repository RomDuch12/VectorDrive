"""Round 944 : Fichier › Imprimer la sélection… — les objets sélectionnés seuls, à l'échelle 1:1 ou ajustés à une
feuille A4 avec des marges de 15 mm ; le dernier choix proposé la fois suivante."""
import os
import pathlib
import re
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r944.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication, QInputDialog

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402
from vectordrive.ui import printing  # noqa: E402


def pdf_printer(folder) -> QPrinter:
    pr = QPrinter(QPrinter.PrinterMode.HighResolution)
    pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    pr.setOutputFileName(str(pathlib.Path(folder) / 'x.pdf'))
    return pr


class PrintSelection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        w = self.w
        w.new_document()
        self.a = Shape(path=geom.Path([geom.rect(0, 0, 400, 300)]))         # plus grand qu'une feuille
        self.b = Shape(path=geom.Path([geom.circle((70.0, 10.0), 8.0)]))
        for it in (self.a, self.b):
            w.canvas.doc.add(it)
        w.canvas.select([self.b])
        self.dir = tempfile.mkdtemp()

    def printed(self, mode):
        """(réglages, objets) passés à l'impression du dessin."""
        with mock.patch.object(printing, 'print_drawing', return_value=(210.0, 297.0)) as draw:
            self.assertTrue(self.w.print_selection(mode, exec_dialog=False, printer=pdf_printer(self.dir)))
        (_doc, _printer, opts), kw = draw.call_args
        return opts, kw['items']

    def test_the_selection_alone_at_true_size(self):
        opts, items = self.printed('1')
        self.assertEqual([id(x) for x in items], [id(self.w.canvas.selection[0])])     # le cercle seul, pas le grand cadre
        self.assertEqual(str(opts['echelle']), '1')
        self.assertFalse(opts['plaque'])
        self.assertEqual(opts['position'], 'centre')

    def test_fitted_to_an_a4_sheet_with_comfortable_margins(self):
        opts, items = self.printed('ajuster')
        self.assertEqual(len(items), 1)
        self.assertEqual((opts['echelle'], opts['format'], opts['orientation']), ('ajuster', 'A4', 'auto'))
        self.assertAlmostEqual(opts['marge'], 15.0)
        pr = pdf_printer(self.dir)                                          # et vraiment imprimé : une page A4
        self.assertTrue(self.w.print_selection('ajuster', exec_dialog=False, printer=pr))
        raw = pathlib.Path(pr.outputFileName()).read_bytes()
        box = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)', raw)
        self.assertIsNotNone(box)
        self.assertEqual(sorted(round(float(v)) for v in box.groups()), [595, 842])

    def test_the_choice_is_asked_and_remembered(self):
        w = self.w
        w.settings.remove('impression/selection_mode')
        asked = []

        def pick(_parent, _title, _label, modes, current, _editable):
            asked.append(current)
            return modes[1], True
        with mock.patch.object(QInputDialog, 'getItem', side_effect=pick), \
                mock.patch.object(printing, 'print_drawing', return_value=(210.0, 297.0)) as draw:
            self.assertTrue(w.print_selection(exec_dialog=False, printer=pdf_printer(self.dir)))
            self.assertEqual(draw.call_args[0][2]['echelle'], 'ajuster')
            self.assertTrue(w.print_selection(exec_dialog=False, printer=pdf_printer(self.dir)))
        self.assertEqual(asked, [0, 1])                                     # la 2e fois : le dernier choix proposé
        w.canvas.select([])
        self.assertFalse(w.print_selection('1', exec_dialog=False, printer=pdf_printer(self.dir)))   # rien de sélectionné
        self.assertIn('print_selection', w.A)


if __name__ == '__main__':
    unittest.main()
