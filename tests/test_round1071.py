"""Round 1071 : réponses du 17/11 - question 43 : « oui », une plaque de reprise posée (un repère de l'usinage) n'est
ni sur le BAT, ni imprimée, ni dans une image exportée ; Q36 : « oui », Dimensions (F2) au-dessus de Calques d'office
sur un poste neuf - un poste déjà servi garde ses onglets."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1071.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QDockWidget  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Group, Layer, Shape  # noqa: E402

BEFORE = 'avant : la plaque de reprise posée y était'


def square(x, y, s):
    return Shape(path=geom.Path([geom.rect(x, y, s, s)]), tool=1)


def drawing(with_plate=True):
    """Un dessin de deux carrés (20 mm) et, dessous, une plaque de reprise posée (un cadre de 200 mm, calque verrouillé
    marqué comme le pose le panneau FAO)."""
    d = Document()
    d.layers[0].items += [square(10, 10, 20), square(40, 10, 20)]
    if with_plate:
        plate = Layer(name='Plaque de reprise : essai', items=[Group(children=[square(-50, -50, 200)])], locked=True)
        plate.extra['plaque_reprise'] = {'fichier': 'essai.smb'}
        d.layers.insert(0, plate)
    return d


class PlateNotShown(unittest.TestCase):

    def test_bat(self):
        from vectordrive.io import proof
        info = proof.ProofInfo()
        d, ref = drawing(), drawing(False)
        self.assertEqual(len(proof.engravings(d, info)), 2, BEFORE)
        self.assertEqual(proof.page_scale(d, info), proof.page_scale(ref, info), BEFORE)
        got, want = proof.build(d, info), proof.build(ref, info)
        self.assertEqual(got[1:], want[1:])
        self.assertEqual(len(got[0]), len(want[0]), BEFORE)
        self.assertEqual(len(d.layers), 2)                                   # le dessin n'est pas touché

    def test_bat_selection(self):
        from vectordrive.io import proof
        info = proof.ProofInfo(content='selection')
        d = drawing()
        plate_item = d.layers[0].items[0]
        mixed = [plate_item] + d.layers[1].items
        self.assertEqual(proof.engravings(d, info, mixed), d.layers[1].items, BEFORE)   # Ctrl+A : sans elle
        self.assertEqual(proof.engravings(d, info, [plate_item]), [plate_item])       # choisie exprès : montrée

    def test_print(self):
        from vectordrive.ui import printing
        from vectordrive.ui.print_dialog import items_for
        d, ref = drawing(), drawing(False)
        self.assertEqual(printing.extent(d, {}, None)[0], printing.extent(ref, {}, None)[0], BEFORE)
        chosen = items_for(d, [], {'quoi': 'calques', 'calques': [L.id for L in d.layers]})
        self.assertEqual(chosen, d.layers[1].items, BEFORE)

    def test_print_dialog_does_not_offer_it(self):
        from vectordrive.ui.print_dialog import PrintDialog
        d = drawing()
        try:
            dlg = PrintDialog(None, d, [])
        except TypeError:
            self.skipTest('fenêtre d’impression : autre signature')
        names = [dlg.layers.item(i).text() for i in range(dlg.layers.count())]
        self.assertNotIn('Plaque de reprise : essai', names, BEFORE)
        self.assertEqual(len(names), 1)
        dlg.deleteLater()

    def test_image(self):
        from vectordrive.io import raster
        spec = raster.RasterSpec(dpi=50)
        got, want = raster.render(drawing(), spec), raster.render(drawing(False), spec)
        self.assertEqual((got.width(), got.height()), (want.width(), want.height()), BEFORE)

    def test_image_of_the_plate_chosen(self):
        """Exportée exprès (la sélection : sa marque ôtée par l'export), la plaque est dans l'image."""
        from vectordrive.io import raster
        d = drawing()
        d.layers[0].extra.pop('plaque_reprise')
        spec = raster.RasterSpec(dpi=50)
        self.assertGreater(raster.render(d, spec).width(), raster.render(drawing(False), spec).width())


# --- Q36 -------------------------------------------------------------------------------------------------------------
KEYS = ('panneaux_colonnes', 'fenetre/geometrie', 'fenetre/plein_ecran', 'fenetre/plein_ecran_barre', 'vue/mode')


def forget():
    from vectordrive import portable
    s = portable.settings()
    for k in KEYS:
        s.remove(k)
    s.sync()


def window():
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    w.settings.setValue('fenetre/plein_ecran', False)
    w.show()
    app.processEvents()
    return w


def close(w):
    from shiboken6 import isValid
    if not isValid(w):
        return
    w.modified = False
    for t in getattr(w, 'docks', []):
        t.modified = False
    w.close()
    app.processEvents()


def restart(w):
    w.settings.sync()
    close(w)
    return window()


def docks(w):
    return w.findChild(QDockWidget, 'dims'), w.findChild(QDockWidget, 'layers')


class F2AboveLayers(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def above(self, w):
        dims, layers = docks(w)
        app.processEvents()
        self.assertNotIn(layers, w.tabifiedDockWidgets(dims), 'avant : en onglets d’office')
        self.assertEqual(w.columns.side(dims), w.columns.side(layers))
        self.assertLess(dims.geometry().top(), layers.geometry().top())
        self.assertTrue(w.columns.in_front(dims) and w.columns.in_front(layers))   # les deux montrés à la fois

    def test_new_station(self):
        w = window()
        self.addCleanup(lambda: close(w))
        self.assertEqual(w.settings.value('panneaux_colonnes/f2_rangement'), 'dessus')
        self.above(w)
        self.assertEqual(w.tabifiedDockWidgets(docks(w)[0]), [])               # Dimensions hors des onglets
        w2 = restart(w)
        self.addCleanup(lambda: close(w2))
        self.above(w2)                                                       # au lancement suivant aussi

    def test_new_station_user_puts_them_in_tabs(self):
        w = window()
        self.addCleanup(lambda: close(w))
        dims, layers = docks(w)
        self.assertTrue(w.columns.tab_with(dims, layers))                    # son choix : retenu, gardé
        w2 = restart(w)
        self.addCleanup(lambda: close(w2))
        dims, layers = docks(w2)
        self.assertIn(layers, w2.tabifiedDockWidgets(dims))

    def test_used_station_keeps_its_tabs(self):
        self.used_station('fenetre/geometrie', 'AAAA')                       # la fenêtre a déjà été fermée ici

    def test_used_station_in_full_screen_keeps_its_tabs(self):
        self.used_station('fenetre/plein_ecran', True)                       # plein écran : sa place n'est pas écrite

    def used_station(self, key, value):
        from vectordrive import portable
        s = portable.settings()
        s.setValue(key, value)
        s.sync()
        w = window()
        self.addCleanup(lambda: close(w))
        self.assertEqual(w.settings.value('panneaux_colonnes/f2_rangement'), 'onglet')
        dims, layers = docks(w)
        self.assertIn(layers, w.tabifiedDockWidgets(dims))
        self.assertIsNone(w.settings.value('panneaux_colonnes/partage/dims'))
        w2 = restart(w)                                                      # décidé une fois : toujours en onglets
        self.addCleanup(lambda: close(w2))
        dims, layers = docks(w2)
        self.assertIn(layers, w2.tabifiedDockWidgets(dims))


if __name__ == '__main__':
    unittest.main()
