"""Round 1026 : plaques de reprise (suite) — la plaque posée depuis les dossiers de plaques (symbole, DXF…), sur un
calque à elle, verrouillé, jamais usiné ; la fenêtre des trous de fixation la pose et la prend pour la plaque."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1026.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Group, Layer, Plate, Shape  # noqa: E402


def circle(x, y, d, tool=0):
    return Shape(path=geom.Path([geom.circle((x, y), d / 2)]), tool=tool)


def no_plugin(family, key, value=None):
    """`plugins.default` sans plugin : les essais ne dépendent pas de ceux du poste."""
    return value


def plate_file(folder: pathlib.Path, name='Plaque 4x3.dxf') -> pathlib.Path:
    """Une plaque d'essai : 80 × 60, percée Ø 3,2 tous les 20 mm (4 × 3), dans une couleur (7) que le dessin n'a pas."""
    from vectordrive.io import dxf
    items = [Shape(path=geom.Path([geom.rect(0.0, 0.0, 80.0, 60.0)]), tool=7)]
    items += [circle(10.0 + 20 * i, 10.0 + 20 * j, 3.2, tool=7) for i in range(4) for j in range(3)]
    path = folder / name
    dxf.write(Document(layers=[Layer(name='Plaque', items=items)]), str(path))
    return path


class Model(unittest.TestCase):

    def test_plate_folders_and_files(self):
        from vectordrive.cam import fixture as FX
        tmp = pathlib.Path(tempfile.mkdtemp())
        mine, shop = tmp / 'mes plaques', tmp / 'atelier'
        (shop / 'Grandes').mkdir(parents=True)
        mine.mkdir()
        for p in (mine / 'B 2x2.smb', mine / 'notes.txt', shop / 'A 3x4.SMB', shop / 'Grandes' / 'C 6x4.dxf'):
            p.write_bytes(b'')

        class Settings:
            def value(self, key, default=None):
                return str(mine) if key == FX.FOLDER_KEY else default
        with mock.patch('vectordrive.plugins.default', lambda family, key, value=None:
                        [str(shop), str(tmp / 'absent'), str(mine)] if (family, key) == ('plaques', 'dossiers')
                        else value):
            folders = FX.plate_folders(Settings())
        self.assertEqual(folders, [mine, shop])                              # le dossier choisi d'abord, chacun une fois
        files = FX.plate_files(folders)
        self.assertEqual([n for n, _p in files], ['A 3x4', 'B 2x2', 'Grandes / C 6x4'])
        self.assertEqual(files[2][1], shop / 'Grandes' / 'C 6x4.dxf')
        with mock.patch('vectordrive.plugins.default', no_plugin):
            self.assertEqual(FX.plate_folders(None), [])
        with mock.patch.object(FX, 'MAX_FILES', 2):
            self.assertEqual(len(FX.plate_files(folders)), 2)                # un dossier trop vaste : liste bornée

    def test_plate_layer_never_machined(self):
        from vectordrive.cam import fixture as FX
        from vectordrive.cam import model, strategies
        plate = Layer(name='Plaque', items=[circle(10.0, 10.0, 3.2), circle(30.0, 10.0, 3.2)])
        plate.extra[FX.PLATE_LAYER] = {'fichier': 'x.dxf'}
        part = circle(20.0, 20.0, 6.0)
        doc = Document(layers=[plate, Layer(name='Dessin', items=[part])])
        self.assertTrue(FX.is_plate_layer(plate))
        self.assertFalse(FX.is_plate_layer(doc.layers[1]))
        got = strategies.source_items(doc, model.Operation(sources=[0]))
        self.assertEqual([it.id for it in got], [part.id])                   # la plaque : un repère
        got = strategies.source_items(doc, model.Operation(items=[plate.items[0].id, part.id]))
        self.assertEqual([it.id for it in got], [part.id])
        self.assertEqual(FX.without_plates(doc).layers, [doc.layers[1]])
        self.assertEqual(len(doc.layers), 2)                                 # le dessin lui-même inchangé
        plain = Document(layers=[doc.layers[1]])
        self.assertIs(FX.without_plates(plain), plain)
        from vectordrive.io import hpgl
        self.assertEqual(hpgl.write_text(doc)[0], hpgl.write_text(plain)[0])   # jamais tracée, origine comprise
        from vectordrive.cam import relief
        sim = relief.from_drawing(doc, res=0.5)
        self.assertGreater(sim.x0, 10.0)                                     # relief : la zone du dessin seul


class Panel(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.tmp = pathlib.Path(tempfile.mkdtemp())

        def close():
            self.w.modified = False
            for t in getattr(self.w, 'docs', []):
                t.modified = False
            self.w.settings.remove('fao/plaques_dossier')
            self.w.close()
            app.processEvents()
        self.addCleanup(close)

    def test_plate_placed_on_its_own_locked_layer(self):
        from vectordrive.cam import fixture as FX
        p = self.w.cam_panel
        path = plate_file(self.tmp)
        first = p.doc.layers[0]
        p.doc.plate = Plate(width=200.0, height=100.0)
        layer = p.place_fixture_plate(str(path))
        self.assertIs(p.doc.layers[0], layer)                                # sous le dessin
        self.assertTrue(layer.locked)
        self.assertEqual(layer.extra[FX.PLATE_LAYER], {'fichier': str(path)})
        self.assertEqual(p.doc.active, first.id)                             # on dessine toujours dans son calque
        bb = layer.items[0].bbox()
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 100.0, places=3)        # centrée sur la plaque du dessin
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, 50.0, places=3)
        self.assertEqual(len(FX.plate_holes(layer.items, 2.5, 9.0)), 12)
        self.w.undo()
        self.assertFalse(any(FX.is_plate_layer(L) for L in self.w.cam_panel.doc.layers))   # Annuler la retire
        p = self.w.cam_panel
        p.doc.plate = None
        layer = p.place_fixture_plate(str(path))
        bb = layer.items[0].bbox()
        self.assertAlmostEqual(bb[0], 0.0, places=3)                         # sans plaque : coin bas-gauche à l'origine
        self.assertAlmostEqual(bb[1], 0.0, places=3)
        bad = self.tmp / 'abime.dxf'
        bad.write_bytes(b'\x00\x01 pas un dxf')
        n = len(p.doc.layers)
        self.assertIsNone(p.place_fixture_plate(str(bad)))
        self.assertEqual(len(p.doc.layers), n)

    def test_dialog_places_and_prefers_the_placed_plate(self):
        from vectordrive.cam import fixture as FX
        from vectordrive.ui.fixture_dialog import FixtureDialog
        nop = mock.patch('vectordrive.plugins.default', no_plugin)
        nop.start()
        self.addCleanup(nop.stop)
        p = self.w.cam_panel
        plate_file(self.tmp)
        self.w.settings.setValue(FX.FOLDER_KEY, str(self.tmp))
        p.doc.plate = None                                                   # la plaque posée : coin bas-gauche en 0, 0
        other = Layer(name='Grille', items=[Group(children=[circle(300.0 + 20 * i, 0.0, 3.2) for i in range(30)])])
        blank = Shape(path=geom.Path([geom.rect(5.0, 5.0, 50.0, 30.0)]), tool=1)
        p.doc.layers.extend([other, Layer(name='Bruts', items=[blank])])
        dlg = FixtureDialog(None, p.doc, FX.Spec(), placer=p.place_fixture_plate, settings=self.w.settings)
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.library.count(), 1)
        self.assertEqual(dlg.library.itemText(0), 'Plaque 4x3')
        self.assertTrue(dlg.place_btn.isEnabled())
        self.assertIs(dlg.plate_layer(), other)
        self.assertTrue(dlg.place(dlg.library.currentData()))
        placed = p.doc.layers[0]
        self.assertTrue(FX.is_plate_layer(placed))
        self.assertIs(dlg.plate_layer(), placed)                             # la plaque posée devient celle des trous
        dlg.blank_src.setCurrentIndex(dlg.blank_src.findData(p.doc.layers[-1].id))
        self.assertEqual(dlg.placement.count(), 4)                           # le brut couvre six trous : quatre vis
        again = FixtureDialog(None, p.doc, FX.Spec())
        self.addCleanup(again.deleteLater)
        self.assertIs(again.plate_layer(), placed)                           # d'office : la plaque posée, pas la grille
        self.assertFalse(again.place_btn.isEnabled())                        # sans `placer` : rien à poser
        self.assertFalse(again.other_btn.isEnabled())
        before = len(p.setup().operations)
        p.ops_from_colors()                                                  # une gravure par couleur du dessin
        self.assertEqual(sorted(o.sources[0] for o in p.setup().operations[before:]), [0, 1])
        elsewhere = self.tmp / 'ailleurs'
        elsewhere.mkdir()
        other_file = plate_file(elsewhere, 'Autre 2x2.dxf')
        with mock.patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', lambda *a, **k: (str(other_file), '')):
            self.assertTrue(dlg.place_other())
        self.assertEqual(self.w.settings.value(FX.FOLDER_KEY), str(elsewhere))   # posée : son dossier retenu
        self.assertEqual(dlg.library.currentText(), 'Autre 2x2')
        bad = elsewhere / 'abime.dxf'
        bad.write_bytes(b'\x00 pas un dxf')
        self.w.settings.setValue(FX.FOLDER_KEY, str(self.tmp))
        with mock.patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', lambda *a, **k: (str(bad), '')):
            self.assertFalse(dlg.place_other())
        self.assertEqual(self.w.settings.value(FX.FOLDER_KEY), str(self.tmp))    # rien posé : rien retenu


if __name__ == '__main__':
    unittest.main()
