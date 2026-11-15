"""Round 488 : catalogue — « Documentation » ouvre le PDF du poste à la page de l'opération."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtGui import QPageSize, QPainter, QPdfWriter
from PySide6.QtWidgets import QApplication

from vectordrive.cam import catalog as C

app = QApplication.instance() or QApplication([])


def make_pdf(pages: int) -> str:
    path = os.path.join(tempfile.mkdtemp(), 'manuel.pdf')
    w = QPdfWriter(path)
    w.setPageSize(QPageSize(QPageSize.PageSizeId.A6))
    p = QPainter(w)
    for k in range(pages):
        if k:
            w.newPage()
        p.drawText(100, 100, f'Page {k + 1}')
    p.end()
    return path


class TestDoc(unittest.TestCase):
    def test_open_at_page(self):
        from vectordrive.ui import instruction_catalog as IC
        pdf = make_pdf(5)
        e = C.Entry(name='Commande', text='Commande', doc=pdf, page=4, catalog='Essai')
        st = QSettings(os.path.join(tempfile.mkdtemp(), 'd.ini'), QSettings.Format.IniFormat)
        dlg = IC.CatalogDialog(None, catalogs=[('Essai', [e], '')], settings=st)
        it = dlg.entries()[0][0]
        dlg.tree.setCurrentItem(it)
        self.assertFalse(dlg.doc_button.isHidden())
        self.assertIn('p. 4', dlg.doc_button.text())
        win = dlg.open_doc()
        for _ in range(5):
            app.processEvents()
        self.assertEqual(win.pdf.pageCount(), 5)
        self.assertEqual(win.view.pageNavigator().currentPage(), 3)
        self.assertEqual(win.show_page(pdf, 99), 5)                           # au plus la dernière
        win.close()
        missing = C.Entry(name='Autre', doc='C:/introuvable.pdf', page=2, catalog='Essai')
        self.assertIsNone(dlg.open_doc(missing))
        self.assertIn('introuvable', dlg.note.text())


if __name__ == '__main__':
    unittest.main()
