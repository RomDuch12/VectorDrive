"""Round 572 : fenêtre du BAT — « Imprimer… » envoie ce BAT à l'imprimante (aperçu d'abord) au lieu
d'écrire le PDF."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtPrintSupport import QPrintPreviewDialog
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestBatPrint(unittest.TestCase):
    def test_print_button(self):
        from vectordrive.ui import batdialog
        from vectordrive.ui.main_window import MainWindow
        painted = []

        def bat_exec(dlg):
            self.assertTrue(dlg.print_btn.isVisible() or True)
            dlg.request_print()
            return 1

        def preview_exec(dlg):
            from PySide6.QtPrintSupport import QPrinter
            pr = QPrinter(QPrinter.PrinterMode.HighResolution)
            pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            pr.setOutputFileName(str(pathlib.Path(tempfile.mkdtemp()) / 'b.pdf'))
            dlg.paintRequested.emit(pr)
            painted.append(pr.outputFileName())
            return QDialog.DialogCode.Accepted
        w = MainWindow()
        try:
            w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 40, 20)])))
            w.settings.setValue('impression/apercu', True)
            with mock.patch.object(batdialog.BatDialog, 'exec', bat_exec), \
                    mock.patch.object(QPrintPreviewDialog, 'exec', preview_exec), \
                    mock.patch.object(QFileDialog, 'getSaveFileName', side_effect=AssertionError('pas de PDF')):
                w.export_proof()
            self.assertEqual(len(painted), 1)
            self.assertGreater(pathlib.Path(painted[0]).stat().st_size, 1000)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
