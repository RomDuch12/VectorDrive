"""Round 552 : panneau Bibliothèque — double-clic, puis un clic pour poser (comme la grande fenêtre),
réglage dans F10 › Fichiers."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

DXF = "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n4\n0\nENDSEC\n0\nEOF\n"


class TestPanel(unittest.TestCase):
    def test_panel_double_click(self):
        from vectordrive.ui import tools as T
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.options import BY_KEY
        self.assertTrue(BY_KEY['symboles/poser_au_clic'].default)
        f = pathlib.Path(tempfile.mkdtemp()) / 'a.dxf'
        f.write_text(DXF, encoding='ascii')
        w = MainWindow()
        try:
            w.settings.setValue('symboles/poser_au_clic', True)              # réglage d'autres essais
            w.symbols.insertRequested.emit(str(f))
            self.assertIsInstance(w.canvas.tool_obj, T.PlaceGroupTool)
            w.canvas.tool_obj.press(None, (5.0, 5.0), None)
            self.assertEqual(len(list(w.canvas.doc.iter_items())), 1)
            w.settings.setValue('symboles/poser_au_clic', False)
            w.symbols.insertRequested.emit(str(f))                        # décoché : au centre, aussitôt
            self.assertEqual(len(list(w.canvas.doc.iter_items())), 2)
        finally:
            w.settings.setValue('symboles/poser_au_clic', True)
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
