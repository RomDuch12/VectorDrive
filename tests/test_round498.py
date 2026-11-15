"""Round 498 : bibliothèque et navigateur — la ligne d'un fichier a sa taille de vignette avant que la
vignette n'arrive (plus de vignette tronquée au défilement)."""
import os
import pathlib
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Shape
from vectordrive.io import registry
from vectordrive.ui.symbols import SymbolPanel

app = QApplication.instance() or QApplication([])


class TestThumbPlace(unittest.TestCase):
    def test_item_sized_before_thumbnail(self):
        d = pathlib.Path(tempfile.mkdtemp())
        doc = Document()
        doc.add(Shape(path=geom.Path([geom.circle((0, 0), 10)])))
        for i in range(12):
            registry.save_document(doc, d / f'rond{i:02d}.dxf')
        settings = QSettings(str(d / 's.ini'), QSettings.Format.IniFormat)
        settings.setValue('symboles/dossiers', [str(d)])
        p = SymbolPanel(settings)
        p.resize(500, 700)
        p.show()
        p.size.setValue(120)
        p._timer.stop()
        p.show_folder(d)
        p._timer.stop()                                  # vignettes pas encore tracées
        it = next(p.list.item(i) for i in range(p.list.count()) if p.list.item(i).text() == 'rond00')
        app.processEvents()
        self.assertGreaterEqual(p.list.visualItemRect(it).height(), 120)
        last = p.list.item(p.list.count() - 1).icon().pixmap(120, 120).toImage()
        self.assertEqual(last.pixelColor(60, 60).alpha(), 0)                      # case vide, transparente
        p._timer.start(0)
        t = time.time()
        img = None
        while time.time() - t < 5:
            app.processEvents()
            img = it.icon().pixmap(120, 120).toImage()
            if any(img.pixelColor(x, 60).alpha() for x in range(120)):
                break
            time.sleep(0.02)
        self.assertTrue(any(img.pixelColor(x, 60).alpha() for x in range(120)))     # la vraie vignette
        p.close()


if __name__ == '__main__':
    unittest.main()
