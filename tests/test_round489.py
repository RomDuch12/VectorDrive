"""Round 489 : schéma de l'opération — titre de la coupe sans la rampe (ligne à part)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication

from vectordrive.cam import model

app = QApplication.instance() or QApplication([])


class TestRampText(unittest.TestCase):
    def test_lines(self):
        from vectordrive.ui.cam_panel import FieldsDialog
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            op = model.Operation(kind='contour', ramp=True, ramp_angle=15, depth=1.2, step_down=0.4)
            d = FieldsDialog(w.cam_panel, 'Essai', op, doc=w.canvas.doc, tools=[])
            texts = []
            real = QPainter.drawText

            def spy(self, *a):
                texts.append(a[-1])
                return real(self, *a)
            d.illustration.resize(260, 400)
            with mock.patch.object(QPainter, 'drawText', spy):
                d.illustration.grab()
            self.assertIn('Profondeur 1.2 mm — 3 passe(s)', texts)
            self.assertIn('Rampe 15° sur 1,5 mm par passe', texts)
            d.reject()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
