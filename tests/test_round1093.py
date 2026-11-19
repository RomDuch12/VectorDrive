"""Round 1093 (demande du 19/11 matin) : « Colonnes : onglets toujours tout en bas de la colonne […], quand on affiche
une fonction sur une colonne, elle s'associe à d'autres et ce n'est pas voulu : si user ne précise pas la fonction a sa
colonne et son onglet, et ensuite on peut click droit (sur onglet ou dans panneau affich_colonnes) mettre au dessus
dessous de, puis click droit détacher seul »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1093.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel, QMenu, QTabBar  # noqa: E402

app = QApplication.instance() or QApplication([])
PREFIX = 'panneaux_colonnes/'
BEFORE = 'avant : les onglets au milieu de la colonne'


def forget():
    from vectordrive.portable import settings
    st = settings()
    for k in list(st.allKeys()):
        if k.startswith(PREFIX) or k in ('vue/panneau_fao', 'fao/panneaux_onglet'):
            st.remove(k)
    st.sync()


def window():
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    w.settings.setValue('fenetre/plein_ecran', False)
    w.resize(1400, 900)
    w.show()
    app.processEvents()
    app.processEvents()
    return w


def close(w):
    w.modified = False
    for t in getattr(w, 'docs', []):
        t.modified = False
    w.close()
    app.processEvents()


class Columns(unittest.TestCase):

    def setUp(self):
        forget()
        self.addCleanup(forget)
        self.w = window()
        self.addCleanup(close, self.w)
        self.first = self.w                                                  # gardée jusqu'au nettoyage
        self.cols = self.w.columns

    def dock(self, name):
        return self.w.findChild(QDockWidget, name)

    def names(self, block):
        return {d.objectName() for d in block}

    def tabs_at_bottom(self, side='droite'):
        """Le groupe d'onglets est le dernier bloc de la colonne, et sa barre d'onglets sous tous les panneaux."""
        app.processEvents()
        blocks = self.cols.blocks(side)
        main = self.cols.main_group(side)
        self.assertTrue(main)
        self.assertEqual(self.names(blocks[-1]), self.names(main), BEFORE)
        if len(main) > 1:
            bars = [b for b in self.w.findChildren(QTabBar) if b.parent() is self.w and b.isVisible()
                    and any(self.cols.dock_at(b, i) in main for i in range(b.count()))]
            self.assertEqual(len(bars), 1)
            bar_top = bars[0].mapTo(self.w, QPoint(0, 0)).y()
            for b in blocks[:-1]:
                for d in b:
                    self.assertLess(d.mapTo(self.w, QPoint(0, 0)).y() + d.height(), bar_top + 1, d.objectName())
        return blocks, main

    def show(self, name, side='droite'):
        self.cols.show_in(self.dock(name), side, True)
        app.processEvents()
        return self.dock(name)

    def test_out_of_the_tabs_goes_above_them(self):
        for n in ('historique', 'accrochages'):
            self.show(n)
        layers, hist = self.dock('layers'), self.dock('historique')
        hist.raise_()
        app.processEvents()
        self.assertTrue(self.cols.in_front(hist))
        self.assertTrue(self.cols.untab(layers))                              # « Sortir des onglets »
        blocks, main = self.tabs_at_bottom()
        self.assertTrue(self.cols.in_front(hist))                            # le même onglet devant
        self.assertNotIn('layers', self.names(main))
        self.assertGreaterEqual(len(main), 2)
        self.assertIn({'layers'}, [self.names(b) for b in blocks[:-1]])

    def test_a_panel_shown_gets_its_own_tab_in_the_group(self):
        dims, layers = self.dock('dims'), self.dock('layers')
        self.assertTrue(self.cols.split_with(dims, layers, below=False))     # rangés à part par l'utilisateur
        hist = self.show('historique')
        self.assertNotIn(dims, self.w.tabifiedDockWidgets(hist))             # avant : en onglet avec l'un d'eux
        self.assertNotIn(layers, self.w.tabifiedDockWidgets(hist))
        self.assertFalse(self.w.tabifiedDockWidgets(dims))
        self.assertFalse(self.w.tabifiedDockWidgets(layers))
        self.assertTrue(self.w.tabifiedDockWidgets(hist))                    # son onglet, dans le groupe
        blocks, main = self.tabs_at_bottom()
        self.assertIn('historique', self.names(main))
        self.assertLess(dims.geometry().top(), layers.geometry().top())     # toujours l'un au-dessus de l'autre

    def test_below_a_tabbed_panel_both_go_above_the_tabs(self):
        self.show('historique')
        self.show('accrochages')
        hist, snaps = self.dock('historique'), self.dock('accrochages')
        self.assertTrue(self.cols.split_with(snaps, hist, below=True))
        blocks, main = self.tabs_at_bottom()
        self.assertNotIn('historique', self.names(main))
        self.assertNotIn('accrochages', self.names(main))
        self.assertLess(hist.geometry().top(), snaps.geometry().top())      # au-dessous de l'historique

    def test_kept_at_the_next_start(self):
        for n in ('historique', 'accrochages'):
            self.show(n)
        self.cols.untab(self.dock('layers'))
        w2 = window()                                                        # le lancement suivant
        self.addCleanup(close, w2)
        self.w, self.cols = w2, w2.columns
        self.assertTrue(self.dock('layers').isVisible())
        self.assertFalse(w2.tabifiedDockWidgets(self.dock('layers')))        # toujours seul…
        blocks = self.cols.blocks('droite')                                  # remis en ordre à l'ouverture
        self.assertNotIn('layers', self.names(blocks[-1]))
        for n in ('historique', 'accrochages'):
            self.show(n)
        blocks, main = self.tabs_at_bottom()                                 # … au-dessus des onglets
        self.assertNotIn('layers', self.names(main))

    def test_detach_alone(self):
        self.show('historique')
        hist = self.dock('historique')
        mates = list(self.w.tabifiedDockWidgets(hist))
        self.assertTrue(mates)
        m = self.cols.menu(hist)
        acts = {a.text(): a for a in m.actions() if a.text()}
        self.assertIn('Détacher seul', acts)
        acts['Détacher seul'].trigger()
        app.processEvents()
        self.assertTrue(hist.isFloating())
        self.assertFalse(any(d.isFloating() for d in mates))                 # lui seul
        m.deleteLater()

    def test_hidden_window_waits(self):
        self.show('historique')
        self.w.hide()
        app.processEvents()
        self.show('accrochages')
        self.cols.untab(self.dock('layers'))                                 # fenêtre cachée : remis à plus tard
        self.assertFalse(self.cols.settle('droite'))
        self.w.show()                                                        # remontrée : la colonne en ordre
        app.processEvents()
        app.processEvents()
        self.tabs_at_bottom()

    def test_right_click_on_a_row_of_the_column_window(self):
        p = self.cols.show_panel('droite')
        self.addCleanup(p.close)
        hist = self.dock('historique')
        from vectordrive.ui.columns import full_title
        rows = [lab for lab in p.findChildren(QLabel) if lab.text() == full_title(hist)]
        self.assertEqual(len(rows), 1)
        with mock.patch.object(self.cols, 'show_menu') as shown:
            rows[0].customContextMenuRequested.emit(QPoint(2, 2))
        self.assertEqual(shown.call_count, 1)
        self.assertIs(shown.call_args[0][0], hist)
        self.assertFalse(shown.call_args[1]['table'])                       # sans le tableau en tête
        done = mock.Mock()
        rows_widget = rows[0].parent()
        rows_widget.done = done
        with mock.patch.object(self.cols, 'show_menu', return_value=None):
            rows_widget.row_menu(hist, QPoint(0, 0))
        done.assert_not_called()                                             # Échap : rien de fermé autour
        with mock.patch.object(self.cols, 'show_menu', return_value=object()):
            rows_widget.row_menu(hist, QPoint(0, 0))
        done.assert_called_once()
        m = self.cols.menu(hist, table=False)
        self.assertIsNone(m.findChild(QMenu, 'panneaux'))
        self.assertFalse([a for a in m.actions() if a.objectName() == 'panneaux'])
        names = [a.text() for a in m.actions()]
        self.assertIn('Détacher seul', names)
        m.deleteLater()
        m = self.cols.menu(self.dock('layers'), table=False)                 # un panneau montré : ses voisins
        self.assertIsNotNone(m.findChild(QMenu, 'au_dessus_de'))
        self.assertIsNotNone(m.findChild(QMenu, 'au_dessous_de'))
        m.deleteLater()


if __name__ == '__main__':
    unittest.main()
