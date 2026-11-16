"""Round 1063 : demande du 15/11, 20 h 02 — « fenetre apposable en colonne : accrochage (droite par défaut avec meme
colonne calques et F2) couleur Défaire/refaire (gauche par défaut) » : Accrochages et Défaire / Refaire sont des
panneaux de colonne."""
import importlib.util
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1063.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QDockWidget  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BEFORE = 'avant : les accrochages dans une fenêtre à part, la liste des modifications quelques secondes sur le dessin'


def forget():
    from vectordrive import portable
    s = portable.settings()
    s.remove('panneaux_colonnes')
    s.sync()


def dock(w, name):
    return w.findChild(QDockWidget, name)


class Panels(unittest.TestCase):

    def window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        w.show()
        app.processEvents()

        def close():
            w.modified = False
            w.close()
            w.deleteLater()
            app.processEvents()
        self.addCleanup(close)
        return w

    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('vectordrive.ui.history_panel'), BEFORE)
        forget()
        self.addCleanup(forget)
        self.w = self.window()
        self.cols = self.w.columns

    def test_two_more_column_panels_hidden_until_asked(self):
        snap, hist, layers = dock(self.w, 'accrochages'), dock(self.w, 'historique'), dock(self.w, 'layers')
        self.assertIs(snap, self.w.dock_snap)
        self.assertIs(hist, self.w.dock_history)
        self.assertTrue(snap.isHidden() and hist.isHidden())                 # masqués tant qu'on ne les demande pas
        self.assertEqual((self.cols.side(snap), self.cols.side(hist)), ('droite', 'gauche'))
        self.assertIn(snap, self.cols.docks())
        self.assertIn(hist, self.cols.docks())
        from vectordrive.ui import columns as C
        table = C.PanelRows(self.cols)
        self.addCleanup(table.deleteLater)
        self.assertIn('accrochages', table.choices)                          # dans le tableau Gauche / Masqué / Droite
        self.assertIn('historique', table.choices)
        table.choices['historique']['gauche'].click()
        app.processEvents()
        self.assertFalse(hist.isHidden())
        self.assertEqual(self.cols.side(hist), 'gauche')

    def test_f3_shows_the_panel_then_hides_it(self):
        snap = self.w.dock_snap
        sw = self.w.snap_window()                                            # F3
        app.processEvents()
        self.assertFalse(snap.isHidden())
        self.assertIs(snap.widget(), sw)
        self.assertTrue(self.cols.in_front(snap))                            # devant Calques et Dimensions
        self.assertIn(dock(self.w, 'layers'), self.w.tabifiedDockWidgets(snap))   # dans leur groupe d'onglets
        self.assertEqual(self.cols.side(snap), 'droite')
        self.assertIs(self.w.snap_window(show=False), sw)                    # le même contenu, sans rien changer
        self.assertFalse(snap.isHidden())
        sw.boxes['quadrant'].setChecked(True)                                # ses cases règlent toujours l'accrochage
        self.assertIn('quadrant', self.w.canvas.snap.modes)
        sw.reject()                                                          # Échap : le contenu d'un panneau reste
        self.assertFalse(sw.isHidden())
        self.assertFalse(snap.isHidden())
        self.w.snap_window()                                                 # F3 de nouveau : masqué
        app.processEvents()
        self.assertTrue(snap.isHidden())
        self.w.snap_window()
        app.processEvents()
        self.assertFalse(sw.close())                                         # fermé : c'est le panneau qui se masque
        app.processEvents()
        self.assertTrue(snap.isHidden())
        self.assertFalse(sw.isHidden())

    def test_f3_brings_it_in_front_when_it_is_behind(self):
        snap, layers = self.w.dock_snap, dock(self.w, 'layers')
        self.w.snap_window()
        app.processEvents()
        self.cols._quiet(layers.raise_)                                      # Calques repasse devant
        app.processEvents()
        self.assertFalse(self.cols.in_front(snap))
        self.w.snap_window()                                                 # F3 : devant, pas masqué
        app.processEvents()
        self.assertFalse(snap.isHidden())
        self.assertTrue(self.cols.in_front(snap))

    def test_the_history_panel_follows_and_goes_back(self):
        hist, panel = self.w.dock_history, self.w.history_panel
        self.cols.show_in(hist, 'gauche', True)
        app.processEvents()
        base = len(panel.rows())
        for k in range(2):
            self.w._add_items([Shape(path=geom.Path([geom.rect(10.0 * k, 0.0, 5.0, 5.0)]), tool=0)])
        rows = panel.rows()
        self.assertEqual(len(rows), base + 2)                                # deux modifications de plus, suivies
        self.assertEqual(panel.current, base + 1)
        self.assertTrue(rows[-1][1].startswith('▶'))
        n = len([it for L in self.w.canvas.doc.layers for it in L.items])
        panel._clicked(panel.list.item(base))                                # un clic : l'état d'avant la dernière
        self.assertEqual(len([it for L in self.w.canvas.doc.layers for it in L.items]), n - 1)
        self.assertEqual(panel.current, base)
        self.assertTrue(panel.rows()[base][1].startswith('▶'))
        self.assertEqual(len(panel.rows()), base + 2)                        # la modification défaite reste, en grisé
        self.w.redo()
        self.assertEqual(panel.current, base + 1)                            # Refaire au clavier : le panneau suit
        self.cols.close(hist)
        app.processEvents()
        self.w.undo()                                                        # masqué : il ne suit pas…
        self.assertEqual(panel.current, base + 1)
        self.cols.show_in(hist, 'gauche', True)
        app.processEvents()
        self.assertEqual(panel.current, base)                                # …et se refait en reparaissant

    def test_a_jump_refreshes_once_and_a_stale_list_does_nothing(self):
        hist, panel = self.w.dock_history, self.w.history_panel
        self.cols.show_in(hist, 'gauche', True)
        app.processEvents()
        for k in range(6):
            self.w._add_items([Shape(path=geom.Path([geom.rect(10.0 * k, 0.0, 5.0, 5.0)]), tool=0)])
        base = panel.current - 6
        count = []
        real = panel.refresh
        panel.refresh = lambda: (count.append(1), real())[1]
        self.addCleanup(lambda: setattr(panel, 'refresh', real))
        self.assertEqual(panel.go(base), base)                               # six pas défaits d'un clic…
        self.assertEqual(len(count), 1)                                      # …la liste refaite une seule fois
        self.assertEqual(panel.current, base)
        self.w._redo.pop()                                                   # une commande change les piles sans prévenir
        n = len([it for L in self.w.canvas.doc.layers for it in L.items])
        rows = len(panel.rows())
        self.assertEqual(panel.go(base + 3), base)                           # la liste ne disait plus vrai : rien n'est fait
        self.assertEqual(len([it for L in self.w.canvas.doc.layers for it in L.items]), n)
        self.assertEqual(len(panel.rows()), rows - 1)                        # elle est refaite
        self.assertEqual(panel.go(base + 3), base + 3)                       # le clic suivant agit

    def test_a_column_shown_again_leaves_them_hidden(self):
        snap, hist = self.w.dock_snap, self.w.dock_history
        for side in ('gauche', 'droite'):
            for d in self.cols.column(side):
                self.cols.close(d)                                           # tout fermé un à un : rien de retenu
            app.processEvents()
            self.cols.set_shown(side, True)                                  # la colonne rouverte par son bouton
            app.processEvents()
        self.assertTrue(snap.isHidden() and hist.isHidden())                 # à la demande seulement
        self.assertFalse(dock(self.w, 'dims').isHidden())
        self.w.snap_window()                                                 # demandé, puis caché avec sa colonne…
        app.processEvents()
        self.cols.set_shown('droite', False)
        app.processEvents()
        self.assertTrue(snap.isHidden())
        self.cols.set_shown('droite', True)
        app.processEvents()
        self.assertFalse(snap.isHidden())                                    # …il revient avec elle

    def test_a_place_already_chosen_is_kept(self):
        from vectordrive import portable
        st = portable.settings()
        st.setValue('panneaux_colonnes/place/accrochages', 'gauche')
        st.sync()
        other = self.window()
        self.assertEqual(other.columns.side(other.dock_snap), 'gauche')      # un poste déjà réglé garde sa disposition
        other.snap_window()
        app.processEvents()
        self.assertEqual(other.columns.side(other.dock_snap), 'gauche')
        self.assertFalse(other.dock_snap.isHidden())


if __name__ == '__main__':
    unittest.main()
