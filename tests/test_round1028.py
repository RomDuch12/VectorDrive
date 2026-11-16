"""Round 1028 : demande du 15/11, 8 h 40 — les deux colonnes partagées en hauteur (Dimensions (F2) au-dessus de
Calques, retenu au lancement suivant) ; un clic droit sur un bouton de colonne ouvre sa fenêtre : tout ce qu'elle peut
accueillir, un œil par panneau, « ✕ » ou un clic droit la ferme."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1028.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QContextMenuEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDockWidget, QMenu  # noqa: E402

app = QApplication.instance() or QApplication([])

PREFIX = 'panneaux_colonnes'


def forget():
    from vectordrive import portable
    s = portable.settings()
    s.remove(PREFIX)
    s.remove('vue/mode')
    s.remove('vue/panneau_fao')
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


def dock(w, name):
    return w.findChild(QDockWidget, name)


class Split(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)

    def test_f2_above_layers_both_shown_and_kept(self):
        w = window()
        self.addCleanup(close, w)
        dims, layers = dock(w, 'dims'), dock(w, 'layers')
        self.assertTrue(w.columns.split_with(dims, layers, below=False))     # au-dessus de Calques
        app.processEvents()
        self.assertNotIn(layers, w.tabifiedDockWidgets(dims))
        self.assertEqual(w.columns.side(dims), w.columns.side(layers))
        self.assertLess(dims.geometry().top(), layers.geometry().top())     # l'un au-dessus de l'autre
        self.assertTrue(w.columns.in_front(dims) and w.columns.in_front(layers))   # les deux montrés à la fois
        self.assertEqual(w.settings.value(f'{PREFIX}/partage/dims'), 'layers|dessus')
        w.settings.sync()
        close(w)
        w = window()                                                          # au lancement suivant
        self.addCleanup(close, w)
        dims, layers = dock(w, 'dims'), dock(w, 'layers')
        self.assertNotIn(layers, w.tabifiedDockWidgets(dims))                 # pas remis en onglets d'office
        self.assertEqual(w.columns.side(dims), w.columns.side(layers))
        self.assertLess(dims.geometry().top(), layers.geometry().top())
        w.columns.tab_with(dims, layers)                                      # de nouveau en onglets : retenu
        self.assertIsNone(w.settings.value(f'{PREFIX}/partage/dims'))
        self.assertIn(layers, w.tabifiedDockWidgets(dims))

    def test_left_column_too_and_below(self):
        w = window()
        self.addCleanup(close, w)
        dims, layers = dock(w, 'dims'), dock(w, 'layers')
        w.columns.move(layers, 'gauche')
        w.columns.move(dims, 'gauche')
        self.assertIn(layers, w.tabifiedDockWidgets(dims))
        self.assertTrue(w.columns.split_with(dims, layers, below=True))      # au-dessous, colonne de gauche
        app.processEvents()
        self.assertEqual(w.columns.side(dims), 'gauche')
        self.assertGreater(dims.geometry().top(), layers.geometry().top())
        self.assertEqual(w.settings.value(f'{PREFIX}/partage/dims'), 'layers|dessous')
        w.columns.move(dims, 'droite')                                        # envoyé ailleurs : plus partagé
        self.assertIsNone(w.settings.value(f'{PREFIX}/partage/dims'))

    def test_in_the_panel_menu(self):
        w = window()
        self.addCleanup(close, w)
        dims = dock(w, 'dims')
        m = w.columns.menu(dims)
        self.addCleanup(m.deleteLater)
        above = m.findChild(QMenu, 'au_dessus_de')
        self.assertIsNotNone(above)
        self.assertIsNotNone(m.findChild(QMenu, 'au_dessous_de'))
        self.assertIn('Calques', [a.text() for a in above.actions()])
        next(a for a in above.actions() if a.text() == 'Calques').trigger()
        app.processEvents()
        layers = dock(w, 'layers')
        self.assertNotIn(layers, w.tabifiedDockWidgets(dims))
        self.assertEqual(w.columns.side(dims), w.columns.side(layers))
        self.assertLess(dims.geometry().top(), layers.geometry().top())
        self.assertEqual(w.settings.value(f'{PREFIX}/partage/dims'), 'layers|dessus')

    def test_a_moved_reference_forgets_the_split(self):
        w = window()
        self.addCleanup(close, w)
        dims, layers = dock(w, 'dims'), dock(w, 'layers')
        w.columns.split_with(dims, layers, below=False)
        w.columns.move(layers, 'gauche')                                      # le repère part ailleurs
        self.assertIsNone(w.settings.value(f'{PREFIX}/partage/dims'))         # Dimensions ne le suit plus
        w.columns.move(layers, 'droite')
        w.columns.split_with(dims, layers, below=False)
        w.columns.untab(dock(w, 'symbols'))
        self.assertEqual(w.settings.value(f'{PREFIX}/partage/dims'), 'layers|dessus')   # un autre : rien
        w.columns.tab_with(layers, dock(w, 'symbols'))                        # le repère en onglet ailleurs
        self.assertIsNone(w.settings.value(f'{PREFIX}/partage/dims'))

    def test_opening_the_fao_keeps_the_split(self):
        w = window()
        self.addCleanup(close, w)
        dims, layers = dock(w, 'dims'), dock(w, 'layers')
        w.columns.split_with(dims, layers, below=False)
        app.processEvents()
        w.A['cam_panel'].trigger()                                            # la FAO : opérations en grand
        app.processEvents()
        self.assertFalse(dock(w, 'fao_liste').isHidden())
        self.assertNotIn(dims, w.tabifiedDockWidgets(dock(w, 'fao_liste')))   # Dimensions pas mis en onglet
        self.assertFalse(dims.isHidden())


class ColumnWindow(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)
        self.w = window()
        self.addCleanup(close, self.w)

    def test_right_click_on_the_column_button(self):
        w = self.w
        b = w.ribbon.column_buttons[1]
        ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(2, 2), b.mapToGlobal(QPoint(2, 2)))
        with mock.patch.object(type(w), '_ribbon_button_menu') as bm:
            self.assertFalse(w.eventFilter(b, ev))                            # le filtre de la fenêtre le laisse passer
            bm.assert_not_called()                                            # pas le menu du ruban
        b.customContextMenuRequested.emit(QPoint(2, 2))                      # clic droit sur le bouton de droite
        p = w.columns.panel('droite')
        self.assertIsNotNone(p)
        self.assertTrue(p.isVisible())
        names = {d.objectName() for d in p.rows()}
        self.assertTrue({'dims', 'layers', 'symbols', 'fao', 'fao_liste', 'programme'} <= names)  # tout, FAO comprise
        self.assertEqual(w.columns.side(p.rows()[0]), 'droite')              # ceux de cette colonne d'abord
        p.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5)))   # clic droit : fermée
        self.assertIsNone(w.columns.panel('droite'))
        p = w.column_panel('gauche')
        p.close()                                                             # 0.921.0 : plus de « ✕ »
        self.assertIsNone(w.columns.panel('gauche'))

    def test_eye_shows_or_removes_a_panel(self):
        w = self.w
        sym = dock(w, 'symbols')
        p = w.column_panel('gauche')
        self.assertFalse(p.eyes['symbols'].isChecked())                       # à droite aujourd'hui
        p.eyes['symbols'].click()                                             # œil : montré dans la colonne de gauche
        app.processEvents()
        self.assertEqual(w.columns.side(sym), 'gauche')
        self.assertFalse(sym.isHidden())
        p = w.columns.panel('gauche')
        self.assertTrue(p.eyes['symbols'].isChecked())                        # la fenêtre a suivi
        p.eyes['symbols'].click()                                             # œil fermé : retiré
        app.processEvents()
        self.assertTrue(sym.isHidden())
        p = w.columns.panel('gauche')
        p.eyes['fao_liste'].click()                                           # un panneau FAO : la FAO s'ouvre
        app.processEvents()
        self.assertTrue(w.A['cam_panel'].isChecked())
        self.assertEqual(w.columns.side(dock(w, 'fao_liste')), 'gauche')
        self.assertFalse(dock(w, 'fao_liste').isHidden())


if __name__ == '__main__':
    unittest.main()
