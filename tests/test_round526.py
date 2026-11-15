"""Round 526 : ouvrir plusieurs dessins d'un coup — lus ensemble (sur plusieurs processus quand c'est
long), puis un onglet chacun ; un fichier illisible n'arrête pas les autres."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.core import geom, workers
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry

app = QApplication.instance() or QApplication([])


class TestOpenPaths(unittest.TestCase):
    def test_open_together(self):
        d = pathlib.Path(tempfile.mkdtemp())
        files = []
        for i in range(5):
            doc = Document()
            for k in range(i + 1):
                doc.add(Shape(path=geom.Path([geom.circle((6 * k, 0), 2)])))
            f = d / f'rond{i}.dxf'
            registry.save_document(doc, f)
            files.append(str(f))
        bad = d / 'abime.dxf'
        bad.write_text('pas un dxf')
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            workers.set_count(3)
            with mock.patch.object(workers, 'SWITCH_S', 0.0), mock.patch.object(workers, 'PARALLEL_MIN', 2), \
                    mock.patch.object(QMessageBox, 'critical') as crit:
                n = w.open_paths(files + [str(bad)])
            self.assertEqual(n, 5)
            crit.assert_called_once()                                      # l'abîmé signalé, les autres ouverts
            w._store_current()
            counts = sorted(sum(1 for _ in t.doc.iter_leaves()) for t in w.docs if str(getattr(t.doc, 'source_path', '')) in files)
            self.assertEqual(counts, [1, 2, 3, 4, 5])
            self.assertEqual(registry.read_for_open(str(bad)).__class__.__name__ != 'Document', True)
        finally:
            workers.set_count(0)
            for t in w.docs:
                t.modified = False
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
