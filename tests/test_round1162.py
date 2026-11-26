"""Round 1162 (demandes du 25/11) :
(e) « Colonne droite : Lorsque on veut afficher quelque chose de masqué dans la colonne, ne pas le mettre dans la même
colonne qu'un autre : son propre onglet_colonne; » — un panneau remontré prend son onglet dans le groupe de sa colonne
(poste neuf compris : Dimensions d'office au-dessus de Calques, le repère d'un « Au-dessous de »), jamais en onglet sur
la colonne Datron ; la colonne rouverte, la FAO rouverte ou refermée, une machine choisie, une session empilée font de
même.
(b) « Fermeture partie simpl d'une colonne : redimensionne dynamiquement la colonne en la réduisant de largeur
equivalente; » — le texte du programme fermé, sa colonne rétrécit d'autant ; rouvert, elle s'élargit d'autant.
Le poste est neuf à chaque essai (F2_KEY décidé par l'application, jamais forcé)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1162.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel, QVBoxLayout, QWidget  # noqa: E402

from vectordrive import plugins  # noqa: E402
from vectordrive.cam import post  # noqa: E402

app = QApplication.instance() or QApplication([])
PREFIX = 'panneaux_colonnes/'
OTHER_KEYS = ('vue/panneau_fao', 'fao/panneaux_onglet', 'fao/programme_vue', 'fao/programme_parties',
              'fao/programme_texte_colonne', 'fenetre/geometrie', 'fenetre/plein_ecran', 'fenetre/plein_ecran_barre')
BEFORE_E = 'avant : le panneau remontré restait empilé, ou en onglet sur la colonne Datron'
BEFORE_B = 'avant : la colonne voisine prenait la largeur du texte fermé, le dessin rien'
RIGHT = Qt.DockWidgetArea.RightDockWidgetArea


def forget():
    """Un poste neuf : rien de retenu pour les colonnes, ni la fenêtre (Dimensions d'office au-dessus de Calques)."""
    from vectordrive.portable import settings
    st = settings()
    for k in list(st.allKeys()):
        if k.startswith(PREFIX) or k in OTHER_KEYS:
            st.remove(k)
    st.sync()


def pump(n=6):
    for _ in range(n):
        app.processEvents()


def window(state=None):
    """La fenêtre montrée hors écran, dimensionnée (les places et les largeurs s'y lisent) ; `state` : la disposition
    d'une session, remise avant de la montrer."""
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    if state is not None:
        w.restoreState(state)
    w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    w.show()
    w.resize(2200, 1000)                                 # la fenêtre Programme et ses parties : larges
    pump()
    return w


def shut(w):
    from shiboken6 import isValid
    if not isValid(w):
        return
    w.modified = False
    for t in getattr(w, 'docs', []):
        t.modified = False
    w.close()
    w.deleteLater()
    pump()


def part(text, height=0):
    def make(win):
        box = QWidget()
        lay = QVBoxLayout(box)
        label = QLabel(text)
        if height:
            label.setMinimumHeight(height)
        lay.addWidget(label)
        return box
    return make


def writer(toolpaths, setup, *, title='', machine=None, stem='p', box_mm=None, machine_dir=''):
    return post.PostResult('', [], '.txt')


def x_of(w, dock):
    return dock.mapTo(w, QPoint(0, 0)).x()


class Base(unittest.TestCase):
    plugin = False                                       # une machine d'essai à parties (la colonne Datron)
    extra = False

    def setUp(self):
        forget()
        self.addCleanup(forget)
        if self.plugin:
            r = plugins.REGISTRY
            saved = (dict(r.posts), list(r.post_providers), list(r.actions), list(r.panels), list(r.post_hooks),
                     dict(r.post_exports))

            def restore():
                r.posts, r.post_providers, r.actions, r.panels, r.post_hooks, r.post_exports = saved
            self.addCleanup(restore)
            api = plugins.Api(r, plugins.PluginInfo('essai', 'essai'))
            api.add_post('essai_col', 'Machine d’essai', writer)
            api.add_panel('essai_params', 'ESSAI — Paramètres programme', part('paramètres', 300),
                          posts=('essai_col',), host='programme')
            api.add_panel('essai_ops', 'ESSAI — Opérations', part('opérations'), posts=('essai_col',),
                          host='programme')
            if self.extra:                               # un panneau à part, de la même machine
                api.add_panel('essai_dock', 'ESSAI — Panneau', part('panneau'), posts=('essai_col',))
        self.w = window()
        self.addCleanup(lambda: shut(self.w))
        self.c = self.w.columns

    def restart(self):
        """Le lancement suivant (les réglages gardés)."""
        self.w.settings.sync()
        shut(self.w)
        self.w = window()
        self.c = self.w.columns

    def empty_right(self):
        for name in ('dims', 'layers', 'symbols'):
            self.c.close(self.dock(name))
        pump()
        self.assertFalse(self.c.shown('droite'))

    def dock(self, name, w=None):
        return (w or self.w).findChild(QDockWidget, name)

    def names(self, block):
        return {d.objectName() for d in block}

    def in_group(self, d, side='droite', w=None):
        """`d` montré dans la colonne `side`, dans son groupe d'onglets (en bas de la colonne), devant."""
        w = w or self.w
        c = w.columns
        pump()
        self.assertFalse(d.isHidden())
        self.assertEqual(c.side(d), side)
        main = c.main_group(side)
        self.assertIn(d, main, BEFORE_E)
        self.assertEqual(self.names(c.blocks(side)[-1]), self.names(main))     # onglets toujours en bas
        self.assertTrue(c.in_front(d))

    def lone(self, d, hidden=False):
        """`d` seul dans la colonne de droite, sous les autres (comme une disposition d'avant le round 1143)."""
        self.c._quiet(lambda: (self.w.removeDockWidget(d), self.w.addDockWidget(RIGHT, d, Qt.Orientation.Vertical),
                               d.setVisible(not hidden)))
        pump()
        self.assertFalse(self.w.tabifiedDockWidgets(d))

    # --- la colonne Datron (parties de plugin dans la fenêtre Programme, le texte à côté) ---------------------------
    def choose(self, key):
        self.w.cam_panel.set_post(key)
        pump()

    def datron(self, side='droite'):
        w = self.w
        self.choose('essai_col')
        self.c.move(w.dock_program, side)
        w.show_program(refresh=False)
        pump()
        d = w.dock_program_text
        self.assertIs(d.widget(), w.program_panel.viewer)
        self.assertFalse(d.isHidden())
        self.assertEqual(self.c.side(d), side)
        return w, w.dock_program, d


class Shown(Base):

    def test_fresh_post_dims_shown_again_takes_its_tab(self):
        dims = self.dock('dims')
        self.assertEqual(self.c.f2_mode(), 'dessus')                            # poste neuf : au-dessus de Calques
        self.assertFalse(self.w.tabifiedDockWidgets(dims))
        self.c.close(dims)
        pump()
        dims.toggleViewAction().trigger()
        self.in_group(dims)
        self.assertEqual(self.w.settings.value(PREFIX + 'onglet/dims'), 'layers')
        self.restart()                                                          # au lancement suivant : le même
        self.assertIn(self.dock('layers'), self.w.tabifiedDockWidgets(self.dock('dims')))

    def test_f2_on_a_fresh_post(self):
        dims = self.dock('dims')
        self.c.close(dims)
        pump()
        self.w.focus_dimensions()                                               # F2 sans forme ni outil
        self.in_group(dims)

    def test_the_reference_of_a_below_takes_its_tab(self):
        a, sym = self.dock('assistant'), self.dock('symbols')
        a.setVisible(True)
        pump()
        self.assertTrue(self.c.split_with(a, sym, below=True))                 # l'Assistant au-dessous : choisi
        pump()
        self.c.close(sym)
        pump()
        sym.toggleViewAction().trigger()                                        # le repère remontré : son onglet
        self.in_group(sym)
        self.assertNotIn(a, self.c.main_group('droite'))                        # l'Assistant reste rangé à part
        self.assertFalse(self.w.tabifiedDockWidgets(a))
        st = self.w.settings
        self.assertIsNone(st.value(PREFIX + 'partage/assistant'))               # le repère ne ressortira pas
        self.assertIn(str(st.value(PREFIX + 'seul/assistant', '')).lower(), ('1', 'true'))
        self.restart()
        self.assertTrue(self.w.tabifiedDockWidgets(self.dock('symbols')))       # au lancement suivant : le même

    def test_column_shown_again_regroups_a_lone_panel(self):
        d = self.dock('accrochages')
        self.lone(d)
        self.c.set_shown('droite', False)
        pump()
        self.assertTrue(d.isHidden())
        self.c.set_shown('droite', True)
        self.in_group(d)

    def test_closing_the_cam_regroups_a_panel_closed_meanwhile(self):
        d = self.dock('accrochages')
        self.lone(d)
        self.w.A['cam_panel'].setChecked(True)
        pump()
        self.c.close(d)                                                         # fermé pendant la FAO
        pump()
        self.w.A['cam_panel'].setChecked(False)                                 # la disposition d'avant le remontre
        pump()
        self.in_group(d)

    def test_cam_tab_gives_back_its_panels_in_tabs(self):
        self.w.A['cam_panel'].setChecked(True)
        pump()
        d = self.w.dock_paths
        self.lone(d)
        self.c.tab_clicked('cad')
        pump()
        self.assertTrue(d.isHidden())
        self.c.tab_clicked('fao')                                               # un onglet FAO les rétablit
        self.in_group(d)

    def test_session_stacked_then_relaunched(self):
        from vectordrive.ui.columns import REGROUPED_KEY
        d = self.dock('accrochages')
        self.lone(d)
        state = self.w.saveState()                                              # une session d'avant, empilée
        shut(self.w)
        from vectordrive.portable import settings
        settings().remove(REGROUPED_KEY)                                        # 1er lancement après la mise à jour
        self.w = w2 = window(state)
        d2 = self.dock('accrochages', w2)
        self.in_group(d2, w=w2)
        self.assertTrue(str(w2.settings.value(REGROUPED_KEY, '')).lower() in ('1', 'true'))
        self.c = w2.columns
        self.lone(d2)                                                           # rangé ainsi à la souris, ensuite
        state = w2.saveState()
        shut(w2)
        self.w = w3 = window(state)
        pump()
        self.assertFalse(w3.tabifiedDockWidgets(self.dock('accrochages', w3)))  # une fois par poste : laissé

    def test_opening_the_cam_leaves_dims_taken_out_of_the_tabs(self):
        dims, layers = self.dock('dims'), self.dock('layers')
        self.assertTrue(self.c.tab_with(dims, layers))
        self.assertTrue(self.c.untab(dims))                                     # « Sortir des onglets » : choisi
        pump()
        self.w.A['cam_panel'].setChecked(True)
        pump()
        self.assertNotIn(dims, self.w.tabifiedDockWidgets(self.w.dock_paths), BEFORE_E)
        self.assertFalse(self.w.tabifiedDockWidgets(dims))


class DatronColumn(Base):
    plugin = True

    def test_anchored_beside_its_text(self):
        w = self.w
        self.choose('essai_col')
        w.show_program(refresh=False)                                           # fenêtre détachée, texte ancré
        pump()
        dp, text = w.dock_program, w.dock_program_text
        self.assertTrue(dp.isFloating())
        self.assertEqual(self.c.side(text), 'droite')
        self.c.toggle_floating(dp)                                              # « Ancrer »
        pump()
        self.assertFalse(dp.isFloating())
        self.assertEqual(self.c.side(dp), 'droite')
        self.assertFalse(w.tabifiedDockWidgets(dp), BEFORE_E)
        self.assertGreater(x_of(w, dp), x_of(w, text) + 40)                     # à côté du texte, pas sous lui
        self.assertLess(dp.mapTo(w, QPoint(0, 0)).y(), text.mapTo(w, QPoint(0, 0)).y() + text.height())
        self.assertTrue(self.c.in_front(dp) and self.c.in_front(text))

    def test_already_in_tabs_it_comes_out(self):
        w = self.w
        dp = w.dock_program
        self.c.move(dp, 'droite')                                               # ancrée sous une autre machine
        w.show_program(refresh=False)
        pump()
        self.assertTrue(w.tabifiedDockWidgets(dp))
        self.choose('essai_col')                                                # puis la machine à parties
        pump()
        self.assertFalse(w.tabifiedDockWidgets(dp), BEFORE_E)
        text = w.dock_program_text
        self.assertFalse(text.isHidden())
        self.assertGreater(x_of(w, dp), x_of(w, text) + 40)
        w.A['cam_panel'].setChecked(True)                                       # la FAO : ses opérations en onglet
        pump()
        ops = w.dock_paths
        self.assertIn(ops, self.c.main_group('droite'))
        self.assertTrue(self.c.in_front(ops) and self.c.in_front(dp))
        self.assertNotIn(dp, w.tabifiedDockWidgets(ops))

    def test_once_per_post_it_comes_out_of_its_tabs(self):
        from vectordrive.portable import settings
        from vectordrive.ui.columns import REGROUPED_KEY
        w, dp, text = self.datron('droite')
        layers = self.dock('layers')
        self.c._quiet(lambda: (w.tabifyDockWidget(layers, dp), dp.raise_()))    # une disposition d'avant
        pump()
        self.assertTrue(w.tabifiedDockWidgets(dp))
        settings().remove(REGROUPED_KEY)
        self.c.settle_all()
        pump()
        self.assertFalse(w.tabifiedDockWidgets(dp), BEFORE_E)
        self.assertGreater(x_of(w, dp), x_of(w, text) + 40)

    def test_shown_again_never_on_the_datron_column(self):
        self.empty_right()
        w, dp, text = self.datron('droite')
        layers = self.dock('layers')
        layers.toggleViewAction().trigger()                                     # Calques remontré
        pump()
        self.assertFalse(layers.isHidden())
        self.assertEqual(self.c.side(layers), 'droite')
        self.assertNotIn(dp, w.tabifiedDockWidgets(layers), BEFORE_E)
        self.assertTrue(self.c.in_front(dp))                                    # la colonne Datron reste devant
        self.assertTrue(self.c.in_front(text))
        self.assertTrue(self.c.in_front(layers))
        self.assertGreater(abs(x_of(w, layers) - x_of(w, dp)), 40)              # sa propre colonne
        w.snap_window()                                                         # F3 : son onglet, avec Calques
        pump()
        snaps = self.dock('accrochages')
        self.assertFalse(snaps.isHidden())
        self.assertIn(layers, w.tabifiedDockWidgets(snaps))
        self.assertTrue(self.c.in_front(dp))

    def test_a_tab_on_the_datron_column_comes_out(self):
        self.empty_right()
        w, dp, text = self.datron('droite')
        sym = self.dock('symbols')
        self.c._quiet(lambda: (w.tabifyDockWidget(dp, sym), sym.setVisible(False)))   # une disposition d'avant
        pump()
        sym.toggleViewAction().trigger()
        pump()
        self.assertFalse(sym.isHidden())
        self.assertNotIn(dp, w.tabifiedDockWidgets(sym), BEFORE_E)
        self.assertTrue(self.c.in_front(dp))
        self.assertTrue(self.c.in_front(sym))

    def test_put_away_by_cad_then_another_drawing_never_in_tabs(self):
        w, dp, text = self.datron('droite')
        w.settings.setValue('fao/panneaux_onglet', True)                       # panneaux FAO par onglet
        self.c.tab_clicked('cad')                                               # l'onglet CAD les range
        pump()
        self.assertTrue(dp.isHidden() and text.isHidden())
        prog = w.program_panel
        prog._laid = None                                                       # un autre dessin, machine à parties :
        prog.put_text_dock('droite')                                            # la colonne refaite, fenêtre cachée
        pump()
        self.c.tab_clicked('fao')                                               # l'onglet FAO les rétablit
        pump()
        self.assertFalse(dp.isHidden())
        self.assertEqual(w.tabifiedDockWidgets(dp), [], BEFORE_E)
        self.assertTrue(self.c.in_front(dp))
        self.assertFalse(self.c._in_tabs(dp))

    def test_hidden_old_tab_shown_again_comes_out(self):
        self.empty_right()
        w, dp, text = self.datron('droite')
        sym = self.dock('symbols')
        self.c._quiet(lambda: (w.tabifyDockWidget(sym, dp), dp.setVisible(False), sym.setVisible(True)))
        pump()                                                                  # une disposition d'avant, cachée
        self.c._quiet(lambda: dp.setVisible(True))                              # remontrée (onglet FAO…)
        self.c.regroup([dp, sym])
        pump()
        self.assertFalse(dp.isHidden())
        self.assertNotIn(sym, w.tabifiedDockWidgets(dp), BEFORE_E)

    def test_under_the_program_window_when_room_lacks(self):
        from unittest import mock
        self.empty_right()
        w, dp, text = self.datron('droite')
        sym, layers = self.dock('symbols'), self.dock('layers')
        self.c._quiet(lambda: (w.tabifyDockWidget(dp, sym), sym.setVisible(False)))   # voisin d'onglet caché
        pump()
        self.assertTrue(self.c._in_tabs(dp))
        self.c.move(layers, 'gauche')
        pump()
        with mock.patch.object(self.c, '_room_beside', return_value=False):    # pas la place d'une colonne
            self.c.move(layers, 'droite')
            pump()
        self.assertFalse(layers.isHidden())
        self.assertEqual(self.c.side(layers), 'droite')
        self.assertNotIn(layers, w.tabifiedDockWidgets(dp), BEFORE_E)          # avant : en onglet sous elle
        self.assertTrue(self.c.in_front(dp) and self.c.in_front(layers))

    def test_two_hidden_tab_mates_freed_once(self):
        from unittest import mock
        self.empty_right()
        w, dp, text = self.datron('droite')
        sym, layers = self.dock('symbols'), self.dock('layers')
        self.c._quiet(lambda: (w.tabifyDockWidget(dp, sym), w.tabifyDockWidget(dp, layers),
                               sym.setVisible(False), layers.setVisible(False)))   # deux voisins d'onglet cachés
        pump()
        self.assertTrue(self.c._in_tabs(dp))
        with mock.patch.object(self.c, '_in_tabs', return_value=True):         # toujours « en onglet » :
            self.assertTrue(self.c.free_program())                              # une fois, pas de récursion
        pump()
        self.assertFalse(self.c._in_tabs(dp))
        sym.toggleViewAction().trigger()
        pump()
        self.assertFalse(sym.isHidden())
        self.assertNotIn(sym, w.tabifiedDockWidgets(dp))
        self.assertTrue(self.c.in_front(dp))

    def test_tab_menu_never_offers_the_datron_column(self):
        from PySide6.QtWidgets import QMenu

        from vectordrive.ui.columns import full_title
        w, dp, text = self.datron('droite')
        m = self.c.menu(self.dock('layers'))
        self.addCleanup(m.deleteLater)
        sub = m.findChild(QMenu, 'en_onglet_avec')
        names = [a.text() for a in sub.actions()] if sub is not None else []
        self.assertNotIn(full_title(dp), names, BEFORE_E)
        self.assertNotIn(full_title(text), names)
        m2 = self.c.menu(dp)                                                    # ni pour elle-même
        self.addCleanup(m2.deleteLater)
        self.assertIsNone(m2.findChild(QMenu, 'en_onglet_avec'))

    def test_an_old_tab_with_the_program_window_not_put_back(self):
        from unittest import mock

        from vectordrive.ui import columns
        w = self.w
        self.c.move(w.dock_program, 'droite')
        w.settings.setValue(PREFIX + 'onglet/programme', 'layers')              # retenu avant la mise à jour
        calls, orig = [], columns.Columns.tab_with

        def spy(c, dock, other, *a, **k):
            calls.append((dock.objectName(), other.objectName()))
            return orig(c, dock, other, *a, **k)
        with mock.patch.object(columns.Columns, 'tab_with', spy):
            self.restart()
        self.assertNotIn(('programme', 'layers'), calls, BEFORE_E)


class MachineDock(Base):
    plugin = extra = True

    def test_machine_chosen_its_panel_takes_its_tab(self):
        pd, dims = self.dock('plugin_essai_dock'), self.dock('dims')
        self.assertTrue(pd.isHidden())
        self.assertTrue(self.c.tab_with(dims, self.dock('layers')))
        self.assertTrue(self.c.untab(dims))                                     # Dimensions sorti des onglets : choisi
        self.lone(pd, hidden=True)                                              # seul sous la colonne, caché
        self.dock('accrochages').toggleViewAction().trigger()                  # le groupe : Calques, Biblio, Accroch.
        pump()
        self.choose('essai_col')                                                # sa machine : montré, en grand
        pump()
        self.in_group(pd)
        self.assertNotIn(dims, self.w.tabifiedDockWidgets(pd), BEFORE_E)       # Dimensions laissé à part
        self.assertFalse(self.w.tabifiedDockWidgets(dims))


class TextWidth(Base):
    """(b) Le texte du programme fermé : sa colonne rétrécit d'autant ; rouvert : elle s'élargit d'autant."""
    plugin = True

    def widths(self):
        w = self.w
        pump()
        return w.dock_program_text.width(), w.dock_program.width(), w.centralWidget().width()

    def closed_gives_room(self, before, close, near=None):
        t0, p0, c0 = before
        self.assertGreater(t0, 60)
        close()
        pump()
        self.assertTrue(self.w.dock_program_text.isHidden())
        near = near or self.w.dock_program
        self.assertAlmostEqual(near.width(), p0, delta=8)                       # la voisine garde sa largeur
        self.assertAlmostEqual(self.w.centralWidget().width(), c0 + t0, delta=12, msg=BEFORE_B)

    def same(self, a, b):
        for u, v in zip(a, b):
            self.assertAlmostEqual(u, v, delta=12)

    def test_closed_on_the_right_then_opened_again(self):
        w, dp, d = self.datron('droite')
        before = self.widths()
        self.closed_gives_room(before, lambda: self.c.close(d))                # sa croix
        w.show_program(refresh=False)                                           # le bouton Programme le rouvre
        pump()
        self.assertFalse(d.isHidden())
        self.same(self.widths(), before)                                        # la colonne s'élargit d'autant

    def test_program_window_alone_beside_its_text(self):
        self.empty_right()                                                      # rien d'autre à droite
        w, dp, d = self.datron('droite')
        self.assertEqual({k.objectName() for k in self.c.column('droite') if not k.isHidden()},
                         {'programme', 'programme_texte'})
        before = self.widths()
        self.closed_gives_room(before, lambda: self.c.close(d))
        w.show_program(refresh=False)
        pump()
        self.assertFalse(d.isHidden())
        self.same(self.widths(), before)

    def test_set_by_hand_meanwhile_nothing_forced(self):
        w, dp, d = self.datron('droite')
        before = self.widths()
        self.closed_gives_room(before, lambda: self.c.close(d))
        self.assertIsNotNone(d._vd_room)                                        # retenue à la fermeture
        self.by_hand(lambda: w.resizeDocks([dp], [dp.width() + 150], Qt.Orientation.Horizontal))   # à la souris
        self.assertIsNone(d._vd_room)                                           # oubliée dès le réglage
        from unittest import mock
        with mock.patch.object(self.c, '_widen') as widen:
            w.show_program(refresh=False)
            pump()
        self.assertFalse(d.isHidden())
        self.assertIsNone(d._vd_room)                                           # oubliée : Qt fait sa place
        widen.assert_not_called()

    def by_hand(self, change):
        """`change` pendant qu'un séparateur de colonnes est tiré : le bouton appuyé sur la fenêtre elle-même."""
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtGui import QMouseEvent
        w, at = self.w, QPointF(3, 3)
        left, none, mods = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
        QApplication.sendEvent(w, QMouseEvent(QEvent.Type.MouseButtonPress, at, at, left, left, mods))
        try:
            change()
            pump()
        finally:
            QApplication.sendEvent(w, QMouseEvent(QEvent.Type.MouseButtonRelease, at, at, left, none, mods))
        pump()

    def test_resized_by_qt_meanwhile_kept(self):
        w, dp, d = self.datron('droite')
        before = self.widths()
        self.closed_gives_room(before, lambda: self.c.close(d))
        w.resizeDocks([dp], [dp.width() + 150], Qt.Orientation.Horizontal)     # pas la souris : Qt
        pump()
        self.assertIsNotNone(d._vd_room)                                        # retenue (avant : oubliée)
        _t, p1, c1 = self.widths()
        w.show_program(refresh=False)
        pump()
        self.same(self.widths(), (before[0], p1, c1 - before[0]))               # sa largeur prise au dessin

    def test_centred_then_set_by_hand_not_overwritten(self):
        from unittest import mock
        w, dp, d = self.datron('droite')
        self.assertTrue(w.program_center(True))                                 # ▣ : le texte part, sans rétrécir
        pump()
        self.assertIsNotNone(d._vd_room)
        near = next(k for k in self.c.column('droite') if not k.isHidden() and self.c.in_front(k))
        self.by_hand(lambda: w.resizeDocks([near], [near.width() + 120], Qt.Orientation.Horizontal))
        self.assertIsNone(d._vd_room)                                           # avant : remise à l'ancienne largeur
        with mock.patch.object(self.c, '_widen') as widen:
            self.assertFalse(w.program_center(False))
            pump()
        self.assertFalse(d.isHidden())
        widen.assert_not_called()

    def test_closed_on_the_left_by_the_eye(self):
        w, dp, d = self.datron('gauche')
        before = self.widths()
        self.closed_gives_room(before, lambda: self.c.show_in(d, 'gauche', False))
        self.c.show_in(d, 'gauche', True)
        pump()
        self.same(self.widths(), before)

    def test_closed_with_the_program_window(self):
        w, dp, d = self.datron('droite')
        t0, p0, c0 = self.widths()
        dp.close()                                                              # le texte la suit (text_follow)
        pump()
        self.assertTrue(d.isHidden())
        near = next(k for k in self.c.column('droite') if not k.isHidden() and self.c.in_front(k))
        self.assertAlmostEqual(near.width(), p0, delta=8)
        self.assertAlmostEqual(w.centralWidget().width(), c0 + t0, delta=12, msg=BEFORE_B)

    def test_no_more_parts(self):
        w, dp, d = self.datron('droite')
        before = self.widths()
        self.closed_gives_room(before, lambda: self.choose('iso'))              # le texte revient sous les parties
        self.choose('essai_col')
        self.assertFalse(d.isHidden())
        self.same(self.widths(), before)

    def test_program_centred_and_back_shrinks_once(self):
        w, dp, d = self.datron('droite')
        before = self.widths()
        self.assertTrue(w.program_center(True))
        pump()
        self.assertFalse(w.program_center(False))                               # ▣ aller-retour : la même largeur
        pump()
        self.assertFalse(d.isHidden())
        self.same(self.widths(), before)
        self.closed_gives_room(before, lambda: self.c.close(d))                # puis fermé : rétrécie une fois

    def test_column_hidden_and_shown_again(self):
        w = self.w
        self.choose('essai_col')
        w.show_program(refresh=False)                                           # fenêtre Programme détachée
        pump()
        d = w.dock_program_text
        self.assertTrue(w.dock_program.isFloating())
        self.assertEqual(self.c.side(d), 'droite')
        near = next(k for k in self.c.column('droite') if k is not d and not k.isHidden() and self.c.in_front(k))
        t0, n0, c0 = d.width(), near.width(), w.centralWidget().width()
        self.c.set_shown('droite', False)
        pump()
        self.c.set_shown('droite', True)
        pump()
        self.assertFalse(d.isHidden())
        self.same((d.width(), near.width(), w.centralWidget().width()), (t0, n0, c0))
        self.closed_gives_room((t0, n0, c0), lambda: self.c.close(d), near=near)
        self.c.set_shown('droite', False)
        pump()
        self.c.set_shown('droite', True)
        pump()
        self.assertTrue(d.isHidden())                                           # fermé, il ne revient pas
        self.assertAlmostEqual(w.centralWidget().width(), c0 + t0, delta=12)

    def test_detached_nothing_moves(self):
        w, dp, d = self.datron('droite')
        self.c.toggle_floating(d)
        pump()
        self.assertTrue(d.isFloating())
        p1, c1 = dp.width(), w.centralWidget().width()
        self.c.close(d)
        pump()
        self.assertEqual((dp.width(), w.centralWidget().width()), (p1, c1))
        w.show_program(refresh=False)
        pump()
        self.assertTrue(d.isFloating())
        self.assertFalse(d.isHidden())
        self.assertEqual((dp.width(), w.centralWidget().width()), (p1, c1))
        self.c.toggle_floating(d)                                               # ancré de nouveau, puis fermé
        pump()
        self.assertFalse(d.isFloating())
        self.closed_gives_room(self.widths(), lambda: self.c.close(d))

    def test_opened_again_the_drawing_keeps_its_minimum(self):
        from vectordrive.ui.columns import DRAWING_MIN
        w, dp, d = self.datron('droite')
        c0 = w.centralWidget().width()
        self.c.close(d)
        pump()
        width, keep, shrunk, floor = d._vd_room
        self.assertTrue(shrunk)
        self.assertEqual(floor, min(DRAWING_MIN, c0))
        d._vd_room = (4000, keep, shrunk, floor)                                # plus large que la fenêtre
        w.show_program(refresh=False)
        pump()
        self.assertFalse(d.isHidden())
        self.assertGreaterEqual(w.centralWidget().width(), floor - 12)          # le dessin garde son minimum


if __name__ == '__main__':
    unittest.main()
