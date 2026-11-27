"""Round 1013 : demande du 14/11 (soir) — Dimensions (F2) et Calques peuvent partager un onglet de colonne (clic droit
« En onglet avec › », « Sortir des onglets »), retenu au lancement suivant."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1013.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QDockWidget, QMenu  # noqa: E402

app = QApplication.instance() or QApplication([])

KEYS = ('panneaux_colonnes/onglet/dims', 'panneaux_colonnes/seul/dims', 'panneaux_colonnes/onglet/layers',
        'panneaux_colonnes/seul/layers', 'panneaux_colonnes/place/dims', 'panneaux_colonnes/place/layers')


def close(w):
    from shiboken6 import isValid
    if not isValid(w):                                   # déjà fermée (et détruite) par l'essai
        return
    w.modified = False
    for t in getattr(w, 'docks', []):
        t.modified = False
    w.close()
    app.processEvents()


def window():
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    w.settings.setValue('fenetre/plein_ecran', False)
    w.show()
    app.processEvents()
    return w


def forget():
    from vectordrive import portable
    s = portable.settings()
    for k in KEYS:
        s.remove(k)
    s.setValue('panneaux_colonnes/f2_rangement', 'onglet')   # un poste déjà servi : F2 et Calques en onglets (round 1071)
    s.sync()


class F2AndLayers(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def docks(self, w):
        return w.findChild(QDockWidget, 'dims'), w.findChild(QDockWidget, 'layers')

    def test_menu_puts_them_together_and_apart(self):
        w = window()
        self.addCleanup(close, w)
        dims, layers = self.docks(w)
        self.assertEqual(w.columns.side(dims), w.columns.side(layers))
        self.assertIn(layers, w.tabifiedDockWidgets(dims))                    # d'office : en onglet (round 1022)
        self.assertTrue(w.columns.untab(dims))                                # séparés : Dimensions au-dessus
        m = w.columns.menu(dims)                                              # rcol2 (27/11) : ni « En
        self.addCleanup(m.deleteLater)                                        # onglet avec », ni « Sortir des
        self.assertIsNone(m.findChild(QMenu, 'en_onglet_avec'))               # onglets » ; « Seul à … »
        self.assertNotIn('Sortir des onglets', [a.text() for a in m.actions()])
        side = w.columns.side(layers)
        act = next(a for a in m.actions() if a.objectName() == f'seul_{side}')
        self.assertFalse(act.isChecked())                                     # hors des onglets
        act.trigger()
        self.assertIn(layers, w.tabifiedDockWidgets(dims))
        self.assertFalse(dims.isHidden())
        self.assertIsNone(w.settings.value('panneaux_colonnes/seul/dims'))
        m = w.columns.menu(dims)
        self.addCleanup(m.deleteLater)
        act = next(a for a in m.actions() if a.objectName() == f'seul_{side}')
        self.assertTrue(act.isChecked())
        self.assertFalse(act.isEnabled())                                     # il y est déjà
        self.assertEqual(w.columns.side(dims), w.columns.side(layers))        # toujours dans sa colonne

    def test_kept_for_the_next_start(self):
        w = window()
        self.addCleanup(close, w)
        dims, layers = self.docks(w)
        self.assertTrue(w.columns.tab_with(dims, layers))
        w.settings.sync()
        close(w)
        w = window()
        self.addCleanup(close, w)
        dims, layers = self.docks(w)
        self.assertIn(layers, w.tabifiedDockWidgets(dims))                    # ensemble au lancement suivant
        self.assertTrue(w.columns.untab(layers))                              # Calques sorti : Dimensions aussi
        self.assertIsNone(w.settings.value('panneaux_colonnes/onglet/dims'))
        self.assertIn(str(w.settings.value('panneaux_colonnes/seul/layers')).lower(), ('1', 'true'))
        w.settings.sync()
        close(w)
        w = window()
        self.addCleanup(close, w)
        dims, layers = self.docks(w)
        self.assertNotIn(layers, w.tabifiedDockWidgets(dims))
        self.assertEqual(w.tabifiedDockWidgets(layers), [])                  # Calques seul, comme laissé
        self.assertFalse(dims.isHidden() or layers.isHidden())

    def test_layers_out_then_f2_with_layers(self):
        w = window()
        self.addCleanup(close, w)
        dims, layers = self.docks(w)
        mates = [d.objectName() for d in w.tabifiedDockWidgets(layers) if d is not dims]
        w.columns.untab(layers)                                               # Calques sorti de son groupe…
        self.assertTrue(w.columns.tab_with(dims, layers))                     # … puis F2 avec lui
        w.settings.sync()
        close(w)
        w = window()
        self.addCleanup(close, w)
        dims, layers = self.docks(w)
        self.assertEqual(w.tabifiedDockWidgets(dims), [layers])               # le couple, et lui seul
        self.assertTrue(all(w.findChild(QDockWidget, n) not in w.tabifiedDockWidgets(dims) for n in mates))


if __name__ == '__main__':
    unittest.main()
