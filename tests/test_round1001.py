"""Round 1001 : colonnes de panneaux (demandes du 14/11) — chaque panneau a la même barre de titre (plein écran
translucide, détacher, fermer) et le même menu au clic droit de sa barre ou de son onglet ; un panneau passe d'une
colonne à l'autre et s'y range en onglet ; deux boutons montrent ou cachent la colonne de gauche et celle de droite ;
un clic sur l'onglet CAD range les panneaux FAO, un clic sur un onglet FAO les rétablit."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1001.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QContextMenuEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel, QSizePolicy, QTabBar  # noqa: E402

from vectordrive.i18n import tr  # noqa: E402

app = QApplication.instance() or QApplication([])
PREFIX = 'panneaux_colonnes/'


def window():
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    w.settings.setValue('fenetre/plein_ecran', False)
    w.resize(1400, 900)
    w.show()
    app.processEvents()
    return w


def close(w):
    w.modified = False
    for t in getattr(w, 'docs', []):
        t.modified = False
    w.close()
    app.processEvents()


def forget():
    from vectordrive.portable import settings
    st = settings()
    for k in list(st.allKeys()):
        if k.startswith(PREFIX) or k in ('vue/panneau_fao', 'fao/panneaux_onglet'):
            st.remove(k)
    st.sync()


def index_of(w, title):
    r = w.ribbon
    return next(i for i in range(r.count()) if r.tabText(i) == tr(title))


def click_tab(w, title):
    """Un clic de l'utilisateur sur l'onglet du ruban."""
    i = index_of(w, title)
    w.ribbon.tabBarClicked.emit(i)
    w.ribbon.setCurrentIndex(i)
    app.processEvents()


class Base(unittest.TestCase):

    def setUp(self):
        forget()
        self.w = window()
        self.cols = self.w.columns
        self.addCleanup(forget)
        self.addCleanup(close, self.w)

    def dock(self, name):
        return self.w.findChild(QDockWidget, name)

    def fao(self, on=True):
        self.w.A['cam_panel'].setChecked(on)
        app.processEvents()

    def fao_open(self):
        return str(self.w.settings.value('vue/panneau_fao')).lower() == 'true'


class Bars(Base):

    def test_every_panel_has_the_same_bar(self):
        docks = [d for d in self.w.findChildren(QDockWidget) if d.parent() is self.w]
        self.assertGreaterEqual(len(docks), 5)
        for d in docks:
            bar = d.titleBarWidget()
            self.assertIsNotNone(bar, d.objectName())
            self.assertEqual(list(bar.buttons), ['plein', 'detacher', 'fermer'], d.objectName())
            self.assertEqual(bar.title.text(), d.property('vd_titre') or d.windowTitle())   # son titre entier
            self.assertEqual(bar.title.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Ignored)   # il s'abrège
            self.assertTrue(d._vd_grip.isHidden())                  # la poignée : seulement quand il est détaché
        late = QDockWidget('Plus tard', self.w)                     # un panneau créé après coup (plugin)
        late.setObjectName('plus_tard')
        late.setWidget(QLabel('x'))
        self.w.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, late)
        app.processEvents()
        self.assertIsNotNone(late.titleBarWidget())
        self.assertIn(late, self.cols.docks())

    def test_full_screen_from_the_bar_of_any_panel(self):
        d = self.dock('layers')
        bar = d.titleBarWidget()
        bar.buttons['plein'].click()
        app.processEvents()
        ov = self.cols.overlay(d)
        self.assertTrue(ov.active and d.isFloating())
        self.assertIsNot(d.titleBarWidget(), bar)                   # la barre du plein écran (opacité)
        self.assertLess(d.windowOpacity(), 1.0)
        bar.buttons['detacher'].click()                             # du plein écran : de retour à sa place
        app.processEvents()
        self.assertFalse(ov.active or d.isFloating())
        self.assertIs(d.titleBarWidget(), bar)
        self.assertFalse(bar.isHidden())
        bar.buttons['detacher'].click()                             # détaché, puis plein écran, puis retour :
        app.processEvents()
        d.setGeometry(200, 150, 420, 380)
        app.processEvents()
        where = d.geometry()
        ov.set_active(True)
        ov.set_active(False)
        app.processEvents()
        self.assertTrue(d.isFloating())                             # il reste détaché, à sa place
        self.assertEqual(d.geometry().size(), where.size())

    def test_detach_and_close(self):
        d = self.dock('layers')
        bar = d.titleBarWidget()
        bar.buttons['detacher'].click()
        app.processEvents()
        self.assertTrue(d.isFloating())
        self.assertIsNone(self.cols.side(d))
        grip = d._vd_grip                                           # détaché : une poignée dans le coin bas droit
        self.assertFalse(grip.isHidden())
        self.assertEqual(grip.geometry().bottomRight(), d.rect().bottomRight())
        bar.buttons['detacher'].click()
        app.processEvents()
        self.assertEqual((d.isFloating(), self.cols.side(d)), (False, 'droite'))
        self.assertTrue(self.w.tabifiedDockWidgets(d))              # de retour en onglet, pas empilé
        bar.buttons['fermer'].click()
        app.processEvents()
        self.assertTrue(d.isHidden())

    def test_the_menu_of_a_panel(self):
        d = self.dock('layers')
        m = self.cols.menu(d)
        acts = {a.text(): a for a in m.actions() if a.text()}
        self.assertEqual([t for t in acts if t not in (tr('En onglet avec'), tr('Sortir des onglets'),
                                                       tr('Au-dessus de'), tr('Au-dessous de'),     # 1028
                                                       'Titres entiers dans les onglets')],         # 1049
                         [tr('Plein écran translucide'), tr('Détacher seul'), tr('Colonne de gauche'),   # 1093
                          tr('Colonne de droite'), tr('Fermer')])                # 1013 : et les onglets
        self.assertTrue(acts[tr('Colonne de droite')].isChecked())
        self.assertFalse(acts[tr('Colonne de droite')].isEnabled())     # il y est déjà
        self.assertTrue(acts[tr('Colonne de gauche')].isEnabled())
        acts[tr('Colonne de gauche')].trigger()
        app.processEvents()
        self.assertEqual(self.cols.side(d), 'gauche')
        self.assertFalse(d.isHidden())
        m.deleteLater()

    def test_right_click_on_a_tab(self):
        bars = [b for b in self.w.findChildren(QTabBar) if b.parent() is self.w and b.count() > 1]
        self.assertTrue(bars)
        bar = bars[0]
        first, second = self.cols.dock_at(bar, 0), self.cols.dock_at(bar, 1)
        self.assertEqual((first.windowTitle(), second.windowTitle()), (bar.tabText(0), bar.tabText(1)))
        self.assertIsNone(self.cols.dock_at(bar, -1))
        second.setWindowTitle(first.windowTitle())                  # deux panneaux du même titre : pas confondus
        app.processEvents()
        self.assertIs(self.cols.dock_at(bar, 0), first)
        self.assertIs(self.cols.dock_at(bar, 1), second)
        pos = bar.tabRect(1).center()
        with mock.patch.object(self.cols, 'show_menu') as shown:
            QApplication.sendEvent(bar, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos, bar.mapToGlobal(pos)))
        self.assertEqual(shown.call_count, 1)
        self.assertIs(shown.call_args[0][0], second)
        d = self.dock('dims')
        with mock.patch.object(self.cols, 'show_menu') as shown:
            p = QPoint(8, 4)
            QApplication.sendEvent(d.titleBarWidget(), QContextMenuEvent(QContextMenuEvent.Reason.Mouse, p,
                                                                         d.titleBarWidget().mapToGlobal(p)))
        self.assertEqual(shown.call_count, 1)                       # la barre de titre : le même menu
        self.assertIs(shown.call_args[0][0], d)


class Sides(Base):

    def test_a_panel_sent_left_joins_the_tabs_there(self):
        self.fao()
        palette, ops = self.w.dock_cam, self.w.dock_paths
        self.assertEqual((self.cols.side(palette), self.cols.side(ops)), ('gauche', 'droite'))
        self.cols.move(ops, 'gauche')
        app.processEvents()
        self.assertEqual(self.cols.side(ops), 'gauche')
        self.assertIn(palette, self.w.tabifiedDockWidgets(ops))     # en onglet avec la palette, pas empilé
        self.assertFalse(ops.isHidden() or palette.isHidden())
        self.assertEqual(str(self.w.settings.value(PREFIX + 'place/fao_liste')), 'gauche')
        self.cols.move(palette, 'droite')                           # « idem parcours » : la palette à droite
        app.processEvents()
        self.assertEqual(self.cols.side(palette), 'droite')
        self.assertTrue(self.w.tabifiedDockWidgets(palette))

    def test_the_palette_covered_by_a_tab_does_not_close_the_cam(self):
        self.fao()
        palette, ops = self.w.dock_cam, self.w.dock_paths
        self.cols.move(ops, 'gauche')                               # les deux panneaux FAO dans la même colonne
        app.processEvents()
        for front in (palette, ops, palette, ops):                  # on passe d'un onglet à l'autre
            front.raise_()
            app.processEvents()
            self.assertFalse(palette.isHidden() or ops.isHidden(), front.objectName())
            self.assertTrue(self.w.A['cam_panel'].isChecked() and self.fao_open(), front.objectName())
        self.fao(False)                                             # fermée puis rouverte : elle reste ouverte
        self.assertTrue(palette.isHidden() and ops.isHidden())
        self.fao(True)
        self.assertFalse(palette.isHidden() or ops.isHidden())
        self.assertTrue(self.w.A['cam_panel'].isChecked() and self.fao_open())
        self.assertEqual(self.cols.side(ops), 'gauche')             # et le déplacement n'est pas défait

    def test_closing_the_cam_does_not_undo_a_move(self):
        self.fao()
        layers = self.dock('layers')
        self.cols.move(layers, 'gauche')
        app.processEvents()
        self.fao(False)
        self.assertEqual(self.cols.side(layers), 'gauche')
        self.assertFalse(layers.isHidden())
        palette = self.w.dock_cam
        self.fao(True)
        palette.titleBarWidget().buttons['fermer'].click()          # la palette fermée par sa croix : la FAO fermée
        app.processEvents()
        self.assertTrue(palette.isHidden() and self.w.dock_paths.isHidden())
        self.assertFalse(self.w.A['cam_panel'].isChecked() or self.fao_open())

    def test_the_side_is_kept_for_the_next_launch(self):
        layers, ops = self.dock('layers'), self.w.dock_paths
        self.cols.move(layers, 'gauche')
        self.cols.move(ops, 'gauche')
        ops.setVisible(False)
        app.processEvents()
        self.cols.toggle_floating(layers)                           # détaché puis ancré : toujours à gauche
        self.cols.toggle_floating(layers)
        app.processEvents()
        self.assertEqual(self.cols.side(layers), 'gauche')
        self.w.settings.setValue('vue/panneau_fao', False)
        w2 = window()
        try:
            self.assertEqual(w2.columns.side(w2.findChild(QDockWidget, 'layers')), 'gauche')
            ops2, palette2 = w2.dock_paths, w2.dock_cam
            self.assertTrue(ops2.isHidden())                        # rangé à gauche, sans être montré pour autant
            w2.A['cam_panel'].setChecked(True)
            app.processEvents()
            self.assertEqual(w2.columns.side(ops2), 'gauche')
            self.assertIn(palette2, w2.tabifiedDockWidgets(ops2))   # en onglet avec la palette, pas empilé dessous
        finally:
            close(w2)

    def test_the_two_column_buttons(self):
        self.fao()
        A, cols = self.w.A, self.cols
        self.assertEqual([b.text() for b in self.w.ribbon.column_buttons], ['◧', '◨'])
        self.assertTrue(A['col_left'].isChecked() and A['col_right'].isChecked())
        right = [d for d in cols.column('droite') if not d.isHidden()]
        self.assertGreaterEqual(len(right), 3)
        self.w.ribbon.column_buttons[1].click()                     # la colonne de droite cachée
        app.processEvents()
        self.assertFalse(cols.shown('droite') or A['col_right'].isChecked())
        self.assertTrue(cols.shown('gauche') and A['col_left'].isChecked())
        self.assertFalse(self.w.dock_cam.isHidden())                # la palette, à gauche, n'a pas bougé
        self.assertTrue(self.fao_open() and A['cam_panel'].isChecked())   # ni ce qui est retenu
        self.w.ribbon.column_buttons[1].click()
        app.processEvents()
        self.assertEqual([d for d in cols.column('droite') if not d.isHidden()], right)   # les mêmes reviennent
        self.assertTrue(A['col_right'].isChecked())
        self.assertFalse(self.w.settings.contains(PREFIX + 'cachees/droite'))   # revenue : plus rien de retenu
        A['col_left'].setChecked(False)
        app.processEvents()
        self.assertTrue(self.w.dock_cam.isHidden())
        self.assertFalse(self.w.dock_paths.isHidden())              # les opérations, à droite, restent
        self.assertTrue(self.fao_open() and A['cam_panel'].isChecked())   # la FAO n'est pas fermée pour autant
        A['col_left'].setChecked(True)
        app.processEvents()
        self.assertFalse(self.w.dock_cam.isHidden())                # la palette revient avec sa colonne

    def test_what_comes_back_with_a_column(self):
        self.fao()
        A, cols = self.w.A, self.cols
        A['col_right'].setChecked(False)                            # dims, calques, bibliothèque, opérations
        app.processEvents()
        self.fao(False)                                             # la FAO fermée pendant que la colonne est cachée
        A['col_right'].setChecked(True)
        app.processEvents()
        shown = {d.objectName() for d in cols.column('droite') if not d.isHidden()}
        self.assertTrue({'dims', 'layers', 'symbols'} <= shown)
        self.assertNotIn('fao_liste', shown)                        # les opérations ne reviennent pas sans la FAO
        A['col_right'].setChecked(False)
        app.processEvents()
        self.dock('dims').setVisible(True)                          # un seul panneau rouvert à la main (F2)
        app.processEvents()
        A['col_right'].setChecked(False)
        app.processEvents()
        A['col_right'].setChecked(True)
        app.processEvents()
        shown = {d.objectName() for d in cols.column('droite') if not d.isHidden()}
        self.assertTrue({'dims', 'layers', 'symbols'} <= shown)     # les autres n'ont pas été oubliés

    def test_a_column_closed_panel_by_panel(self):
        for d in self.cols.column('droite'):
            d.close()
        app.processEvents()
        self.assertFalse(self.w.A['col_right'].isChecked())         # le bouton suit
        self.w.A['col_right'].setChecked(True)
        app.processEvents()
        shown = {d.objectName() for d in self.cols.column('droite') if not d.isHidden()}
        self.assertTrue({'dims', 'layers', 'symbols'} <= shown)
        self.assertNotIn('fao_liste', shown)                        # la FAO fermée ne revient pas avec la colonne


class CadTab(Base):

    def test_cad_puts_the_cam_panels_away_and_cam_brings_them_back(self):
        click_tab(self.w, 'FAO 2D')
        self.fao()
        palette, ops = self.w.dock_cam, self.w.dock_paths
        click_tab(self.w, 'CAD')
        self.assertTrue(palette.isHidden() and ops.isHidden())
        self.assertTrue(self.fao_open())                            # pas oubliés pour autant
        click_tab(self.w, 'Edition')
        self.assertTrue(palette.isHidden() and ops.isHidden())      # un autre onglet ne les ramène pas
        click_tab(self.w, 'FAO 2D')
        self.assertFalse(palette.isHidden() or ops.isHidden())
        self.assertTrue(self.w.A['cam_panel'].isChecked())

    def test_only_clicks_count(self):
        click_tab(self.w, 'FAO 2D')
        self.fao()
        palette, ops = self.w.dock_cam, self.w.dock_paths
        r = self.w.ribbon
        r.setCurrentIndex(index_of(self.w, 'CAD'))                  # l'onglet change de lui-même (2D / 3D, texte…)
        app.processEvents()
        self.assertFalse(palette.isHidden() or ops.isHidden())
        click_tab(self.w, 'CAD')
        self.assertTrue(palette.isHidden() and ops.isHidden())
        r.setCurrentIndex(index_of(self.w, 'FAO 2D'))               # … et ne ramène rien non plus
        app.processEvents()
        self.assertTrue(palette.isHidden() and ops.isHidden())
        page = r.page(index_of(self.w, 'Edition'))
        page.setProperty('vd_fao', True)                            # un onglet FAO sous un autre titre (TypeEdit)
        click_tab(self.w, 'Edition')
        self.assertFalse(palette.isHidden() or ops.isHidden())

    def test_only_the_panels_that_were_shown(self):
        click_tab(self.w, 'FAO 2D')
        click_tab(self.w, 'CAD')
        click_tab(self.w, 'FAO 2D')
        self.assertTrue(self.w.dock_cam.isHidden() and self.w.dock_paths.isHidden())   # jamais ouverts : pas montrés
        self.fao()
        self.cols._quiet(lambda: self.w.dock_cam.setVisible(False))    # la palette cachée (avec sa colonne, par exemple)
        app.processEvents()
        click_tab(self.w, 'CAD')
        click_tab(self.w, 'FAO 2D')
        self.assertFalse(self.w.dock_paths.isHidden())
        self.assertTrue(self.w.dock_cam.isHidden())

    def test_kept_for_the_next_launch(self):
        click_tab(self.w, 'FAO 2D')
        self.fao()
        click_tab(self.w, 'CAD')
        self.assertTrue(self.w.settings.value(PREFIX + 'rangees_cad'))
        w2 = window()
        try:
            for d in (w2.dock_cam, w2.dock_paths):                  # comme une session reprise : restés cachés
                w2.columns._quiet(lambda d=d: d.setVisible(False))
            click_tab(w2, 'FAO 2D')
            self.assertFalse(w2.dock_cam.isHidden() or w2.dock_paths.isHidden())
            self.assertFalse(w2.settings.contains(PREFIX + 'rangees_cad'))
        finally:
            close(w2)

    def test_the_option_turns_it_off(self):
        from vectordrive.ui import options as O
        self.assertIs(O.BY_KEY['fao/panneaux_onglet'].default, True)
        self.w.settings.setValue('fao/panneaux_onglet', False)
        click_tab(self.w, 'FAO 2D')
        self.fao()
        click_tab(self.w, 'CAD')
        self.assertFalse(self.w.dock_cam.isHidden() or self.w.dock_paths.isHidden())


if __name__ == '__main__':
    unittest.main()
