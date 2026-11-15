"""Round 468 : grande fenêtre de la bibliothèque — « Fermer après avoir posé »."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

DXF = "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n5\n0\nENDSEC\n0\nEOF\n"


class TestCloseAfter(unittest.TestCase):
    def test_close_after(self):
        from vectordrive.ui.main_window import MainWindow
        f = pathlib.Path(tempfile.mkdtemp()) / 'a.dxf'
        f.write_text(DXF, encoding='ascii')
        w = MainWindow()
        try:
            lw = w.library_window(show=True)
            lw.click_place.setChecked(False)                                      # pose au centre (r544)
            lw.close_after.setChecked(False)
            lw.panel.insertRequested.emit(str(f))
            self.assertTrue(lw.isVisible())                                       # reste ouverte
            lw.close_after.setChecked(True)
            self.assertIn(w.settings.value('symboles/fermer_apres'), (True, 'true'))
            lw.panel.insertRequested.emit(str(f))
            self.assertFalse(lw.isVisible())                                      # fermée après la pose
            self.assertEqual(len(list(w.canvas.doc.iter_items())), 2)
        finally:
            w.settings.setValue('symboles/poser_au_clic', True)              # pas de fuite (r552)
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
