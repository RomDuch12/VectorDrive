"""Round 450 : bibliothèque — vignettes à la taille voulue (curseur, Ctrl + molette), tracées en
vectoriel ; aperçu grand format et fiche du fichier ; grande fenêtre."""
import os
import pathlib
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

DXF = ("0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n8\n0\n90\n4\n70\n1\n10\n0\n20\n0\n10\n40\n20\n0\n10\n40\n20\n20\n"
       "10\n0\n20\n20\n0\nENDSEC\n0\nEOF\n")


def library():
    root = pathlib.Path(tempfile.mkdtemp()) / 'bibliotheque'
    (root / 'Plaques').mkdir(parents=True)
    (root / 'Plaques' / 'rect.dxf').write_text(DXF, encoding='ascii')
    return root


def settle(p):
    t = time.time()
    while (p._pending or p._jobs) and time.time() - t < 20:
        p._load_some()
        time.sleep(0.01)


class TestPreviews(unittest.TestCase):
    def test_vector_preview_and_info(self):
        from vectordrive.ui import symbols as S
        root = library()
        img = S.preview_image(root / 'Plaques' / 'rect.dxf', 200)
        self.assertEqual((img.width(), img.height()), (200, 200))
        self.assertLess(QColor(img.pixel(100, 100)).lightness(), 255)            # rectangle teinté
        info = S.describe_file(root / 'Plaques' / 'rect.dxf')
        self.assertIn('40,00 × 20,00 mm', info)
        self.assertIn('1 objet(s)', info)

    def test_size_slider_and_preview_pane(self):
        from vectordrive.ui import symbols as S
        root = library()
        st = QSettings(os.path.join(tempfile.mkdtemp(), 'r.ini'), QSettings.Format.IniFormat)
        st.setValue('symboles/dossiers', [str(root)])
        p = S.SymbolPanel(st)
        p.roots = [root]
        p._fill_tree()
        p.show_folder(root / 'Plaques')
        settle(p)
        p.size.setValue(200)
        self.assertEqual(int(st.value(S.SIZE_KEY)), 200)
        self.assertEqual(p.list.iconSize().width(), 200)
        settle(p)
        f = next(p.list.item(i) for i in range(p.list.count()) if p.list.item(i).data(S.ROLE_KIND) is None)
        self.assertFalse(f.icon().isNull())
        self.assertGreaterEqual(p.list.visualItemRect(f).width(), 200)            # cases à la taille des vignettes
        p.list.setCurrentItem(f)
        p.update_preview()
        self.assertFalse(p.preview.pixmap().isNull())
        self.assertIn('rect.dxf', p.file_info.text())
        p.deleteLater()


class TestBigWindow(unittest.TestCase):
    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            lw = w.library_window(show=False)
            self.assertIs(w.library_window(show=False), lw)                       # une seule, gardée
            self.assertTrue(lw.panel.big)
            self.assertTrue(lw.vd_keep)
            self.assertEqual(lw.panel.splitter_orientation() if hasattr(lw.panel, 'splitter_orientation')
                             else Qt.Orientation.Horizontal, Qt.Orientation.Horizontal)
            self.assertTrue(hasattr(w.symbols, 'big_button'))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
