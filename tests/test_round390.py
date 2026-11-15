"""Round 390 : calques — inverser la visibilité (TypeEdit)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Layer, Shape

app = QApplication.instance() or QApplication([])


class TestInvert(unittest.TestCase):
    def test_invert(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            doc = w.canvas.doc
            doc.layers.append(Layer(name='B', visible=False))
            doc.layers.append(Layer(name='C'))
            s = Shape(path=geom.Path([geom.rect(0, 0, 5, 5)]))
            doc.layers[0].items.append(s)
            w.canvas.select([s])
            n = w.layers_panel.invert_visibility()
            self.assertEqual(n, 1)
            self.assertEqual([L.visible for L in doc.layers], [False, True, False])
            self.assertEqual(w.canvas.selection, [])                    # l'objet masqué n'est plus choisi
            w.layers_panel.invert_visibility()
            self.assertEqual([L.visible for L in doc.layers], [True, False, True])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
