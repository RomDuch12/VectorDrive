"""Round 514 : F10 › Performances — mémoire de VectorDrive et de ses mémoires de séance (vignettes,
simulations, parcours), bouton « Vider les mémoires »."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from vectordrive.ui import resources as R

app = QApplication.instance() or QApplication([])


class TestResources(unittest.TestCase):
    def test_usage_and_clear(self):
        from vectordrive.cam import strategies
        from vectordrive.core import fonts
        from vectordrive.ui.symbols import _PREVIEWS
        _PREVIEWS[('essai', 1, 0)] = QImage(512, 512, QImage.Format.Format_ARGB32)
        strategies._TP_CACHE['essai'] = None
        ff = fonts.find_font('Arial')
        if ff:
            fonts.glyph(ff[0], ff[1], 'A')
        u = R.usage()
        self.assertGreaterEqual(u['thumbs'], 1.0)
        self.assertGreaterEqual(u['paths'], 1)
        if sys.platform == 'win32':
            self.assertGreater(u['process'], 10)
            self.assertIn('Mo de mémoire', R.usage_text())
        R.clear_all()
        u = R.usage()
        self.assertEqual((u['thumbs'], u['paths'], u['glyphs'], u['sims']), (0.0, 0, 0, 0.0))

    def test_options_page(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            dlg = w.options_dialog(exec_dialog=False, page='Performances')
            self.assertIn('parcours gardés', dlg.usage.text())
            dlg.clear_memories()
            self.assertIn('Vignettes : 0 Mo', dlg.usage.text())
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
