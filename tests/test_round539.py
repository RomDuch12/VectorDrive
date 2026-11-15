"""Round 539 : fenêtre BAT — sur un gros dessin, la page de l'aperçu est calculée dans un fil (la fenêtre
ne gèle plus à chaque réglage) ; même page qu'à la suite."""
import os
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import proof
from vectordrive.ui import batdialog as BD

app = QApplication.instance() or QApplication([])


class TestBatAsync(unittest.TestCase):
    def test_async_preview(self):
        doc = Document()
        for i in range(30):
            doc.add(Shape(path=geom.Path([geom.circle((6 * (i % 6), 6 * (i // 6)), 2)])))
        with mock.patch.object(BD, 'ASYNC_ITEMS', 5):
            dlg = BD.BatDialog(None, doc, proof.ProofInfo(client='BFM'))
            dlg.refresh()
            self.assertIn('Aperçu en cours', dlg.scale_info.text())
            t = time.time()
            while time.time() - t < 20 and getattr(dlg, '_pjob', None) is not None:
                app.processEvents()
                time.sleep(0.02)
        self.assertIn(':1', dlg.scale_info.text())
        self.assertFalse(dlg.preview.pixmap().isNull())
        ref = BD.render_page(doc, dlg.result_info())
        self.assertEqual((ref.width(), ref.height()), (dlg.preview.pixmap().width(), dlg.preview.pixmap().height()))


if __name__ == '__main__':
    unittest.main()
