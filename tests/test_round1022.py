"""Round 1022 : demande du 15/11 — « colonnes F2 dimensions et calques se partagent la même ; fao bouton réglages dans
expert »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1022.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QDockWidget  # noqa: E402

app = QApplication.instance() or QApplication([])

KEYS = ('panneaux_colonnes/onglet/dims', 'panneaux_colonnes/seul/dims', 'panneaux_colonnes/onglet/layers',
        'panneaux_colonnes/seul/layers', 'panneaux_colonnes/place/dims', 'panneaux_colonnes/place/layers',
        'vue/mode')


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


def docks(w):
    return w.findChild(QDockWidget, 'dims'), w.findChild(QDockWidget, 'layers')


class F2AndLayersTogether(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def test_together_by_default_f2_in_front(self):
        w = window()
        self.addCleanup(close, w)
        dims, layers = docks(w)
        self.assertIn(layers, w.tabifiedDockWidgets(dims))                    # avant : Dimensions au-dessus
        self.assertEqual(w.columns.side(dims), w.columns.side(layers))
        self.assertTrue(w.columns.in_front(dims))                             # Dimensions devant
        self.assertIsNone(w.settings.value('panneaux_colonnes/onglet/dims'))  # rien d'écrit : la règle d'office

    def test_apart_when_the_user_took_them_apart(self):
        w = window()
        self.addCleanup(close, w)
        dims, layers = docks(w)
        self.assertTrue(w.columns.untab(dims))                                # « Sortir des onglets »
        w.settings.sync()
        close(w)
        w = window()
        self.addCleanup(close, w)
        dims, layers = docks(w)
        self.assertNotIn(layers, w.tabifiedDockWidgets(dims))                 # retenu : séparés
        w.settings.remove('panneaux_colonnes/seul/dims')
        w.settings.setValue('panneaux_colonnes/seul/layers', True)            # Calques sorti, lui
        w.settings.sync()
        close(w)
        w = window()
        self.addCleanup(close, w)
        dims, layers = docks(w)
        self.assertNotIn(layers, w.tabifiedDockWidgets(dims))

    def test_not_across_columns(self):
        w = window()
        self.addCleanup(close, w)
        dims, layers = docks(w)
        self.assertIn(layers, w.tabifiedDockWidgets(dims))                    # d'office ensemble…
        w.columns.move(dims, 'gauche')                                        # … rangé à gauche par l'utilisateur
        w.settings.sync()
        close(w)
        w = window()
        self.addCleanup(close, w)
        dims, layers = docks(w)
        self.assertEqual(w.columns.side(dims), 'gauche')
        self.assertNotIn(layers, w.tabifiedDockWidgets(dims))


class SetupButtonInExpertMode(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def test_shown_in_expert_mode_only(self):
        from vectordrive.ui import modes
        from vectordrive import portable
        portable.settings().setValue(modes.KEY, 'simple')
        w = window()
        self.addCleanup(close, w)
        b = w.cam_panel.setup_btn
        from vectordrive.i18n import tr
        self.assertEqual(b.text(), tr('Réglage…'))
        self.assertTrue(b.isHidden())                                         # avant : montré en mode simple
        w.set_ui_mode('expert', announce=False)
        self.assertFalse(b.isHidden())
        w.set_ui_mode('simple', announce=False)
        self.assertTrue(b.isHidden())


if __name__ == '__main__':
    unittest.main()
