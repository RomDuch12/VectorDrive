"""Round 546 : BAT et impression réglables — F10 › BAT (orientation portrait d'office, échelle imposée,
cartouche, cotes, légende) et F10 › Impression (que faut-il imprimer, format, orientation, échelle,
réduction, position, marge, plaque, sélection ; imprimante retenue)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtGui import QPageLayout
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.core.geom import Path
from vectordrive.ui import options as O
from vectordrive.ui import printing

app = QApplication.instance() or QApplication([])


def pdf_printer(d) -> QPrinter:
    pr = QPrinter(QPrinter.PrinterMode.HighResolution)
    pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    pr.setOutputFileName(str(pathlib.Path(d) / 'x.pdf'))
    return pr


class TestPrintOptions(unittest.TestCase):
    def setUp(self):
        self.doc = Document()
        self.doc.plate = None
        self.doc.add(Shape(path=Path([geom.rect(0, 0, 100, 20)])))
        self.t = tempfile.mkdtemp()

    def test_defaults(self):
        s = QSettings(os.path.join(self.t, 'o.ini'), QSettings.Format.IniFormat)
        o = printing.print_options(s)
        self.assertEqual((o['format'], o['orientation'], o['echelle'], o['position']), ('A4', 'portrait', '1', 'centre'))
        self.assertEqual(O.value(s, 'bat/orientation'), 'portrait')
        self.assertIn('Impression', O.PAGES)

    def test_portrait_1_1(self):
        pr = pdf_printer(self.t)
        o = dict(printing.PRINT_DEFAULTS, orientation='portrait')
        printing.setup_printer(pr, o)
        pw, ph = printing.print_drawing(self.doc, pr, o)
        self.assertLess(pw, ph)                                            # reste en portrait
        self.assertAlmostEqual(pw, 210, delta=1)

    def test_scale_and_reduce(self):
        pr = pdf_printer(self.t)
        big = Document()
        big.plate = None
        big.add(Shape(path=Path([geom.rect(0, 0, 500, 20)])))
        o = dict(printing.PRINT_DEFAULTS, orientation='portrait', echelle='1', reduire=True)
        printing.setup_printer(pr, o)
        self.assertEqual(printing.print_drawing(big, pr, o)[0] < 300, True)
        self.assertGreater(pathlib.Path(self.t, 'x.pdf').stat().st_size, 500)
        for e in ('ajuster', '2', '0.5'):
            pr = pdf_printer(self.t)
            printing.print_drawing(self.doc, pr, dict(printing.PRINT_DEFAULTS, echelle=e, position='coin'))

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.add(Shape(path=Path([geom.rect(0, 0, 40, 30)])))
            pr = pdf_printer(self.t)
            self.assertTrue(w.print_dialog(exec_dialog=False, printer=pr, what='dessin'))
            self.assertEqual(pr.pageLayout().orientation(), QPageLayout.Orientation.Portrait)
            self.assertGreater(pathlib.Path(self.t, 'x.pdf').stat().st_size, 500)
            dlg = w.options_dialog(exec_dialog=False, page='Impression')
            self.assertIn('impression/echelle', dlg.widgets)
            dlg.reject()
        finally:
            w.modified = False
            w.close()

    def test_bat_default_portrait(self):
        from unittest import mock
        from vectordrive.ui import batdialog
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        seen = {}

        class Dlg:
            def __init__(self, parent, doc, info, items=None):
                seen['info'] = info

            def exec(self):
                return 0
        try:
            w.settings.remove('bat/orientation')
            with mock.patch.object(batdialog, 'BatDialog', Dlg):
                w._proof_info()
            self.assertEqual(seen['info'].orientation, 'portrait')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
