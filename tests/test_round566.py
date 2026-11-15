"""Round 566 : Ouvrir › « Insérer dans le dessin » d'un seul dessin — posé d'un clic, comme depuis la
bibliothèque (même réglage) ; plusieurs : au centre de la vue comme avant."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

DXF = "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n4\n0\nENDSEC\n0\nEOF\n"


class TestInsertByClick(unittest.TestCase):
    def run_browser(self, w, paths):
        from vectordrive.ui import file_browser as FB

        def fake_exec(dlg):
            dlg.paths, dlg.insert = [str(p) for p in paths], True
            return 1
        with mock.patch.object(FB.FileBrowser, 'exec', fake_exec):
            w.file_browser()

    def test_single_and_many(self):
        from vectordrive.ui import tools as T
        from vectordrive.ui.main_window import MainWindow
        d = pathlib.Path(tempfile.mkdtemp())
        a, b = d / 'a.dxf', d / 'b.dxf'
        a.write_text(DXF, encoding='ascii')
        b.write_text(DXF, encoding='ascii')
        w = MainWindow()
        try:
            w.settings.setValue('symboles/poser_au_clic', True)
            self.run_browser(w, [a])
            self.assertIsInstance(w.canvas.tool_obj, T.PlaceGroupTool)
            w.canvas.toolFinished.emit()
            self.assertEqual(len(list(w.canvas.doc.iter_items())), 0)
            self.run_browser(w, [a, b])                                        # plusieurs : au centre, aussitôt
            self.assertEqual(len(list(w.canvas.doc.iter_items())), 2)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
