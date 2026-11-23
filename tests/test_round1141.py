"""Round 1141 : demande du 22/11 soir — « Sur tout icone bouton_outil click droit permet d'ajuster la taille et le
position bouton dans le ruban ». Au clic droit sur un bouton du ruban : sa taille (grand ou petit) et sa place (vers la
gauche, vers la droite, en tête, en fin, dans un autre groupe de l'onglet), retenues d'un lancement à l'autre ; taille
et place d'origine rétablies (un bouton, ou tout le ruban) ; un outil qui a ses réglages les garde en tête du menu."""
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1141.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QAction, QContextMenuEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QSpinBox, QToolButton  # noqa: E402

app = QApplication.instance() or QApplication([])


# --- le rangement seul (sans fenêtre) -------------------------------------------------------------------------------
class Plan(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.ribbon import RibbonPage
        self.page = RibbonPage()
        self.addCleanup(self.page.deleteLater)
        self.acts = {}

    def group(self, gid, spec):
        """spec : [(nom, grand)] ; None : un petit champ (pas une commande)."""
        g = self.page.group(gid)
        g.group_id = gid
        for item in spec:
            if item is None:
                g.add_widget(QSpinBox())
                continue
            name, big = item
            a = self.acts.setdefault(name, QAction(name, self.page))
            a.setObjectName(name)
            g.add(a, big=big)
        return g

    @staticmethod
    def ident(w):
        a = w.defaultAction()
        return a.objectName() if a is not None else None

    def names(self, ents):
        return [(self.ident(w) if isinstance(w, QToolButton) else '#', big) for w, big in ents]

    def test_order_and_size(self):
        from vectordrive.ui.ribbon import plan_layout
        g = self.group('A', [('a', True), ('b', True), None, ('c', False)])
        self.assertEqual(self.names(plan_layout([g], {}, self.ident)[g]),
                         [('a', True), ('b', True), ('#', None), ('c', False)], 'sans réglage : l’origine')
        conf = {'A': [['c', True], ['a', False], ['b', True]]}
        self.assertEqual(self.names(plan_layout([g], conf, self.ident)[g]),
                         [('c', True), ('a', False), ('#', None), ('b', True)], 'le champ garde sa case')

    def test_new_button_keeps_its_place(self):
        from vectordrive.ui.ribbon import plan_layout
        g = self.group('A', [('a', True), ('n', True), ('b', True), ('c', True)])
        conf = {'A': [['c', True], ['a', True], ['b', True]]}          # « n » : venu après (plugin, version)
        self.assertEqual([k for k, _b in self.names(plan_layout([g], conf, self.ident)[g])], ['c', 'a', 'n', 'b'])

    def test_move_to_another_group_and_back(self):
        from vectordrive.ui.ribbon import plan_layout
        g = self.group('A', [('a', True), ('b', True)])
        h = self.group('B', [('x', True)])
        conf = {'A': [['a', True]], 'B': [['b', False], ['x', True]]}
        p = plan_layout([g, h], conf, self.ident)
        self.assertEqual(self.names(p[g]), [('a', True)])
        self.assertEqual(self.names(p[h]), [('b', False), ('x', True)])
        conf = {'A': [['a', True], ['b', True]], 'B': [['b', False], ['x', True]]}   # encore listé chez lui
        p = plan_layout([g, h], conf, self.ident)
        self.assertEqual(self.names(p[g]), [('a', True), ('b', True)], 'il y reste')
        self.assertEqual(self.names(p[h]), [('x', True)], 'jamais en double')
        p = plan_layout([g, h], {'A': [['a', True]], 'Z': [['b', True]]}, self.ident)
        self.assertEqual(self.names(p[g]), [('a', True), ('b', True)], 'groupe disparu : il reste chez lui')

    def test_same_command_in_two_groups(self):
        from vectordrive.ui.ribbon import plan_layout
        g = self.group('A', [('a', True), ('b', True)])
        h = self.group('B', [('b', True), ('x', True)])
        p = plan_layout([g, h], {'B': [['x', True], ['b', False]]}, self.ident)
        self.assertEqual(self.names(p[g]), [('a', True), ('b', True)], 'son double ailleurs ne bouge pas')
        self.assertEqual(self.names(p[h]), [('x', True), ('b', False)])
        self.assertIsNot(p[h][1][0], p[g][1][0])
        hb = p[h][1][0]
        c = self.group('C', [('y', True)])                            # celui du 2e groupe déplacé : lui seul part
        p = plan_layout([g, h, c], {'B': [['x', True]], 'C': [['y', True], ['b', False]]}, self.ident)
        self.assertEqual(self.names(p[g]), [('a', True), ('b', True)])
        self.assertEqual(self.names(p[h]), [('x', True)])
        self.assertEqual(self.names(p[c]), [('y', True), ('b', False)])
        self.assertIs(p[c][1][0], hb)
        gb = p[g][1][0]
        d = self.group('D', [('z', True)])                            # les deux exemplaires déplacés, chacun ailleurs
        p = plan_layout([g, h, c, d], {'A': [['a', True]], 'B': [['x', True]], 'C': [['y', True], ['b', False]],
                                       'D': [['z', True], ['b', True]]}, self.ident)
        self.assertEqual(self.names(p[g]), [('a', True)])
        self.assertEqual(self.names(p[h]), [('x', True)])
        self.assertEqual(self.names(p[c]), [('y', True), ('b', False)])
        self.assertEqual(self.names(p[d]), [('z', True), ('b', True)])
        self.assertEqual({id(p[c][1][0]), id(p[d][1][0])}, {id(gb), id(hb)}, 'chacun une fois')

    def test_never_between_layouts(self):
        from vectordrive.ui.ribbon import plan_layout
        g = self.group('vd:a', [('a', True), ('b', True)])
        h = self.group('te:x', [('x', True)])                         # groupe de TypeEdit 13 sur la même page
        p = plan_layout([g, h], {'vd:a': [['a', True]], 'te:x': [['x', True], ['b', True]]}, self.ident)
        self.assertEqual(self.names(p[g]), [('a', True), ('b', True)], 'il reste dans la disposition VectorDrive')
        self.assertEqual(self.names(p[h]), [('x', True)])

    def test_drifted_group_list_is_ignored(self):
        from vectordrive.ui.ribbon import plan_layout
        g = self.group('A', [('a', True), ('b', True)])
        p = plan_layout([g], {'A': [['autre', True], ['encore', False]]}, self.ident)
        self.assertEqual(self.names(p[g]), [('a', True), ('b', True)], 'liste d’un autre groupe : ignorée')

    def test_moves_stay_in_the_tab(self):
        from vectordrive.ui.ribbon import RibbonPage, plan_layout
        g = self.group('A', [('a', True), ('b', True)])
        other = RibbonPage()
        self.addCleanup(other.deleteLater)
        h = other.group('B')
        h.group_id = 'B'
        h.add(self.acts.setdefault('x', QAction('x', other)), big=True)
        self.acts['x'].setObjectName('x')
        p = plan_layout([g, h], {'A': [['a', True]], 'B': [['x', True], ['b', True]]}, self.ident)
        self.assertEqual(self.names(p[h]), [('x', True)], 'jamais pris dans un autre onglet')

    def test_rearrange_moves_without_destroying(self):
        from shiboken6 import isValid
        from vectordrive.ui.ribbon import plan_layout, rearrange
        g = self.group('A', [('a', True), ('b', True)])
        h = self.group('B', [('x', False)])
        b = next(w for w, _b in g._entries if self.ident(w) == 'b')
        changed = rearrange(plan_layout([g, h], {'A': [['a', True]], 'B': [['x', False], ['b', False]]},
                                        self.ident))
        app.processEvents()
        self.assertEqual(set(changed), {g, h})
        self.assertTrue(isValid(b))
        self.assertTrue(h.body.isAncestorOf(b))
        self.assertEqual(b.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon, 'petit bouton')
        self.assertFalse(b.property('ribbon_big'))
        self.assertEqual(rearrange(plan_layout([g, h], {'A': [['a', True]], 'B': [['x', False], ['b', False]]},
                                               self.ident)), [], 'rien à refaire')
        rearrange(plan_layout([g, h], {}, self.ident))                 # tout rétabli
        app.processEvents()
        self.assertTrue(isValid(b))
        self.assertTrue(g.body.isAncestorOf(b))
        self.assertTrue(b.property('ribbon_big'))
        self.assertEqual(b.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

    def test_emptied_group_is_hidden(self):
        from vectordrive.ui.ribbon import plan_layout, rearrange
        g = self.group('A', [('a', True)])
        h = self.group('B', [('x', True)])
        rearrange(plan_layout([g, h], {'A': [], 'B': [['x', True], ['a', True]]}, self.ident))
        self.assertFalse(g.refresh_visibility(None))
        self.assertTrue(g.vacant)


# --- dans la fenêtre ------------------------------------------------------------------------------------------------
def forget():
    from vectordrive import portable
    s = portable.settings()
    for k in ('ruban/boutons', 'ruban/perso', 'ruban/onglets', 'ruban/favoris', 'vue/mode'):
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


def ribbon_button(w, key):
    return next(b for b in w.ribbon.findChildren(QToolButton)
                if b.defaultAction() is w.A[key] and w._group_of_button(b) is not None)


def menu_actions(m):
    out = {}
    for a in m.actions():
        if a.menu() is not None:
            out[a.text()] = a
            for b in a.menu().actions():
                if b.text():
                    out[a.text() + ' › ' + b.text()] = b
        elif a.text():
            out[a.text()] = a
    return out


def keys_of(w, g):
    return [it[0] for it in w._button_listing(g)]


class Window(unittest.TestCase):
    def setUp(self):
        forget()
        self.addCleanup(forget)
        self.w = window()
        self.addCleanup(close, self.w)

    def a_group(self, n=3):
        """Un groupe d'au moins `n` boutons montrés, et ses boutons."""
        for g in self.w._ribbon_button_groups():
            shown = [it for it in self.w._button_listing(g) if not it[2].isHidden()]
            if len(shown) >= n and g.page is self.w.ribbon.page(self.w.ribbon.currentIndex()):
                return g, shown
        for g in self.w._ribbon_button_groups():
            shown = [it for it in self.w._button_listing(g) if not it[2].isHidden()]
            if len(shown) >= n:
                return g, shown
        self.skipTest('pas de groupe assez grand')

    def test_menu_has_size_and_position(self):
        w = self.w
        g, shown = self.a_group()
        b = shown[1][2]
        m = w._ribbon_button_menu(b, QPoint(0, 0), exec_menu=False)
        self.addCleanup(m.deleteLater)
        acts = menu_actions(m)
        for t in ('Taille du bouton › Grand bouton', 'Taille du bouton › Petit bouton', 'Position du bouton › Vers la '
                  'gauche', 'Position du bouton › Vers la droite', 'Position du bouton › En tête du groupe',
                  'Position du bouton › En fin de groupe'):
            self.assertIn(t, acts)
        big = g.entry_big(b)
        self.assertEqual(acts['Taille du bouton › Grand bouton'].isChecked(), bool(big))
        self.assertNotIn('Taille et place d’origine', acts, 'rien de choisi encore')
        first = shown[0][2]
        m2 = w._ribbon_button_menu(first, QPoint(0, 0), exec_menu=False)
        self.addCleanup(m2.deleteLater)
        acts2 = menu_actions(m2)
        self.assertFalse(acts2['Position du bouton › Vers la gauche'].isEnabled(), 'déjà en tête')

    def test_every_ribbon_button_gets_the_menu(self):
        w = self.w
        ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(2, 2), QPoint(2, 2))
        n = 0
        for g in w._ribbon_button_groups():
            for it in w._button_listing(g)[:2]:
                with mock.patch.object(type(w), '_ribbon_button_menu') as bm:
                    self.assertTrue(w.eventFilter(it[2], ev))
                    bm.assert_called_once()
                from PySide6.QtWidgets import QMenu
                m = QMenu()
                self.assertTrue(w._button_place_menu(m, it[2]), w._button_id(it[2]))   # taille et place proposées
                m.deleteLater()
                n += 1
        self.assertGreater(n, 20)

    def test_reset_one_copy_leaves_the_other(self):
        w = self.w
        copies = [b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is w.A['tool_select']
                  and w._group_of_button(b) is not None]
        if len(copies) < 2:
            self.skipTest('Sélection dans un seul groupe')
        moved = None
        for b in copies:
            g = w._group_of_button(b)
            dst = next((x for x in w._ribbon_button_groups() if x.page is g.page and x is not g
                        and not x.vacant and 'tool_select' not in keys_of(w, x)), None)
            if dst is not None:
                moved = (b, g, dst)
                break
        if moved is None:
            self.skipTest('pas d’autre groupe')
        b, g, dst = moved
        other = next(x for x in copies if x is not b)
        self.assertTrue(w.ribbon_button_op(b, 'group', dst.group_id))
        self.assertIs(w._group_of_button(b), dst)
        self.assertTrue(w.button_layout_changed(b))
        self.assertFalse(w.button_layout_changed(other), 'l’autre exemplaire n’a pas bougé')
        self.assertFalse(w.ribbon_button_op(other, 'reset'))
        self.assertIs(w._group_of_button(b), dst, 'toujours déplacé')
        m = w._ribbon_button_menu(other, QPoint(0, 0), exec_menu=False)
        self.addCleanup(m.deleteLater)
        self.assertNotIn('Taille et place d’origine', menu_actions(m))
        self.assertTrue(w.ribbon_button_op(b, 'reset'))
        self.assertIs(w._group_of_button(b), g)
        self.assertIsNone(w.settings.value('ruban/boutons'))

    def test_hidden_button_stays_hidden(self):
        w = self.w
        g, shown = self.a_group(3)
        hid, b = shown[0], shown[-1][2]
        act = hid[2].defaultAction()
        act.setVisible(False)
        self.addCleanup(act.setVisible, True)
        app.processEvents()
        self.assertTrue(hid[2].isHidden())
        self.assertTrue(w.ribbon_button_op(b, 'first'))
        self.assertTrue(hid[2].isHidden(), 'caché par sa commande : il le reste')
        self.assertFalse(b.isHidden())
        self.assertTrue(w.ribbon_button_op(b, 'reset'))
        self.assertTrue(hid[2].isHidden())

    def test_custom_tab_braces_and_absent_command(self):
        w = self.w
        tabs = [{'titre': 'Atelier', 'position': 'fin', 'groupes': [
            {'titre': 'Un', 'commandes': [{'key': 'open', 'big': True}, {'key': 'plugin_absent', 'big': True},
                                          {'key': 'save', 'big': True}]},
            {'titre': 'Deux {x}', 'commandes': [{'key': 'undo', 'big': False}]},
            {'titre': 'Fantôme', 'commandes': [{'key': 'plugin_absent2', 'big': True}]}]}]
        w.settings.setValue('ruban/onglets', json.dumps(tabs))
        w._build_custom_tab()

        def btn(key):
            return next(b for b in w.ribbon.findChildren(QToolButton)
                        if b.property('ribbon_custom_at') and w._action_key(b.defaultAction()) == key)

        def conf():
            from vectordrive.ui.ribbon_editor import load_all
            return next(t for t in load_all(w.settings) if t['titre'] == 'Atelier')['groupes']
        m = w._ribbon_button_menu(btn('save'), QPoint(0, 0), exec_menu=False)
        self.addCleanup(m.deleteLater)
        acts = menu_actions(m)
        self.assertNotIn('Position du bouton › Dans le groupe « Fantôme »', acts, 'groupe pas affiché')
        self.assertFalse(acts['Position du bouton › Vers la droite'].isEnabled())
        self.assertTrue(w.ribbon_button_op(btn('save'), 'left'))      # par-dessus la commande absente
        self.assertEqual([c['key'] for c in conf()[0]['commandes']], ['save', 'open', 'plugin_absent'])
        self.assertTrue(w.ribbon_button_op(btn('open'), 'group', '1'))  # titre avec accolades
        self.assertEqual([c['key'] for c in conf()[1]['commandes']], ['undo', 'open'])
        self.assertIn('Deux {x}', w.statusBar().currentMessage())

    def test_shape_tool_settings_first(self):
        w = self.w
        rect = next((b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is w.A.get('tool_rect')),
                    None)
        if rect is None:
            self.skipTest('pas de bouton Rectangle')
        ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(2, 2), rect.mapToGlobal(QPoint(2, 2)))
        with mock.patch.object(type(w), '_ribbon_button_menu') as bm:
            self.assertTrue(w.eventFilter(rect, ev))
        settings = bm.call_args.kwargs['settings']
        m = w._ribbon_button_menu(rect, QPoint(0, 0), exec_menu=False, settings=settings)
        self.addCleanup(m.deleteLater)
        first = m.actions()[0]
        self.assertTrue(first.text().startswith('Réglages de'))
        self.assertIs(m.defaultAction(), first)
        self.assertIn('Taille du bouton', menu_actions(m))
        with mock.patch.object(type(w), 'tool_form_dialog') as fd:
            first.trigger()
            fd.assert_called_once_with('rect')
        self.assertIsNone(w._tool_settings(w.A['open']))
        with mock.patch.object(type(w), 'dim_options') as dd:
            w._tool_settings(w.A['tool_dim'])()
            dd.assert_called_once()

    def test_size_kept_after_restart(self):
        w = self.w
        g, shown = self.a_group()
        b = next((it[2] for it in shown if g.entry_big(it[2]) is True), None)
        if b is None:
            self.skipTest('pas de grand bouton')
        key = w._button_id(b)
        self.assertTrue(w.ribbon_button_op(b, 'small'))
        self.assertFalse(g.entry_big(b))
        self.assertEqual(b.toolButtonStyle() in (Qt.ToolButtonStyle.ToolButtonTextBesideIcon,
                                                 Qt.ToolButtonStyle.ToolButtonIconOnly), True)
        self.assertFalse(w.ribbon_button_op(b, 'small'), 'déjà petit')
        conf = json.loads(w.settings.value('ruban/boutons'))
        self.assertIn(g.group_id, conf)
        self.assertIn([key, False], conf[g.group_id])
        gid = g.group_id
        close(w)
        w2 = window()
        self.addCleanup(close, w2)
        g2 = next(x for x in w2._ribbon_button_groups() if x.group_id == gid)
        b2 = next(it[2] for it in w2._button_listing(g2) if it[0] == key)
        self.assertFalse(g2.entry_big(b2), 'retenu au lancement suivant')
        m = w2._ribbon_button_menu(b2, QPoint(0, 0), exec_menu=False)
        self.addCleanup(m.deleteLater)
        acts = menu_actions(m)
        self.assertTrue(acts['Taille du bouton › Petit bouton'].isChecked())
        acts['Taille et place d’origine'].trigger()
        self.assertTrue(g2.entry_big(b2))
        self.assertIsNone(w2.settings.value('ruban/boutons'))

    def test_move_left_right_first_last(self):
        w = self.w
        g, shown = self.a_group()
        b = shown[1][2]
        k = w._button_id(b)
        before = keys_of(w, g)
        self.assertTrue(w.ribbon_button_op(b, 'left'))
        after = keys_of(w, g)
        self.assertLess(after.index(k), after.index(w._button_id(shown[0][2])), 'avant son voisin de gauche')
        self.assertTrue(w.button_layout_changed(b), 'le bouton déplacé propose de revenir à sa place')
        self.assertEqual(sorted(after), sorted(before), 'rien perdu, rien en double')
        self.assertTrue(w.ribbon_button_op(b, 'last'))
        self.assertEqual(keys_of(w, g)[-1], k)
        self.assertFalse(w.ribbon_button_op(b, 'last'))
        self.assertTrue(w.ribbon_button_op(b, 'first'))
        self.assertEqual(keys_of(w, g)[0], k)
        self.assertTrue(w.ribbon_button_op(b, 'right'))
        self.assertEqual(keys_of(w, g)[1], k)
        if keys_of(w, g) == before:                                   # revenu à l'origine : plus rien de retenu
            self.assertIsNone(w.settings.value('ruban/boutons'))
            self.assertFalse(w.ribbon_button_op(b, 'reset'))
        self.assertTrue(w.ribbon_button_op(b, 'last'))
        self.assertTrue(w.button_layout_changed(b))
        self.assertFalse(w.button_layout_changed(shown[0][2]), 'ses voisins restés dans l’ordre : pas touchés')
        layout = [g.body.layout().itemAt(i).widget() for i in range(g.body.layout().count())]
        self.assertTrue(any(x is b or (x is not None and x.isAncestorOf(b)) for x in layout), 'dans le groupe affiché')
        self.assertTrue(w.ribbon_button_op(b, 'reset'))
        self.assertEqual(keys_of(w, g), before)
        self.assertIsNone(w.settings.value('ruban/boutons'))

    def test_move_to_another_group_of_the_tab(self):
        w = self.w
        g, shown = self.a_group(2)
        b = shown[0][2]
        k = w._button_id(b)
        m = w._ribbon_button_menu(b, QPoint(0, 0), exec_menu=False)
        self.addCleanup(m.deleteLater)
        targets = [t for t in menu_actions(m) if t.startswith('Position du bouton › Dans le groupe')]
        if not targets:
            self.skipTest('un seul groupe dans cet onglet')
        menu_actions(m)[targets[0]].trigger()
        app.processEvents()
        self.assertNotIn(k, keys_of(w, g))
        dst = w._group_of_button(b)                                   # (la commande peut être ailleurs aussi)
        self.assertIsNot(dst, g)
        self.assertIs(dst.page, g.page)
        self.assertEqual(keys_of(w, dst)[-1], k, 'au bout du groupe choisi')
        self.assertTrue(dst.body.isAncestorOf(b))
        self.assertIs(w._group_of_button(b), dst)
        self.assertTrue(w.reset_button_layout(ask=False))
        self.assertIn(k, keys_of(w, g))
        self.assertTrue(g.body.isAncestorOf(b))
        self.assertFalse(w.reset_button_layout(ask=False), 'déjà tout d’origine')

    def test_simple_mode_keeps_working(self):
        w = self.w
        g, shown = self.a_group()
        b = shown[-1][2]
        self.assertTrue(w.ribbon_button_op(b, 'first'))
        w.ribbon.set_mode_filter(lambda a: True)                    # un mode qui montre tout
        self.assertEqual(keys_of(w, g)[0], w._button_id(b))
        self.assertFalse(b.isHidden())
        w.ribbon.set_mode_filter(None)
        self.assertFalse(b.isHidden())

    def test_custom_tab_buttons(self):
        w = self.w
        tabs = [{'titre': 'Atelier', 'position': 'fin', 'groupes': [
            {'titre': 'Un', 'commandes': [{'key': 'open', 'big': True}, {'key': 'save', 'big': True}]},
            {'titre': 'Deux', 'commandes': [{'key': 'undo', 'big': False}]}]}]
        w.settings.setValue('ruban/onglets', json.dumps(tabs))
        w.settings.remove('ruban/perso')
        w._build_custom_tab()

        def btn(key):
            return next(b for b in w.ribbon.findChildren(QToolButton)
                        if b.property('ribbon_custom_at') and w._action_key(b.defaultAction()) == key)

        def conf():
            from vectordrive.ui.ribbon_editor import load_all
            return next(t for t in load_all(w.settings) if t['titre'] == 'Atelier')['groupes']
        m = w._ribbon_button_menu(btn('save'), QPoint(0, 0), exec_menu=False)
        self.addCleanup(m.deleteLater)
        acts = menu_actions(m)
        self.assertIn('Position du bouton › Dans le groupe « Deux »', acts)
        self.assertNotIn('Tout le ruban d’origine…', acts)
        acts['Position du bouton › Vers la gauche'].trigger()
        self.assertEqual([c['key'] for c in conf()[0]['commandes']], ['save', 'open'])
        self.assertTrue(w.ribbon_button_op(btn('save'), 'small'))
        self.assertFalse(conf()[0]['commandes'][0]['big'])
        self.assertTrue(w.ribbon_button_op(btn('undo'), 'group', '0'))
        self.assertEqual(len(conf()), 1, 'groupe vidé : retiré')
        self.assertEqual([c['key'] for c in conf()[0]['commandes']], ['save', 'open', 'undo'])
        self.assertIsNone(w.settings.value('ruban/boutons'), 'les onglets à soi gardent leurs propres réglages')

    def test_favorites_and_unknown_buttons_left_alone(self):
        w = self.w
        w.add_favorite('zoom_fit')
        fb = next(x for x in w.fav_bar.findChildren(QToolButton) if x.defaultAction() is w.A['zoom_fit'])
        m = w._ribbon_button_menu(fb, QPoint(0, 0), exec_menu=False)
        self.addCleanup(m.deleteLater)
        self.assertNotIn('Taille du bouton', menu_actions(m))
        self.assertFalse(w.ribbon_button_op(fb, 'small'))
        w.settings.setValue('ruban/boutons', '{pas du json')
        self.assertEqual(w.button_layout(), {})
        w.settings.setValue('ruban/boutons', json.dumps({'vd:rien': [['inconnue', True]], 'x': 3}))
        self.assertEqual(w.apply_button_layout(), 0, 'commande inconnue, groupe inconnu : rien ne bouge')


if __name__ == '__main__':
    unittest.main()
