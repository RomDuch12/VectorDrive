"""Round 538 : récents — aperçu d'un gros fichier calculé en fond (la liste ne gèle plus) ; poser un
symbole lourd — lu dans le fil de calcul (barre de progression, fenêtre vivante)."""
import os
import pathlib
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry
from vectordrive.ui import recent

app = QApplication.instance() or QApplication([])


def drawing():
    d = pathlib.Path(tempfile.mkdtemp())
    doc = Document()
    doc.add(Shape(path=geom.Path([geom.circle((0, 0), 5)])))
    f = d / 'rond.dxf'
    registry.save_document(doc, f)
    return f


class TestRecentAsync(unittest.TestCase):
    def test_big_file_in_background(self):
        f = drawing()
        p = recent.RecentPanel([str(f)])
        with mock.patch.object(recent, 'SYNC_MAX', 0), mock.patch.object(recent, 'previews_on', return_value=True):
            p.tree.setCurrentItem(p.tree.topLevelItem(0))
            p._current_changed()
            self.assertIn('Aperçu', p.preview.text())                    # pas calculé dans le fil de l'interface
            t = time.time()
            while time.time() - t < 10 and getattr(p, '_pjob', None) is not None:
                app.processEvents()
                time.sleep(0.02)
        self.assertFalse(p.preview.pixmap().isNull())

    def test_insert_symbol_in_worker(self):
        from vectordrive.ui import progress
        from vectordrive.ui.main_window import MainWindow
        f = drawing()
        w = MainWindow()
        try:
            real = progress.run
            with mock.patch.object(progress, 'run', side_effect=real) as r:
                w.insert_symbol(str(f))
            self.assertTrue(r.called)
            self.assertEqual(len(w.canvas.selection), 1)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
