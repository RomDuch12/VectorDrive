"""Round 492 : Ouvrir (Ctrl+O) — navigateur à vignettes (dossiers du poste, filtre par format, recherche
par nom, vignettes à la taille choisie, ouvrir ou insérer)."""
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

app = QApplication.instance() or QApplication([])


def pump(sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.01)


class TestFileBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = pathlib.Path(tempfile.mkdtemp())
        doc = Document()
        doc.add(Shape(path=geom.Path([geom.circle((0, 0), 10)])))
        for ext in ('.vnd', '.dxf', '.svg', '.eps'):
            registry.save_document(doc, cls.dir / ('rond' + ext))
        (cls.dir / 'notes.txt').write_text('x')
        (cls.dir / 'Sous dossier').mkdir()
        registry.save_document(doc, cls.dir / 'Sous dossier' / 'Éclair.dxf')

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w._remember_dir('ouvrir', str(self.dir / 'rond.vnd'))
        self.w.settings.setValue('navigateur/filtre', 0)              # filtre retenu d'un essai à l'autre
        self.dlg = self.w.file_browser(exec_dialog=False)
        self.p = self.dlg.panel

    def tearDown(self):
        self.dlg.reject()
        self.w.modified = False
        self.w.close()

    def names(self):
        return [self.p.list.item(i).text() for i in range(self.p.list.count())]

    def test_folder_and_filter(self):
        self.assertEqual(self.p._folder, self.dir)                  # dernier dossier d'ouverture
        self.assertEqual(self.names(), ['..', 'Sous dossier', 'rond.dxf', 'rond.eps', 'rond.svg', 'rond.vnd'])
        self.dlg.filter.setCurrentIndex(next(i for i in range(self.dlg.filter.count())
                                             if self.dlg.filter.itemData(i) == ['.dxf']))
        self.assertEqual(self.names(), ['..', 'Sous dossier', 'rond.dxf'])
        self.p.search.setText('eclair')                             # sans accents ni casse, sous-dossiers compris
        self.p._search()
        self.assertEqual(self.names(), ['Sous dossier/Éclair.dxf'])                 # Détails (r545) : son sous-dossier devant

    def test_thumbnails_size(self):
        self.p.size.setValue(300)
        self.assertEqual(self.p.list.thumb, 300)
        pump(3)
        it = next(self.p.list.item(i) for i in range(self.p.list.count()) if self.p.list.item(i).text() == 'rond.vnd')
        self.assertFalse(it.icon().isNull())
        self.assertEqual(self.p.size.maximum(), 512)

    def test_choose(self):
        it = next(self.p.list.item(i) for i in range(self.p.list.count()) if self.p.list.item(i).text() == 'rond.svg')
        up = next(self.p.list.item(i) for i in range(self.p.list.count()) if self.p.list.item(i).text() == '..')
        self.assertEqual(pathlib.Path(up.data(256)), self.dir.parent)          # jusqu'à la racine du lecteur
        self.p._activated(it)
        self.assertEqual(self.dlg.paths, [str(self.dir / 'rond.svg')])
        self.assertFalse(self.dlg.insert)

    def test_option(self):
        from vectordrive.ui.options import value
        self.assertTrue(value(self.w.settings, 'ouvrir/navigateur'))


if __name__ == '__main__':
    unittest.main()
