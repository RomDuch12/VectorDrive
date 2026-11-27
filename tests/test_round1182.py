"""Round 1182 (demande du 27/11) : « FAO et opérations je n'arrive pas à lui octroyer son onglet colonne de droite, il se
mets toujours en partage de colonne; » — la palette FAO (« FAO : parcours », 'fao') et les opérations (« FAO :
opérations et parcours », 'fao_liste') gardent leur onglet dans le groupe d'onglets de la colonne de droite (FAO fermée
puis rouverte, onglets CAD / FAO du ruban, lancement suivant) tant que l'utilisateur ne choisit pas « Au-dessus de /
Au-dessous de ».

Causes trouvées : « En onglet avec › » un panneau seul faisait sortir du groupe le panneau choisi (une paire à part :
la colonne partagée) ; « Colonne de droite » était grisée pour un panneau déjà dans la colonne mais hors de son groupe ;
reposé à la souris dans les onglets, un panneau gardait son « au-dessous de » / « sorti des onglets » (refait au
lancement) et la fermeture de la FAO rendait la disposition d'avant son ouverture ; au lancement, la palette FAO sortie
des onglets par le rangement retenu fermait la FAO à moitié (« Opérations » caché, FAO cochée) ; la paire à part
retenue par une version d'avant (réglages, ou disposition de la session remise après le rangement des colonnes)
revenait à chaque lancement — rendue une fois par poste à son groupe d'onglets (`panneaux_colonnes/fao_onglets`),
écrit seulement quand aucun panneau FAO ancré n'est caché (colonne cachée, opérations fermées seules, fenêtre réduite :
à leur réouverture) ; une paire FAO devenue le groupe de sa colonne y reçoit les panneaux restés seuls ; « Colonne de
droite » d'un panneau resté dans sa colonne laisse seuls ceux rangés par rapport à lui.

Les menus ne sont jamais ouverts (`QMenu.exec`) : leurs actions sont déclenchées, ou les fonctions derrière elles
appelées."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'rcolfao.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDockWidget  # noqa: E402

app = QApplication.instance() or QApplication([])
PREFIX = 'panneaux_colonnes/'
OTHER_KEYS = ('vue/panneau_fao', 'fao/panneaux_onglet')
RIGHT = Qt.DockWidgetArea.RightDockWidgetArea
BEFORE_PAIR = 'avant : « En onglet avec » un panneau seul en faisait une paire à part, la colonne partagée'
BEFORE_MENU = 'avant : « Colonne de droite » grisée pour un panneau de la colonne hors de son groupe d’onglets'
BEFORE_HAND = 'avant : reposé à la souris dans les onglets, il ressortait (lancement suivant, FAO refermée)'
BEFORE_START = 'avant : au lancement, la FAO cochée mais « Opérations » caché, hors des onglets'
BEFORE_MIGRATION = 'avant : la paire à part retenue par une version d’avant revenait à chaque lancement'
BEFORE_SESSION = 'avant : la session remettait la paire à part, rien ne la défaisait'


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

    def open(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1400, 900)
        self.w.show()
        pump()
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

    def both_in_group(self, why=''):
        for name in ('fao', 'fao_liste'):
            self.in_group(name, why)

    def round_trip(self, why=''):
        """FAO fermée puis rouverte, onglet CAD puis FAO du ruban, lancement suivant (FAO ouverte, puis fermée et
        rouverte) : les deux panneaux FAO toujours dans le groupe d'onglets de droite."""
        self.both_in_group(why)
        self.fao(False)
        self.fao(True)
        self.both_in_group(why + ' (FAO refermée puis rouverte)')
        self.c.tab_clicked('cad')
        pump()
        self.c.tab_clicked('fao')
        pump()
        self.both_in_group(why + ' (onglets CAD puis FAO du ruban)')
        self.restart()
        self.assertTrue(self.w.A['cam_panel'].isChecked())
        self.both_in_group(why + ' (lancement suivant)')
        self.fao(False)
        self.fao(True)
        self.both_in_group(why + ' (lancement suivant, FAO refermée puis rouverte)')

    def palette_right(self):
        """La FAO ouverte, sa palette envoyée dans la colonne de droite (« Colonne de droite ») : son onglet."""
        self.fao(True)
        self.c.move(self.dock('fao'), 'droite')
        pump()
        self.both_in_group('palette envoyée à droite')

    def column_action(self, dock, side='droite'):
        from vectordrive.ui.columns import SIDES
        m = self.c.menu(dock, table=False)
        self.addCleanup(m.deleteLater)
        label = {'gauche': 'Seul à gauche', 'droite': 'Seul à droite'}[side]   # (rcol2 : le modèle du 27/11)
        from vectordrive.i18n import tr
        acts = [a for a in m.actions() if a.text() == tr(label)]
        self.assertEqual(len(acts), 1)
        self.assertIn(side, SIDES)
        return acts[0]

    def hand_drop_in_tabs(self, dock, onto):
        """Le panneau reposé à la souris dans le groupe d'onglets de `onto` : sa place d'arrivée posée comme Qt la
        pose (sans signal à nous), puis le panneau tiré (détaché) et relâché (ancré de nouveau, à cette place) —
        hors de nos fonctions. Un vrai glisser-déposer ne se rejoue pas hors écran."""
        self.c._quiet(lambda: self.w.tabifyDockWidget(onto, dock))
        pump()
        dock.setFloating(True)                             # tiré : Qt le détache
        pump()
        dock.setFloating(False)                            # relâché : ancré à sa place d'arrivée, dans les onglets
        pump()
        self.assertIn(onto, self.w.tabifiedDockWidgets(dock))


class TabWith(Base):
    def test_out_of_tabs_palette_pair_kept_then_right_column_entry(self):
        """La palette sortie des onglets, « Opérations » mis en onglet avec elle : leur paire à part (choisie, round
        1013), refaite au lancement suivant — les deux montrés, la FAO cochée ; puis « Seul à droite » sur Opérations
        seul (adapté au round rcol2) : l'autre de la paire, resté seul, reprend aussi son onglet ; ils y restent."""
        self.palette_right()
        fao, ops = self.dock('fao'), self.dock('fao_liste')
        self.assertTrue(self.c.untab(fao))                                  # « Sortir des onglets »
        pump()
        self.assertTrue(self.c.tab_with(ops, fao))                         # « En onglet avec › FAO : parcours »
        pump()
        self.assertIn(fao, self.w.tabifiedDockWidgets(ops))
        self.restart()
        fao, ops = self.dock('fao'), self.dock('fao_liste')
        self.assertTrue(self.w.A['cam_panel'].isChecked())
        self.assertFalse(ops.isHidden(), BEFORE_START)
        self.assertIn(fao, self.w.tabifiedDockWidgets(ops), BEFORE_START)
        act = self.column_action(ops)                                       # (rcol2 : Opérations seul)
        self.assertTrue(act.isEnabled(), BEFORE_MENU)
        act.trigger()
        pump()
        self.both_in_group(BEFORE_MENU)
        self.assertFalse(self.key('seul/fao'))
        self.round_trip(BEFORE_MENU)

    def test_two_lone_panels_tabbed_join_the_group(self):
        self.palette_right()
        self.assertTrue(self.c.split_with(self.dock('fao_liste'), self.dock('fao'), below=True))
        pump()
        self.assertEqual(self.key('partage/fao_liste'), 'fao|dessous')
        self.assertTrue(self.c.tab_with(self.dock('fao_liste'), self.dock('fao')))   # le partage défait
        pump()
        self.both_in_group(BEFORE_PAIR)
        self.assertFalse(self.key('partage/fao_liste'))
        self.round_trip(BEFORE_PAIR)

    def test_reference_freed_when_its_partner_goes_alone(self):
        """Remplace test_from_the_group_with_a_lone_panel_by_the_menu (round rcol2, 27/11 : plus de « En onglet avec › »
        au menu, ni de palette laissée seule) : « Opérations au-dessous de FAO : parcours », puis « Seul à droite » sur
        Opérations — la palette ne partage plus la hauteur avec personne : elle reprend aussi son onglet."""
        self.palette_right()
        self.c.split_with(self.dock('fao_liste'), self.dock('fao'), below=True)   # la palette seule : repère
        pump()
        self.assertNotIn(self.dock('fao'), self.c.main_group('droite'))
        self.column_action(self.dock('fao_liste')).trigger()               # l'action du menu, sans l'ouvrir
        pump()
        self.both_in_group(BEFORE_PAIR)

    def test_third_panel_below_the_lone_one_stays_alone(self):
        """« Assistant au-dessous de FAO : parcours » (la palette, son repère, sortie des onglets), puis « Opérations en
        onglet avec FAO : parcours » : les deux FAO dans le groupe ; l'assistant, qui ne partage plus la hauteur avec
        personne, reprend son onglet (adapté au round rcol2 : avant, il restait à part, seul)."""
        self.palette_right()
        fao, ops, ass = self.dock('fao'), self.dock('fao_liste'), self.dock('assistant')
        self.c.show_in(ass, 'droite', True)
        pump()
        self.assertTrue(self.c.split_with(ass, fao, below=True))
        pump()
        self.assertEqual(self.key('partage/assistant'), 'fao|dessous')
        self.assertTrue(self.c.tab_with(ops, fao))
        pump()
        self.both_in_group(BEFORE_PAIR)
        self.assertFalse(self.key('partage/assistant'))
        self.assertFalse(self.key('seul/assistant'))                        # (rcol2 : plus de panneau seul à part)
        self.in_group('assistant', 'rcol2 : il ne partage plus la hauteur avec personne')

    def test_user_pair_outside_the_group_still_possible(self):
        """Deux panneaux sortis des onglets par l'utilisateur, mis en onglet l'un avec l'autre : leur paire à part,
        comme avant (le panneau choisi n'est pas dans le groupe, l'autre a été sorti par l'utilisateur)."""
        self.palette_right()
        fao, ops = self.dock('fao'), self.dock('fao_liste')
        self.c.untab(fao)
        pump()
        self.c.untab(ops)
        pump()
        self.assertTrue(self.c.tab_with(ops, fao))
        pump()
        self.assertIn(fao, self.w.tabifiedDockWidgets(ops))
        self.assertNotIn(ops, self.c.main_group('droite'))


class ColumnEntry(Base):
    def test_right_column_entry_gives_its_tab(self):
        self.fao(True)
        ops, dims = self.dock('fao_liste'), self.dock('dims')
        self.c.split_with(ops, dims, below=True)                            # « Au-dessous de › Dimensions »
        pump()
        self.assertNotIn(ops, self.c.main_group('droite'))
        act = self.column_action(ops)
        self.assertFalse(act.isChecked())                                   # (rcol2 : « Au-dessous de › » coché)
        self.assertTrue(act.isEnabled(), BEFORE_MENU)
        act.trigger()
        pump()
        self.in_group('fao_liste', BEFORE_MENU)
        self.assertFalse(self.key('partage/fao_liste'))
        self.c.move(self.dock('fao'), 'droite')
        pump()
        self.round_trip(BEFORE_MENU)

    def test_table_right_on_a_panel_outside_gives_its_tab(self):
        """Tableau Gauche / Masqué / Droite : la palette dans la colonne de droite mais hors du groupe (au-dessous de
        Dimensions) — « Droite » coché ; un clic lui donne son onglet, la FAO reste ouverte. Dans le groupe, un clic
        sur « Droite » masque, comme avant (15/11)."""
        from vectordrive.ui.columns import PanelRows
        self.palette_right()
        fao, ops, dims = self.dock('fao'), self.dock('fao_liste'), self.dock('dims')
        self.assertTrue(self.c.split_with(fao, dims, below=True))
        pump()
        rows = PanelRows(self.c, 'droite')
        self.addCleanup(rows.deleteLater)
        self.assertTrue(rows.choices['fao']['droite'].isChecked())
        rows.choose(fao, 'droite')
        pump()
        self.assertTrue(self.w.A['cam_panel'].isChecked(), 'avant : « Droite » masquait la palette, la FAO fermée')
        self.both_in_group(BEFORE_MENU)
        self.assertFalse(self.key('partage/fao'))
        rows = PanelRows(self.c, 'droite')
        self.addCleanup(rows.deleteLater)
        rows.choose(ops, 'droite')                                          # dans le groupe : masqué
        pump()
        self.assertTrue(ops.isHidden())

    def test_right_column_entry_keeps_a_third_panel_below_alone(self):
        """« Opérations au-dessous de Dimensions », « Assistant au-dessous de Opérations », puis « Seul à droite »
        sur Opérations : son onglet ; l'assistant, qui ne partage plus la hauteur avec personne, reprend aussi le sien
        (adapté au round rcol2 : avant, il restait à part, seul)."""
        self.fao(True)
        ops, dims, ass = self.dock('fao_liste'), self.dock('dims'), self.dock('assistant')
        self.assertTrue(self.c.split_with(ops, dims, below=True))
        pump()
        self.c.show_in(ass, 'droite', True)
        pump()
        self.assertTrue(self.c.split_with(ass, ops, below=True))
        pump()
        self.assertEqual(self.key('partage/assistant'), 'fao_liste|dessous')
        self.column_action(ops).trigger()
        pump()
        self.in_group('fao_liste', BEFORE_MENU)
        self.assertFalse(self.key('partage/assistant'))
        self.assertFalse(self.key('seul/assistant'))                        # (rcol2 : plus de panneau seul à part)
        self.in_group('assistant', 'rcol2 : il ne partage plus la hauteur avec personne')

    def test_table_tooltip_outside_the_group(self):
        from vectordrive.i18n import tr
        from vectordrive.ui.columns import PLACES, PanelRows
        self.fao(True)
        ops, dims = self.dock('fao_liste'), self.dock('dims')
        rows = PanelRows(self.c, 'droite')
        self.addCleanup(rows.deleteLater)
        tip = tr(dict((k, t) for k, _x, t in PLACES)['droite'])
        self.assertEqual(rows.choices['fao_liste']['droite'].toolTip(), tip)  # dans le groupe : un clic masque
        self.assertTrue(self.c.split_with(ops, dims, below=True))
        pump()
        rows = PanelRows(self.c, 'droite')
        self.addCleanup(rows.deleteLater)
        self.assertNotEqual(rows.choices['fao_liste']['droite'].toolTip(), tip, 'avant : « un second clic : masqué »')

    def test_entry_greyed_without_a_group_to_join(self):
        self.fao(True)
        fao, hist = self.dock('fao'), self.dock('historique')
        self.c.show_in(hist, 'gauche', True)
        pump()
        self.assertTrue(self.c.split_with(hist, fao, below=True))         # la colonne de gauche : deux partagés
        pump()
        self.assertEqual(self.c.main_group('gauche'), [])
        act = self.column_action(hist, 'gauche')                           # rcol2 : « Seul à gauche » actif — les
        self.assertTrue(act.isEnabled())                                    # deux font le groupe de la colonne
        act.trigger()
        pump()
        self.assertIn(fao, self.w.tabifiedDockWidgets(hist))
        self.assertEqual(len(self.c.blocks('gauche')), 1)

    def test_entry_greyed_in_the_group(self):
        self.fao(True)
        act = self.column_action(self.dock('fao_liste'))
        self.assertTrue(act.isChecked())
        self.assertFalse(act.isEnabled())                                   # déjà son onglet : rien à faire
        self.assertTrue(self.column_action(self.dock('fao_liste'), 'gauche').isEnabled())


class ByHand(Base):
    def test_dropped_in_tabs_forgets_below(self):
        self.palette_right()
        ops, dims, layers = self.dock('fao_liste'), self.dock('dims'), self.dock('layers')
        self.c.split_with(ops, dims, below=True)
        pump()
        self.fao(False)
        self.fao(True)                                                      # la disposition d'avant la FAO : partagée
        self.assertNotIn(ops, self.c.main_group('droite'))
        self.hand_drop_in_tabs(ops, layers)
        self.in_group('fao_liste', BEFORE_HAND)
        self.assertFalse(self.key('partage/fao_liste'), BEFORE_HAND)
        self.assertIsNone(getattr(self.w, '_docks_before_cam', None), BEFORE_HAND)
        self.round_trip(BEFORE_HAND)

    def test_palette_dropped_right_stays_after_closing_the_cam(self):
        self.fao(True)
        fao, layers = self.dock('fao'), self.dock('layers')
        self.assertEqual(self.c.side(fao), 'gauche')                        # d'office : à gauche
        self.fao(False)
        self.fao(True)                                                      # la disposition d'avant la FAO retenue
        self.assertIsNotNone(getattr(self.w, '_docks_before_cam', None))
        self.hand_drop_in_tabs(fao, layers)                                 # tirée à la souris dans les onglets
        self.in_group('fao', BEFORE_HAND)
        self.fao(False)                                                     # pas de disposition d'avant rendue
        self.fao(True)
        self.in_group('fao', BEFORE_HAND)

    def test_out_of_tabs_dropped_back_forgets_it(self):
        self.palette_right()
        fao, layers = self.dock('fao'), self.dock('layers')
        self.c.untab(fao)
        pump()
        self.assertTrue(self.key('seul/fao'))
        self.hand_drop_in_tabs(fao, layers)
        self.in_group('fao', BEFORE_HAND)
        self.assertFalse(self.key('seul/fao'), BEFORE_HAND)
        self.round_trip(BEFORE_HAND)

    def test_reference_dropped_in_tabs_partner_stays_alone(self):
        """« Assistant au-dessous de Opérations », puis Opérations reposé à la souris dans le groupe : l'assistant, qui
        ne partage plus la hauteur avec personne, reprend son onglet (adapté au round rcol2 : avant, à part, seul)."""
        self.fao(True)
        ops, ass, layers = self.dock('fao_liste'), self.dock('assistant'), self.dock('layers')
        self.c.show_in(ass, 'droite', True)
        pump()
        self.assertTrue(self.c.split_with(ass, ops, below=True))
        pump()
        self.hand_drop_in_tabs(ops, layers)
        self.in_group('fao_liste', BEFORE_HAND)
        self.assertFalse(self.key('partage/assistant'))
        self.assertFalse(self.key('seul/assistant'))                        # (rcol2 : plus de panneau seul à part)
        self.in_group('assistant', 'rcol2 : il ne partage plus la hauteur avec personne')

    def test_palette_detached_keeps_the_cam_open(self):
        """La palette détachée (son bouton ⧉ ; Qt la cache un instant, comme quand on la tire) puis ancrée de nouveau :
        la FAO reste ouverte, « Opérations » montré."""
        self.fao(True)
        fao, ops = self.dock('fao'), self.dock('fao_liste')
        self.assertTrue(self.c.toggle_floating(fao))
        pump()
        self.assertTrue(self.w.A['cam_panel'].isChecked(), BEFORE_START)
        self.assertFalse(ops.isHidden(), 'avant : la palette détachée fermait la FAO à moitié')
        self.c.toggle_floating(fao)
        pump()
        self.assertTrue(self.w.A['cam_panel'].isChecked())
        self.assertFalse(fao.isHidden())
        self.assertFalse(ops.isHidden(), 'avant : la palette détachée fermait la FAO à moitié')
        self.c.close(fao)                                                   # sa croix : la FAO fermée, comme avant
        pump()
        self.assertFalse(self.w.A['cam_panel'].isChecked())
        self.assertTrue(ops.isHidden())

    def test_cam_command_follows_after_closing(self):
        self.fao(True)
        self.fao(False)                                                     # la disposition d'avant rendue
        self.assertFalse(self.w.A['cam_panel'].isChecked(), 'avant : « Panneau FAO » restait coché, FAO fermée')
        self.fao(True)
        self.assertFalse(self.dock('fao_liste').isHidden())

    def test_overlay_round_trip_keeps_the_layout_before_the_cam(self):
        before = [{m.objectName() for m in b} for b in self.c.blocks('droite')]
        self.fao(True)
        self.assertIsNotNone(getattr(self.w, '_docks_before_cam', None))
        self.c.toggle_overlay(self.dock('fao_liste'))                       # plein écran translucide, et retour
        pump()
        self.c.toggle_overlay(self.dock('fao_liste'))
        pump()
        self.assertIsNotNone(getattr(self.w, '_docks_before_cam', None))   # pas un rangement à la main
        self.fao(False)
        self.assertEqual([{m.objectName() for m in b} for b in self.c.blocks('droite')], before)


class Start(Base):
    def keys(self, pairs, fao_open=True, migrated=False):
        """La fenêtre relancée avec ces réglages de colonnes (`migrated` : le poste déjà remis en ordre)."""
        self._close()
        from vectordrive.portable import settings
        st = settings()
        for k, v in pairs + (('regroupes', True),) + ((('fao_onglets', True),) if migrated else ()):
            st.setValue(PREFIX + k, v)
        st.setValue('vue/panneau_fao', fao_open)
        if not migrated:                                                    # un poste d'une version d'avant
            st.remove(PREFIX + 'fao_onglets_cles')
        st.sync()
        self.open()

    def test_palette_out_of_tabs_at_start_keeps_the_cam_open(self):
        """Retenu, le poste déjà remis en ordre : la palette à droite, sortie des onglets, les opérations en onglet avec
        elle (une paire choisie, round 1013) ; la FAO ouverte au lancement : les deux montrés, la FAO cochée."""
        self.keys((('place/fao', 'droite'), ('place/fao_liste', 'droite'), ('seul/fao', True),
                   ('onglet/fao_liste', 'fao')), migrated=True)
        self.assertTrue(self.w.A['cam_panel'].isChecked())
        fao, ops = self.dock('fao'), self.dock('fao_liste')
        self.assertFalse(fao.isHidden())
        self.assertFalse(ops.isHidden(), BEFORE_START)
        self.assertIn(fao, self.w.tabifiedDockWidgets(ops), BEFORE_START)  # leur paire retenue, refaite
        self.assertIsNone(getattr(self.w, '_docks_before_cam', None))       # rien de rendu à la fermeture de la FAO

    def test_old_pair_keys_migrated_once(self):
        """Réglages d'une version d'avant (la paire à part laissée par « En onglet avec ») : au premier lancement,
        chacun son onglet dans le groupe ; le poste est marqué ; au lancement suivant, c'est retenu."""
        self.keys((('place/fao', 'droite'), ('place/fao_liste', 'droite'), ('seul/fao', True),
                   ('onglet/fao_liste', 'fao')))
        self.assertTrue(self.w.A['cam_panel'].isChecked())
        self.both_in_group(BEFORE_MIGRATION)
        self.assertTrue(self.key('fao_onglets'))
        self.assertFalse(self.key('seul/fao'))
        self.assertFalse(self.key('onglet/fao_liste'))
        self.round_trip(BEFORE_MIGRATION)

    def test_pair_cam_closed_migrated_at_opening(self):
        """La paire à part (réglages et disposition d'une session), la FAO fermée au lancement : rangée à la première
        ouverture de la FAO ; le poste marqué seulement alors."""
        self.keys((('place/fao', 'droite'), ('seul/fao_liste', True), ('onglet/fao', 'fao_liste')), fao_open=False)
        self.assertFalse(self.key('seul/fao_liste'))                       # les clés retirées avant le rangement
        self.assertFalse(self.key('onglet/fao'))
        self.assertFalse(self.key('fao_onglets'))                          # rien rangé encore
        fao, ops = self.dock('fao'), self.dock('fao_liste')

        def pair():                                                         # la disposition d'une session : la paire
            for d in (ops, fao):                                            # à part, cachée avec la FAO
                self.w.removeDockWidget(d)
            self.w.addDockWidget(RIGHT, ops, Qt.Orientation.Vertical)
            self.w.tabifyDockWidget(ops, fao)
            ops.setVisible(False)
            fao.setVisible(False)
        self.c._quiet(pair)
        pump()
        self.fao(True)
        self.both_in_group(BEFORE_MIGRATION)
        self.assertTrue(self.key('fao_onglets'))

    def test_below_chosen_survives_the_migration(self):
        self.keys((('place/fao', 'droite'), ('partage/fao_liste', 'fao|dessous')))
        ops = self.dock('fao_liste')
        self.assertEqual(self.key('partage/fao_liste'), 'fao|dessous')
        self.assertFalse(self.w.tabifiedDockWidgets(ops))
        self.assertNotIn(ops, self.c.main_group('droite'))
        self.assertTrue(self.key('fao_onglets'))


class Pending(Base):
    """Le rangement d'une fois par poste attend qu'aucun panneau FAO ancré ne soit caché : le réglage n'est écrit
    qu'une fois les deux rangés (sinon la paire de la session revenait pour toujours)."""

    def pending_pair(self, hide=()):
        """Le poste pas encore remis en ordre, la paire à part d'une session dans la colonne de droite ; `hide` :
        les panneaux cachés hors de nos fonctions."""
        fao, ops = self.dock('fao'), self.dock('fao_liste')
        self.w.settings.remove(PREFIX + 'fao_onglets')
        self.c._fao_due = False

        def pair():
            for d in (ops, fao):
                self.w.removeDockWidget(d)
            self.w.addDockWidget(RIGHT, ops, Qt.Orientation.Vertical)
            self.w.tabifyDockWidget(ops, fao)
            ops.setVisible(True)
            fao.setVisible(True)
            for d in hide:
                d.setVisible(False)
        self.c._quiet(pair)
        pump()
        return fao, ops

    def test_operations_closed_alone_wait_for_them(self):
        self.fao(True)
        fao, ops = self.pending_pair(hide=[self.dock('fao_liste')])
        self.c.settle_all()
        pump()
        self.in_group('fao', BEFORE_MIGRATION)
        self.assertFalse(self.key('fao_onglets'), 'avant : réglage écrit, les opérations cachées pas rangées')
        self.c.show_in(ops, 'droite', True)                                 # rouvertes
        pump()
        self.both_in_group(BEFORE_MIGRATION)
        self.assertTrue(self.key('fao_onglets'))

    def test_palette_closed_by_its_cross_then_reopened(self):
        """La palette fermée par la croix de Qt (`close`) pendant que le rangement attend : la FAO fermée ; rouverte,
        les deux rangés, le réglage écrit."""
        self.fao(True)
        fao, ops = self.pending_pair(hide=[self.dock('fao_liste')])
        self.c.settle_all()
        pump()
        fao.close()
        pump()
        self.assertFalse(self.w.A['cam_panel'].isChecked())
        self.assertFalse(self.key('fao_onglets'))
        self.fao(True)
        self.both_in_group(BEFORE_MIGRATION)
        self.assertTrue(self.key('fao_onglets'))

    def test_column_hidden_at_start_migrated_when_shown(self):
        self.fao(True)
        fao, ops = self.pending_pair()
        self.c.set_shown('droite', False)                                   # cachée par son bouton
        pump()
        self.c.settle_all()
        pump()
        self.assertFalse(self.key('fao_onglets'))
        self.c.set_shown('droite', True)                                    # rouverte : la paire revenue, rangée
        pump(10)
        self.both_in_group('avant : la colonne rouverte, la paire de la session restait à part')
        self.assertTrue(self.key('fao_onglets'))

    def test_pair_become_the_main_group_gathers_the_lone_panel(self):
        """La colonne de droite : [Calques] seul et la paire [FAO, Opérations] — la paire est le groupe de la
        colonne : Calques y prend son onglet, la colonne n'est plus partagée."""
        self.fao(True)
        layers = self.dock('layers')
        keep = {'fao', 'fao_liste', 'layers'}
        others = [d for d in self.c.column('droite') if d.objectName() not in keep and not d.isHidden()]
        self.c._quiet(lambda: [d.setVisible(False) for d in others])
        fao, ops = self.pending_pair()
        self.c._quiet(lambda: (self.w.removeDockWidget(layers), self.w.addDockWidget(RIGHT, layers),
                               layers.setVisible(True)))
        pump()
        self.assertEqual(len(self.c.blocks('droite')), 2)
        self.c.settle_all()
        pump()
        self.assertEqual(len(self.c.blocks('droite')), 1, 'avant : la paire FAO restait à part de Calques')
        self.both_in_group(BEFORE_MIGRATION)
        self.in_group('layers')
        self.assertTrue(self.key('fao_onglets'))

    def test_window_minimized_at_start(self):
        self._close()
        from vectordrive.portable import settings
        st = settings()
        for k, v in (('place/fao', 'droite'), ('place/fao_liste', 'droite'), ('seul/fao', True),
                     ('onglet/fao_liste', 'fao'), ('regroupes', True)):
            st.setValue(PREFIX + k, v)
        st.setValue('vue/panneau_fao', True)
        st.remove(PREFIX + 'fao_onglets_cles')                              # un poste d'une version d'avant
        st.sync()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1400, 900)
        self.w.showMinimized()                                              # réduite au lancement
        pump()
        self.c = self.w.columns
        self.assertFalse(self.key('fao_onglets'), 'fenêtre réduite : rien rangé encore')
        self.w.showNormal()
        pump(10)
        self.both_in_group(BEFORE_MIGRATION)
        self.assertTrue(self.key('fao_onglets'), 'avant : la fenêtre rendue, le rangement attendu jamais fait')


class Session(Base):
    """Le lancement réel (VectorDrive.py) : `start_session`, `show_at_start(True)` — plein écran d'office :
    `restore_panels` puis `set_full_screen` —, les événements, `restore_session` ; la disposition de la session
    remise après le rangement des colonnes ; le premier rangement (`regroupes`) déjà fait sur le poste."""

    def session_window(self, folder):
        from vectordrive.portable import settings
        from vectordrive.ui.main_window import MainWindow
        st = settings()
        st.remove('fenetre/plein_ecran')                                    # plein écran d'office
        st.setValue(PREFIX + 'regroupes', True)
        st.sync()
        self.w = MainWindow()
        on = self.w.start_session(folder)
        self.assertTrue(on)
        self.w.show_at_start(bool(on))
        app.processEvents()
        self.w.restore_session()
        pump(10)
        self.c = self.w.columns

    def end_session(self):
        lock = getattr(self.w, '_session_lock', None)
        if lock is not None:
            lock.unlock()
        self.w._session_lock, self.w.session_dir = None, None
        self._close()

    def test_session_pair_migrated_once(self):
        folder = tempfile.mkdtemp()
        self.w.settings.setValue(PREFIX + 'fao_onglets', True)             # la session d'une version d'avant :
        self.palette_right()                                                # la paire à part y est faite à la main
        fao, ops = self.dock('fao'), self.dock('fao_liste')
        self.c.untab(fao)
        pump()
        self.c.tab_with(ops, fao)
        pump()
        self.assertNotIn(ops, self.c.main_group('droite'))
        self.w.start_session(folder)
        self.assertTrue(self.w.save_session())
        self.end_session()
        from vectordrive.portable import settings
        st = settings()
        st.remove(PREFIX + 'fao_onglets')                                   # le poste pas encore remis en ordre
        st.remove(PREFIX + 'fao_onglets_cles')
        st.setValue('vue/panneau_fao', True)
        st.sync()
        self.session_window(folder)
        self.assertTrue(self.w.A['cam_panel'].isChecked())
        self.both_in_group(BEFORE_SESSION)
        self.assertTrue(self.key('fao_onglets'))
        self.assertTrue(self.w.save_session())
        self.end_session()
        self.session_window(folder)                                         # relance suivante : la même
        self.both_in_group(BEFORE_SESSION + ' (relance suivante)')
        self.end_session()


class Kept(Base):
    """Les autres règles : « Au-dessus de / Au-dessous de » choisi reste partagé ; la disposition d'un premier lancement."""

    def test_below_chosen_stays_split(self):
        self.palette_right()
        ops, fao = self.dock('fao_liste'), self.dock('fao')
        self.c.split_with(ops, fao, below=True)
        pump()

        def split(why):
            pump()
            self.assertFalse(ops.isHidden(), why)
            self.assertNotIn(ops, self.c.main_group('droite'), why)
            self.assertFalse(self.w.tabifiedDockWidgets(ops), why)
        split('choisi')
        self.fao(False)
        self.fao(True)
        split('FAO refermée puis rouverte')
        self.c.tab_clicked('cad')
        pump()
        self.c.tab_clicked('fao')
        split('onglets CAD puis FAO')
        self.restart()
        ops, fao = self.dock('fao_liste'), self.dock('fao')
        split('lancement suivant')

    def test_first_start_default(self):
        self.fao(True)
        self.assertEqual(self.c.side(self.dock('fao')), 'gauche')           # la palette à gauche d'office
        self.in_group('fao_liste', 'défaut')                                # les opérations en onglet à droite


class FreshPost(Base):
    """Poste neuf : Dimensions d'office au-dessus de Calques."""
    F2 = 'dessus'

    def test_palette_right_on_a_fresh_post(self):
        self.assertIn('dims', self.c.placed())
        self.palette_right()
        self.round_trip('poste neuf')

    def test_out_of_tabs_palette_back_on_a_fresh_post(self):
        self.palette_right()
        self.c.untab(self.dock('fao'))
        pump()
        self.c.tab_with(self.dock('fao'), self.dock('fao_liste'))          # depuis la palette : elle y revient
        pump()
        self.round_trip('poste neuf, palette revenue en onglet')

    def test_dimensions_dropped_in_the_group_remembered(self):
        dims, layers = self.dock('dims'), self.dock('layers')
        self.assertFalse(self.w.tabifiedDockWidgets(dims))                  # d'office au-dessus de Calques
        self.hand_drop_in_tabs(dims, layers)
        self.in_group('dims', BEFORE_HAND)
        self.assertEqual(self.key('onglet/dims'), 'layers')                 # comme remontré (`_joined`)
        self.restart()
        self.in_group('dims', BEFORE_HAND + ' (lancement suivant)')

    def test_lone_dimensions_brought_into_the_group(self):
        dims, layers = self.dock('dims'), self.dock('layers')
        self.assertFalse(self.w.tabifiedDockWidgets(dims))                  # seul, au-dessus du groupe
        self.assertTrue(self.c.tab_with(layers, dims))                     # « En onglet avec › Dimensions »
        pump()
        for name in ('dims', 'layers', 'symbols'):                          # Calques n'a pas quitté son groupe
            self.in_group(name, BEFORE_PAIR)
        self.restart()
        for name in ('dims', 'layers', 'symbols'):
            self.in_group(name, BEFORE_PAIR + ' (lancement suivant)')


if __name__ == '__main__':
    unittest.main()
