"""Round 233 : B = bibliothèque — dossier `bibliotheque` à côté du programme,
symboles .smb et dessins DXF/VDZ posés d'un double-clic, vignettes des DXF."""
import os
import pathlib
import shutil
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
LIB = pathlib.Path(tempfile.mkdtemp()) / 'bibliotheque'
os.environ['VECTORDRIVE_BIBLIOTHEQUE'] = str(LIB)

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Document, Group, Shape
from vectordrive.io import registry

app = QApplication.instance() or QApplication([])


def make_dxf(path: pathlib.Path) -> pathlib.Path:
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(100, 200, 20, 10)]), tool=0))
    d.add(Shape(path=geom.Path([geom.circle((110, 205), 3)]), tool=0))
    registry.save_document(d, path)
    return path


class TestLibrary(unittest.TestCase):
    def test_root_dxf_listing_preview_and_insert(self):
        from vectordrive.ui import symbols as SY
        from vectordrive.ui.main_window import MainWindow
        self.assertEqual(SY.library_root(), LIB)
        shutil.rmtree(LIB, ignore_errors=True)        # vide au début (un essai d'avant : « Logos BAT »)
        self.addCleanup(shutil.rmtree, LIB, True)     # et à la fin (l'export des essais suivants)
        f = make_dxf(LIB / 'plaque_type.dxf') if LIB.mkdir(parents=True, exist_ok=True) is None else None
        (LIB / 'notes.txt').write_text('pas un dessin', encoding='utf-8')
        w = MainWindow()
        panel = w.symbols
        self.assertEqual(panel.roots[0], LIB)                               # la bibliothèque en tête
        self.assertEqual(panel.tree.topLevelItem(2).text(0), 'bibliotheque')    # 0, 1 : Récents, Favoris
        panel.show_folder(LIB)
        names = [panel.list.item(i).text() for i in range(panel.list.count())]
        self.assertEqual(names, ['plaque_type'])                            # DXF listé, .txt ignoré
        for _ in range(100):                                                # vignette : tracée en fond (255)
            if not panel.list.item(0).icon().isNull():
                break
            QTest.qWait(30)
        self.assertFalse(panel.list.item(0).icon().isNull())
        img = SY.preview_image(f)
        self.assertEqual((img.width(), img.height()), (SY.THUMB, SY.THUMB))
        w.insert_symbol(str(f), at=(10.0, 20.0))                            # posé centré sur le point
        items = [it for L in w.canvas.doc.layers for it in L.items]
        self.assertEqual(len(items), 1)
        g = items[0]
        self.assertIsInstance(g, Group)
        bb = g.bbox()
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 10.0, 6)
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, 20.0, 6)
        self.assertEqual(g.name, 'plaque_type')
        self.assertTrue(w.A['symbols'].isCheckable())                       # B (TypeEdit) : le panneau
        w.modified = False
        w.close()


if __name__ == '__main__':
    unittest.main()
