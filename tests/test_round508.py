"""Round 508 : vignettes lentes (gros DXF, dossier réseau) tracées sur plusieurs processus — la bibliothèque
et Ouvrir basculent d'eux-mêmes quand la moyenne dépasse SLOW_PREVIEW_S."""
import os
import pathlib
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry
from vectordrive.ui import symbols as SY

app = QApplication.instance() or QApplication([])


class TestSlowPreviews(unittest.TestCase):
    def test_png_in_process_function(self):
        d = pathlib.Path(tempfile.mkdtemp())
        doc = Document()
        doc.add(Shape(path=geom.Path([geom.circle((0, 0), 5)])))
        registry.save_document(doc, d / 'rond.dxf')
        png, dt = SY.preview_png(str(d / 'rond.dxf'), 64)
        self.assertEqual(QImage.fromData(png).width(), 64)
        self.assertGreaterEqual(dt, 0.0)
        self.assertEqual(SY.preview_png(str(d / 'absent.dxf'), 64)[0], b'')

    def test_switch_to_processes(self):
        d = pathlib.Path(tempfile.mkdtemp())
        for i in range(10):
            doc = Document()
            doc.add(Shape(path=geom.Path([geom.circle((0, 0), 1 + i)])))
            registry.save_document(doc, d / f'rond{i}.dxf')
        st = QSettings(str(d / 's.ini'), QSettings.Format.IniFormat)
        st.setValue('symboles/dossiers', [str(d)])
        p = SY.SymbolPanel(st)
        with mock.patch.object(SY, 'SLOW_PREVIEW_S', -1.0):            # toutes « lentes »
            p.show_folder(d)
            t = time.time()
            while time.time() - t < 60 and (p._pending or getattr(p, '_jobs', None)):
                app.processEvents()
                time.sleep(0.02)
            self.assertTrue(p.slow_previews())
            self.assertGreater(p.queue_size(), p.QUEUE)
        self.assertIsNotNone(SY._PROC_POOL)
        icons = [p.list.item(i).icon().pixmap(64, 64).toImage() for i in range(p.list.count())
                 if (p.list.item(i).data(256) or '').endswith('.dxf')]
        self.assertEqual(len(icons), 10)
        self.assertTrue(all(any(img.pixelColor(x, 32).alpha() for x in range(64)) for img in icons))
        p.close()


if __name__ == '__main__':
    unittest.main()
