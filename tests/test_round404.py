"""Round 404 : vectoriser en arcs et segments (TypeEdit)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QFileDialog

from vectordrive.core import biarc
from tests.test_round28 import logo

app = QApplication.instance() or QApplication([])


class TestTraceArcs(unittest.TestCase):
    def test_arcs(self):
        from vectordrive.ui import dialogs
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        g = (logo() * 255).astype(np.uint8)
        img = QImage(g.data, g.shape[1], g.shape[0], g.shape[1], QImage.Format.Format_Grayscale8).copy()

        class Fake:
            def __init__(self, parent, title, params, labels, warning=''):
                self.p = params
                self.p.width = 100.0
                self.p.arcs = True

            def exec(self):
                return True

            def result_params(self):
                return self.p
        saved = (dialogs.ParamsDialog, QFileDialog.getOpenFileName)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                f = pathlib.Path(tmp) / 'logo.png'
                img.save(str(f))
                dialogs.ParamsDialog = Fake
                QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(f), ''))
                w.trace_image()
            st = biarc.stats(w.canvas.selection[0].path)
            self.assertEqual(st['autres'], 0)                      # rien que des droites et des arcs
            self.assertGreater(st['arcs'], 0)
        finally:
            dialogs.ParamsDialog, QFileDialog.getOpenFileName = saved[0], staticmethod(saved[1])
            w.settings.setValue('vectorisation/arcs', False)
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
