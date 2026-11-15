"""Round 344 : isoler la sélection (comme ISOLER en DAO) — les autres objets
masqués le temps de l'isolement, ceux masqués avant restent masqués."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestIsolate(unittest.TestCase):
    def test_isolate(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            a, b, h = (Shape(path=geom.Path([geom.rect(i * 10, 0, 5, 5)])) for i in range(3))
            h.visible = False                                            # masqué avant
            for s in (a, b, h):
                c.doc.add(s)
            c.select([a])
            self.assertEqual(w.isolate(), 1)
            self.assertEqual([s.visible for s in c.doc.layers[0].items], [True, False, False])
            self.assertEqual(w.unisolate(), 1)
            self.assertEqual([s.visible for s in c.doc.layers[0].items], [True, True, False])
            self.assertFalse(any('isole' in s.extra for s in c.doc.layers[0].items))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
