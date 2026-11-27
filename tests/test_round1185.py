"""Round rcol2 (demande du 27/11) : « pour tout élément s'affichant dans les colonnes, possibilité click droit seul dans
la colonne. Reviser complétement cette gestion d'affichage trop brouillonne, que ce soit clair et facile pour user A
droite seul a gauche seul (onglets pour les colonnes) puis ensuite possibilité de mettre audessusdessous d'un autre; »

Un seul modèle, le même partout : chaque panneau est « Seul à gauche » ou « Seul à droite » (son onglet dans le groupe
d'onglets de la colonne), ou « Au-dessus de › X » / « Au-dessous de › X » (la colonne de X partagée en hauteur avec
lui) ; « Masquer ». Le même menu court au clic droit de tout ce qu'une colonne montre (barre, onglet, fond du contenu,
« Disposition › » des menus propres des listes, le menu du panneau sur leur zone vide), l'état coché ; le tableau des
panneaux dit la même chose ; un panneau qui ne partage plus la hauteur avec personne (son partenaire remis en onglet,
masqué, reposé à la souris) reprend son onglet ; retenu au lancement suivant ; les réglages d'avant (`seul/`,
`onglet/`) remis à ce modèle une fois par poste.

Les menus ne sont jamais ouverts (`QMenu.exec`) : leurs actions sont déclenchées."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rcol2.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

import tests  # noqa: E402,F401  (dossiers du poste redirigés)

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QContextMenuEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel, QMenu  # noqa: E402

app = QApplication.instance() or QApplication([])
PREFIX = 'panneaux_colonnes/'
OTHER_KEYS = ('vue/panneau_fao', 'fao/panneaux_onglet')
RIGHT = Qt.DockWidgetArea.RightDockWidgetArea
BEFORE_MENU = 'avant : ni « Seul à gauche » ni « Seul à droite » au clic droit, l’état jamais coché'
BEFORE_RELEASE = 'avant : laissé seul hors des onglets, sans partager la hauteur avec personne'
BEFORE_LONELY = 'avant : son partenaire masqué, le repère restait seul hors des onglets'
BEFORE_MODEL = 'avant : les réglages « Sortir des onglets » / « En onglet avec » d’avant refaits à chaque lancement'
BEFORE_CONTENT = 'avant : le fond d’un panneau n’ouvrait pas son menu'
BEFORE_TABLE = 'avant : le tableau des panneaux ne disait ni « seul » ni « au-dessous de X »'
BEFORE_EMPTY = 'avant : aucun menu sur la zone vide de la liste'


def forget():
    from vectordrive.portable import settings
    st = settings()
    for k in list(st.allKeys()):
        if k.startswith(PREFIX) or k in OTHER_KEYS:
            st.remove(k)
    st.sync()


def pump(n=6):
    for _ in range(n):
        app.processEvents()


class Base(unittest.TestCase):
    F2 = 'onglet'

    def setUp(self):
        forget()
        self.addCleanup(forget)
        from vectordrive.portable import settings
        from vectordrive.ui.columns import F2_KEY
        settings().setValue(F2_KEY, self.F2)
        settings().setValue('fenetre/plein_ecran', False)
        self.w = None
        self.open()
        self.addCleanup(self._close)

    def open(self, state=None):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        if state is not None:
            self.w.restoreState(state)                   # la disposition d'une session, remise avant de la montrer
        self.w.resize(1400, 900)
        self.w.show()
        pump(10)
        self.c = self.w.columns

    def _close(self):
        if self.w is None:
            return
        self.w.modified = False
        for t in getattr(self.w, 'docs', []):
            t.modified = False
        self.w.settings.sync()
        self.w.close()
        pump()
        self.w = None

    def restart(self):
        self._close()
        self.open()

    def dock(self, name):
        return self.w.findChild(QDockWidget, name)

    def fao(self, on=True):
        self.w.A['cam_panel'].setChecked(on)
        pump()

    def key(self, name):
        return self.w.settings.value(PREFIX + name)

    def in_group(self, name, why='', side='droite'):
        """Le panneau `name` montré, dans le groupe d'onglets de la colonne `side`, groupe en bas de la colonne."""
        pump()
        d = self.dock(name)
        self.assertFalse(d.isHidden(), f'{name} caché — {why}')
        self.assertEqual(self.c.side(d), side, why)
        main = self.c.main_group(side)
        self.assertIn(d, main, f'{name} hors du groupe d’onglets — {why}')
        self.assertEqual({m.objectName() for m in self.c.blocks(side)[-1]}, {m.objectName() for m in main})

    def menu(self, dock, table=False):
        m = self.c.menu(dock, table=table)
        self.addCleanup(m.deleteLater)
        return m

    def act(self, m, name):
        acts = [a for a in m.actions() if a.objectName() == name]
        self.assertEqual(len(acts), 1, f'{name} — {BEFORE_MENU}')
        return acts[0]

    def sub(self, m, name):
        subs = [a.menu() for a in m.actions() if a.menu() is not None and a.menu().objectName() == name]
        self.assertEqual(len(subs), 1, name)
        return subs[0]

    def entry(self, m, name, dock):
        """L'entrée de `dock` dans le sous-menu `name` (« au_dessus_de », « au_dessous_de »)."""
        from vectordrive.ui.columns import full_title
        acts = [a for a in self.sub(m, name).actions() if a.text() == full_title(dock)]
        self.assertEqual(len(acts), 1, full_title(dock))
        return acts[0]


class Menu(Base):
    def test_the_short_menu(self):
        from vectordrive.i18n import tr
        layers = self.dock('layers')
        m = self.menu(layers, table=True)
        self.assertEqual([a.text() for a in m.actions()],
                         [tr('Seul à gauche'), tr('Seul à droite'), tr('Au-dessus de'), tr('Au-dessous de'),
                          tr('Masquer'), '', tr('Plein écran translucide'), tr('Détacher seul'),
                          tr('Titres entiers dans les onglets'), tr('Tous les panneaux')], BEFORE_MENU)
        self.assertIsNone(m.findChild(QMenu, 'en_onglet_avec'))
        right, left = self.act(m, 'seul_droite'), self.act(m, 'seul_gauche')
        self.assertTrue(right.isChecked())                                   # son onglet à droite : coché, grisé
        self.assertFalse(right.isEnabled())
        self.assertFalse(left.isChecked())
        self.assertTrue(left.isEnabled())
        self.assertFalse(self.act(m, 'masquer').isChecked())
        table = self.sub(m, 'tous_les_panneaux')                            # le tableau, au bas du menu
        self.assertEqual(table.actions()[0].objectName(), 'panneaux')
        self.assertEqual(self.c.state(layers), ('droite', None))

    def test_content_background_opens_the_same_menu(self):
        d = QDockWidget('Essai rcol2', self.w)
        d.setObjectName('essai_rcol2')
        lab = QLabel('fond')
        d.setWidget(lab)
        self.w.addDockWidget(RIGHT, d)
        d.setVisible(True)
        pump()
        self.assertTrue(any(x is d for x in self.c.docks()))
        for target, dock in ((lab, d), (self.w.dims, self.dock('dims'))):
            with mock.patch.object(self.c, 'show_menu') as shown:
                p = QPoint(4, 4)
                QApplication.sendEvent(target, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, p,
                                                                 target.mapToGlobal(p)))
            self.assertEqual(shown.call_count, 1, BEFORE_CONTENT)
            self.assertIs(shown.call_args[0][0], dock)

    def test_disposition_at_the_bottom_of_a_list_menu(self):
        from vectordrive.ui.columns import add_layout_menu
        m = self.w.symbols.menu(self.w.symbols.list, None, exec_menu=False)
        self.addCleanup(m.deleteLater)
        self.assertIsNotNone(m)
        self.assertEqual(m.actions()[-1].menu().objectName(), 'disposition')   # au bas de son menu propre
        sub = self.sub(m, 'disposition')
        self.assertTrue(self.act(sub, 'seul_droite').isChecked())
        self.assertIsNotNone(self.act(sub, 'masquer'))
        alone = QMenu()
        self.addCleanup(alone.deleteLater)
        self.assertIsNone(add_layout_menu(alone, QLabel()))                  # hors d'une colonne : rien
        self.assertFalse(alone.actions())

    def layout_sub(self, m):
        """« Disposition › », le dernier élément du menu propre `m`."""
        self.assertIsNotNone(m, BEFORE_EMPTY)
        self.addCleanup(m.deleteLater)
        last = m.actions()[-1].menu()
        self.assertIsNotNone(last, 'avant : pas de « Disposition › » au bas du menu')
        self.assertEqual(last.objectName(), 'disposition')
        self.assertIsNotNone(self.act(last, 'masquer'))
        return last

    def is_panel_menu(self, m, dock):
        """`m` : le menu du panneau `dock` (ses entrées « Seul à … »)."""
        self.assertIsNotNone(m, BEFORE_EMPTY)
        self.addCleanup(m.deleteLater)
        self.assertEqual(self.act(m, f'seul_{self.c.side(dock)}').isChecked(), self.c.state(dock)[0] in ('gauche',
                                                                                                       'droite'))

    def test_disposition_in_the_operation_menus(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        self.fao(True)
        p = self.w.cam_panel
        m = p.op_menu(None, exec_menu=False)                                # aucune opération : la zone vide
        self.is_panel_menu(m, self.dock('fao_liste'))
        sh = Shape(path=geom.Path([geom.rect(0.0, 0.0, 20.0, 14.0)]), tool=0)
        self.w.canvas.doc.add(sh)
        s = p.setup()
        tool = model.CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0, spindle=20000)
        s.tools = [tool]
        s.operations = [model.Operation(name='Gravure', kind='gravure', tool_id=tool.id, items=[sh.id], depth=0.2)]
        p.save(s)
        self.w.modified = False
        p._select_row(p.ops, 0)
        self.layout_sub(p.op_menu(None, exec_menu=False))                   # une opération : son menu, puis
        p.ops.clearSelection()                                              # « Disposition › »
        p.ops.setCurrentCell(-1, -1)
        if p._row(p.ops) < 0:
            self.is_panel_menu(p.op_menu(None, exec_menu=False), self.dock('fao_liste'))   # sans sélection

    def test_disposition_in_the_palette_color_and_assistant_menus(self):
        self.fao(True)
        self.layout_sub(self.w.cam_palette._menu(QPoint(5, 5), exec_menu=False))
        self.c.show_in(self.dock('couleur'), 'droite', True)
        pump()
        cp = self.w.color_panel
        self.is_panel_menu(cp._menu(QPoint(2, 30000), exec_menu=False), self.dock('couleur'))   # sans couleur
        item = cp.list.item(0)
        if item is not None:
            self.layout_sub(cp._menu(cp.list.visualItemRect(item).center(), exec_menu=False))
        self.c.show_in(self.dock('assistant'), 'droite', True)
        pump()
        ap = self.w.assistant_panel()
        v = ap.stack.currentWidget()
        self.layout_sub(ap._view_menu(v, QPoint(2, 2), exec_menu=False))

    def test_virtual_folder_of_the_library(self):
        from vectordrive.ui.symbols import VIRTUAL
        sym = self.w.symbols
        tree = sym.tree
        it = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                  if tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) in VIRTUAL)
        tree.setCurrentItem(it)
        self.is_panel_menu(sym.menu(tree, None, exec_menu=False), self.dock('symbols'))

    def test_lists_keep_their_own_menu(self):
        """Clic droit sur l'arbre des calques (« solo ») ou la liste des opérations : leur menu propre, pas celui du
        panneau."""
        self.fao(True)
        ops = self.w.cam_panel.ops
        tree = self.w.layers_panel.tree
        with mock.patch.object(self.c, 'show_menu') as shown, mock.patch.object(self.w.cam_panel, 'op_menu') as own:
            for target in (ops.viewport(), tree.viewport()):
                p = QPoint(3, 3)
                QApplication.sendEvent(target, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, p,
                                                                 target.mapToGlobal(p)))
                pump()
        self.assertEqual(own.call_count, 1)
        self.assertEqual(shown.call_count, 0)

    def test_words_of_the_menu(self):
        from vectordrive.i18n import tr
        self.fao(True)
        self.assertEqual(self.act(self.menu(self.dock('fao')), 'masquer').text(), tr('Masquer (ferme la FAO)'))
        bar = self.dock('layers').titleBarWidget()
        self.assertEqual(bar.buttons['fermer'].toolTip(), tr('Masquer le panneau'))

    def test_no_program_as_reference(self):
        from vectordrive.ui.columns import full_title
        prog = self.dock('programme')
        if self.c.side(prog) is None:
            self.c.move(prog, 'droite', remember=False)                     # (détaché d'office : dans la colonne)
        self.c._quiet(lambda: prog.setVisible(True))
        pump()
        self.assertIsNotNone(self.c.side(prog))
        self.addCleanup(lambda: self.c._quiet(prog.hide))
        m = self.menu(self.dock('layers'))
        for name in ('au_dessus_de', 'au_dessous_de'):
            self.assertNotIn(full_title(prog), [a.text() for a in self.sub(m, name).actions()])

    def test_mask_from_the_menu(self):
        layers = self.dock('layers')
        self.act(self.menu(layers), 'masquer').trigger()
        pump()
        self.assertTrue(layers.isHidden())
        m = self.menu(layers)                                                # sa ligne du tableau : masqué coché
        self.assertTrue(self.act(m, 'masquer').isChecked())
        self.assertFalse(self.act(m, 'masquer').isEnabled())
        self.act(m, 'seul_droite').trigger()                                 # « Seul à droite » : montré, son onglet
        self.in_group('layers', BEFORE_MENU)


class Alone(Base):
    def test_alone_on_the_right_from_below(self):
        """« Opérations au-dessous de Dimensions » : coché dans « Au-dessous de › » ; « Seul à droite » lui rend son
        onglet, Dimensions (qui ne partage plus la hauteur avec personne) aussi ; retenu."""
        self.fao(True)
        ops, dims = self.dock('fao_liste'), self.dock('dims')
        self.assertTrue(self.c.split_with(ops, dims, below=True))
        pump()
        m = self.menu(ops)
        act = self.act(m, 'seul_droite')
        self.assertFalse(act.isChecked())
        self.assertTrue(act.isEnabled())
        self.assertTrue(self.entry(m, 'au_dessous_de', dims).isChecked(), BEFORE_MENU)
        self.assertFalse(self.entry(m, 'au_dessus_de', dims).isChecked())
        act.trigger()
        pump()
        self.in_group('fao_liste', BEFORE_MENU)
        self.in_group('dims', BEFORE_RELEASE)
        self.assertIsNone(self.key('partage/fao_liste'))
        self.restart()
        self.in_group('fao_liste', 'lancement suivant')
        self.assertEqual(self.c.state(self.dock('fao_liste')), ('droite', None))

    def test_the_reference_sees_its_partner_checked(self):
        self.fao(True)
        ops, dims = self.dock('fao_liste'), self.dock('dims')
        self.c.split_with(ops, dims, below=True)
        pump()
        m = self.menu(dims)
        self.assertTrue(self.entry(m, 'au_dessus_de', ops).isChecked(), BEFORE_MENU)
        self.assertFalse(self.act(m, 'seul_droite').isChecked())
        self.assertEqual(self.c.state(dims), ('dessus', ops))

    def test_above_by_the_menu_kept_at_the_next_start(self):
        self.fao(True)
        ops, layers = self.dock('fao_liste'), self.dock('layers')
        self.entry(self.menu(ops), 'au_dessus_de', layers).trigger()
        pump()
        self.assertEqual(self.key('partage/fao_liste'), 'layers|dessus')
        self.assertEqual(self.c.state(ops), ('dessus', layers))
        self.restart()
        ops, layers = self.dock('fao_liste'), self.dock('layers')
        self.assertNotIn(ops, self.c.main_group('droite'))
        self.assertTrue(self.entry(self.menu(ops), 'au_dessus_de', layers).isChecked())

    def test_left_column_two_shared_then_alone(self):
        """La colonne de gauche : l'historique au-dessous de la palette FAO, sans groupe d'onglets ; « Seul à gauche »
        sur l'historique : les deux font le groupe d'onglets de la colonne."""
        self.fao(True)
        fao, hist = self.dock('fao'), self.dock('historique')
        self.c.show_in(hist, 'gauche', True)
        pump()
        self.assertTrue(self.c.split_with(hist, fao, below=True))
        pump()
        self.assertEqual(self.c.main_group('gauche'), [])
        act = self.act(self.menu(hist), 'seul_gauche')
        self.assertTrue(act.isEnabled(), BEFORE_MENU)
        act.trigger()
        pump()
        self.assertIn(fao, self.w.tabifiedDockWidgets(hist), BEFORE_RELEASE)
        self.assertEqual(len(self.c.blocks('gauche')), 1)
        self.assertEqual(self.c.state(fao), ('gauche', None))

    def test_alone_on_the_left_moves_it(self):
        layers = self.dock('layers')
        self.act(self.menu(layers), 'seul_gauche').trigger()
        pump()
        self.assertEqual(self.c.side(layers), 'gauche')
        self.assertEqual(self.key('place/layers'), 'gauche')
        self.assertTrue(self.act(self.menu(layers), 'seul_gauche').isChecked())


class Release(Base):
    def test_partner_takes_its_tab_when_the_reference_goes_alone(self):
        self.fao(True)
        ops, ass = self.dock('fao_liste'), self.dock('assistant')
        self.c.show_in(ass, 'droite', True)
        pump()
        self.assertTrue(self.c.split_with(ass, ops, below=True))
        pump()
        self.act(self.menu(ops), 'seul_droite').trigger()
        pump()
        self.in_group('fao_liste', BEFORE_MENU)
        self.in_group('assistant', BEFORE_RELEASE)
        self.assertIsNone(self.key('seul/assistant'))
        self.assertIsNone(self.key('partage/assistant'))

    def test_old_reference_takes_its_tab_when_another_is_chosen(self):
        self.fao(True)
        ops, dims, layers = self.dock('fao_liste'), self.dock('dims'), self.dock('layers')
        self.assertTrue(self.c.split_with(ops, dims, below=True))
        pump()
        self.assertTrue(self.c.split_with(ops, layers, below=True))         # au-dessous d'un autre : Dimensions libre
        pump()
        self.in_group('dims', BEFORE_RELEASE)
        self.assertEqual(self.c.state(ops), ('dessous', layers))


class Hidden(Base):
    def below_library(self):
        ass, sym = self.dock('assistant'), self.dock('symbols')
        self.c.show_in(ass, 'droite', True)
        pump()
        self.assertTrue(self.c.split_with(ass, sym, below=True))
        pump()
        return ass, sym

    def test_partner_masked_the_reference_takes_its_tab(self):
        """« Assistant au-dessous de Bibliothèque », puis Masquer l'Assistant : la Bibliothèque reprend son onglet, son
        menu ne coche rien qui vise un panneau caché ; le choix de l'Assistant gardé : remontré, il y revient."""
        ass, sym = self.below_library()
        self.act(self.menu(ass), 'masquer').trigger()
        pump()
        self.assertTrue(ass.isHidden())
        self.in_group('symbols', BEFORE_LONELY)
        m = self.menu(sym)
        self.assertEqual(self.c.state(sym), ('droite', None))
        self.assertTrue(self.act(m, 'seul_droite').isChecked(), BEFORE_LONELY)
        for name in ('au_dessus_de', 'au_dessous_de'):
            self.assertFalse([a.text() for a in self.sub(m, name).actions() if a.isChecked()])
        self.assertEqual(self.key('partage/assistant'), 'symbols|dessous')  # gardé pour son retour
        ass.toggleViewAction().trigger()                                    # remontré : au-dessous d'elle
        pump()
        self.assertFalse(ass.isHidden())
        self.assertEqual(self.c.state(ass), ('dessous', sym))
        self.assertNotIn(sym, self.c.main_group('droite'))

    def test_reference_masked_then_shown_takes_its_tab(self):
        """Le repère masqué puis remontré prend son onglet (round 1162, gardé) : l'Assistant reste où il est."""
        ass, sym = self.below_library()
        self.c.close(sym)
        pump()
        self.assertNotIn(ass, self.c.main_group('droite'))                  # le repère masqué : rien ne bouge
        sym.toggleViewAction().trigger()
        self.in_group('symbols', 'round 1162')
        self.assertFalse(ass.isHidden())
        self.assertNotIn(ass, self.c.main_group('droite'))


class CadTab(Base):
    """L'onglet CAD range les panneaux FAO, un onglet FAO les rétablit (`fao/panneaux_onglet`) : « Opérations
    au-dessous de Dimensions » rendu tel quel."""

    def below_dims(self):
        self.w.settings.setValue('fao/panneaux_onglet', True)
        self.fao(True)
        ops, dims = self.dock('fao_liste'), self.dock('dims')
        self.assertTrue(self.c.split_with(ops, dims, below=True))
        pump()
        return ops, dims

    def back_below(self, why):
        ops, dims = self.dock('fao_liste'), self.dock('dims')
        self.assertFalse(ops.isHidden())
        self.assertEqual(self.c.state(ops), ('dessous', dims), why)
        self.assertNotIn(dims, self.c.main_group('droite'), why)
        self.assertEqual(self.key('partage/fao_liste'), 'dims|dessous')

    def test_cad_then_fao_keeps_the_pair(self):
        ops, dims = self.below_dims()
        self.c.tab_clicked('cad')
        pump()
        self.assertTrue(ops.isHidden())
        self.assertNotIn(dims, self.c.main_group('droite'), 'rangé par l’onglet CAD : Dimensions laissé à sa place')
        self.c.tab_clicked('fao')
        pump()
        self.back_below('onglet FAO : la paire rendue')

    def test_put_away_at_the_last_start(self):
        ops, dims = self.below_dims()
        self.c.tab_clicked('cad')
        pump()
        self.assertTrue(self.key('rangees_cad'))
        state = self.w.saveState()                                           # la disposition de la session
        self._close()
        self.open(state)
        ops = self.dock('fao_liste')
        self.assertTrue(ops.isHidden())
        self.assertIn(ops, self.c.put_away())
        self.c.tab_clicked('fao')
        pump()
        self.back_below('lancement : rangés par l’onglet CAD, puis onglet FAO')


class ByHand(Base):
    def test_chooser_dropped_in_tabs_frees_its_reference(self):
        """« Opérations au-dessous de Calques », puis Opérations reposé à la souris dans le groupe d'onglets : Calques,
        qui ne partage plus la hauteur avec personne, reprend son onglet."""
        self.fao(True)
        ops, layers = self.dock('fao_liste'), self.dock('layers')
        self.assertTrue(self.c.split_with(ops, layers, below=True))
        pump()
        self.assertNotIn(layers, self.c.main_group('droite'))
        onto = self.c.main_group('droite')[0]
        self.c._quiet(lambda: self.w.tabifyDockWidget(onto, ops))           # sa place d'arrivée, comme Qt la pose
        pump()
        ops.setFloating(True)                                               # tiré
        pump()
        ops.setFloating(False)                                              # relâché dans les onglets
        pump()
        self.in_group('fao_liste')
        self.in_group('layers', BEFORE_RELEASE)
        self.assertIsNone(self.key('partage/fao_liste'))

    def test_detached_then_docked_frees_its_reference(self):
        ass, layers = self.dock('assistant'), self.dock('layers')
        self.c.show_in(ass, 'droite', True)
        pump()
        self.assertTrue(self.c.split_with(ass, layers, below=True))
        pump()
        self.assertTrue(self.c.toggle_floating(ass))                        # détaché
        pump()
        self.assertFalse(self.c.toggle_floating(ass))                       # ancré de nouveau : son onglet
        pump()
        self.in_group('assistant')
        self.in_group('layers', BEFORE_RELEASE)

    def test_mouse_pair_then_alone_on_the_right(self):
        """La palette FAO et Opérations en paire à part, faite à la souris ; « Seul à droite » sur Opérations : la
        palette, restée seule, reprend aussi son onglet."""
        self.fao(True)
        fao, ops = self.dock('fao'), self.dock('fao_liste')

        def pair():
            for d in (fao, ops):
                self.w.removeDockWidget(d)
            self.w.addDockWidget(RIGHT, fao, Qt.Orientation.Vertical)
            self.w.tabifyDockWidget(fao, ops)
            fao.setVisible(True)
            ops.setVisible(True)
        self.c._quiet(pair)
        pump()
        self.assertNotIn(ops, self.c.main_group('droite'))
        self.assertEqual(self.c.state(ops), ('hors', None))
        self.act(self.menu(ops), 'seul_droite').trigger()
        pump()
        self.in_group('fao_liste', BEFORE_MENU)
        self.in_group('fao', BEFORE_RELEASE)

    def test_partner_read_from_the_real_layout(self):
        """« Opérations au-dessous de Dimensions », puis Opérations remis dans les onglets à la souris, sans que le
        réglage le sache : rien de coché à tort."""
        self.fao(True)
        ops, dims = self.dock('fao_liste'), self.dock('dims')
        self.assertTrue(self.c.split_with(ops, dims, below=True))
        pump()
        group = self.c.main_group('droite')
        self.c._quiet(lambda: self.w.tabifyDockWidget(group[0], ops))
        pump()
        self.assertEqual(self.key('partage/fao_liste'), 'dims|dessous')
        self.assertNotEqual(self.c.state(ops), ('dessous', dims))
        self.assertFalse(self.entry(self.menu(ops), 'au_dessous_de', dims).isChecked())


class Table(Base):
    def test_the_table_says_the_same(self):
        from vectordrive.i18n import tr
        from vectordrive.ui.columns import PanelRows, full_title
        self.fao(True)
        ops, dims = self.dock('fao_liste'), self.dock('dims')
        self.c.split_with(ops, dims, below=True)
        pump()
        rows = PanelRows(self.c, 'droite')
        self.addCleanup(rows.deleteLater)
        below = tr('au-dessous de {0}').format(full_title(dims))
        self.assertEqual(rows.where(ops), below, BEFORE_TABLE)
        self.assertEqual(rows.where(dims), tr('au-dessus de {0}').format(full_title(ops)))
        self.assertEqual(rows.where(self.dock('layers')), tr('seul'))     # le mot du menu (« Seul à droite »)
        texts = [lab.text() for lab in rows.findChildren(QLabel, 'disposition')]
        self.assertIn(below, texts)
        self.assertTrue(rows.choices['fao_liste']['droite'].isChecked())     # sa colonne
        rows.choose(ops, 'droite')                                          # « Droite » : son onglet, pas masqué
        pump()
        self.in_group('fao_liste', BEFORE_TABLE)


class Model(Base):
    def test_old_keys_migrated_once(self):
        self._close()
        from vectordrive.portable import settings
        st = settings()
        st.remove(PREFIX + 'modele')                                         # un poste d'une version d'avant
        for k, v in (('seul/layers', True), ('onglet/symbols', 'layers'), ('onglet/dims', 'layers'),
                     ('partage/assistant', 'symbols|dessous'), ('regroupes', True)):
            st.setValue(PREFIX + k, v)
        st.sync()
        self.open()
        self.assertIsNone(self.key('seul/layers'), BEFORE_MODEL)
        self.assertIsNone(self.key('onglet/symbols'), BEFORE_MODEL)
        self.assertEqual(self.key('onglet/dims'), 'layers')                  # gardés
        self.assertEqual(self.key('partage/assistant'), 'symbols|dessous')
        self.assertEqual(str(self.key('modele')), '2')
        self.in_group('layers', BEFORE_MODEL)
        self.c.untab(self.dock('layers'))                                    # rangé ainsi ensuite (fonction d'office)
        pump()
        self.restart()
        self.assertTrue(self.key('seul/layers'))                             # une fois par poste : gardé
        self.assertFalse(self.w.tabifiedDockWidgets(self.dock('layers')))

    def test_model_key_written_once_laid_out(self):
        """`modele` vaut 1 tant que la disposition n'a pas été rangée (fenêtre pas encore montrée), 2 ensuite."""
        self._close()
        from vectordrive.portable import settings
        from vectordrive.ui.main_window import MainWindow
        st = settings()
        st.remove(PREFIX + 'modele')
        st.setValue(PREFIX + 'seul/layers', True)
        st.sync()
        self.w = MainWindow()                                                # pas encore montrée
        self.c = self.w.columns
        pump()
        self.assertEqual(str(self.key('modele')), '1', BEFORE_MODEL)
        self.assertIsNone(self.key('seul/layers'))
        self.w.resize(1400, 900)
        self.w.show()
        pump(10)
        self.assertEqual(str(self.key('modele')), '2')

    def test_session_layout_migrated(self):
        """La disposition d'une session d'avant : Calques et Bibliothèque en paire à part au-dessus du groupe — au
        premier lancement de cette version, chacun son onglet dans le groupe."""
        for name in ('accrochages', 'historique'):
            self.c.show_in(self.dock(name), 'droite', True)
            pump()
        layers, sym = self.dock('layers'), self.dock('symbols')

        def pair():
            for d in (layers, sym):
                self.w.removeDockWidget(d)
            self.w.addDockWidget(RIGHT, layers, Qt.Orientation.Vertical)
            self.w.tabifyDockWidget(layers, sym)
            layers.setVisible(True)
            sym.setVisible(True)
        self.c._quiet(pair)
        pump()
        self.assertNotIn(layers, self.c.main_group('droite'))
        state = self.w.saveState()
        self._close()
        from vectordrive.portable import settings
        st = settings()
        st.remove(PREFIX + 'modele')
        for k, v in (('seul/layers', True), ('onglet/symbols', 'layers'), ('regroupes', True)):
            st.setValue(PREFIX + k, v)
        st.sync()
        self.open(state)
        self.in_group('layers', BEFORE_MODEL)
        self.in_group('symbols', BEFORE_MODEL)
        self.assertEqual(len([b for b in self.c.blocks('droite') if len(b) > 1]), 1)


class FreshPost(Base):
    """Poste neuf : Dimensions d'office au-dessus de Calques."""
    F2 = 'dessus'

    def test_dimensions_alone_on_the_right_kept(self):
        dims, layers = self.dock('dims'), self.dock('layers')
        self.assertFalse(self.w.tabifiedDockWidgets(dims))
        m = self.menu(dims)
        self.assertTrue(self.entry(m, 'au_dessus_de', layers).isChecked(), BEFORE_MENU)   # d'office au-dessus
        self.act(m, 'seul_droite').trigger()
        pump()
        self.in_group('dims', BEFORE_MENU)
        self.assertEqual(self.key('onglet/dims'), 'layers')
        self.restart()
        self.in_group('dims', 'lancement suivant')


if __name__ == '__main__':
    unittest.main()
