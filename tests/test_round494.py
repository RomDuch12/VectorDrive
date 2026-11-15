"""Round 494 : navigateur Ouvrir — accès rapides de Windows en tête de l'arbre."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.ui import file_browser as FB

app = QApplication.instance() or QApplication([])


class TestQuickAccess(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        (self.dir / 'Clients').mkdir()
        self.old = FB._QUICK
        FB._QUICK = [self.dir / 'Clients', pathlib.Path('//serveur-absent/partage/GRAVURE')]

    def tearDown(self):
        FB._QUICK = self.old

    def test_tree_and_list(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            dlg = w.file_browser(exec_dialog=False)
            p = dlg.panel
            q = p.tree.topLevelItem(2)
            self.assertEqual(q.data(0, 256), FB.QUICK)
            self.assertEqual([q.child(i).text(0) for i in range(q.childCount())], ['Clients', 'GRAVURE'])
            p._folder_clicked(q)
            names = [p.list.item(i).text() for i in range(p.list.count())]
            self.assertEqual(names, ['Clients', 'GRAVURE'])
            p._folder_clicked(q.child(0))
            self.assertEqual(p._folder, self.dir / 'Clients')
            dlg.reject()
        finally:
            w.modified = False
            w.close()

    def test_image_thumbnail(self):
        from PySide6.QtCore import QBuffer, QIODevice
        from PySide6.QtGui import QColor, QImage
        from vectordrive.core.document import Document, Image
        from vectordrive.core.geom import Affine
        from vectordrive.io import registry
        from vectordrive.ui.symbols import preview_image
        q = QImage(20, 10, QImage.Format.Format_RGB32)
        q.fill(QColor('red'))
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        q.save(buf, 'PNG')
        doc = Document()
        doc.add(Image(data=bytes(buf.data()), fmt='png', matrix=Affine(40, 0, 0, -20, 0, 20)))
        f = self.dir / 'photo.vdz'
        registry.save_document(doc, f)
        img = preview_image(f, 100)
        c = img.pixelColor(50, 50)
        self.assertGreater(c.red(), 200)                     # l'image est dans la vignette (avant : blanche)
        self.assertLess(c.green(), 80)

    def test_read_once(self):
        FB._QUICK = None
        os.environ['VECTORDRIVE_NO_QUICK'] = '1'
        try:
            self.assertEqual(FB.quick_access(), [])
            self.assertEqual(FB._QUICK, [])
        finally:
            del os.environ['VECTORDRIVE_NO_QUICK']


if __name__ == '__main__':
    unittest.main()
