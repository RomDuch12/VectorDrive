"""Round 1143 (demande du 23/11) : « par défaut, un volet masqué affiché dans une colonne n'est jamais combiné à un
autre (dans la même colonne) sauf quand user choisit au-dessus de en dessous de ». Un panneau masqué montré par son
bouton, sa commande ou le menu de Qt prend son onglet dans le groupe de sa colonne."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1143.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtWidgets import QApplication, QDockWidget  # noqa: E402

app = QApplication.instance() or QApplication([])
PREFIX = 'panneaux_colonnes/'
BEFORE = 'avant : le panneau montré par son bouton s’empilait sous les autres'


def forget():
    from vectordrive.portable import settings
    st = settings()
    for k in list(st.allKeys()):
        if k.startswith(PREFIX) or k in ('vue/panneau_fao', 'fao/panneaux_onglet'):
            st.remove(k)
    st.sync()


def pump():
    for _ in range(4):
        app.processEvents()


class Shown(unittest.TestCase):
    def setUp(self):
        forget()
        self.addCleanup(forget)
        from vectordrive.portable import settings
        from vectordrive.ui.columns import F2_KEY
        settings().setValue(F2_KEY, 'onglet')                                   # la même disposition à chaque essai
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.settings.setValue('fenetre/plein_ecran', False)
        self.w.resize(1400, 900)
        self.w.show()
        pump()
        self.addCleanup(self._close)
        self.c = self.w.columns

    def _close(self):
        self.w.modified = False
        for t in getattr(self.w, 'docs', []):
            t.modified = False
        self.w.close()
        pump()

    def dock(self, name):
        return self.w.findChild(QDockWidget, name)

    def names(self, block):
        return {d.objectName() for d in block}

    def in_group(self, d, side='droite'):
        pump()
        self.assertFalse(d.isHidden())
        self.assertEqual(self.c.side(d), side)
        main = self.c.main_group(side)
        self.assertIn(d, main, BEFORE)
        self.assertEqual(self.names(self.c.blocks(side)[-1]), self.names(main))   # onglets toujours en bas
        self.assertTrue(self.c.in_front(d))                                     # montré devant

    def test_set_visible_takes_its_tab(self):
        d = self.dock('assistant')
        self.assertTrue(d.isHidden())
        d.setVisible(True)                                                      # mis devant par la colonne
        self.in_group(d)
        self.assertIn(self.dock('layers'), self.w.tabifiedDockWidgets(d))

    def test_toggle_view_action_takes_its_tab(self):
        d = self.dock('polices')
        d.toggleViewAction().trigger()
        self.in_group(d)

    def test_left_column_with_the_cam(self):
        self.w.A['cam_panel'].setChecked(True)
        pump()
        fao = self.dock('fao')
        self.assertFalse(fao.isHidden())
        for name in ('couleur', 'historique'):
            d = self.dock(name)
            d.toggleViewAction().trigger()
            self.in_group(d, 'gauche')
            self.assertIn(fao, self.w.tabifiedDockWidgets(d))
        self.assertEqual(len(self.c.blocks('gauche')), 1)                      # un seul bloc : les onglets

    def test_hidden_again_and_shown_again(self):
        d = self.dock('assistant')
        d.setVisible(True)
        pump()
        self.c.close(d)
        pump()
        d.setVisible(True)
        self.in_group(d)

    def test_above_or_below_chosen_stays(self):
        d, dims = self.dock('assistant'), self.dock('dims')
        d.setVisible(True)
        pump()
        self.assertTrue(self.c.split_with(d, dims, below=True))
        pump()
        self.c.close(d)
        pump()
        d.setVisible(True)
        pump()
        self.assertFalse(d.isHidden())
        self.assertNotIn(d, self.c.main_group('droite'))                        # au-dessous de Dimensions, choisi
        self.assertFalse(self.w.tabifiedDockWidgets(d))

    def test_out_of_tabs_chosen_stays(self):
        d = self.dock('symbols')
        self.assertTrue(self.c.untab(d))
        pump()
        self.c.close(d)
        pump()
        d.setVisible(True)
        pump()
        self.assertFalse(self.w.tabifiedDockWidgets(d))                        # sorti des onglets, choisi

    def test_dims_above_layers_by_default_until_closed(self):
        from vectordrive.ui.columns import F2_KEY
        self._close()
        self.w.settings.setValue(F2_KEY, 'dessus')                              # poste neuf : Dimensions au-dessus
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1400, 900)
        self.w.show()
        pump()
        self.c = self.w.columns
        dims = self.dock('dims')
        self.assertIn('dims', self.c.placed())
        self.assertFalse(self.w.tabifiedDockWidgets(dims))
        self.c.close(dims)
        pump()
        dims.setVisible(True)                                                   # remontré : son onglet (round 1162)
        self.in_group(dims)

    def test_alone_in_its_column_stays(self):
        d = self.dock('couleur')                                                # colonne de gauche vide
        self.assertFalse(self.c.shown('gauche'))
        d.setVisible(True)
        pump()
        self.assertFalse(d.isHidden())
        self.assertEqual(self.c.blocks('gauche'), [[d]])

    def test_shown_by_our_functions_left_as_placed(self):
        d = self.dock('polices')
        self.c._quiet(lambda: d.setVisible(True))                               # montré et rangé par l'appelant
        pump()
        self.assertFalse(self.w.tabifiedDockWidgets(d))

    def test_floating_left_floating(self):
        d = self.dock('assistant')
        d.setFloating(True)
        d.setVisible(True)
        pump()
        self.assertTrue(d.isFloating())
        self.assertIsNone(self.c.side(d))

    def test_placed_by_hand_stays(self):
        from PySide6.QtCore import Qt
        d = self.dock('assistant')
        d.setVisible(True)
        pump()
        self.assertTrue(self.w.tabifiedDockWidgets(d))
        d.setFloating(True)                                                     # détaché à la souris
        pump()
        self.assertTrue(d.isFloating())
        self.c._quiet(lambda: (self.w.removeDockWidget(d),                      # reposé à la souris sous la colonne
                               self.w.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, d, Qt.Orientation.Vertical),
                               d.setVisible(True)))
        pump()
        self.assertFalse(self.w.tabifiedDockWidgets(d))
        d.setFloating(True)                                                     # détaché puis ancré de nouveau
        pump()
        d.setFloating(False)
        pump()
        self.assertFalse(d.isFloating())
        self.assertFalse(self.w.tabifiedDockWidgets(d))                         # là où Qt l'a reposé
        self.c.close(d)                                                         # fermé, puis montré de nouveau :
        pump()
        d.setVisible(True)
        self.in_group(d)                                                        # son onglet

    def test_shown_before_the_window_left_behind(self):
        self._close()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()                                                   # pas encore montrée
        self.c = self.w.columns
        acc, layers = self.dock('accrochages'), self.dock('layers')
        acc.setVisible(True)                                                    # la disposition rendue au lancement
        layers.raise_()
        self.w.resize(1400, 900)
        self.w.show()
        pump()
        self.assertFalse(acc.isHidden())
        self.assertTrue(self.c.in_front(layers))                                # Calques reste devant
        self.assertFalse(self.c.in_front(acc))

    def test_closing_the_cam_gives_back_the_layout(self):
        before = [self.names(b) for b in self.c.blocks('droite')]
        self.w.A['cam_panel'].setChecked(True)
        pump()
        self.w.A['cam_panel'].setChecked(False)
        pump()
        self.assertEqual([self.names(b) for b in self.c.blocks('droite')], before)


if __name__ == '__main__':
    unittest.main()
