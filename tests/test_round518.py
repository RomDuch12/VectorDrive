"""Round 518 : plan de travail — encre des outils calculée une fois par couleur et par repeint (le thème
était relu pour chaque objet : 10 000 objets, repeint 0,5 s → 0,1 s)."""
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


class TestInkCache(unittest.TestCase):
    def test_once_per_color_and_paint(self):
        from vectordrive.ui import canvas as C
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            for i in range(200):
                w.canvas.doc.add(Shape(path=geom.Path([geom.circle((3 * (i % 20), 3 * (i // 20)), 1)]),
                                       tool=i % 2))
            w.resize(800, 600)
            w.show()
            app.processEvents()
            real = C.ink
            with mock.patch.object(C, 'ink', side_effect=real) as k:
                w.canvas.invalidate()
                w.canvas.repaint()
                app.processEvents()
            colors = {w.canvas.doc.tool_color(t) for t in (0, 1)}
            calls = [c for c in k.call_args_list if c.args and c.args[0] in colors]
            self.assertGreaterEqual(len(calls), 1)                          # le repeint a bien eu lieu
            self.assertLessEqual(len(calls), len(colors))                   # une fois par couleur, pas par objet
            it = w.canvas.doc.layers[0].items[0]
            self.assertEqual(w.canvas._color(it), real(w.canvas.doc.tool_color(it.tool)))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
