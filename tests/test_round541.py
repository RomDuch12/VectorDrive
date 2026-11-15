"""Round 541 : plan de travail sans couleurs d'outils — l'encre unique est calculée une fois par repeint
(comme les encres des outils depuis le round 518)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestBlackInk(unittest.TestCase):
    def test_once_per_paint(self):
        from vectordrive.ui import canvas as C
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            for i in range(100):
                w.canvas.doc.add(Shape(path=geom.Path([geom.circle((3 * (i % 10), 3 * (i // 10)), 1)])))
            w.canvas.tool_colors = False
            w.resize(800, 600)
            w.show()
            app.processEvents()
            with mock.patch.object(C, 'ink', side_effect=C.ink) as k:
                w.canvas.invalidate()
                w.canvas.repaint()
                app.processEvents()
            calls = [c for c in k.call_args_list if c.args and c.args[0] == '#000000']
            self.assertEqual(len(calls), 1)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
