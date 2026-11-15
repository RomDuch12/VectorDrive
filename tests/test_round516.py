"""Round 516 : boîte Ouvrir — tri des fichiers par nom, date (récents d'abord), taille ou type, retenu."""
import os
import pathlib
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry
from vectordrive.ui import file_browser as FB

app = QApplication.instance() or QApplication([])


class TestSort(unittest.TestCase):
    def test_sorts(self):
        d = pathlib.Path(tempfile.mkdtemp())
        names = ['b.dxf', 'a.svg', 'c.vnd']
        for i, n in enumerate(names):
            doc = Document()
            for k in range(1 + 3 * i):                       # c.vnd le plus gros
                doc.add(Shape(path=geom.Path([geom.circle((5 * k, 0), 2)])))
            registry.save_document(doc, d / n)
        os.utime(d / 'a.svg', (time.time() - 3600, time.time() - 3600))   # le plus ancien
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w._remember_dir('ouvrir', str(d / 'b.dxf'))
            w.settings.setValue('navigateur/filtre', 0)
            dlg = w.file_browser(exec_dialog=False)
            files = lambda: [dlg.panel.list.item(i).text() for i in range(dlg.panel.list.count())  # noqa: E731
                             if dlg.panel.list.item(i).text() in names]
            dlg.sort.setCurrentIndex(dlg.sort.findData('nom'))
            self.assertEqual(files(), ['a.svg', 'b.dxf', 'c.vnd'])
            dlg.sort.setCurrentIndex(dlg.sort.findData('date'))
            self.assertEqual(files()[-1], 'a.svg')
            dlg.sort.setCurrentIndex(dlg.sort.findData('type'))
            self.assertEqual(files(), ['b.dxf', 'a.svg', 'c.vnd'])
            dlg.sort.setCurrentIndex(dlg.sort.findData('taille'))
            biggest = max(names, key=lambda n: (d / n).stat().st_size)
            self.assertEqual(files()[0], biggest)
            self.assertEqual(w.settings.value(FB.SORT_KEY), 'taille')
            dlg.reject()
            dlg2 = w.file_browser(exec_dialog=False)                  # retenu
            self.assertEqual(dlg2.sort.currentData(), 'taille')
            dlg2.sort.setCurrentIndex(dlg2.sort.findData('nom'))
            dlg2.reject()
        finally:
            w.settings.setValue(FB.SORT_KEY, 'nom')                   # pas de trace pour les autres essais
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
