"""Round 1175 (demande : « placer barre de recherche bouton dans Favorites_bar, dans la liste de résultat indiquer
emplacement bouton actuel et permettre le menu click droit comme si on le faisait dans le ruban »). La disposition
TypeEdit 13 est celle, synthétique, de test_round1155."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1175.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QContextMenuEvent, QKeySequence  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402

from tests import test_round1155 as T  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : pas de champ de recherche dans la barre des favoris'
SIZE, PLACE, FAV = T.SIZE, T.PLACE, T.FAV


def forget():
    from vectordrive import portable
    s = portable.settings()
    for k in ('ruban/favoris', 'ruban/favoris_libelles', 'vue/mode'):
        s.remove(k)
    s.sync()


def deep(m):
    """Le contenu d'un menu (sous-menus compris) : texte, actif, coché."""
    out = []
    for a in m.actions():
        if a.isSeparator():
            continue
        out.append((a.text(), a.isEnabled(), a.isChecked(), deep(a.menu()) if a.menu() is not None else None))
    return out


def box_of(w):
    from shiboken6 import isValid
    box = getattr(w, 'fav_search', None)
    return box if box is not None and isValid(box) else None


def search(w, text):
    """Les résultats de `text` dans le champ : [(clé, libellé)]."""
    box = box_of(w)
    box.edit.clear()                                     # (le même texte : la liste refaite quand même)
    box.edit.setText(text)
    lst = box.results
    return [(lst.item(i).data(Qt.ItemDataRole.UserRole), lst.item(i).text()) for i in range(lst.count())]


def where(w, text, key):
    """Les emplacements (2e ligne du libellé) du résultat `key` de la recherche `text`."""
    label = next(label for k, label in search(w, text) if k == key)
    return label.split('\n', 1)[1].strip().split(' · ')


def ribbon_menu(w, btn):
    """Le menu du clic droit sur `btn`, par le filtre de la fenêtre (comme dans le ruban), bâti sans l'attendre."""
    menus = []
    real = type(w)._ribbon_button_menu

    def no_wait(win, *a, **k):
        k['exec_menu'] = False
        menus.append(real(win, *a, **k))
        return menus[-1]
    with mock.patch.object(type(w), '_ribbon_button_menu', autospec=True, side_effect=no_wait), \
            mock.patch.object(type(w), 'tool_form_dialog'), mock.patch.object(type(w), '_fav_bar_menu'):
        QApplication.sendEvent(btn, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(2, 2),
                                                      btn.mapToGlobal(QPoint(2, 2))))
    assert len(menus) == 1
    return menus[0]


def result_menu(w, text, key):
    """Le menu du clic droit sur le résultat `key` de la recherche `text` (touche Menu), sans l'attendre ; et les
    boutons passés à `_ribbon_button_menu`."""
    box = box_of(w)
    rows = [k for k, _l in search(w, text)]
    box.results.setCurrentRow(rows.index(key))
    seen = []
    real = type(w)._ribbon_button_menu

    def spy(win, button, *a, **k):
        seen.append(button)
        return real(win, button, *a, **k)
    with mock.patch.object(type(w), '_ribbon_button_menu', autospec=True, side_effect=spy):
        m = box.menu_current(exec_menu=False)
    return m, seen


class VD(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        forget()
        self.addCleanup(forget)
        self.w = w = MainWindow()
        self.addCleanup(self.close)
        w.settings.setValue('fenetre/plein_ecran', False)
        self.addCleanup(lambda: w.settings.remove('fenetre/plein_ecran'))
        w.show()
        app.processEvents()

    def close(self):
        T.close(self.w)

    def corner_widgets(self):
        lay = self.w.ribbon._corner_layout
        return [lay.itemAt(i).widget() for i in range(lay.count())]

    def test_field_in_the_ribbon_row_without_favorites(self):
        w = self.w
        box = box_of(w)
        self.assertIsNotNone(box, BEFORE)                                    # sans favoris : pas de barre, mais
        r = w.ribbon                                                         # le champ, dans la rangée des onglets
        self.assertIsNone(w.fav_bar)
        self.assertIs(box.parentWidget(), r.cornerWidget(Qt.Corner.TopRightCorner))
        ws = self.corner_widgets()
        self.assertEqual(ws.index(box) + 1, ws.index(r.right_bar))           # juste avant Options et Aide
        self.assertTrue(box.isVisible())
        self.assertEqual(w.menuWidget().layout().count(), 1)                 # pas de rangée en plus
        self.assertEqual(box.edit.focusPolicy(), Qt.FocusPolicy.ClickFocus)  # pas le clavier d'office ni par Tab
        self.assertIsNot(QApplication.focusWidget(), box.edit)              # le clavier ne lui va pas d'office
        w.add_favorite('zoom_fit')                                           # la barre revenue : il y va
        app.processEvents()
        self.assertIs(box_of(w).parentWidget(), w.fav_bar)
        self.assertFalse(any(isinstance(x, type(box)) for x in self.corner_widgets()))
        w.remove_favorite('zoom_fit')
        app.processEvents()
        self.assertIn(box_of(w), self.corner_widgets())                      # et en revient

    def test_field_in_the_favorites_bar(self):
        w = self.w
        w.add_favorite('zoom_fit')
        w.add_favorite('undo')
        app.processEvents()
        box = box_of(w)
        self.assertIsNotNone(box, BEFORE)
        self.assertIs(box.parentWidget(), w.fav_bar)                         # dans la barre même
        self.assertTrue(box.isVisible())
        self.assertEqual(w.fav_bar.actions(), [w.A['zoom_fit'], w.A['undo']])   # pas un favori : une enfant
        right = max(w.fav_bar.widgetForAction(w.A[k]).geometry().right() for k in ('zoom_fit', 'undo'))
        self.assertLess(right, box.geometry().left())                        # au bout, sans rien couvrir
        self.assertLessEqual(box.geometry().right(), w.fav_bar.width())

    def test_ctrl_k_gives_the_field_the_focus(self):
        from vectordrive.ui import command_search, fav_search
        w = self.w
        for fav in (False, True):                                            # rangée des onglets, puis barre
            if fav:
                w.add_favorite('zoom_fit')
                app.processEvents()
            with mock.patch.object(fav_search.SearchBox, 'take_focus') as focus, \
                    mock.patch.object(command_search.CommandSearch, 'exec', return_value=0) as dlg:
                w.A['command_search'].trigger()
            focus.assert_called_once()
            dlg.assert_not_called()                                          # pas la fenêtre de recherche

    def test_search_finds_a_command_and_tells_where_its_button_is(self):
        w = self.w
        w.add_favorite('zoom_fit')
        rows = search(w, 'symétrique dessin')
        self.assertTrue(rows, BEFORE)
        self.assertEqual(rows[0][0], 'sym_draw')
        self.assertIn('CAD › Création', where(w, 'symétrique dessin', 'sym_draw'))   # onglet › groupe du ruban
        label = where(w, 'tout voir', 'zoom_fit')
        self.assertIn('Vue › Zoom', label)
        self.assertIn('Barre des favoris', label)
        self.assertIn('Raccourci Ctrl+0', label)
        self.assertIn('CAD › Création', where(w, 'étoile', 'tool_star'))

    def test_enter_runs_the_command(self):
        w = self.w
        w.add_favorite('zoom_fit')
        box = box_of(w)
        self.assertIsNotNone(box, BEFORE)
        self.assertFalse(w.canvas.symmetric)
        box.edit.setText('dessin symetrique')
        self.assertTrue(box.results.isVisible())                             # la liste sous le champ
        QTest.keyClick(box.edit, Qt.Key.Key_Return)
        QTest.qWait(20)                                                      # (lancée au tour suivant)
        self.assertTrue(w.canvas.symmetric)                                  # lancée
        self.assertEqual(box.edit.text(), '')
        self.assertFalse(box.results.isVisible())
        w.A['sym_draw'].trigger()                                            # (rendu comme avant)

    def test_right_click_menu_is_the_ribbon_one(self):
        w = self.w
        w.add_favorite('zoom_fit')
        self.assertIsNotNone(box_of(w), BEFORE)
        b = next(x for x in w.ribbon.findChildren(QToolButton) if x.defaultAction() is w.A['tool_star'])
        ref = ribbon_menu(w, b)
        self.addCleanup(ref.deleteLater)
        m, seen = result_menu(w, 'étoile', 'tool_star')
        self.addCleanup(m.deleteLater)
        self.assertEqual(seen, [b])                                          # la même fonction, sur ce bouton
        self.assertEqual(deep(m), deep(ref))                                 # le même menu
        texts = T.texts(m)
        self.assertEqual(texts[0], 'Réglages de « Étoile »…')
        self.assertIn(SIZE, texts)
        self.assertIn(FAV, texts)
        fb = w.fav_bar.widgetForAction(w.A['zoom_fit'])                      # une commande des favoris (et du ruban)
        m2, seen2 = result_menu(w, 'tout voir', 'zoom_fit')
        self.addCleanup(m2.deleteLater)
        self.assertIsNot(seen2[0], fb)                                       # son bouton du ruban d'abord
        self.assertIn(T.UNFAV, T.texts(m2))

    def test_field_survives_arranging_and_removing_favorites(self):
        w = self.w
        for k in ('zoom_fit', 'undo', 'redo'):
            w.add_favorite(k)
        box = box_of(w)
        self.assertIsNotNone(box, BEFORE)
        w.arrange_favorites(True)
        app.processEvents()
        self.assertIs(box_of(w), box)
        self.assertNotIn(box, [b for _k, b in w._fav_arranger.items])       # pas rangé par l'agencement
        self.assertTrue(box.isVisible())
        w.move_favorite('redo', 'zoom_fit')
        app.processEvents()
        self.assertIs(box_of(w), box)                                        # la barre refaite : toujours là
        w.arrange_favorites(False)
        w.remove_favorite('undo')
        app.processEvents()
        self.assertIs(box_of(w), box)
        self.assertTrue(box.isVisible())
        self.assertNotIn(box, [w.fav_bar.widgetForAction(a) for a in w.fav_bar.actions()])
        w.remove_favorite('zoom_fit')
        w.remove_favorite('redo')
        app.processEvents()
        self.assertIsNone(w.fav_bar)                                         # plus de favoris : plus de barre
        self.assertIs(box_of(w).parentWidget(), w.ribbon.cornerWidget(Qt.Corner.TopRightCorner))   # (le champ :
        self.assertEqual(w.menuWidget().layout().count(), 1)                 # dans la rangée des onglets)
        w.add_favorite('undo')
        self.assertIs(box_of(w).parentWidget(), w.fav_bar)                   # revenu avec la barre

    def test_escape_closes_the_list(self):
        w = self.w
        box = box_of(w)
        self.assertIsNotNone(box, BEFORE)
        box.take_focus()
        box.edit.setText('tout voir')
        self.assertTrue(box.results.isVisible())
        QTest.keyClick(box.edit, Qt.Key.Key_Escape)
        self.assertFalse(box.results.isVisible())                            # la liste fermée, le texte gardé
        self.assertEqual(box.edit.text(), 'tout voir')
        QTest.keyClick(box.edit, Qt.Key.Key_Down)                            # rouverte par les flèches
        self.assertTrue(box.results.isVisible())
        QTest.keyClick(box.edit, Qt.Key.Key_Escape)
        QTest.keyClick(box.edit, Qt.Key.Key_Escape)                          # puis le champ vidé
        self.assertEqual(box.edit.text(), '')
        self.assertFalse(box.results.isVisible())

    def test_right_click_in_the_list(self):
        w = self.w
        box = box_of(w)
        self.assertIsNotNone(box, BEFORE)
        rows = [k for k, _l in search(w, 'étoile')]
        lst = box.results
        item = lst.item(rows.index('tool_star'))
        p = lst.visualItemRect(item).center()
        m = box.menu_at(p, exec_menu=False)                                  # le clic droit de la liste
        self.addCleanup(m.deleteLater)
        self.assertIs(lst.currentItem(), item)
        texts = T.texts(m)
        self.assertEqual(texts[0], 'Réglages de « Étoile »…')
        self.assertIn(SIZE, texts)                                           # celui du bouton du ruban
        self.assertIsNone(box.menu_at(QPoint(5, lst.viewport().height() + 50), exec_menu=False))   # hors d'un
        #                                                                      résultat : rien

    def test_simple_mode_marks_expert_buttons_and_prefers_shown_ones(self):
        w = self.w
        self.assertIsNotNone(box_of(w), BEFORE)
        w.set_ui_mode('simple', announce=False)
        self.addCleanup(lambda: w.set_ui_mode('expert', announce=False))
        label = where(w, 'spirale', 'tool_spiral')
        ribbon = [x for x in label if ' › ' in x]
        self.assertTrue(ribbon)
        self.assertTrue(all(x.endswith(' (mode expert)') for x in ribbon), label)   # caché en mode simple
        self.assertFalse(any('(mode expert)' in x for x in where(w, 'rectangle', 'tool_rect')))
        w.add_favorite('tool_spiral')                                        # aussi dans la barre des favoris :
        app.processEvents()                                                  # le bouton montré d'abord
        label = where(w, 'spirale', 'tool_spiral')
        self.assertEqual(label[0], 'Barre des favoris')
        m, seen = result_menu(w, 'spirale', 'tool_spiral')
        self.addCleanup(m.deleteLater)
        self.assertEqual(seen, [w.fav_bar.widgetForAction(w.A['tool_spiral'])])   # son menu : celui-là
        w.set_ui_mode('expert', announce=False)
        label = where(w, 'spirale', 'tool_spiral')
        self.assertFalse(any('(mode expert)' in x for x in label))
        self.assertIn(' › ', label[0])                                       # en mode expert : le ruban d'abord

    def test_invisible_command_is_not_sent_to_expert_mode(self):
        from vectordrive.ui import fav_search
        w = self.w
        self.assertIsNotNone(box_of(w), BEFORE)
        w.set_ui_mode('simple', announce=False)
        self.addCleanup(lambda: w.set_ui_mode('expert', announce=False))
        act = w.A['tool_rect']                                               # (une commande propre à une machine,
        act.setVisible(False)                                                # absente aujourd'hui)
        self.addCleanup(lambda: (act.setVisible(True), w.ribbon.refresh_visibility()))
        w.ribbon.refresh_visibility()
        buttons = [b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is act]
        self.assertTrue(buttons and all(b.isHidden() for b in buttons))      # caché, mais pas par le mode
        self.assertFalse(any('(mode expert)' in x for x, _b in fav_search.places(w, 'tool_rect')))
        self.assertNotIn('tool_rect', [k for k, _l in search(w, 'rectangle')])   # ni listée

    def test_disabled_command_is_listed_greyed(self):
        w = self.w
        box = box_of(w)
        self.assertIsNotNone(box, BEFORE)
        top = [k for k, _l in search(w, 'tout voir')][0]                     # le premier résultat, désactivé
        act = w.A[top]
        act.setEnabled(False)
        self.addCleanup(act.setEnabled, True)
        keys = [k for k, _l in search(w, 'tout voir')]
        self.assertEqual(keys[0], top)                                       # listé, toujours en tête
        self.assertGreater(len(keys), 1)
        lst = box.results
        item = lst.item(0)
        self.assertNotEqual(item.foreground().color(), lst.item(1).foreground().color())   # grisé
        self.assertNotEqual(box.current_key(), top)                          # pas choisi d'office : le premier
        self.assertTrue(w.A[box.current_key()].isEnabled())                  # activé
        lst.setCurrentItem(item)
        w.statusBar().clearMessage()
        QTest.keyClick(box.edit, Qt.Key.Key_Return)
        QTest.qWait(20)
        self.assertEqual(box.edit.text(), 'tout voir')                       # Entrée : ne le lance pas,
        name = act.text().replace('&', '').replace('\n', ' ').strip()
        self.assertEqual(w.statusBar().currentMessage(), '« {0} » n’est pas disponible ici'.format(name))   # le dit
        w.statusBar().clearMessage()
        box.run_item(item)                                                   # (le clic : de même)
        self.assertIn(name, w.statusBar().currentMessage())
        m = box.menu_current(exec_menu=False)                                # le clic droit : son menu
        self.addCleanup(m.deleteLater)
        self.assertIn(FAV, T.texts(m))

    def test_hint_shows_the_real_shortcut(self):
        w = self.w
        box = box_of(w)
        self.assertIsNotNone(box, BEFORE)
        cmd = w.A['command_search']
        sc = cmd.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        self.assertTrue(sc)
        self.assertEqual(box.edit.placeholderText(), 'Chercher un bouton… ({0})'.format(sc))
        old = cmd.shortcut()
        cmd.setShortcut(QKeySequence())
        self.addCleanup(cmd.setShortcut, old)
        box.update_hint()
        self.assertEqual(box.edit.placeholderText(), 'Chercher un bouton…')  # sans raccourci : rien

    def test_right_click_event_on_the_list(self):
        w = self.w
        box = box_of(w)
        self.assertIsNotNone(box, BEFORE)
        b = next(x for x in w.ribbon.findChildren(QToolButton) if x.defaultAction() is w.A['tool_star'])
        ref = ribbon_menu(w, b)
        self.addCleanup(ref.deleteLater)
        keys = [k for k, _l in search(w, 'étoile')]
        lst = box.results
        p = lst.visualItemRect(lst.item(keys.index('tool_star'))).center()
        menus = []
        real = type(w)._ribbon_button_menu

        def no_wait(win, *a, **k):
            k['exec_menu'] = False
            menus.append(real(win, *a, **k))
            return menus[-1]
        with mock.patch.object(type(w), '_ribbon_button_menu', autospec=True, side_effect=no_wait):
            QApplication.sendEvent(lst.viewport(), QContextMenuEvent(QContextMenuEvent.Reason.Mouse, p,
                                                                     lst.viewport().mapToGlobal(p)))
            QTest.qWait(20)                                                  # (ouvert au tour suivant)
        self.assertEqual(len(menus), 1)
        self.addCleanup(menus[0].deleteLater)
        self.assertEqual(deep(menus[0]), deep(ref))                          # le menu du bouton du ruban

    def test_list_follows_the_window(self):
        w = self.w
        w.add_favorite('zoom_fit')
        w.resize(1700, 800)
        app.processEvents()
        box = box_of(w)
        self.assertIsNotNone(box, BEFORE)
        box.edit.setText('tout voir')
        lst = box.results
        self.assertTrue(lst.isVisible())
        w.resize(1100, 800)
        app.processEvents()
        self.assertLess(w.width(), 1300)
        right = box.mapTo(w, QPoint(box.width() - 1, box.height())).x()
        self.assertEqual(lst.geometry().right(), min(right, w.width() - 5))  # sous le bout du champ, dans la
        #                                                                      fenêtre (4 pixels de bord)


class TypeEdit(T.Base):
    def test_places_in_the_typeedit_layout(self):
        w = self.w
        box = box_of(w)
        self.assertIsNotNone(box, BEFORE)
        self.assertIs(box.parentWidget(), w.te_quickbar)                     # la barre où vont les favoris
        te = w.te_quickbar                                                   # (pas une de ses actions)
        self.assertNotIn(box, [te.widgetForAction(a) for a in te.actions()])
        label = where(w, 'étoile', 'tool_star')
        self.assertIn('CAD › Dessin', label)                                 # le groupe de TypeEdit, pas
        self.assertNotIn('CAD › Création', label)                            # celui de VectorDrive
        self.assertIn('Barre d’accès rapide', label)
        self.assertIn('VectorDrive › CAD › Création', where(w, 'dessin symétrique', 'sym_draw'))  # menu de
        #                                                                      l'onglet « VectorDrive »
        self.assertNotIn('Pas de bouton dans cette disposition', where(w, 'dessin symétrique', 'sym_draw'))
        w.add_favorite('zoom_fit')                                           # un favori : dans la barre d'accès
        label = where(w, 'tout voir', 'zoom_fit')                            # rapide, dite comme telle
        self.assertIn('Barre d’accès rapide', label)
        self.assertNotIn('Barre des favoris', label)

    def test_right_click_menu_in_the_typeedit_layout(self):
        w = self.w
        self.assertIsNotNone(box_of(w), BEFORE)
        b = T.te_button(w, w.A['tool_star'])
        ref = ribbon_menu(w, b)
        self.addCleanup(ref.deleteLater)
        m, seen = result_menu(w, 'étoile', 'tool_star')
        self.addCleanup(m.deleteLater)
        self.assertEqual(seen, [b])
        self.assertEqual(deep(m), deep(ref))
        m2, seen2 = result_menu(w, 'dessin symétrique', 'sym_draw')           # pas de bouton à elle : ce qui a un
        self.addCleanup(m2.deleteLater)                                       # sens hors du ruban
        texts = T.texts(m2)
        self.assertNotIn(SIZE, texts)
        self.assertNotIn(PLACE, texts)
        self.assertIn(FAV, texts)
        self.assertIsNone(seen2[0].parentWidget())


if __name__ == '__main__':
    unittest.main()
