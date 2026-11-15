"""Round 584 : Ouvrir › clic droit › « Imprimer… » — un dessin imprimé à l'échelle sans l'ouvrir (lu dans le
fil de calcul, réglages de F10 › Impression)."""
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
from vectordrive.io import registry

app = QApplication.instance() or QApplication([])


class TestPrintFile(unittest.TestCase):
    def test_print_without_opening(self):
        from vectordrive.ui import file_browser as FB
        from vectordrive.ui.main_window import MainWindow
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 80, 40)])))
        t = pathlib.Path(tempfile.mkdtemp())
        f = t / 'plaque.dxf'
        registry.save_document(d, f)
        out = t / 'x.pdf'
        pr = QPrinter(QPrinter.PrinterMode.HighResolution)
        pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        pr.setOutputFileName(str(out))
        w = MainWindow()
        try:
            n_tabs = len(w.docs)
            self.assertTrue(w.print_file(str(f), exec_dialog=False, printer=pr))
            self.assertGreater(out.stat().st_size, 500)
            self.assertEqual(len(w.docs), n_tabs)                              # pas d'onglet ouvert
            self.assertEqual(list(w.canvas.doc.iter_items()), [])
            dlg = w.file_browser(exec_dialog=False)
            dlg.panel.show_folder(t)
            row = next(i for i in range(dlg.panel.list.count()) if dlg.panel.list.item(i).text() == 'plaque.dxf')
            dlg.panel.list.setCurrentRow(row)
            dlg.panel.list.item(row).setSelected(True)
            m = dlg.panel.menu(dlg.panel.list, None, exec_menu=False)
            self.assertIn('Imprimer…', [a.text() for a in m.actions()])
            dlg.reject()
            lw = w.library_window(show=False)                                 # r585 : bibliothèque aussi
            lw.panel.show_folder(t)
            row = next(i for i in range(lw.panel.list.count()) if lw.panel.list.item(i).text().startswith('plaque'))
            lw.panel.list.item(row).setSelected(True)
            m = lw.panel.menu(lw.panel.list, None, exec_menu=False)
            self.assertIn('Imprimer…', [a.text() for a in m.actions()])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
