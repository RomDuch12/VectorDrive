"""Round 537 : vignettes — changer de taille réutilise une vignette déjà tracée plus grande (réduite,
sans retracer) ; une plus petite s'affiche agrandie le temps que la bonne arrive. Grand aperçu et fiche du
fichier choisi calculés dans un fil (un gros DXF figeait la fenêtre ~6 s à chaque clic)."""
import os
import pathlib
import tempfile
import threading
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry
from vectordrive.ui import symbols as SY

app = QApplication.instance() or QApplication([])


class TestNearest(unittest.TestCase):
    def test_cache_index(self):
        c = SY.ImageCache(64)
        c[('a', 96, 1.0)] = QImage(96, 96, QImage.Format.Format_ARGB32)
        c[('a', 256, 1.0)] = QImage(256, 256, QImage.Format.Format_ARGB32)
        self.assertEqual(c.nearest('a', 128, 1.0)[1], 256)
        self.assertEqual(c.nearest('a', 512, 1.0)[1], 256)
        self.assertEqual(c.nearest('a', 128, 2.0), (None, 0))           # autre date : rien
        c.clear()
        self.assertEqual(c.nearest('a', 128, 1.0), (None, 0))

    def test_resize_without_redraw(self):
        d = pathlib.Path(tempfile.mkdtemp())
        doc = Document()
        doc.add(Shape(path=geom.Path([geom.circle((0, 0), 5)])))
        registry.save_document(doc, d / 'rond.dxf')
        st = QSettings(str(d / 's.ini'), QSettings.Format.IniFormat)
        st.setValue('symboles/dossiers', [str(d)])
        p = SY.SymbolPanel(st, big=True)
        p.size.setValue(300)
        p.show_folder(d)
        t = time.time()
        while time.time() - t < 20 and (p._pending or getattr(p, '_jobs', None)):
            app.processEvents()
            time.sleep(0.02)
        with mock.patch.object(SY, 'preview_image', wraps=SY.preview_image) as draw:
            p.size.setValue(120)                                          # plus petite : réduite
            t = time.time()
            while time.time() - t < 5 and (p._pending or getattr(p, '_jobs', None)):
                app.processEvents()
                time.sleep(0.02)
        self.assertEqual(draw.call_count, 0)                              # pas retracée
        it = next(p.list.item(i) for i in range(p.list.count()) if p.list.item(i).text() == 'rond')
        img = it.icon().pixmap(120, 120).toImage()
        self.assertTrue(any(img.pixelColor(x, 60).alpha() for x in range(120)))
        p.close()


class TestDetailsInThread(unittest.TestCase):
    def test_async_details(self):
        d = pathlib.Path(tempfile.mkdtemp())
        doc = Document()
        doc.add(Shape(path=geom.Path([geom.circle((0, 0), 5)])))
        registry.save_document(doc, d / 'rond.dxf')
        st = QSettings(str(d / 's.ini'), QSettings.Format.IniFormat)
        st.setValue('symboles/dossiers', [str(d)])
        p = SY.SymbolPanel(st, big=True)
        p.resize(900, 600)
        p.show_folder(d)
        it = next(p.list.item(i) for i in range(p.list.count()) if p.list.item(i).text() == 'rond')
        p.list.setCurrentItem(it)
        threads = []
        real = SY.describe_file

        def slow(path):
            threads.append(threading.current_thread().name)
            time.sleep(0.3)
            return real(path)
        with mock.patch.object(SY, 'describe_file', side_effect=slow):
            t = time.perf_counter()
            p.update_preview()
            self.assertLess(time.perf_counter() - t, 0.25)               # rend la main tout de suite
            self.assertTrue(p.file_info.text().startswith('rond.dxf'))
            t = time.time()
            while time.time() - t < 10 and getattr(p, '_djob', None) is not None:
                app.processEvents()
                time.sleep(0.02)
        self.assertTrue(threads and threads[0].startswith('fiche'))
        self.assertIn('objet', p.file_info.text())
        self.assertFalse(p.preview.pixmap().isNull())
        with mock.patch.object(SY, 'describe_file', side_effect=AssertionError('relue')):
            p.update_preview()                                            # gardée : rien à relire
        p.close()


if __name__ == '__main__':
    unittest.main()
