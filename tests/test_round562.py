"""Round 562 : impression — aperçu avant d'imprimer (F10 › Impression, coché) : la feuille telle qu'elle
sortira ; son bouton imprime, l'imprimante choisie est retenue."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import QApplication, QDialog

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestPreview(unittest.TestCase):
    def test_preview_paints_and_prints(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.options import BY_KEY
        self.assertTrue(BY_KEY['impression/apercu'].default)
        out = pathlib.Path(tempfile.mkdtemp()) / 'x.pdf'
        pr = QPrinter(QPrinter.PrinterMode.HighResolution)
        pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        pr.setOutputFileName(str(out))
        painted = []

        def fake_exec(dlg):
            dlg.paintRequested.emit(pr)                                     # l'aperçu peint la feuille
            painted.append(True)
            return QDialog.DialogCode.Accepted
        w = MainWindow()
        try:
            w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 40, 30)])))
            with mock.patch.object(QPrintPreviewDialog, 'exec', fake_exec):
                self.assertTrue(w.print_dialog(printer=pr, what='dessin'))
            self.assertEqual(painted, [True])
            self.assertGreater(out.stat().st_size, 500)
            w.settings.setValue('impression/apercu', False)                # décoché : boîte d'impression
            with mock.patch('PySide6.QtPrintSupport.QPrintDialog.exec', return_value=QDialog.DialogCode.Rejected):
                self.assertFalse(w.print_dialog(printer=pr, what='dessin'))
        finally:
            w.settings.setValue('impression/apercu', True)
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
